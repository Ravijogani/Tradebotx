#!/usr/bin/env python3
"""
HTTP-based Bot Manager - MULTI-BOT SUPPORT
Accepts bot start/stop commands from Supabase edge functions.
Supports multiple simultaneous bots per user (Pro: 5, Enterprise: unlimited).

Shared auth/logging/process-tracking logic lives in bot_manager_core.py —
see that file for what changed and why. This entry point just wires it up.
"""
from flask import Flask
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
logger.info(f"BOT MANAGER STARTING - {datetime.now()}")
logger.info(f"Python Version: {sys.version}")
logger.info(f"Working Directory: {os.getcwd()}")
logger.info("=" * 80)
core.log_environment_summary()

BOT_MANAGER_SECRET = os.getenv('BOT_MANAGER_SECRET', '')
if not BOT_MANAGER_SECRET:
    logger.error("FATAL: BOT_MANAGER_SECRET is not set. Refusing to start with no auth secret.")
    sys.exit(1)

BOT_DIR = Path(__file__).parent

app = Flask(__name__)
app.register_blueprint(core.build_bot_blueprint(
    get_secret=lambda: BOT_MANAGER_SECRET,
    bot_dir=BOT_DIR,
))

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info("=" * 80)
    logger.info(f"BOT MANAGER HTTP SERVER — listening on 0.0.0.0:{port}")
    logger.info("=" * 80)

    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception:
        logger.error(f"FATAL: Server failed to start:\n{traceback.format_exc()}")
        sys.exit(1)
