-- Fix cleanup_expired_otps function search path
CREATE OR REPLACE FUNCTION public.cleanup_expired_otps()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
  DELETE FROM user_otps WHERE expires_at < now();
END;
$function$;
