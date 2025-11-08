-- Update handle_new_user to create setup and subscription records
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  default_plan_id UUID;
  ref_code TEXT;
BEGIN
  -- Insert profile
  INSERT INTO public.profiles (id, email, full_name, phone)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    COALESCE(NEW.raw_user_meta_data->>'phone', '')
  );
  
  -- Assign default user role
  INSERT INTO public.user_roles (user_id, role)
  VALUES (NEW.id, 'user');
  
  -- Get default starter plan
  SELECT id INTO default_plan_id
  FROM public.plans
  WHERE plan_type = 'starter' AND is_active = true
  LIMIT 1;
  
  -- Create user subscription with trial
  IF default_plan_id IS NOT NULL THEN
    INSERT INTO public.user_subscriptions (
      user_id, 
      plan_id, 
      status,
      trial_ends_at,
      subscription_ends_at
    )
    VALUES (
      NEW.id,
      default_plan_id,
      'trial',
      NOW() + INTERVAL '7 days',
      NOW() + INTERVAL '7 days'
    );
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

-- Create trigger for automatic trial expiry notifications
CREATE OR REPLACE FUNCTION notify_trial_expiring()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- This function can be called by a cron job to send trial expiry notifications
  -- For now it's a placeholder - notifications will be sent via edge function
  NULL;
END;
$$;

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_trial_ends ON user_subscriptions(trial_ends_at) WHERE status = 'trial';
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_status ON user_subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_trades_user_status ON trades(user_id, status);
CREATE INDEX IF NOT EXISTS idx_payment_history_user_date ON payment_history(user_id, created_at DESC);
