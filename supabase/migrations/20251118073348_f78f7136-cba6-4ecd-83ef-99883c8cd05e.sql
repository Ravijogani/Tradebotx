-- Add ticket column to trades table to store MT5 ticket IDs
ALTER TABLE public.trades
ADD COLUMN ticket bigint;