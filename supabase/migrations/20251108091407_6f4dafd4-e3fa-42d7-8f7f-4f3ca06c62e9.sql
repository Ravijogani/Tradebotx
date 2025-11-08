-- Enable realtime for notification_log table
ALTER PUBLICATION supabase_realtime ADD TABLE public.notification_log;

-- Enable realtime for trades table
ALTER PUBLICATION supabase_realtime ADD TABLE public.trades;

-- Enable realtime for user_strategies table
ALTER PUBLICATION supabase_realtime ADD TABLE public.user_strategies;