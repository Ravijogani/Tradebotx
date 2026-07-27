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


def _read_marker(folder: str):
    """Read the full user_id an instance folder was provisioned for, if marked."""
    marker = os.path.join(folder, "user_id.txt")
    if os.path.exists(marker):
        with open(marker, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def get_existing_instances():
    """Map full user_id -> instance folder for already-provisioned users.

    Instances are identified by their user_id.txt marker, not by folder name
    alone — the folder name is a truncated (8-char) prefix of the user_id and
    two different users can share that prefix. Legacy instances provisioned
    before the marker existed are still recognized by folder name, but a new
    user whose prefix collides with one of those gets a disambiguated folder
    instead of silently reusing someone else's MT5 terminal.
    """
    existing_by_user_id = {}
    if not os.path.exists(MT5_INSTANCES_DIR):
        return existing_by_user_id

    for d in os.listdir(MT5_INSTANCES_DIR):
        folder = os.path.join(MT5_INSTANCES_DIR, d)
        if not os.path.isdir(folder) or not os.path.exists(os.path.join(folder, "terminal64.exe")):
            continue
        marked_user_id = _read_marker(folder)
        if marked_user_id:
            existing_by_user_id[marked_user_id] = folder
        else:
            # Legacy instance with no marker — best-effort match on folder name.
            existing_by_user_id[d] = folder

    return existing_by_user_id


def provision_instance(full_user_id, folder_name):
    """Copy MT5 template to create a new, uniquely-marked user instance."""
    target = os.path.join(MT5_INSTANCES_DIR, folder_name)
    try:
        log.info(f"[PROVISION] {full_user_id} — copying MT5 template to {folder_name}...")
        shutil.copytree(MT5_TEMPLATE_DIR, target)
        with open(os.path.join(target, "user_id.txt"), "w", encoding="utf-8") as f:
            f.write(full_user_id)
        log.info(f"[OK] {full_user_id} — MT5 instance created at {target}")
        return True
    except Exception as e:
        log.error(f"[FAIL] {full_user_id} — {e}")
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

    # Existing instances, keyed by the full user_id they were provisioned for.
    existing = get_existing_instances()
    used_folder_names = {os.path.basename(p) for p in existing.values()}
    log.info(f"Existing instances: {len(existing)}")

    # Provision new users
    provisioned = 0
    skipped = 0
    failed = 0

    for full_id in approved_user_ids:
        if full_id in existing:
            log.debug(f"[SKIP] {full_id} — already exists at {existing[full_id]}")
            skipped += 1
            continue

        short_id = full_id[:8]
        folder_name = short_id
        if folder_name in used_folder_names:
            # Prefix collision with a different user's folder — disambiguate
            # instead of provisioning into (or being mistaken for) theirs.
            suffix = 2
            while f"{short_id}-{suffix}" in used_folder_names:
                suffix += 1
            folder_name = f"{short_id}-{suffix}"
            log.warning(f"[COLLISION] {full_id} shares prefix {short_id} with an existing instance — using {folder_name}")

        if provision_instance(full_id, folder_name):
            provisioned += 1
            existing[full_id] = os.path.join(MT5_INSTANCES_DIR, folder_name)
            used_folder_names.add(folder_name)
        else:
            failed += 1

    # Summary
    log.info("=" * 60)
    log.info(f"DONE — Provisioned: {provisioned} | Skipped: {skipped} | Failed: {failed}")
    log.info(f"Total instances: {len(existing)}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
