-- Add balance and equity columns to bot_heartbeats table
ALTER TABLE bot_heartbeats
ADD COLUMN IF NOT EXISTS balance numeric DEFAULT 0,
ADD COLUMN IF NOT EXISTS equity numeric DEFAULT 0;