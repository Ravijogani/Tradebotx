#!/usr/bin/env python3
"""
Shared HTTP bot-manager logic used by both bot_manager_http.py (Linux/basic)
and bot_manager_http_windows.py (Windows, per-user MT5 isolation).

Pulling this out of the two near-identical entry-point scripts exists to fix
a specific problem found in a security review: the two files had drifted
apart while sharing the same auth/logging code, so every bug in that shared
code had to be found and fixed twice. Now there's exactly one copy.

Hardening applied here (previously present in both copies):
  - Debug logs no longer include MT5 passwords, API keys, or the bot-manager
    shared secret. Only lengths/booleans are logged.
  - The auth-failure path no longer logs the received or expected secret.
  - Token comparison uses hmac.compare_digest (constant-time).
  - /health now requires auth (it used to leak user IDs/PIDs to anyone who
    could reach the port).
  - script_path from the caller is checked against an allow-list of known
    bot scripts *and* resolved to confirm it stays inside the bots
    directory, closing a path-traversal / arbitrary-file-execution hole.
  - running_bots is keyed by an actual (user_id, strategy_id) tuple instead
    of a naively concatenated string, and all reads/writes go through a
    lock (Flask's dev server runs threaded).
"""
from flask import Blueprint, request, jsonify
from functools import wraps
import subprocess
import hmac
import json
import sys
import os
import logging
import threading
import time
import traceback
from pathlib import Path
import psutil
from datetime import datetime

logger = logging.getLogger("bot_manager")


def configure_logging(log_file: str = "bot_manager.log") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )


# Fields that must never be written to the log, echoed in an error message,
# or otherwise leave process memory in cleartext.
_SENSITIVE_CONFIG_KEYS = {
    'mt5_password', 'supabase_service_key', 'gemini_api_key',
    'telegram_bot_token', 'supabase_url',
}
_SENSITIVE_ENV_MARKERS = ('SECRET', 'PASSWORD', 'KEY', 'TOKEN')


def redact_config(config: dict) -> dict:
    """Copy of a bot-start config safe to log: sensitive values replaced with a length marker."""
    if not isinstance(config, dict):
        return {}
    redacted = {}
    for k, v in config.items():
        if k in _SENSITIVE_CONFIG_KEYS and v is not None:
            redacted[k] = f"<redacted, len={len(str(v))}>"
        else:
            redacted[k] = v
    return redacted


def log_environment_summary() -> None:
    """Log which env vars are set without ever logging secret values."""
    logger.info("Environment variables (names only for sensitive ones):")
    for key in sorted(os.environ.keys()):
        if any(marker in key for marker in _SENSITIVE_ENV_MARKERS):
            logger.info(f"  {key}=<set, len={len(os.environ[key])}>")
        else:
            logger.info(f"  {key}={os.environ[key]}")


