-- Add 'OPEN' value to trade_status enum to support active trades
ALTER TYPE trade_status ADD VALUE IF NOT EXISTS 'OPEN';