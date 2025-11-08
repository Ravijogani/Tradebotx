-- Create table for storing OTPs
CREATE TABLE IF NOT EXISTS public.user_otps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  otp_code TEXT NOT NULL,
  otp_type TEXT NOT NULL CHECK (otp_type IN ('signup', 'login')),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  verified BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Enable RLS
ALTER TABLE public.user_otps ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own OTPs
CREATE POLICY "Users can view own OTPs"
ON public.user_otps
FOR SELECT
USING (email = (SELECT email FROM auth.users WHERE id = auth.uid()));

-- Policy: Anyone can insert OTPs (for signup before user exists)
CREATE POLICY "Anyone can insert OTPs"
ON public.user_otps
FOR INSERT
WITH CHECK (true);

-- Policy: Users can update their own OTPs
CREATE POLICY "Users can update own OTPs"
ON public.user_otps
FOR UPDATE
USING (email = (SELECT email FROM auth.users WHERE id = auth.uid()));

-- Add phone and referral code to profiles
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS phone TEXT,
ADD COLUMN IF NOT EXISTS referral_code TEXT;

-- Create index for faster OTP lookups
CREATE INDEX IF NOT EXISTS idx_user_otps_email ON public.user_otps(email);
CREATE INDEX IF NOT EXISTS idx_user_otps_expires_at ON public.user_otps(expires_at);

-- Function to clean up expired OTPs
CREATE OR REPLACE FUNCTION cleanup_expired_otps()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  DELETE FROM user_otps WHERE expires_at < now();
END;
$$;

-- Function to generate and store OTP
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
BEGIN
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

-- Function to verify OTP
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
BEGIN
  -- Check if OTP is valid
  SELECT EXISTS (
    SELECT 1 FROM user_otps
    WHERE email = p_email
    AND otp_code = p_otp_code
    AND otp_type = p_otp_type
    AND verified = false
    AND expires_at > now()
  ) INTO v_valid;
  
  -- If valid, mark as verified
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