
-- Tighten bot_heartbeats: service role bypasses RLS, no permissive public policies needed
DROP POLICY IF EXISTS "Service role can insert heartbeats" ON public.bot_heartbeats;
DROP POLICY IF EXISTS "Service role can update heartbeats" ON public.bot_heartbeats;

-- Tighten trades: service role bypasses RLS; require ownership for any client write
DROP POLICY IF EXISTS "Service role can insert trades" ON public.trades;
DROP POLICY IF EXISTS "Service role can update trades" ON public.trades;
CREATE POLICY "Users can insert their own trades"
  ON public.trades FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own trades"
  ON public.trades FOR UPDATE TO authenticated
  USING (auth.uid() = user_id);

-- user_roles: use has_role() and restrict to authenticated
DROP POLICY IF EXISTS "Only admins can assign roles" ON public.user_roles;
DROP POLICY IF EXISTS "Only admins can update roles" ON public.user_roles;
DROP POLICY IF EXISTS "Only admins can delete roles" ON public.user_roles;

CREATE POLICY "Only admins can assign roles"
  ON public.user_roles FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(), 'admin'::app_role));
CREATE POLICY "Only admins can update roles"
  ON public.user_roles FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'::app_role));
CREATE POLICY "Only admins can delete roles"
  ON public.user_roles FOR DELETE TO authenticated
  USING (public.has_role(auth.uid(), 'admin'::app_role));
