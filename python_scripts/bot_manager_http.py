#!/usr/bin/env python3
"""
HTTP-based Bot Manager
Runs on AWS Lightsail and accepts commands via HTTP
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

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store running bot processes
running_bots = {}

# Security: Shared secret for authentication
BOT_MANAGER_SECRET = os.getenv('BOT_MANAGER_SECRET', 'your-secure-secret-here')

def require_auth(f):
    """Authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        
        token = auth_header.split(' ')[1]
        if token != BOT_MANAGER_SECRET:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'active_bots': len(running_bots)
    })

@app.route('/bot/start', methods=['POST'])
@require_auth
def start_bot():
    """Start a trading bot for a user"""
    try:
        config = request.json
        user_id = config.get('user_id')
        strategy_id = config.get('strategy_id')
        
        if not user_id or not strategy_id:
            return jsonify({'error': 'user_id and strategy_id required'}), 400
        
        bot_key = f"{user_id}_{strategy_id}"
        
        if bot_key in running_bots:
            return jsonify({
                'success': False,
                'message': 'Bot already running for this user and strategy'
            }), 400
        
        # Validate required fields
        required_fields = [
            'mt5_account', 'mt5_password', 'mt5_server',
            'account_size', 'risk_per_trade', 'supabase_url', 'supabase_service_key'
        ]
        
        for field in required_fields:
            if field not in config:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Build command line arguments
        bot_dir = Path(__file__).parent
        bot_script = bot_dir / 'bot_wrapper.py'
        
        cmd = [
            sys.executable,
            str(bot_script)
        ]
        
        # Prepare config JSON
        config_json = json.dumps(config)
        cmd.append(config_json)
        
        # Start bot process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(bot_dir)
        )
        
        running_bots[bot_key] = {
            'process': process,
            'config': config,
            'pid': process.pid,
            'user_id': user_id,
            'strategy_id': strategy_id
        }
        
        logger.info(f"✅ Started bot for user {user_id}, strategy {strategy_id} (PID: {process.pid})")
        
        return jsonify({
            'success': True,
            'message': f'Bot started for user {user_id}',
            'pid': process.pid
        })
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/bot/stop', methods=['POST'])
@require_auth
def stop_bot():
    """Stop a trading bot for a user"""
    try:
        config = request.json
        user_id = config.get('user_id')
        strategy_id = config.get('strategy_id')
        
        if not user_id or not strategy_id:
            return jsonify({'error': 'user_id and strategy_id required'}), 400
        
        bot_key = f"{user_id}_{strategy_id}"
        
        if bot_key not in running_bots:
            return jsonify({
                'success': False,
                'message': 'No bot running for this user and strategy'
            }), 400
        
        bot_info = running_bots[bot_key]
        process = bot_info['process']
        
        # Graceful shutdown
        process.terminate()
        
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        
        del running_bots[bot_key]
        logger.info(f"✅ Stopped bot for user {user_id}, strategy {strategy_id}")
        
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
    dead_bots = []
    
    for bot_key, bot_info in running_bots.items():
        process = bot_info['process']
        is_running = process.poll() is None
        
        status[bot_key] = {
            'pid': bot_info['pid'],
            'running': is_running,
            'user_id': bot_info.get('user_id'),
            'strategy_id': bot_info.get('strategy_id')
        }
        
        # Mark dead processes for cleanup
        if not is_running:
            dead_bots.append(bot_key)
    
    # Clean up dead processes
    for bot_key in dead_bots:
        del running_bots[bot_key]
        logger.info(f"Cleaned up dead bot process: {bot_key}")
    
    return jsonify({
        'active_bots': len(running_bots),
        'bots': status
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🚀 Bot Manager HTTP Server starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
