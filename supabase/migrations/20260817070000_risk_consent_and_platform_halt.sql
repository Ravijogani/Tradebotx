-- Risk-disclosure consent audit trail + a platform halt the bots actually read.
--
-- 1. accepted_risk_disclaimer_at
--    Signup previously had no affirmative risk acknowledgment at all -- the
--    Disclaimer page existed but nothing required a user to accept it, so
--    there was no record of who consented or when. SignupDialog.tsx now
--    requires an explicit checkbox and sends the timestamp in user metadata.
--
-- 2. platform_settings.trading_halted / maintenance_mode
--    PlatformSettings.tsx has always offered admins a maintenance/halt toggle,
--    but nothing in the stack ever read platform_settings back (confirmed by
--    grepping supabase/functions and python_scripts: zero reads).
--    python_scripts/bot_control.py now polls both as a genuine platform-wide
--    stop, so the rows need to exist with a safe default rather than being
--    absent until an admin first saves the form.
--
-- !! DO NOT add a `CREATE OR REPLACE FUNCTION handle_new_user()` here. !!
--    The first version of this migration did exactly that, rebuilt from the
--    ORIGINAL 2025-11-08 definition -- but the live function has evolved a long
--    way since: it selects the signup plan, creates the user_subscriptions row
--    with 7-day trial handling, creates the user_setup row, processes referral
--    codes, and stores `phone`. Replacing it wholesale would have silently
--    destroyed all of that, so every new signup would get no plan, no
--    subscription, no trial, no setup record and no referral credit. Caught by
--    reading the live definition before applying, not by testing afterwards.
--
--    The consent field is instead added to handle_new_user by a separate,
--    surgical migration (see 20260817080000) that starts FROM the live
--    definition and only adds the one column to its profiles INSERT.

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS accepted_risk_disclaimer_at TIMESTAMPTZ;

COMMENT ON COLUMN public.profiles.accepted_risk_disclaimer_at IS
  'When the user affirmatively accepted the Risk Disclaimer and Terms at signup. NULL for accounts created before consent was required.';

INSERT INTO public.platform_settings (key, value, description)
VALUES (
  'trading_halted',
  'false'::jsonb,
  'Platform-wide emergency halt. When true, every running bot stops at its next check (python_scripts/bot_control.py). Distinct from maintenance_mode, which also halts trading.'
)
ON CONFLICT (key) DO NOTHING;

INSERT INTO public.platform_settings (key, value, description)
VALUES (
  'maintenance_mode',
  'false'::jsonb,
  'Maintenance mode. When true, running bots stop at their next check (python_scripts/bot_control.py).'
)
ON CONFLICT (key) DO NOTHING;
