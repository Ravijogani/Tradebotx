ALTER TABLE public.trades REPLICA IDENTITY FULL;
ALTER TABLE public.user_strategies REPLICA IDENTITY FULL;
ALTER TABLE public.bot_heartbeats REPLICA IDENTITY FULL;
ALTER TABLE public.user_notifications REPLICA IDENTITY FULL;
ALTER TABLE public.strategy_performance REPLICA IDENTITY FULL;
ALTER TABLE public.withdrawal_milestones REPLICA IDENTITY FULL;
ALTER TABLE public.bot_audit_logs REPLICA IDENTITY FULL;
DO $$
BEGIN
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.strategy_performance; EXCEPTION WHEN duplicate_object THEN NULL; END;
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.withdrawal_milestones; EXCEPTION WHEN duplicate_object THEN NULL; END;
  BEGIN ALTER PUBLICATION supabase_realtime ADD TABLE public.bot_audit_logs; EXCEPTION WHEN duplicate_object THEN NULL; END;
END $$;