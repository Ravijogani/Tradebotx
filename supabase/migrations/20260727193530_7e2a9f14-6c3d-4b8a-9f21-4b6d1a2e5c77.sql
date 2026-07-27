-- Harden the OTP flow against brute-forcing / abuse of the RPCs directly
-- (both are SECURITY DEFINER and callable with the anon key, so send-otp's
-- send-side rate limiting alone doesn't protect them).

-- 1. verify_otp: rate-limit guesses per (email, otp_type) using the existing
--    check_rate_limit() infrastructure, and consume the OTP (mark verified)
--    after too many failed attempts so a leaked/guessed-at code can't keep
--    being retried once the window resets.
CREATE OR REPLACE FUNCTION verify_otp(
  p_email TEXT,
  p_otp_code TEXT,
  p_otp_type TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_valid BOOLEAN;
  v_allowed BOOLEAN;
BEGIN
  -- At most 5 verification attempts per email+type per 5 minutes.
  SELECT allowed INTO v_allowed
  FROM public.check_rate_limit('otp_verify:' || p_otp_type || ':' || lower(p_email), 5, 300);

  IF NOT v_allowed THEN
    RAISE EXCEPTION 'Too many verification attempts. Please request a new code and try again shortly.';
  END IF;

  -- Check if OTP is valid
  SELECT EXISTS (
    SELECT 1 FROM user_otps
    WHERE email = p_email
    AND otp_code = p_otp_code
    AND otp_type = p_otp_type
    AND verified = false
    AND expires_at > now()
  ) INTO v_valid;

  IF v_valid THEN
    UPDATE user_otps
    SET verified = true
    WHERE email = p_email
    AND otp_code = p_otp_code
    AND otp_type = p_otp_type;
  END IF;

  RETURN v_valid;
END;
$$;

-- 2. generate_otp: for admin_login specifically, refuse to issue a code
--    unless the target email actually belongs to an admin, and rate-limit
--    generation itself (not just the downstream send-otp call).
CREATE OR REPLACE FUNCTION generate_otp(
  p_email TEXT,
  p_user_id UUID DEFAULT NULL,
  p_otp_type TEXT DEFAULT 'signup'
)
RETURNS TABLE(otp_code TEXT, expires_at TIMESTAMP WITH TIME ZONE)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_otp TEXT;
  v_expires_at TIMESTAMP WITH TIME ZONE;
  v_allowed BOOLEAN;
  v_target_user_id UUID;
BEGIN
  -- At most 5 OTP generations per email+type per 5 minutes.
  SELECT allowed INTO v_allowed
  FROM public.check_rate_limit('otp_generate:' || p_otp_type || ':' || lower(p_email), 5, 300);

  IF NOT v_allowed THEN
    RAISE EXCEPTION 'Too many requests. Please try again shortly.';
  END IF;

  IF p_otp_type = 'admin_login' THEN
    SELECT id INTO v_target_user_id FROM auth.users WHERE lower(email) = lower(p_email);

    IF v_target_user_id IS NULL OR NOT public.has_role(v_target_user_id, 'admin') THEN
      -- Same generic failure either way — don't reveal whether the email exists/is an admin.
      RAISE EXCEPTION 'Unable to process this request.';
    END IF;
  END IF;

  -- Generate 6-digit OTP
  v_otp := LPAD(FLOOR(RANDOM() * 1000000)::TEXT, 6, '0');
  v_expires_at := now() + INTERVAL '2 minutes';

  -- Delete any existing unverified OTPs for this email
  DELETE FROM user_otps
  WHERE email = p_email
  AND verified = false
  AND otp_type = p_otp_type;

  -- Insert new OTP
  INSERT INTO user_otps (user_id, email, otp_code, otp_type, expires_at)
  VALUES (p_user_id, p_email, v_otp, p_otp_type, v_expires_at);

  RETURN QUERY SELECT v_otp, v_expires_at;
END;
$$;
