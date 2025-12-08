#!/usr/bin/env python3
"""
HTTP-based Bot Manager for Windows Server - MULTI-BOT SUPPORT
Runs on AWS Lightsail Windows and accepts commands via HTTP
Supports multiple simultaneous bots per user (Pro: 5, Enterprise: unlimited)
"""
from flask import Flask, request, jsonify
from functools import wraps
import subprocess
import json
import sys
import os
import signal
import logging
from pathlib import Path
import psutil
import traceback
from datetime import datetime

app = Flask(__name__)

# Enhanced logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('bot_manager.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("="*80)
logger.info(f"BOT MANAGER STARTING - MULTI-BOT SUPPORT - {datetime.now()}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"Working Directory: {os.getcwd()}")
logger.info(f"Script Location: {__file__}")
logger.info("="*80)

# Store running bot processes - KEY: "user_id_strategy_id" for multi-bot support
running_bots = {}

# Security: Shared secret for authentication
BOT_MANAGER_SECRET = os.getenv('BOT_MANAGER_SECRET', 'your-secure-secret-here')

# Log secret configuration (safely)
if BOT_MANAGER_SECRET == 'your-secure-secret-here':
    logger.warning("⚠️ WARNING: Using default BOT_MANAGER_SECRET! Set environment variable!")
else:
    logger.info(f"✅ BOT_MANAGER_SECRET configured: Length={len(BOT_MANAGER_SECRET)}, First 4 chars={BOT_MANAGER_SECRET[:4]}...")
    
# Log all environment variables (excluding sensitive values)
logger.info("Environment Variables:")
for key in sorted(os.environ.keys()):
    if 'SECRET' in key or 'PASSWORD' in key or 'KEY' in key:
        logger.info(f"  {key}=***HIDDEN*** (length: {len(os.environ[key])})")
    else:
        logger.info(f"  {key}={os.environ[key]}")

def get_bot_key(user_id, strategy_id):
    """Generate composite key for multi-bot tracking"""
    return f"{user_id}_{strategy_id}"

def get_user_bots(user_id):
    """Get all running bots for a specific user"""
    user_bots = {}
    for key, bot_info in running_bots.items():
        if key.startswith(f"{user_id}_"):
            user_bots[key] = bot_info
    return user_bots

def require_auth(f):
    """Authentication decorator with enhanced debugging"""
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.debug(f"🔐 AUTH CHECK for {request.path}")
        logger.debug(f"Request Headers: {dict(request.headers)}")
        logger.debug(f"Request Method: {request.method}")
        logger.debug(f"Request Remote Addr: {request.remote_addr}")
        
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            logger.warning('❌ No Authorization header provided')
            return jsonify({'error': 'Unauthorized - No auth header'}), 401
            
        if not auth_header.startswith('Bearer '):
            logger.warning(f'❌ Invalid Authorization format: {auth_header[:20]}...')
            return jsonify({'error': 'Unauthorized - Invalid format'}), 401
        
        token = auth_header.split(' ')[1]
        logger.info(f'📨 Received token: Length={len(token)}, First 4={token[:4]}..., Last 4={token[-4:]}...')
        logger.info(f'🔑 Expected secret: Length={len(BOT_MANAGER_SECRET)}, First 4={BOT_MANAGER_SECRET[:4]}..., Last 4={BOT_MANAGER_SECRET[-4:]}...')
        
        # Character-by-character comparison for debugging
        if token != BOT_MANAGER_SECRET:
            logger.error('❌ TOKEN MISMATCH!')
            logger.error(f'Received: "{token}"')
            logger.error(f'Expected: "{BOT_MANAGER_SECRET}"')
            
            # Find first difference
            for i, (c1, c2) in enumerate(zip(token, BOT_MANAGER_SECRET)):
                if c1 != c2:
                    logger.error(f'First difference at position {i}: received "{c1}" vs expected "{c2}"')
                    break
            
            return jsonify({'error': 'Invalid token'}), 401
        
        logger.info('✅ Token validated successfully')
        return f(*args, **kwargs)
    return decorated

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint with detailed system info"""
    logger.info(f"💚 Health check from {request.remote_addr}")
    
    # Group bots by user for summary
    bots_by_user = {}
    for key, bot_info in running_bots.items():
        user_id = bot_info['config'].get('user_id', 'unknown')
        if user_id not in bots_by_user:
            bots_by_user[user_id] = []
        bots_by_user[user_id].append({
            'strategy_id': bot_info.get('strategy_id'),
            'strategy_name': bot_info.get('strategy_name'),
            'pid': bot_info.get('pid')
        })
    
    system_info = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_bots': len(running_bots),
        'active_users': len(bots_by_user),
        'platform': 'windows',
        'python_version': sys.version,
        'working_directory': os.getcwd(),
        'secret_configured': BOT_MANAGER_SECRET != 'your-secure-secret-here',
        'secret_length': len(BOT_MANAGER_SECRET),
        'bot_keys': list(running_bots.keys()),
        'bots_by_user': bots_by_user,
        'multi_bot_support': True
    }
    
    logger.debug(f"System info: {json.dumps(system_info, indent=2)}")
    return jsonify(system_info)

@app.route('/bot/start', methods=['POST'])
@require_auth
def start_bot():
    """Start a trading bot for a user - Supports multiple bots per user"""
    try:
        logger.info("="*80)
        logger.info("🚀 BOT START REQUEST RECEIVED (MULTI-BOT)")
        logger.info(f"Request from: {request.remote_addr}")
        logger.info(f"Content-Type: {request.content_type}")
        
        config = request.json
        logger.debug(f"Full config received: {json.dumps(config, indent=2)}")
        
        user_id = config.get('user_id')
        strategy_id = config.get('strategy_id')
        strategy_name = config.get('strategy_name', 'Unknown')
        
        logger.info(f"User ID: {user_id}")
        logger.info(f"Strategy ID: {strategy_id}")
        logger.info(f"Strategy Name: {strategy_name}")
        
        if not user_id:
            logger.error("❌ Missing user_id in request")
            return jsonify({'error': 'user_id required'}), 400
        
        if not strategy_id:
            logger.error("❌ Missing strategy_id in request")
            return jsonify({'error': 'strategy_id required'}), 400
        
        # Generate composite key for multi-bot support
        bot_key = get_bot_key(user_id, strategy_id)
        logger.info(f"Bot Key: {bot_key}")
        
        # Check if THIS specific strategy is already running for this user
        if bot_key in running_bots:
            logger.warning(f"⚠️ Bot already running for key {bot_key}")
            return jsonify({
                'success': False,
                'message': f'Bot already running for strategy {strategy_name}'
            }), 400
        
        # Log how many bots this user is already running
        user_bots = get_user_bots(user_id)
        logger.info(f"User {user_id} currently has {len(user_bots)} bot(s) running")
        
        # Get bot directory and determine script from config
        bot_dir = Path(__file__).parent
        
        # Use script_path from config, fallback to default
        script_name = config.get('script_path', 'hybrid_trading_bot_multiuser.py')
        bot_script = bot_dir / script_name
        
        logger.info(f"Bot directory: {bot_dir}")
        logger.info(f"Script from config: {script_name}")
        logger.info(f"Bot script path: {bot_script}")
        logger.info(f"Bot script exists: {bot_script.exists()}")
        logger.info(f"Python executable: {sys.executable}")
        
        if not bot_script.exists():
            logger.error(f"❌ Bot script not found at {bot_script}")
            logger.error(f"   Requested script: {script_name}")
            logger.error(f"   Available scripts in directory:")
            for f in bot_dir.glob("*.py"):
                logger.error(f"     - {f.name}")
            return jsonify({'error': f'Bot script not found: {script_name}'}), 500

        # Build the command list with NAMED arguments
        logger.info("Building command list with named arguments...")
        command = [
            sys.executable,
            str(bot_script),
            '--user-id', str(config.get('user_id')),
            '--strategy-id', str(config.get('strategy_id')),
            '--mt5-login', str(config.get('mt5_account')),
            '--mt5-password', str(config.get('mt5_password')),
            '--mt5-server', str(config.get('mt5_server')),
            '--supabase-url', str(config.get('supabase_url')),
            '--supabase-key', str(config.get('supabase_service_key')),
            '--gemini-api-key', str(config.get('gemini_api_key'))
        ]

        # Add optional arguments ONLY if they exist in the config
        if config.get('telegram_chat_id'):
            command.extend(['--telegram-chat-id', str(config.get('telegram_chat_id'))])
    
        if config.get('telegram_bot_token'):
            command.extend(['--telegram-bot-token', str(config.get('telegram_bot_token'))])
        else:
            logger.warning("⚠️ 'telegram_bot_token' not found in config. Telegram may fail.")

        logger.debug(f"Executing command: {' '.join(command)}")

        # Create user+strategy specific log directory for startup errors
        user_log_dir = bot_dir / f"Hybrid_AI_Bot_Logs_{user_id}_{strategy_id}"
        user_log_dir.mkdir(exist_ok=True)
        stdout_log = user_log_dir / "bot_startup_stdout.log"
        stderr_log = user_log_dir / "bot_startup_stderr.log"

        # Start bot process (Windows-specific)
        logger.info(f"Starting bot subprocess... Startup logs will be in {user_log_dir.name}")
        try:
            with open(stdout_log, 'wb') as out, open(stderr_log, 'wb') as err:
                process = subprocess.Popen(
                    command,
                    stdout=out,
                    stderr=err,
                    cwd=str(bot_dir),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            logger.info(f"✅ Subprocess created with PID: {process.pid}")
            
        except Exception as proc_error:
            logger.error(f"❌ Failed to create subprocess: {proc_error}")
            logger.error(traceback.format_exc())
            return jsonify({'error': f'Failed to start bot: {str(proc_error)}'}), 500
        
        # Store with composite key for multi-bot support
        running_bots[bot_key] = {
            'process': process,
            'config': config,
            'pid': process.pid,
            'started_at': datetime.now().isoformat(),
            'user_id': user_id,
            'strategy_id': strategy_id,
            'strategy_name': strategy_name
        }
        
        # Get updated count for this user
        user_bots_after = get_user_bots(user_id)
        
        logger.info(f"✅ Bot started successfully")
        logger.info(f"   Bot Key: {bot_key}")
        logger.info(f"   PID: {process.pid}")
        logger.info(f"   Strategy: {strategy_name}")
        logger.info(f"   User's total running bots: {len(user_bots_after)}")
        logger.info(f"   Total running bots (all users): {len(running_bots)}")
        logger.info("="*80)
        
        return jsonify({
            'success': True,
            'message': f'Bot started for user {user_id} - Strategy: {strategy_name}',
            'pid': process.pid,
            'strategy_id': strategy_id,
            'bot_key': bot_key,
            'user_bot_count': len(user_bots_after)
        })
        
    except Exception as e:
        logger.error("="*80)
        logger.error(f"❌ FATAL ERROR starting bot: {e}")
        logger.error(traceback.format_exc())
        logger.error("="*80)
        return jsonify({'error': str(e)}), 500

@app.route('/bot/stop', methods=['POST'])
@require_auth
def stop_bot():
    """Stop a trading bot - Supports stopping specific strategy or all user bots"""
    try:
        config = request.json
        user_id = config.get('user_id')
        strategy_id = config.get('strategy_id')
        stop_all = config.get('stop_all', False)  # New flag to stop all user bots
        
        if not user_id:
            return jsonify({'error': 'user_id required'}), 400
        
        stopped_bots = []
        
        if stop_all:
            # Stop all bots for this user
            logger.info(f"🛑 Stopping ALL bots for user {user_id}")
            user_bots = get_user_bots(user_id)
            
            if not user_bots:
                return jsonify({
                    'success': False,
                    'message': 'No bots running for this user'
                }), 400
            
            for bot_key, bot_info in list(user_bots.items()):
                try:
                    _stop_single_bot(bot_key, bot_info)
                    stopped_bots.append({
                        'strategy_id': bot_info['strategy_id'],
                        'strategy_name': bot_info.get('strategy_name', 'Unknown'),
                        'pid': bot_info['pid']
                    })
                except Exception as e:
                    logger.error(f"Error stopping bot {bot_key}: {e}")
            
            logger.info(f"✅ Stopped {len(stopped_bots)} bot(s) for user {user_id}")
            return jsonify({
                'success': True,
                'message': f'Stopped {len(stopped_bots)} bot(s) for user {user_id}',
                'stopped_bots': stopped_bots
            })
        
        else:
            # Stop specific strategy
            if not strategy_id:
                return jsonify({'error': 'strategy_id required (or use stop_all=true)'}), 400
            
            bot_key = get_bot_key(user_id, strategy_id)
            logger.info(f"🛑 Stopping bot: {bot_key}")
            
            if bot_key not in running_bots:
                return jsonify({
                    'success': False,
                    'message': f'No bot running for strategy {strategy_id}'
                }), 400
            
            bot_info = running_bots[bot_key]
            _stop_single_bot(bot_key, bot_info)
            
            # Get remaining count for user
            user_bots_remaining = get_user_bots(user_id)
            
            logger.info(f"✅ Stopped bot for key {bot_key}")
            logger.info(f"   User's remaining bots: {len(user_bots_remaining)}")
            
            return jsonify({
                'success': True,
                'message': f'Bot stopped for strategy {bot_info.get("strategy_name", strategy_id)}',
                'strategy_id': strategy_id,
                'user_remaining_bots': len(user_bots_remaining)
            })
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def _stop_single_bot(bot_key, bot_info):
    """Internal helper to stop a single bot"""
    process = bot_info['process']
    pid = bot_info['pid']
    
    try:
        parent = psutil.Process(pid)
        # Terminate child processes first
        for child in parent.children(recursive=True):
            child.terminate()
        parent.terminate()
        
        # Wait for termination
        parent.wait(timeout=10)
    except psutil.NoSuchProcess:
        logger.info(f"Process {pid} already terminated")
    except psutil.TimeoutExpired:
        # Force kill if graceful termination fails
        logger.warning(f"Process {pid} did not terminate gracefully, forcing kill")
        try:
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except:
            pass
    
    # Remove from tracking
    if bot_key in running_bots:
        del running_bots[bot_key]

@app.route('/bot/status', methods=['GET'])
@require_auth
def bot_status():
    """Get status of all running bots - Enhanced for multi-bot"""
    # Optional: filter by user_id
    filter_user_id = request.args.get('user_id')
    
    status = {}
    bots_by_user = {}
    
    for bot_key, bot_info in list(running_bots.items()):
        process = bot_info['process']
        pid = bot_info['pid']
        user_id = bot_info.get('user_id', 'unknown')
        strategy_id = bot_info.get('strategy_id')
        
        # Apply filter if specified
        if filter_user_id and user_id != filter_user_id:
            continue
        
        # Check if process is still running
        is_running = False
        try:
            is_running = psutil.pid_exists(pid) and process.poll() is None
        except:
            pass
        
        # Clean up dead processes
        if not is_running and bot_key in running_bots:
            del running_bots[bot_key]
            logger.info(f"Cleaned up dead process for key {bot_key}")
            continue
        
        bot_status = {
            'pid': pid,
            'running': is_running,
            'strategy_id': strategy_id,
            'strategy_name': bot_info.get('strategy_name', 'Unknown'),
            'started_at': bot_info.get('started_at'),
            'user_id': user_id
        }
        
        status[bot_key] = bot_status
        
        # Group by user
        if user_id not in bots_by_user:
            bots_by_user[user_id] = []
        bots_by_user[user_id].append(bot_status)
    
    return jsonify({
        'active_bots': len(status),
        'active_users': len(bots_by_user),
        'bots': status,
        'bots_by_user': bots_by_user,
        'multi_bot_support': True
    })

@app.route('/bot/user/<user_id>', methods=['GET'])
@require_auth
def get_user_bot_status(user_id):
    """Get status of all bots for a specific user"""
    user_bots = get_user_bots(user_id)
    
    bots_status = []
    for bot_key, bot_info in list(user_bots.items()):
        process = bot_info['process']
        pid = bot_info['pid']
        
        # Check if process is still running
        is_running = False
        try:
            is_running = psutil.pid_exists(pid) and process.poll() is None
        except:
            pass
        
        # Clean up dead processes
        if not is_running and bot_key in running_bots:
            del running_bots[bot_key]
            logger.info(f"Cleaned up dead process for key {bot_key}")
            continue
        
        bots_status.append({
            'bot_key': bot_key,
            'pid': pid,
            'running': is_running,
            'strategy_id': bot_info.get('strategy_id'),
            'strategy_name': bot_info.get('strategy_name', 'Unknown'),
            'started_at': bot_info.get('started_at')
        })
    
    return jsonify({
        'user_id': user_id,
        'bot_count': len(bots_status),
        'bots': bots_status
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info("="*80)
    logger.info(f"🚀 BOT MANAGER HTTP SERVER (Windows) - MULTI-BOT SUPPORT")
    logger.info(f"   Port: {port}")
    logger.info(f"   Host: 0.0.0.0 (all interfaces)")
    logger.info(f"   Secret configured: {BOT_MANAGER_SECRET != 'your-secure-secret-here'}")
    logger.info(f"   Log file: bot_manager.log")
    logger.info(f"   Multi-bot per user: ENABLED")
    logger.info("="*80)
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ FATAL: Server failed to start: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
