-- Add unique constraint on ticket + user_id for trade upserts from Python scripts
ALTER TABLE public.trades ADD CONSTRAINT trades_ticket_user_id_unique UNIQUE (ticket, user_id);