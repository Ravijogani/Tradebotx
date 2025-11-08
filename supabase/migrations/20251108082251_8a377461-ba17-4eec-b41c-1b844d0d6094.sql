-- Fix handle_new_user to set free plan as active without trial
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  default_plan_id UUID;
  default_plan_type plan_type;
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
  
  -- Get default free plan
  SELECT id, plan_type INTO default_plan_id, default_plan_type
  FROM public.plans
  WHERE plan_type = 'free' AND is_active = true
  LIMIT 1;
  
  -- Create user subscription
  IF default_plan_id IS NOT NULL THEN
    -- Free plan: active immediately, no trial
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
      'active',  -- Changed from 'trial' to 'active'
      NULL,      -- No trial period for free plan
      NULL       -- Free plan never expires
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