class BotRegistry:
    """Thread-safe tracking of running bot subprocesses, keyed by (user_id, strategy_id).

    Also persisted to a state file on every change so a manager restart can
    reconcile with subprocesses that are still actually running instead of
    losing track of them (they'd otherwise become invisible orphans that a
    later /bot/start call might try to duplicate).
    """

    def __init__(self, state_path: Path | None = None):
        self._lock = threading.Lock()
        self._bots: dict[tuple[str, str], dict] = {}
        self._state_path = state_path

    def set_state_path(self, state_path: Path) -> None:
        self._state_path = state_path

    @staticmethod
    def key_str(key: tuple[str, str]) -> str:
        return f"{key[0]}:{key[1]}"

    def get(self, user_id: str, strategy_id: str):
        with self._lock:
            return self._bots.get((user_id, strategy_id))

    def set(self, user_id: str, strategy_id: str, info: dict):
        with self._lock:
            self._bots[(user_id, strategy_id)] = info
            self._persist_locked()

    def remove(self, user_id: str, strategy_id: str):
        with self._lock:
            self._bots.pop((user_id, strategy_id), None)
            self._persist_locked()

    def for_user(self, user_id: str) -> dict:
        with self._lock:
            return {k: v for k, v in self._bots.items() if k[0] == user_id}

    def all(self) -> dict:
        with self._lock:
            return dict(self._bots)

    def prune_dead(self) -> None:
        """Drop entries whose process has exited. Call before reporting status."""
        with self._lock:
            dead = []
            for key, info in self._bots.items():
                dead.append(key) if not _pid_is_alive(info.get('pid'), info.get('process')) else None
            for key in dead:
                logger.info(f"Cleaned up dead process for {self.key_str(key)}")
                del self._bots[key]
            if dead:
                self._persist_locked()

    def _persist_locked(self) -> None:
        if not self._state_path:
            return
        try:
            serializable = {
                self.key_str(key): {k: v for k, v in info.items() if k != 'process'}
                for key, info in self._bots.items()
            }
            self._state_path.write_text(json.dumps(serializable), encoding='utf-8')
        except OSError as e:
            logger.warning(f"Could not persist bot registry state: {e}")

    def reconcile_from_disk(self, bot_dir: Path) -> None:
        """Called once at startup. Re-adopts entries from the last run whose
        process is still alive AND whose command line still matches the
        expected (user_id, strategy_id) — a bare PID match isn't enough since
        PIDs get reused by unrelated processes over time."""
        if not self._state_path or not self._state_path.exists():
            return
        try:
            saved = json.loads(self._state_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read bot registry state file: {e}")
            return

        adopted = 0
        with self._lock:
            for key_str, info in saved.items():
                user_id, _, strategy_id = key_str.partition(':')
                pid = info.get('pid')
                if not _pid_matches_bot(pid, user_id, strategy_id):
                    continue
                info['process'] = None  # no live Popen handle for an adopted process
                self._bots[(user_id, strategy_id)] = info
                adopted += 1
            self._persist_locked()
        if adopted:
            logger.info(f"Reconciled {adopted} bot(s) still running from before restart")

    def __len__(self):
        with self._lock:
            return len(self._bots)


def _pid_is_alive(pid, process) -> bool:
    if pid is None:
        return False
    try:
        if process is not None:
            return psutil.pid_exists(pid) and process.poll() is None
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, Exception):
        return False


def _pid_matches_bot(pid, user_id: str, strategy_id: str) -> bool:
    if not pid:
        return False
    try:
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return False
        cmdline = ' '.join(proc.cmdline())
        return user_id in cmdline and strategy_id in cmdline
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


running_bots = BotRegistry()


class _FailedAuthTracker:
    """Locks out a source IP after too many bad tokens.

    The bot manager's port is typically reachable from the open internet
    (Supabase edge functions don't have a fixed egress IP to allowlist), so
    the shared secret is the only real gate. This adds a second layer:
    repeated bad guesses from one IP get locked out for a cooldown window
    instead of being able to retry indefinitely.
    """
    MAX_FAILURES = 10
    WINDOW_SECONDS = 300
    LOCKOUT_SECONDS = 900

    def __init__(self):
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def is_locked(self, ip: str) -> bool:
        with self._lock:
            until = self._locked_until.get(ip)
            if until and until > time.time():
                return True
            if until:
                del self._locked_until[ip]
            return False

    def record_failure(self, ip: str) -> None:
        now = time.time()
        with self._lock:
            attempts = [t for t in self._failures.get(ip, []) if now - t < self.WINDOW_SECONDS]
            attempts.append(now)
            self._failures[ip] = attempts
            if len(attempts) >= self.MAX_FAILURES:
                self._locked_until[ip] = now + self.LOCKOUT_SECONDS
                logger.error(f"IP {ip} locked out for {self.LOCKOUT_SECONDS}s after {len(attempts)} failed auth attempts")

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)


_auth_tracker = _FailedAuthTracker()


