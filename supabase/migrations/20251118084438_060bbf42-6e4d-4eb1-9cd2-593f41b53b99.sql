-- Add lowercase 'open' to trade_status enum if not exists
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_enum 
    WHERE enumlabel = 'open' 
    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'trade_status')
  ) THEN
    ALTER TYPE trade_status ADD VALUE 'open';
  END IF;
END $$;