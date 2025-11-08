#!/usr/bin/env python3
"""
Dynamic Trading Bot Wrapper
Accepts user-specific parameters and integrates with Supabase
"""

import sys
import json
import os
import requests
from supabase import create_client, Client
from datetime import datetime
import MetaTrader5 as mt5
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupabaseTradingBot:
    def __init__(self, config: dict):
        """Initialize bot with user-specific configuration"""
        self.user_id = config['user_id']
        self.strategy_id = config['strategy_id']
        self.mt5_login = int(config['mt5_account'])
        self.mt5_password = config['mt5_password']
        self.mt5_server = config['mt5_server']
        self.account_size = float(config['account_size'])
        self.risk_per_trade = float(config['risk_per_trade'])
        self.max_positions = int(config.get('max_positions', 3))
        self.telegram_chat_id = config.get('telegram_chat_id')
        self.telegram_bot_token = config.get('telegram_bot_token')
        
        # Initialize Supabase client
        self.supabase: Client = create_client(
            config['supabase_url'],
            config['supabase_service_key']
        )
        
        # Trading state
        self.is_running = True
        self.open_positions = {}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.heartbeat_interval = 30  # seconds
        
    def send_telegram_notification(self, message: str):
        """Send Telegram notification"""
        if not self.telegram_chat_id or not self.telegram_bot_token:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            requests.post(url, json=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    
    def update_heartbeat(self, status: str = 'running', mt5_connected: bool = True, error_message: str = None):
        """Update bot heartbeat in Supabase"""
        try:
            self.supabase.table('bot_heartbeats').upsert({
                'user_id': self.user_id,
                'strategy_id': self.strategy_id,
                'last_heartbeat': datetime.utcnow().isoformat(),
                'status': status,
                'mt5_connected': mt5_connected,
                'error_message': error_message,
                'metadata': {
                    'reconnect_attempts': self.reconnect_attempts
                }
            }, on_conflict='user_id,strategy_id').execute()
        except Exception as e:
            logger.error(f"Failed to update heartbeat: {e}")
    
    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection with exponential backoff"""
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                if not mt5.initialize():
                    raise Exception("MT5 initialization failed")
                
                if not mt5.login(self.mt5_login, password=self.mt5_password, server=self.mt5_server):
                    raise Exception(f"MT5 login failed: {mt5.last_error()}")
                
                logger.info(f"✅ MT5 connected: {self.mt5_server} - Account {self.mt5_login}")
                self.reconnect_attempts = 0
                self.update_heartbeat(status='running', mt5_connected=True)
                self.send_telegram_notification(
                    f"🟢 <b>Bot Connected</b>\n\n"
                    f"Account: {self.mt5_login}\n"
                    f"Server: {self.mt5_server}\n"
                    f"Strategy: {self.strategy_id}"
                )
                return True
                
            except Exception as e:
                self.reconnect_attempts += 1
                wait_time = min(2 ** self.reconnect_attempts, 300)  # Exponential backoff, max 5 min
                logger.error(f"MT5 connection failed (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}): {e}")
                self.update_heartbeat(status='reconnecting', mt5_connected=False, error_message=str(e))
                
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    self.send_telegram_notification(
                        f"⚠️ <b>Connection Lost</b>\n\n"
                        f"Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}\n"
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    self.send_telegram_notification(
                        f"🔴 <b>Bot Crashed</b>\n\n"
                        f"Failed to reconnect after {self.max_reconnect_attempts} attempts\n"
                        f"Error: {str(e)}"
                    )
                    mt5.shutdown()
                    return False
        
        return False
    
    def sync_account_balance(self):
        """Sync current account balance to Supabase"""
        try:
            account_info = mt5.account_info()
            if not account_info:
                return
            
            self.supabase.table('user_subscriptions').update({
                'account_balance': float(account_info.equity)
            }).eq('user_id', self.user_id).execute()
            
        except Exception as e:
            logger.error(f"Error syncing balance: {e}")
    
    def sync_open_positions(self):
        """Sync open positions from MT5 to Supabase"""
        try:
            positions = mt5.positions_get()
            if not positions:
                return
            
            for pos in positions:
                # Check if trade already exists in DB
                existing = self.supabase.table('trades').select('id').eq(
                    'user_id', self.user_id
                ).eq('metadata->>ticket', str(pos.ticket)).execute()
                
                if not existing.data:
                    # Create new trade record
                    self.supabase.table('trades').insert({
                        'user_id': self.user_id,
                        'strategy_id': self.strategy_id,
                        'symbol': pos.symbol,
                        'trade_type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                        'entry_price': float(pos.price_open),
                        'quantity': float(pos.volume),
                        'status': 'open',
                        'opened_at': datetime.fromtimestamp(pos.time).isoformat(),
                        'metadata': {
                            'ticket': pos.ticket,
                            'stop_loss': float(pos.sl) if pos.sl else None,
                            'take_profit': float(pos.tp) if pos.tp else None,
                            'current_price': float(pos.price_current),
                            'profit': float(pos.profit),
                            'swap': float(pos.swap),
                            'commission': float(pos.commission)
                        }
                    }).execute()
                    logger.info(f"✅ Synced open position: {pos.symbol} Ticket {pos.ticket}")
                    
                    # Send Telegram notification for new trade
                    self.send_telegram_notification(
                        f"📈 <b>New Position Opened</b>\n\n"
                        f"Symbol: {pos.symbol}\n"
                        f"Type: {'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'}\n"
                        f"Price: {pos.price_open:.5f}\n"
                        f"Volume: {pos.volume}\n"
                        f"Current P&L: ${pos.profit:.2f}"
                    )
                else:
                    # Update existing trade
                    self.supabase.table('trades').update({
                        'metadata': {
                            'ticket': pos.ticket,
                            'stop_loss': float(pos.sl) if pos.sl else None,
                            'take_profit': float(pos.tp) if pos.tp else None,
                            'current_price': float(pos.price_current),
                            'profit': float(pos.profit),
                            'swap': float(pos.swap),
                            'commission': float(pos.commission)
                        }
                    }).eq('user_id', self.user_id).eq(
                        'metadata->>ticket', str(pos.ticket)
                    ).execute()
            
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
    
    def sync_closed_trades(self):
        """Sync closed trades from MT5 to Supabase"""
        try:
            # Get deals from last 24 hours
            from_date = datetime.now().replace(hour=0, minute=0, second=0)
            deals = mt5.history_deals_get(from_date, datetime.now())
            
            if not deals:
                return
            
            for deal in deals:
                if deal.entry != mt5.DEAL_ENTRY_OUT:  # Only exit deals
                    continue
                
                # Check if already synced
                existing = self.supabase.table('trades').select('id').eq(
                    'user_id', self.user_id
                ).eq('metadata->>ticket', str(deal.position_id)).eq(
                    'status', 'closed'
                ).execute()
                
                if existing.data:
                    continue
                
                # Find the open trade record
                open_trade = self.supabase.table('trades').select('*').eq(
                    'user_id', self.user_id
                ).eq('metadata->>ticket', str(deal.position_id)).eq(
                    'status', 'open'
                ).execute()
                
                if open_trade.data:
                    trade = open_trade.data[0]
                    
                    # Update to closed
                    self.supabase.table('trades').update({
                        'status': 'closed',
                        'exit_price': float(deal.price),
                        'profit_loss': float(deal.profit),
                        'closed_at': datetime.fromtimestamp(deal.time).isoformat(),
                        'metadata': {
                            **trade['metadata'],
                            'exit_ticket': deal.ticket,
                            'swap': float(deal.swap),
                            'commission': float(deal.commission)
                        }
                    }).eq('id', trade['id']).execute()
                    
                    logger.info(f"✅ Closed trade synced: {deal.symbol} P&L: ${deal.profit:.2f}")
                    
                    # Send Telegram notification for closed trade
                    profit_emoji = "💚" if deal.profit > 0 else "❌"
                    self.send_telegram_notification(
                        f"{profit_emoji} <b>Position Closed</b>\n\n"
                        f"Symbol: {deal.symbol}\n"
                        f"Exit Price: {deal.price:.5f}\n"
                        f"P&L: <b>${deal.profit:.2f}</b>"
                    )
            
        except Exception as e:
            logger.error(f"Error syncing closed trades: {e}")
    
    def check_bot_status(self) -> bool:
        """Check if bot should continue running"""
        try:
            result = self.supabase.table('user_strategies').select('is_running').eq(
                'user_id', self.user_id
            ).eq('strategy_id', self.strategy_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['is_running']
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking bot status: {e}")
            return False
    
    def run(self):
        """Main bot loop"""
        logger.info("="*80)
        logger.info(f"🤖 TRADING BOT STARTED FOR USER: {self.user_id}")
        logger.info(f"   Strategy ID: {self.strategy_id}")
        logger.info(f"   MT5 Account: {self.mt5_login}")
        logger.info("="*80)
        
        if not self.initialize_mt5():
            logger.error("Failed to initialize MT5. Exiting.")
            return
        
        iteration = 0
        last_heartbeat = time.time()
        
        try:
            while self.is_running:
                iteration += 1
                
                # Check MT5 connection health
                if not mt5.terminal_info():
                    logger.warning("MT5 connection lost. Attempting reconnection...")
                    self.update_heartbeat(status='reconnecting', mt5_connected=False)
                    if not self.initialize_mt5():
                        logger.error("Failed to reconnect to MT5. Exiting.")
                        break
                
                # Check if bot should continue running
                if not self.check_bot_status():
                    logger.info("Bot stopped by user via dashboard")
                    self.send_telegram_notification("🛑 <b>Bot Stopped</b>\n\nStopped by user via dashboard")
                    break
                
                # Update heartbeat every 30 seconds
                if time.time() - last_heartbeat >= self.heartbeat_interval:
                    self.update_heartbeat(status='running', mt5_connected=True)
                    last_heartbeat = time.time()
                
                # Sync data every iteration
                self.sync_account_balance()
                self.sync_open_positions()
                self.sync_closed_trades()
                
                # Log status every 10 iterations
                if iteration % 10 == 0:
                    account_info = mt5.account_info()
                    if account_info:
                        logger.info(f"📊 Equity: ${account_info.equity:.2f} | Balance: ${account_info.balance:.2f}")
                
                # Wait before next iteration
                time.sleep(10)  # Check every 10 seconds
                
        except KeyboardInterrupt:
            logger.info("⚠️ Bot stopped by user")
            self.update_heartbeat(status='stopped', mt5_connected=False)
        except Exception as e:
            logger.error(f"❌ Critical error: {e}", exc_info=True)
            self.update_heartbeat(status='crashed', mt5_connected=False, error_message=str(e))
            self.send_telegram_notification(
                f"🔴 <b>Bot Crashed</b>\n\n"
                f"Error: {str(e)}\n"
                f"Check logs for details"
            )
            
            # Log crash to audit table
            try:
                self.supabase.table('bot_audit_logs').insert({
                    'user_id': self.user_id,
                    'strategy_id': self.strategy_id,
                    'action': 'crash',
                    'metadata': {'error': str(e)}
                }).execute()
            except:
                pass
        finally:
            mt5.shutdown()
            logger.info("🛑 Bot shutdown complete")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python bot_wrapper.py <config_json>")
        sys.exit(1)
    
    try:
        # Parse configuration from command line argument
        config = json.loads(sys.argv[1])
        
        # Validate required fields
        required_fields = [
            'user_id', 'strategy_id', 'mt5_account', 'mt5_password', 
            'mt5_server', 'account_size', 'risk_per_trade',
            'supabase_url', 'supabase_service_key'
        ]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        # Initialize and run bot
        bot = SupabaseTradingBot(config)
        bot.run()
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON configuration: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
