-- Risk-disclosure consent audit trail + a platform halt the bots actually read.
--
-- 1. accepted_risk_disclaimer_at
--    Signup previously had no affirmative risk acknowledgment at all -- the
--    Disclaimer page existed but nothing required a user to accept it, so
--    there was no record of who consented or when. SignupDialog.tsx now
--    requires an explicit checkbox and sends the timestamp in user metadata;
--    handle_new_user() persists it here.
--
-- 2. platform_settings.trading_halted
--    PlatformSettings.tsx has always offered admins a maintenance/halt
--    toggle, but nothing in the stack ever read platform_settings back
--    (confirmed by grepping supabase/functions and python_scripts: zero
--    reads). python_scripts/risk_limits.py + bot_control.py now poll it as a
--    genuine platform-wide stop, so the row needs to exist with a sane
--    default rather than being absent until an admin first saves the form.

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS accepted_risk_disclaimer_at TIMESTAMPTZ;

COMMENT ON COLUMN public.profiles.accepted_risk_disclaimer_at IS
  'When the user affirmatively accepted the Risk Disclaimer and Terms at signup. NULL for accounts created before consent was required.';

-- Carry the consent timestamp from signup metadata into the profile row.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, accepted_risk_disclaimer_at)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    (NEW.raw_user_meta_data->>'accepted_risk_disclaimer_at')::timestamptz
  );

  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, 'user');

  RETURN NEW;
END;
$$;

-- Seed the platform halt switch (off). ON CONFLICT so re-running is safe and
-- an existing admin-set value is never clobbered back to false.
INSERT INTO public.platform_settings (key, value, description)
VALUES (
  'trading_halted',
  'false'::jsonb,
  'Platform-wide emergency halt. When true, every running bot stops at its next check (python_scripts/bot_control.py). Distinct from maintenance_mode, which also halts trading.'
)
ON CONFLICT (key) DO NOTHING;
