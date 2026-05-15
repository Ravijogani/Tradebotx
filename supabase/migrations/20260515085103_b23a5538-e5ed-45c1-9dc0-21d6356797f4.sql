
-- bot_heartbeats: drop public read
DROP POLICY IF EXISTS "Public can view heartbeat data for landing page" ON public.bot_heartbeats;

-- onboarding_emails: drop public ALL
DROP POLICY IF EXISTS "System can manage onboarding emails" ON public.onboarding_emails;

-- strategy_performance: drop public ALL
DROP POLICY IF EXISTS "System can manage performance" ON public.strategy_performance;

-- symbol_performance: drop public ALL
DROP POLICY IF EXISTS "Service role can manage symbol performance" ON public.symbol_performance;

-- withdrawal_milestones: drop public ALL + add owner SELECT
DROP POLICY IF EXISTS "Service role can manage withdrawal milestones" ON public.withdrawal_milestones;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='withdrawal_milestones' AND policyname='Users can view own milestones') THEN
    EXECUTE 'CREATE POLICY "Users can view own milestones" ON public.withdrawal_milestones FOR SELECT TO authenticated USING (auth.uid() = user_id)';
  END IF;
END $$;

-- bot_commands: drop public UPDATE
DROP POLICY IF EXISTS "Service role can update all bot commands" ON public.bot_commands;

-- user_otps: drop public INSERT
DROP POLICY IF EXISTS "Anyone can insert OTPs" ON public.user_otps;

-- bot_audit_logs: drop public INSERT
DROP POLICY IF EXISTS "Service role can insert audit logs" ON public.bot_audit_logs;

-- equity_snapshots: drop public INSERT
DROP POLICY IF EXISTS "Service role can insert equity snapshots" ON public.equity_snapshots;

-- advanced_audit_logs: drop public INSERT
DROP POLICY IF EXISTS "System can insert audit logs" ON public.advanced_audit_logs;

-- user_notifications: tighten INSERT to authenticated owner; triggers/service role bypass RLS
DROP POLICY IF EXISTS "System can insert notifications" ON public.user_notifications;
CREATE POLICY "Users can insert own notifications"
ON public.user_notifications
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);
