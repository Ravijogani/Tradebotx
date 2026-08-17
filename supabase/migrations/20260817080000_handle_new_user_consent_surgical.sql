-- Add accepted_risk_disclaimer_at to handle_new_user() -- SURGICALLY.
--
-- This migration exists because the first attempt got it wrong in a way worth
-- recording. The original version rebuilt handle_new_user() from its 2025-11-08
-- definition and added the consent field to that. But the live function had
-- evolved substantially since: it now selects the signup plan from user
-- metadata, creates the user_subscriptions row with 7-day trial handling for
-- pro/enterprise, creates the user_setup row, processes referral codes, and
-- stores `phone` on the profile.
--
-- A wholesale CREATE OR REPLACE from the old definition would have silently
-- destroyed every one of those behaviours -- new signups would have received no
-- plan, no subscription, no trial, no setup record and no referral credit, with
-- no error to indicate it. Caught by reading pg_get_functiondef() on the live
-- database BEFORE applying, rather than by discovering broken signups later.
--
-- This version therefore starts FROM the live definition and changes exactly
-- one thing: accepted_risk_disclaimer_at is added to the profiles INSERT.
-- Everything else below is preserved verbatim.
--
-- LESSON FOR FUTURE MIGRATIONS IN THIS REPO: never CREATE OR REPLACE a trigger
-- function from an old migration file. Read the live definition first --
-- `SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = '<fn>'` -- and
-- edit that.

CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  target_plan_id UUID;
  target_plan_type plan_type;
  selected_plan TEXT;
  ref_code TEXT;
  trial_end_date TIMESTAMP WITH TIME ZONE;
BEGIN
  -- Insert profile
  -- accepted_risk_disclaimer_at added 2026-08: SignupDialog.tsx now requires an
  -- affirmative risk-disclosure checkbox and sends the timestamp in user
  -- metadata; persisting it here is the audit trail.
  INSERT INTO public.profiles (id, email, full_name, phone, accepted_risk_disclaimer_at)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    COALESCE(NEW.raw_user_meta_data->>'phone', ''),
    (NEW.raw_user_meta_data->>'accepted_risk_disclaimer_at')::timestamptz
  );

  -- Assign default user role
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, 'user');

  -- Get selected plan from user metadata (defaults to 'free')
  selected_plan := COALESCE(NEW.raw_user_meta_data->>'selected_plan', 'free');

  -- Get the plan based on selection
  SELECT id, plan_type INTO target_plan_id, target_plan_type
  FROM public.plans
  WHERE plan_type = selected_plan::plan_type AND is_active = true
  LIMIT 1;

  -- Fallback to free plan if selected plan not found
  IF target_plan_id IS NULL THEN
    SELECT id, plan_type INTO target_plan_id, target_plan_type
    FROM public.plans
    WHERE plan_type = 'free' AND is_active = true
    LIMIT 1;
  END IF;

  -- Create user subscription
  IF target_plan_id IS NOT NULL THEN
    IF target_plan_type = 'free' THEN
      -- Free plan: active immediately, no trial
      INSERT INTO public.user_subscriptions (
        user_id, plan_id, status, trial_ends_at, subscription_ends_at
      )
      VALUES (NEW.id, target_plan_id, 'active', NULL, NULL);
    ELSE
      -- Pro/Enterprise: 7-day trial period
      trial_end_date := NOW() + INTERVAL '7 days';
      INSERT INTO public.user_subscriptions (
        user_id, plan_id, status, trial_ends_at, subscription_ends_at
      )
      VALUES (NEW.id, target_plan_id, 'trial', trial_end_date, trial_end_date);
    END IF;
  END IF;

  -- Create user setup record
  INSERT INTO public.user_setup (user_id, is_completed)
  VALUES (NEW.id, false);

  -- Process referral code if provided
  ref_code := NEW.raw_user_meta_data->>'referral_code';
  IF ref_code IS NOT NULL AND ref_code != '' THEN
    PERFORM process_referral_signup(NEW.id, ref_code);
  END IF;

  RETURN NEW;
END;
$function$;
