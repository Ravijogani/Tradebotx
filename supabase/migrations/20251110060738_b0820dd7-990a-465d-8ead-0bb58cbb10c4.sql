-- Create bot_commands table for queue-based bot management
CREATE TABLE IF NOT EXISTS public.bot_commands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES public.strategies(id) ON DELETE CASCADE,
  action TEXT NOT NULL CHECK (action IN ('start', 'stop', 'restart')),
  config JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  error_message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  processed_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE
);

-- Enable RLS
ALTER TABLE public.bot_commands ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own commands
CREATE POLICY "Users can view own bot commands"
  ON public.bot_commands
  FOR SELECT
  USING (auth.uid() = user_id);

-- Policy: Users can insert their own commands
CREATE POLICY "Users can insert own bot commands"
  ON public.bot_commands
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Policy: Service role can update all commands (for bot manager)
CREATE POLICY "Service role can update all bot commands"
  ON public.bot_commands
  FOR UPDATE
  USING (true);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_bot_commands_user_status 
  ON public.bot_commands(user_id, status);

CREATE INDEX IF NOT EXISTS idx_bot_commands_status_created 
  ON public.bot_commands(status, created_at);

COMMENT ON TABLE public.bot_commands IS 'Queue for bot management commands when direct HTTP connection is not available';