-- Create equity snapshots table to track equity history
CREATE TABLE IF NOT EXISTS public.equity_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  equity NUMERIC NOT NULL,
  balance NUMERIC NOT NULL,
  snapshot_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create withdrawal milestones table
CREATE TABLE IF NOT EXISTS public.withdrawal_milestones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  milestone_type TEXT NOT NULL, -- '2x', '50_percent'
  trigger_equity NUMERIC NOT NULL,
  initial_equity NUMERIC NOT NULL,
  achieved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  notified BOOLEAN NOT NULL DEFAULT FALSE,
  safe_withdrawal_amount NUMERIC,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create symbol performance table for detailed analytics
CREATE TABLE IF NOT EXISTS public.symbol_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  total_trades INTEGER NOT NULL DEFAULT 0,
  winning_trades INTEGER NOT NULL DEFAULT 0,
  losing_trades INTEGER NOT NULL DEFAULT 0,
  total_pnl NUMERIC NOT NULL DEFAULT 0,
  win_rate NUMERIC NOT NULL DEFAULT 0,
  avg_win NUMERIC NOT NULL DEFAULT 0,
  avg_loss NUMERIC NOT NULL DEFAULT 0,
  best_trade NUMERIC NOT NULL DEFAULT 0,
  worst_trade NUMERIC NOT NULL DEFAULT 0,
  last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, symbol)
);

-- Enable RLS
ALTER TABLE public.equity_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.withdrawal_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.symbol_performance ENABLE ROW LEVEL SECURITY;

-- RLS Policies for equity_snapshots
CREATE POLICY "Users can view own equity snapshots"
  ON public.equity_snapshots FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert equity snapshots"
  ON public.equity_snapshots FOR INSERT
  WITH CHECK (true);

-- RLS Policies for withdrawal_milestones
CREATE POLICY "Users can view own withdrawal milestones"
  ON public.withdrawal_milestones FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage withdrawal milestones"
  ON public.withdrawal_milestones FOR ALL
  USING (true);

CREATE POLICY "Users can update own milestone notifications"
  ON public.withdrawal_milestones FOR UPDATE
  USING (auth.uid() = user_id);

-- RLS Policies for symbol_performance
CREATE POLICY "Users can view own symbol performance"
  ON public.symbol_performance FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage symbol performance"
  ON public.symbol_performance FOR ALL
  USING (true);

-- Create function to update symbol performance
CREATE OR REPLACE FUNCTION public.update_symbol_performance()
RETURNS TRIGGER AS $$
DECLARE
  v_total_trades INTEGER;
  v_winning_trades INTEGER;
  v_losing_trades INTEGER;
  v_total_pnl NUMERIC;
  v_win_rate NUMERIC;
  v_best_trade NUMERIC;
  v_worst_trade NUMERIC;
  v_avg_win NUMERIC;
  v_avg_loss NUMERIC;
BEGIN
  -- Calculate statistics for this symbol
  SELECT 
    COUNT(*),
    COUNT(*) FILTER (WHERE profit_loss > 0),
    COUNT(*) FILTER (WHERE profit_loss < 0),
    COALESCE(SUM(profit_loss), 0),
    COALESCE(MAX(profit_loss), 0),
    COALESCE(MIN(profit_loss), 0),
    COALESCE(AVG(profit_loss) FILTER (WHERE profit_loss > 0), 0),
    COALESCE(AVG(profit_loss) FILTER (WHERE profit_loss < 0), 0)
  INTO 
    v_total_trades,
    v_winning_trades,
    v_losing_trades,
    v_total_pnl,
    v_best_trade,
    v_worst_trade,
    v_avg_win,
    v_avg_loss
  FROM trades
  WHERE user_id = COALESCE(NEW.user_id, OLD.user_id)
    AND symbol = COALESCE(NEW.symbol, OLD.symbol)
    AND status = 'closed';

  -- Calculate win rate
  IF v_total_trades > 0 THEN
    v_win_rate := (v_winning_trades::NUMERIC / v_total_trades::NUMERIC) * 100;
  ELSE
    v_win_rate := 0;
  END IF;

  -- Insert or update symbol_performance
  INSERT INTO symbol_performance (
    user_id,
    symbol,
    total_trades,
    winning_trades,
    losing_trades,
    total_pnl,
    win_rate,
    best_trade,
    worst_trade,
    avg_win,
    avg_loss,
    last_updated
  ) VALUES (
    COALESCE(NEW.user_id, OLD.user_id),
    COALESCE(NEW.symbol, OLD.symbol),
    v_total_trades,
    v_winning_trades,
    v_losing_trades,
    v_total_pnl,
    v_win_rate,
    v_best_trade,
    v_worst_trade,
    v_avg_win,
    v_avg_loss,
    NOW()
  )
  ON CONFLICT (user_id, symbol)
  DO UPDATE SET
    total_trades = v_total_trades,
    winning_trades = v_winning_trades,
    losing_trades = v_losing_trades,
    total_pnl = v_total_pnl,
    win_rate = v_win_rate,
    best_trade = v_best_trade,
    worst_trade = v_worst_trade,
    avg_win = v_avg_win,
    avg_loss = v_avg_loss,
    last_updated = NOW();

  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

-- Create trigger for symbol performance updates
CREATE TRIGGER update_symbol_performance_trigger
  AFTER INSERT OR UPDATE OR DELETE ON trades
  FOR EACH ROW
  EXECUTE FUNCTION update_symbol_performance();

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_equity_snapshots_user_date ON public.equity_snapshots(user_id, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_withdrawal_milestones_user ON public.withdrawal_milestones(user_id, achieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_symbol_performance_user ON public.symbol_performance(user_id, total_pnl DESC);

-- Force trigger execution to populate symbol_performance with existing data
UPDATE trades 
SET metadata = metadata 
WHERE status = 'closed';