def require_auth(get_secret):
    """Auth decorator factory. get_secret() is called per-request so the
    secret can be re-read from the environment without a server restart."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr or 'unknown'
            if _auth_tracker.is_locked(ip):
                return jsonify({'error': 'Too many failed attempts. Try again later.'}), 429

            secret = get_secret()
            auth_header = request.headers.get('Authorization', '')
            token = auth_header[7:] if auth_header.startswith('Bearer ') else None

            if not token or not secret or not hmac.compare_digest(token, secret):
                _auth_tracker.record_failure(ip)
                logger.warning(f"Rejected unauthorized request to {request.path} from {ip}")
                return jsonify({'error': 'Unauthorized'}), 401

            _auth_tracker.record_success(ip)
            return f(*args, **kwargs)
        return decorated
    return decorator


# Bot scripts the manager is allowed to launch. A caller-supplied script_path
# is matched against this by filename only — never trusted as a path.
ALLOWED_BOT_SCRIPTS = {
    'hybrid_trading_bot_multiuser.py',
    'hybrid_trading_bot.py',
    'intraday.py',
    'structural_swing_pro.py',
}


class InvalidScriptPath(ValueError):
    pass


def resolve_bot_script(bot_dir: Path, requested_name: str) -> Path:
    """Resolve a caller-supplied script name to a real file inside bot_dir.

    Rejects anything that isn't a bare filename on the allow-list, and — as
    defense in depth — also rejects the result if it doesn't resolve to
    somewhere inside bot_dir (blocks absolute paths and ../ traversal even
    if the allow-list above were ever loosened).
    """
    name = (requested_name or '').strip()
    # A bare filename never contains a path separator.
    if not name or '/' in name or '\\' in name or name != Path(name).name:
        raise InvalidScriptPath(f"Rejected script path (not a bare filename): {requested_name!r}")

    if name not in ALLOWED_BOT_SCRIPTS:
        raise InvalidScriptPath(f"Script not on the allow-list: {name!r}")

    resolved_dir = bot_dir.resolve()
    candidate = (resolved_dir / name).resolve()
    if resolved_dir not in candidate.parents and candidate != resolved_dir:
        raise InvalidScriptPath(f"Resolved script path escapes bot directory: {candidate}")

    return candidate


def stop_single_bot(key: tuple[str, str], bot_info: dict) -> None:
    pid = bot_info['pid']
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        parent.wait(timeout=10)
    except psutil.NoSuchProcess:
        logger.info(f"Process {pid} already terminated")
    except psutil.TimeoutExpired:
        logger.warning(f"Process {pid} did not terminate gracefully, forcing kill")
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except psutil.NoSuchProcess:
            pass
    finally:
        running_bots.remove(*key)


def build_bot_blueprint(get_secret, bot_dir: Path, build_launch_args=None):
    """Build the Flask blueprint shared by both entry-point scripts.

    build_launch_args(config, bot_dir) -> (extra_argv: list[str], error_response: dict | None)
    lets the Windows variant inject a resolved --mt5-path (and refuse to
    start if no MT5 instance is provisioned) without duplicating every route.
    """
    running_bots.set_state_path(bot_dir / "running_bots_state.json")
    running_bots.reconcile_from_disk(bot_dir)

    bp = Blueprint('bot_manager', __name__)
    auth = require_auth(get_secret)

    @bp.route('/health', methods=['GET'])
    @auth
    def health_check():
        bots = running_bots.all()
        bots_by_user: dict[str, list] = {}
        for key, info in bots.items():
            bots_by_user.setdefault(key[0], []).append({
                'strategy_id': key[1],
                'strategy_name': info.get('strategy_name'),
                'pid': info.get('pid'),
            })

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'active_bots': len(bots),
            'active_users': len(bots_by_user),
            'python_version': sys.version,
            'secret_configured': bool(get_secret()),
        })

    @bp.route('/bot/start', methods=['POST'])
    @auth
    def start_bot():
        try:
            config = request.get_json(force=True, silent=True) or {}
            user_id = config.get('user_id')
            strategy_id = config.get('strategy_id')
            strategy_name = config.get('strategy_name', 'Unknown')

            if not user_id:
                return jsonify({'error': 'user_id required'}), 400
            if not strategy_id:
                return jsonify({'error': 'strategy_id required'}), 400

            logger.info(f"Bot start request: user={user_id} strategy={strategy_id} name={strategy_name!r}")
            logger.debug(f"Config (redacted): {json.dumps(redact_config(config))}")

            existing = running_bots.get(user_id, strategy_id)
            if existing:
                pid = existing.get('pid')
                still_running = False
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        still_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                    except psutil.NoSuchProcess:
                        still_running = False
                if still_running:
                    return jsonify({'success': False, 'message': f'Bot already running for strategy {strategy_name}'}), 400
                running_bots.remove(user_id, strategy_id)

            try:
                bot_script = resolve_bot_script(bot_dir, config.get('script_path', 'hybrid_trading_bot_multiuser.py'))
            except InvalidScriptPath as e:
                logger.error(f"Rejected bot start: {e}")
                return jsonify({'error': 'Invalid script_path'}), 400

            if not bot_script.exists():
                logger.error(f"Bot script not found: {bot_script}")
                return jsonify({'error': f'Bot script not found: {bot_script.name}'}), 500

            extra_args: list[str] = []
            if build_launch_args:
                extra_args, error_response = build_launch_args(config, bot_dir)
                if error_response:
                    return jsonify(error_response), 500

            command = [
                sys.executable,
                str(bot_script),
                '--user-id', str(user_id),
                '--strategy-id', str(strategy_id),
                '--mt5-login', str(config.get('mt5_account')),
                '--mt5-server', str(config.get('mt5_server')),
                *extra_args,
                '--supabase-url', str(config.get('supabase_url')),
            ]
            if config.get('telegram_chat_id'):
                command.extend(['--telegram-chat-id', str(config.get('telegram_chat_id'))])

            # Secrets go through the child process's environment, not argv —
            # command-line arguments are visible to any local process via
            # `ps`/Task Manager's "Command line" column or WMI, in addition to
            # whatever ends up in this process's own debug logs.
            child_env = dict(os.environ)
            child_env['MT5_PASSWORD'] = str(config.get('mt5_password', ''))
            child_env['SUPABASE_SERVICE_KEY'] = str(config.get('supabase_service_key', ''))
            if config.get('gemini_api_key'):
                child_env['GEMINI_API_KEY'] = str(config.get('gemini_api_key'))
            if config.get('telegram_bot_token'):
                child_env['TELEGRAM_BOT_TOKEN'] = str(config.get('telegram_bot_token'))

            # Per (user, strategy) log dir — keeping strategy_id in the path
            # (not just user_id) avoids two concurrent strategies for the
            # same user interleaving into the same startup log files.
            user_log_dir = bot_dir / f"Hybrid_AI_Bot_Logs_{user_id}_{strategy_id}"
            user_log_dir.mkdir(exist_ok=True)

            popen_kwargs = dict(cwd=str(bot_dir), env=child_env)
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs['start_new_session'] = True

            try:
                with open(user_log_dir / "bot_startup_stdout.log", 'wb') as out, \
                     open(user_log_dir / "bot_startup_stderr.log", 'wb') as err:
                    process = subprocess.Popen(command, stdout=out, stderr=err, **popen_kwargs)
            except Exception as proc_error:
                logger.error(f"Failed to create subprocess: {proc_error}\n{traceback.format_exc()}")
                return jsonify({'error': 'Failed to start bot process'}), 500

            running_bots.set(user_id, strategy_id, {
                'process': process,
                'pid': process.pid,
                'started_at': datetime.now().isoformat(),
                'user_id': user_id,
                'strategy_id': strategy_id,
                'strategy_name': strategy_name,
            })

            logger.info(f"Bot started: user={user_id} strategy={strategy_id} pid={process.pid}")
            return jsonify({
                'success': True,
                'message': f'Bot started for user {user_id} - Strategy: {strategy_name}',
                'pid': process.pid,
                'strategy_id': strategy_id,
                'user_bot_count': len(running_bots.for_user(user_id)),
            })

        except Exception as e:
            logger.error(f"FATAL ERROR starting bot: {e}\n{traceback.format_exc()}")
            return jsonify({'error': 'Internal error starting bot'}), 500

    @bp.route('/bot/stop', methods=['POST'])
    @auth
    def stop_bot():
        try:
            config = request.get_json(force=True, silent=True) or {}
            user_id = config.get('user_id')
            strategy_id = config.get('strategy_id')
            stop_all = config.get('stop_all', False)

            if not user_id:
                return jsonify({'error': 'user_id required'}), 400

            if stop_all:
                user_bots = running_bots.for_user(user_id)
                if not user_bots:
                    return jsonify({'success': False, 'message': 'No bots running for this user'}), 400

                stopped = []
                for key, info in list(user_bots.items()):
                    try:
                        stop_single_bot(key, info)
                        stopped.append({'strategy_id': key[1], 'strategy_name': info.get('strategy_name', 'Unknown'), 'pid': info['pid']})
                    except Exception as e:
                        logger.error(f"Error stopping bot {BotRegistry.key_str(key)}: {e}")

                logger.info(f"Stopped {len(stopped)} bot(s) for user {user_id}")
                return jsonify({'success': True, 'message': f'Stopped {len(stopped)} bot(s)', 'stopped_bots': stopped})

            if not strategy_id:
                return jsonify({'error': 'strategy_id required (or use stop_all=true)'}), 400

            bot_info = running_bots.get(user_id, strategy_id)
            if not bot_info:
                return jsonify({'success': False, 'message': f'No bot running for strategy {strategy_id}'}), 400

            stop_single_bot((user_id, strategy_id), bot_info)
            logger.info(f"Stopped bot for user={user_id} strategy={strategy_id}")
            return jsonify({
                'success': True,
                'message': f'Bot stopped for strategy {bot_info.get("strategy_name", strategy_id)}',
                'strategy_id': strategy_id,
                'user_remaining_bots': len(running_bots.for_user(user_id)),
            })

        except Exception as e:
            logger.error(f"Error stopping bot: {e}\n{traceback.format_exc()}")
            return jsonify({'error': 'Internal error stopping bot'}), 500

    @bp.route('/bot/status', methods=['GET'])
    @auth
    def bot_status():
        running_bots.prune_dead()
        filter_user_id = request.args.get('user_id')
        bots = running_bots.all()

        status = {}
        bots_by_user: dict[str, list] = {}
        for key, info in bots.items():
            user_id = key[0]
            if filter_user_id and user_id != filter_user_id:
                continue
            entry = {
                'pid': info.get('pid'),
                'running': True,
                'strategy_id': key[1],
                'strategy_name': info.get('strategy_name', 'Unknown'),
                'started_at': info.get('started_at'),
                'user_id': user_id,
            }
            status[BotRegistry.key_str(key)] = entry
            bots_by_user.setdefault(user_id, []).append(entry)

        return jsonify({
            'active_bots': len(status),
            'active_users': len(bots_by_user),
            'bots': status,
            'bots_by_user': bots_by_user,
        })

    @bp.route('/bot/user/<user_id>', methods=['GET'])
    @auth
    def get_user_bot_status(user_id):
        running_bots.prune_dead()
        user_bots = running_bots.for_user(user_id)

        bots_status = [{
            'bot_key': BotRegistry.key_str(key),
            'pid': info.get('pid'),
            'running': True,
            'strategy_id': key[1],
            'strategy_name': info.get('strategy_name', 'Unknown'),
            'started_at': info.get('started_at'),
        } for key, info in user_bots.items()]

        return jsonify({'user_id': user_id, 'bot_count': len(bots_status), 'bots': bots_status})

    return bp
