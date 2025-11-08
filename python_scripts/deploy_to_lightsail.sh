#!/bin/bash
# Deployment script for AWS Lightsail
# Run this on your Lightsail instance to set up the bot environment

set -e

echo "🚀 Setting up Trading Bot on AWS Lightsail..."

# Update system
echo "📦 Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and dependencies
echo "🐍 Installing Python 3.9+..."
sudo apt-get install -y python3.9 python3.9-venv python3-pip

# Install MetaTrader 5 dependencies (if not already done)
echo "📊 Installing MT5 dependencies..."
sudo apt-get install -y wine64 xvfb

# Create bot directory
BOT_DIR="/opt/trading-bot"
echo "📁 Creating bot directory at $BOT_DIR..."
sudo mkdir -p $BOT_DIR
sudo chown $USER:$USER $BOT_DIR

# Copy bot files
echo "📋 Copying bot files..."
cp bot_wrapper.py $BOT_DIR/
cp requirements.txt $BOT_DIR/

# Create Python virtual environment
echo "🔧 Setting up Python virtual environment..."
cd $BOT_DIR
python3.9 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📚 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create bot manager script
echo "⚙️ Creating bot manager..."
cat > $BOT_DIR/bot_manager.py << 'EOF'
#!/usr/bin/env python3
"""
Bot Manager - Handles multiple user bots
Listens for start/stop commands from Supabase
"""
import sys
import json
import subprocess
import signal
import os
from pathlib import Path
from supabase import create_client
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store running processes
running_bots = {}

def start_bot(user_id: str, config: dict):
    """Start a bot for a user"""
    try:
        if user_id in running_bots:
            logger.warning(f"Bot already running for user {user_id}")
            return False
        
        # Prepare config JSON
        config_json = json.dumps(config)
        
        # Start bot process
        process = subprocess.Popen(
            [sys.executable, 'bot_wrapper.py', config_json],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        running_bots[user_id] = {
            'process': process,
            'config': config,
            'started_at': time.time()
        }
        
        logger.info(f"✅ Started bot for user {user_id} (PID: {process.pid})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start bot for user {user_id}: {e}")
        return False

def stop_bot(user_id: str):
    """Stop a bot for a user"""
    try:
        if user_id not in running_bots:
            logger.warning(f"No bot running for user {user_id}")
            return False
        
        bot_info = running_bots[user_id]
        process = bot_info['process']
        
        # Send SIGTERM for graceful shutdown
        process.terminate()
        
        # Wait up to 10 seconds for graceful shutdown
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Force kill if not stopped
            process.kill()
            process.wait()
        
        del running_bots[user_id]
        logger.info(f"✅ Stopped bot for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to stop bot for user {user_id}: {e}")
        return False

def monitor_bots():
    """Monitor running bots and restart if crashed"""
    for user_id, bot_info in list(running_bots.items()):
        process = bot_info['process']
        
        # Check if process is still running
        if process.poll() is not None:
            logger.warning(f"⚠️ Bot crashed for user {user_id}, restarting...")
            del running_bots[user_id]
            start_bot(user_id, bot_info['config'])

def main():
    """Main manager loop"""
    logger.info("🤖 Bot Manager Started")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Get Supabase connection from environment
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        logger.error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    # Main loop
    while True:
        try:
            # Check for new bot start requests
            # You can implement webhook or polling here
            
            # Monitor existing bots
            monitor_bots()
            
            # Status logging
            if len(running_bots) > 0:
                logger.info(f"📊 Active bots: {len(running_bots)}")
            
            time.sleep(10)  # Check every 10 seconds
            
        except KeyboardInterrupt:
            logger.info("⚠️ Shutting down manager...")
            # Stop all bots
            for user_id in list(running_bots.keys()):
                stop_bot(user_id)
            break
        except Exception as e:
            logger.error(f"Manager error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
EOF

chmod +x $BOT_DIR/bot_manager.py

# Create systemd service for bot manager
echo "🔧 Creating systemd service..."
sudo cat > /etc/systemd/system/trading-bot-manager.service << EOF
[Unit]
Description=Trading Bot Manager
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$BOT_DIR
Environment="PATH=$BOT_DIR/venv/bin"
Environment="SUPABASE_URL=REPLACE_WITH_YOUR_SUPABASE_URL"
Environment="SUPABASE_SERVICE_ROLE_KEY=REPLACE_WITH_YOUR_SERVICE_KEY"
ExecStart=$BOT_DIR/venv/bin/python3 $BOT_DIR/bot_manager.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "✅ Installation complete!"
echo ""
echo "⚠️  IMPORTANT: Edit the systemd service file with your credentials:"
echo "   sudo nano /etc/systemd/system/trading-bot-manager.service"
echo ""
echo "Then run:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable trading-bot-manager"
echo "   sudo systemctl start trading-bot-manager"
echo ""
echo "Check status with:"
echo "   sudo systemctl status trading-bot-manager"
echo "   sudo journalctl -u trading-bot-manager -f"
