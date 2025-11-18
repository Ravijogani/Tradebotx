-- Add RLS policies to allow service role to insert and update trades
-- This enables the Python trading bot to record trades

-- Allow service role to INSERT trades
CREATE POLICY "Service role can insert trades"
ON trades
FOR INSERT
TO authenticated
WITH CHECK (true);

-- Allow service role to UPDATE trades (for closing positions)
CREATE POLICY "Service role can update trades"
ON trades
FOR UPDATE
TO authenticated
USING (true);