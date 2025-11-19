#!/usr/bin/env python3
"""
HTTP-based Bot Manager for Windows Server - ENHANCED DEBUG VERSION
Runs on AWS Lightsail Windows and accepts commands via HTTP
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
    level=logging.DEBUG,  # Changed to DEBUG for maximum verbosity
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('bot_manager.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Log startup information
logger.info("="*80)
logger.info(f"BOT MANAGER STARTING - {datetime.now()}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"Working Directory: {os.getcwd()}")
logger.info(f"Script Location: {__file__}")
logger.info("="*80)

# Store running bot processes
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
    
    system_info = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_bots': len(running_bots),
        'platform': 'windows',
        'python_version': sys.version,
        'working_directory': os.getcwd(),
        'secret_configured': BOT_MANAGER_SECRET != 'your-secure-secret-here',
        'secret_length': len(BOT_MANAGER_SECRET),
        'bot_list': list(running_bots.keys())
    }
    
    logger.debug(f"System info: {json.dumps(system_info, indent=2)}")
    return jsonify(system_info)

# =========================================================================
# === THIS IS THE ONLY FUNCTION THAT WAS REPLACED (Lines 133-216) ===
# =========================================================================
@app.route('/bot/start', methods=['POST'])
@require_auth
def start_bot():
    """Start a trading bot for a user - Enhanced with debugging"""
    try:
        logger.info("="*80)
        logger.info("🚀 BOT START REQUEST RECEIVED")
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
        
        if user_id in running_bots:
            logger.warning(f"⚠️ Bot already running for user {user_id}")
            return jsonify({
                'success': False,
                'message': 'Bot already running for this user'
            }), 400
        
        # === START OF MODIFICATIONS ===

        # 1. Get bot directory
        bot_dir = Path(__file__).parent
        
        # 2. === MODIFIED ===
        # Point DIRECTLY to your V11 script, not the wrapper
        bot_script = bot_dir / 'hybrid_trading_bot_multiuser.py'
        
        logger.info(f"Bot directory: {bot_dir}")
        logger.info(f"Bot script: {bot_script}")
        logger.info(f"Bot script exists: {bot_script.exists()}")
        logger.info(f"Python executable: {sys.executable}")
        
        if not bot_script.exists():
            logger.error(f"❌ Bot script not found at {bot_script}")
            logger.error("   Make sure 'hybrid_trading_bot_multiuser.py' is in the same directory as the manager.")
            return jsonify({'error': f'Bot script not found at {bot_script}'}), 500

        # 3. === NEW ===
        # Build the command list with NAMED arguments
        logger.info("Building command list with named arguments...")
        command = [
            sys.executable,
            str(bot_script),
            '--user-id', str(config.get('user_id')),
            '--strategy-id', str(config.get('strategy_id')),
            '--mt5-login', str(config.get('mt5_account')), # Maps 'mt5_account' from config to '--mt5-login'
            '--mt5-password', str(config.get('mt5_password')),
            '--mt5-server', str(config.get('mt5_server')),
            '--supabase-url', str(config.get('supabase_url')),
            '--supabase-key', str(config.get('supabase_service_key')),
            '--gemini-api-key', str(config.get('gemini_api_key'))
        ]

        # 4. === NEW ===
        # Add optional arguments ONLY if they exist in the config
        if config.get('telegram_chat_id'):
            command.extend(['--telegram-chat-id', str(config.get('telegram_chat_id'))])
    
        if config.get('telegram_bot_token'):
            command.extend(['--telegram-bot-token', str(config.get('telegram_bot_token'))])
        else:
            logger.warning("⚠️ 'telegram_bot_token' not found in config. Telegram may fail.")

        logger.debug(f"Executing command: {' '.join(command)}")

        # 5. === NEW ===
        # Create user-specific log directory for startup errors
        user_log_dir = bot_dir / f"Hybrid_AI_Bot_Logs_{user_id}"
        user_log_dir.mkdir(exist_ok=True) # Creates the directory
        stdout_log = user_log_dir / "bot_startup_stdout.log"
        stderr_log = user_log_dir / "bot_startup_stderr.log"

        # 6. === MODIFIED ===
        # Start bot process (Windows-specific)
        logger.info(f"Starting bot subprocess... Startup logs will be in {user_log_dir.name}")
        try:
            # Redirect stdout/stderr to files for debugging startup
            with open(stdout_log, 'wb') as out, open(stderr_log, 'wb') as err:
                process = subprocess.Popen(
                    command,  # Use the new named argument command list
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
        
        # === END OF MODIFICATIONS ===
        
        running_bots[user_id] = {
            'process': process,
            'config': config,
            'pid': process.pid,
            'started_at': datetime.now().isoformat(),
            'strategy_id': strategy_id,
            'strategy_name': strategy_name
        }
        
        logger.info(f"✅ Bot started successfully for user {user_id}")
        logger.info(f"   PID: {process.pid}")
        logger.info(f"   Strategy: {strategy_name}")
        logger.info(f"   Total running bots: {len(running_bots)}")
        logger.info("="*80)
        
        return jsonify({
            'success': True,
            'message': f'Bot started for user {user_id}',
            'pid': process.pid,
            'strategy_id': strategy_id
        })
        
    except Exception as e:
        logger.error("="*80)
        logger.error(f"❌ FATAL ERROR starting bot: {e}")
        logger.error(traceback.format_exc())
        logger.error("="*80)
        return jsonify({'error': str(e)}), 500
# =========================================================================
# === END OF REPLACED SECTION ===
# =========================================================================

@app.route('/bot/stop', methods=['POST'])
@require_auth
def stop_bot():
    """Stop a trading bot for a user"""
    try:
        config = request.json
        user_id = config.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'user_id required'}), 400
        
        if user_id not in running_bots:
            return jsonify({
                'success': False,
                'message': 'No bot running for this user'
            }), 400
        
        bot_info = running_bots[user_id]
        process = bot_info['process']
        pid = bot_info['pid']
        
        # Windows-specific: Use psutil for graceful termination
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
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        
        del running_bots[user_id]
        logger.info(f"✅ Stopped bot for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': f'Bot stopped for user {user_id}'
        })
        
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/bot/status', methods=['GET'])
@require_auth
def bot_status():
    """Get status of all running bots"""
    status = {}
    
    for user_id, bot_info in list(running_bots.items()):
        process = bot_info['process']
        pid = bot_info['pid']
        
        # Check if process is still running
        is_running = False
        try:
            is_running = psutil.pid_exists(pid) and process.poll() is None
        except:
            pass
        
        # Clean up dead processes
        if not is_running and user_id in running_bots:
            del running_bots[user_id]
            logger.info(f"Cleaned up dead process for user {user_id}")
            continue
        
        status[user_id] = {
            'pid': pid,
            'running': is_running,
            'strategy_id': bot_info['config'].get('strategy_id')
        }
    
    return jsonify({
        'active_bots': len(running_bots),
        'bots': status
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info("="*80)
    logger.info(f"🚀 BOT MANAGER HTTP SERVER (Windows) STARTING")
    logger.info(f"   Port: {port}")
    logger.info(f"   Host: 0.0.0.0 (all interfaces)")
    logger.info(f"   Secret configured: {BOT_MANAGER_SECRET != 'your-secure-secret-here'}")
    logger.info(f"   Log file: bot_manager.log")
    logger.info("="*80)
    
    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ FATAL: Server failed to start: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
