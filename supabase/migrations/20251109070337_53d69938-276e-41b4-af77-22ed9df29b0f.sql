-- Create rate limiting function for public endpoints
CREATE TABLE IF NOT EXISTS public.rate_limit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 1,
  window_start TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_key_window ON public.rate_limit_log(key, window_start DESC);

-- Function to check rate limits
CREATE OR REPLACE FUNCTION public.check_rate_limit(
  p_key TEXT,
  p_max_requests INTEGER DEFAULT 5,
  p_window_seconds INTEGER DEFAULT 60
)
RETURNS TABLE(allowed BOOLEAN, remaining INTEGER) 
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_count INTEGER;
  v_window_start TIMESTAMPTZ;
BEGIN
  v_window_start := NOW() - (p_window_seconds || ' seconds')::INTERVAL;
  
  -- Clean up old entries
  DELETE FROM public.rate_limit_log 
  WHERE window_start < v_window_start;
  
  -- Get current count for this key
  SELECT COALESCE(SUM(request_count), 0) INTO v_count
  FROM public.rate_limit_log
  WHERE key = p_key AND window_start >= v_window_start;
  
  -- Check if limit exceeded
  IF v_count >= p_max_requests THEN
    RETURN QUERY SELECT FALSE, 0;
    RETURN;
  END IF;
  
  -- Log this request
  INSERT INTO public.rate_limit_log (key, window_start)
  VALUES (p_key, NOW())
  ON CONFLICT (id) DO NOTHING;
  
  RETURN QUERY SELECT TRUE, (p_max_requests - v_count - 1);
END;
$$;

-- Add SET search_path to existing security definer functions
ALTER FUNCTION public.has_role(_user_id uuid, _role app_role) SET search_path = public;
ALTER FUNCTION public.create_admin_account(admin_email text, admin_password text, admin_name text) SET search_path = public;
ALTER FUNCTION public.generate_otp(p_email text, p_user_id uuid, p_otp_type text) SET search_path = public;
ALTER FUNCTION public.verify_otp(p_email text, p_otp_code text, p_otp_type text) SET search_path = public;
ALTER FUNCTION public.process_referral_signup(referred_user_id_param uuid, referral_code_param text) SET search_path = public;
ALTER FUNCTION public.generate_referral_code(user_id_param uuid) SET search_path = public;
ALTER FUNCTION public.cleanup_expired_otps() SET search_path = public;
ALTER FUNCTION public.notify_trial_expiring() SET search_path = public;
ALTER FUNCTION public.handle_new_user() SET search_path = public;
ALTER FUNCTION public.get_user_performance(p_user_id uuid) SET search_path = public;
ALTER FUNCTION public.get_platform_pnl_overview() SET search_path = public;
ALTER FUNCTION public.get_strategy_performance() SET search_path = public;
ALTER FUNCTION public.update_strategy_performance() SET search_path = public;
ALTER FUNCTION public.notify_bot_started() SET search_path = public;
ALTER FUNCTION public.notify_new_trade() SET search_path = public;
ALTER FUNCTION public.notify_trade_closed() SET search_path = public;

-- Add RLS policies for user_roles table to prevent privilege escalation
CREATE POLICY "Only admins can assign roles" ON public.user_roles
FOR INSERT 
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);

CREATE POLICY "Only admins can update roles" ON public.user_roles
FOR UPDATE 
USING (
  EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);

CREATE POLICY "Only admins can delete roles" ON public.user_roles
FOR DELETE 
USING (
  EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);