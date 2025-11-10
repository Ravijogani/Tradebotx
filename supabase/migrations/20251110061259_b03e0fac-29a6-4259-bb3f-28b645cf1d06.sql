-- Add status column to user_strategies to track bot lifecycle
ALTER TABLE public.user_strategies 
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'stopped' CHECK (status IN ('stopped', 'starting', 'running', 'stopping', 'crashed'));

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_user_strategies_status ON public.user_strategies(status);

-- Add bot_pid column to track actual Python process ID
ALTER TABLE public.user_strategies 
ADD COLUMN IF NOT EXISTS bot_pid INTEGER;

-- Update bot_heartbeats to ensure it has pid column
ALTER TABLE public.bot_heartbeats 
ADD COLUMN IF NOT EXISTS pid INTEGER;