#!/usr/bin/env python3
"""
HTTP-based Bot Manager for Windows Server - MULTI-USER MT5 ISOLATION
Runs on AWS Lightsail Windows and accepts commands via HTTP.
Each user gets their own portable MT5 terminal instance so accounts never
share a running MT5 process.

Shared auth/logging/process-tracking logic lives in bot_manager_core.py —
see that file for what changed and why. This entry point adds the
Windows-specific MT5-instance resolution on top.
"""
from flask import Flask, request, jsonify
from pathlib import Path
import sys
import os
import logging
import traceback
from datetime import datetime

import bot_manager_core as core

core.configure_logging('bot_manager.log')
logger = logging.getLogger("bot_manager")

logger.info("=" * 80)
logger.info(f"BOT MANAGER STARTING - MULTI-USER MT5 ISOLATION - {datetime.now()}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"Working Directory: {os.getcwd()}")
logger.info("=" * 80)
core.log_environment_summary()

BOT_MANAGER_SECRET = os.getenv('BOT_MANAGER_SECRET', '')
if not BOT_MANAGER_SECRET:
    logger.error("FATAL: BOT_MANAGER_SECRET is not set. Refusing to start with no auth secret.")
    sys.exit(1)

BOT_DIR = Path(__file__).parent
MT5_INSTANCES_DIR = Path(os.getenv('MT5_INSTANCES_DIR', r'C:\trading-bot\MT5_Instances'))
logger.info(f"MT5 Instances Directory: {MT5_INSTANCES_DIR} (exists={MT5_INSTANCES_DIR.exists()})")


def _read_marker(folder: Path):
    marker = folder / "user_id.txt"
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip()
    return None


def get_mt5_terminal_path(user_id: str):
    """
    Resolve the path to a user's isolated MT5 terminal64.exe.

    Instance folders are looked up by the 8-char user_id prefix for
    readability, but ownership is verified via a user_id.txt marker written
    at provisioning time (see auto_provision_mt5.py). Two different users
    can share an 8-char prefix — if the folder we find is marked for a
    *different* full user_id, this refuses to use it rather than silently
    running one user's bot against another user's MT5 terminal. Folders with
    no marker (pre-existing installs) are used with a loud warning and get
    self-healed with a marker once matched.
    """
    candidates = [
        MT5_INSTANCES_DIR / (user_id[:8] if len(user_id) > 8 else user_id),
        MT5_INSTANCES_DIR / user_id,
        MT5_INSTANCES_DIR / f"user_{user_id[:8] if len(user_id) > 8 else user_id}",
    ]

    for folder in candidates:
        terminal_path = folder / "terminal64.exe"
        if not terminal_path.exists():
            continue

        marked_user_id = _read_marker(folder)
        if marked_user_id is None:
            logger.warning(f"MT5 instance at {folder} has no ownership marker — trusting folder-name match for user {user_id}, self-healing marker")
            try:
                (folder / "user_id.txt").write_text(user_id, encoding="utf-8")
            except OSError:
                pass
        elif marked_user_id != user_id:
            logger.error(f"MT5 instance at {folder} is marked for a different user ({marked_user_id!r}) — refusing to use it for {user_id!r}")
            continue

        logger.info(f"Resolved MT5 instance for user {user_id}: {terminal_path}")
        return str(terminal_path)

    logger.error(f"No MT5 instance found for user {user_id}. Searched: {[str(c) for c in candidates]}")
    return None


def build_launch_args(config: dict, bot_dir: Path):
    user_id = config.get('user_id')
    mt5_path = get_mt5_terminal_path(user_id)
    if not mt5_path:
        return [], {
            'error': 'No MT5 instance provisioned for this user. '
                     'Admin needs to run auto_provision_mt5.py for this account.'
        }
    return ['--mt5-path', mt5_path], None


app = Flask(__name__)
app.register_blueprint(core.build_bot_blueprint(
    get_secret=lambda: BOT_MANAGER_SECRET,
    bot_dir=BOT_DIR,
    build_launch_args=build_launch_args,
))


@app.route('/mt5/instances', methods=['GET'])
@core.require_auth(lambda: BOT_MANAGER_SECRET)
def list_mt5_instances():
    """List all provisioned MT5 instances and their ownership marker."""
    instances = []
    if MT5_INSTANCES_DIR.exists():
        for user_dir in MT5_INSTANCES_DIR.iterdir():
            if not user_dir.is_dir():
                continue
            terminal_path = user_dir / "terminal64.exe"
            instances.append({
                'folder_name': user_dir.name,
                'terminal_exists': terminal_path.exists(),
                'owner_user_id': _read_marker(user_dir),
            })

    return jsonify({
        'instances_dir_exists': MT5_INSTANCES_DIR.exists(),
        'total_instances': len(instances),
        'instances': instances,
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info("=" * 80)
    logger.info(f"BOT MANAGER HTTP SERVER (Windows) — listening on 0.0.0.0:{port}")
    logger.info(f"MT5 Instances Dir: {MT5_INSTANCES_DIR}")
    logger.info("=" * 80)

    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception:
        logger.error(f"FATAL: Server failed to start:\n{traceback.format_exc()}")
        sys.exit(1)
