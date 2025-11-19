-- Add 'admin_login' to the allowed otp_type values
ALTER TABLE public.user_otps DROP CONSTRAINT IF EXISTS user_otps_otp_type_check;

ALTER TABLE public.user_otps 
ADD CONSTRAINT user_otps_otp_type_check 
CHECK (otp_type IN ('signup', 'login', 'admin_login', 'forgot-password'));