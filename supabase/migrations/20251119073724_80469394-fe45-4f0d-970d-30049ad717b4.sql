-- Allow public read access to bot_heartbeats for landing page equity curve
-- Only expose non-sensitive fields (equity, balance, last_heartbeat)
CREATE POLICY "Public can view heartbeat data for landing page"
ON public.bot_heartbeats
FOR SELECT
TO public
USING (true);