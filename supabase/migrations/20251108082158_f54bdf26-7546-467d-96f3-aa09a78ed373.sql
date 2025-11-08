-- Fix handle_new_user to use correct enum value
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
  
  -- Get default free plan (changed from 'starter' to 'free')
  SELECT id INTO default_plan_id
  FROM public.plans
  WHERE plan_type = 'free' AND is_active = true
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