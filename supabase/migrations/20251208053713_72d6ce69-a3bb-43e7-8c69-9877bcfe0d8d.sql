-- Update the handle_new_user function to use the selected plan from user metadata
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
    -- Determine subscription status and trial period
    IF target_plan_type = 'free' THEN
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
        target_plan_id,
        'active',
        NULL,
        NULL
      );
    ELSE
      -- Pro/Enterprise: 7-day trial period
      trial_end_date := NOW() + INTERVAL '7 days';
      INSERT INTO public.user_subscriptions (
        user_id, 
        plan_id, 
        status,
        trial_ends_at,
        subscription_ends_at
      )
      VALUES (
        NEW.id,
        target_plan_id,
        'trial',
        trial_end_date,
        trial_end_date
      );
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