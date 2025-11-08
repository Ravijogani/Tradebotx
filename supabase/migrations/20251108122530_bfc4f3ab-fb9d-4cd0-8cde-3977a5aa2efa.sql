-- Add INSERT policy for bot_heartbeats (service role can bypass, but let's be explicit)
CREATE POLICY "Service role can insert heartbeats"
  ON public.bot_heartbeats
  FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Service role can update heartbeats"
  ON public.bot_heartbeats
  FOR UPDATE
  USING (true);

-- Add INSERT policy for bot_audit_logs
CREATE POLICY "Service role can insert audit logs"
  ON public.bot_audit_logs
  FOR INSERT
  WITH CHECK (true);