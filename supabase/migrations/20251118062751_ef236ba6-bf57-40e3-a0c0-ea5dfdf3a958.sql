-- Add unique constraint to bot_heartbeats table for upsert operations
ALTER TABLE bot_heartbeats
ADD CONSTRAINT bot_heartbeats_user_strategy_unique UNIQUE (user_id, strategy_id);