"""
Auto-Provision MT5 Instances from Database
===========================================
Pulls all admin-approved users via edge function, provisions MT5 instances
for any user that doesn't have one yet. Safe to run repeatedly — skips
existing instances.

USAGE:
    python auto_provision_mt5.py

ENVIRONMENT VARIABLES (set before running):
    SUPABASE_URL          - Your Supabase project URL
    BOT_MANAGER_SECRET    - Bot manager secret (shared with edge functions)
    MT5_TEMPLATE_DIR      - Path to MT5 template (default: C:\\trading-bot\\MT5_Template)
    MT5_INSTANCES_DIR     - Path to instances folder (default: C:\\trading-bot\\MT5_Instances)

SCHEDULE (optional):
    Use Windows Task Scheduler to run this every hour or on-demand.
"""

import os
import sys
import shutil
import logging
import requests
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
BOT_MANAGER_SECRET = os.environ.get("BOT_MANAGER_SECRET", "")
MT5_TEMPLATE_DIR = os.environ.get("MT5_TEMPLATE_DIR", r"C:\trading-bot\MT5_Template")
MT5_INSTANCES_DIR = os.environ.get("MT5_INSTANCES_DIR", r"C:\trading-bot\MT5_Instances")

# ── Logging ────────────────────────────────────────────────────────────────
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mt5_provision.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


def get_approved_users():
    """Fetch all admin-approved users via edge function."""
    if not SUPABASE_URL or not BOT_MANAGER_SECRET:
        log.error("SUPABASE_URL and BOT_MANAGER_SECRET must be set")
        sys.exit(1)

    url = f"{SUPABASE_URL}/functions/v1/get-approved-users"
    headers = {
        "x-custom-auth": BOT_MANAGER_SECRET,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        users = data.get("users", [])
        log.info(f"Found {len(users)} approved users from edge function")
        return [u["user_id"] for u in users]
    except Exception as e:
        log.error(f"Failed to fetch users: {e}")
        sys.exit(1)


def get_existing_instances():
    """List user IDs that already have MT5 instances provisioned."""
    if not os.path.exists(MT5_INSTANCES_DIR):
        return set()
    return {
        d for d in os.listdir(MT5_INSTANCES_DIR)
        if os.path.isdir(os.path.join(MT5_INSTANCES_DIR, d))
        and os.path.exists(os.path.join(MT5_INSTANCES_DIR, d, "terminal64.exe"))
    }


def provision_instance(user_id_short):
    """Copy MT5 template to create a new user instance."""
    target = os.path.join(MT5_INSTANCES_DIR, user_id_short)
    try:
        log.info(f"[PROVISION] {user_id_short} — copying MT5 template...")
        shutil.copytree(MT5_TEMPLATE_DIR, target)
        log.info(f"[OK] {user_id_short} — MT5 instance created at {target}")
        return True
    except Exception as e:
        log.error(f"[FAIL] {user_id_short} — {e}")
        return False


def main():
    log.info("=" * 60)
    log.info("MT5 Auto-Provisioning Started")
    log.info(f"Template: {MT5_TEMPLATE_DIR}")
    log.info(f"Instances: {MT5_INSTANCES_DIR}")
    log.info("=" * 60)

    # Validate template
    template_exe = os.path.join(MT5_TEMPLATE_DIR, "terminal64.exe")
    if not os.path.exists(template_exe):
        log.error(f"MT5 template not found: {template_exe}")
        sys.exit(1)

    # Create instances directory if needed
    os.makedirs(MT5_INSTANCES_DIR, exist_ok=True)

    # Get approved users via edge function
    approved_user_ids = get_approved_users()

    # Get existing instances (first 8 chars)
    existing = get_existing_instances()
    log.info(f"Existing instances: {len(existing)}")

    # Provision new users
    provisioned = 0
    skipped = 0
    failed = 0

    for full_id in approved_user_ids:
        short_id = full_id[:8]

        if short_id in existing:
            log.debug(f"[SKIP] {short_id} — already exists")
            skipped += 1
            continue

        if provision_instance(short_id):
            provisioned += 1
            existing.add(short_id)
        else:
            failed += 1

    # Summary
    log.info("=" * 60)
    log.info(f"DONE — Provisioned: {provisioned} | Skipped: {skipped} | Failed: {failed}")
    log.info(f"Total instances: {len(existing)}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
