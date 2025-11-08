-- Create bot_heartbeats table for health monitoring
CREATE TABLE public.bot_heartbeats (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  last_heartbeat TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'running',
  mt5_connected BOOLEAN NOT NULL DEFAULT true,
  error_message TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create bot_audit_logs table for tracking bot actions
CREATE TABLE public.bot_audit_logs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
  action TEXT NOT NULL, -- 'start', 'stop', 'crash', 'restart'
  performed_by UUID REFERENCES auth.users(id), -- User who performed the action
  ip_address TEXT,
  user_agent TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE public.bot_heartbeats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bot_audit_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies for bot_heartbeats
CREATE POLICY "Users can view their own bot heartbeats"
  ON public.bot_heartbeats
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all bot heartbeats"
  ON public.bot_heartbeats
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for bot_audit_logs
CREATE POLICY "Users can view their own audit logs"
  ON public.bot_audit_logs
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all audit logs"
  ON public.bot_audit_logs
  FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Enable realtime for bot_heartbeats
ALTER PUBLICATION supabase_realtime ADD TABLE public.bot_heartbeats;

-- Enable realtime for user_strategies (if not already enabled)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables 
    WHERE pubname = 'supabase_realtime' 
    AND tablename = 'user_strategies'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.user_strategies;
  END IF;
END $$;

-- Create trigger to update updated_at on bot_heartbeats
CREATE TRIGGER update_bot_heartbeats_updated_at
  BEFORE UPDATE ON public.bot_heartbeats
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();