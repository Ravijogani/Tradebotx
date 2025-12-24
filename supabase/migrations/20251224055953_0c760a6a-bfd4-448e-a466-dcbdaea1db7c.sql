-- Add daily_trades column to bot_heartbeats table
ALTER TABLE public.bot_heartbeats 
ADD COLUMN IF NOT EXISTS daily_trades integer DEFAULT 0;