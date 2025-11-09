-- Enable RLS on rate_limit_log table
ALTER TABLE public.rate_limit_log ENABLE ROW LEVEL SECURITY;

-- Add policy to prevent direct user access (service role only)
-- This table should only be accessed through the check_rate_limit function
CREATE POLICY "Rate limit log is system managed"
ON public.rate_limit_log
FOR ALL
USING (false)
WITH CHECK (false);

-- Grant necessary permissions to authenticated users to call the function
-- The function itself uses SECURITY DEFINER so it can access the table
GRANT EXECUTE ON FUNCTION public.check_rate_limit(TEXT, INTEGER, INTEGER) TO authenticated;