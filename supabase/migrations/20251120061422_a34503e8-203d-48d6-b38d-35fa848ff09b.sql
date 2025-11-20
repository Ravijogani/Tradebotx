-- Fix search_path security warning for update_strategy_performance function
CREATE OR REPLACE FUNCTION update_strategy_performance()
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
  v_current_balance NUMERIC;
  v_initial_balance NUMERIC;
BEGIN
  -- Get initial balance from user_setup
  SELECT account_size INTO v_initial_balance
  FROM user_setup
  WHERE user_id = COALESCE(NEW.user_id, OLD.user_id)
  LIMIT 1;

  -- Calculate statistics from closed trades only
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
    AND strategy_id = COALESCE(NEW.strategy_id, OLD.strategy_id)
    AND status = 'closed';

  -- Calculate win rate
  IF v_total_trades > 0 THEN
    v_win_rate := (v_winning_trades::NUMERIC / v_total_trades::NUMERIC) * 100;
  ELSE
    v_win_rate := 0;
  END IF;

  -- Calculate current balance
  v_current_balance := COALESCE(v_initial_balance, 0) + v_total_pnl;

  -- Insert or update strategy_performance
  INSERT INTO strategy_performance (
    user_id,
    strategy_id,
    initial_balance,
    current_balance,
    total_trades,
    winning_trades,
    losing_trades,
    total_profit_loss,
    win_rate,
    best_trade,
    worst_trade,
    avg_win,
    avg_loss,
    last_updated
  ) VALUES (
    COALESCE(NEW.user_id, OLD.user_id),
    COALESCE(NEW.strategy_id, OLD.strategy_id),
    COALESCE(v_initial_balance, 0),
    v_current_balance,
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
  ON CONFLICT (user_id, strategy_id)
  DO UPDATE SET
    current_balance = v_current_balance,
    total_trades = v_total_trades,
    winning_trades = v_winning_trades,
    losing_trades = v_losing_trades,
    total_profit_loss = v_total_pnl,
    win_rate = v_win_rate,
    best_trade = v_best_trade,
    worst_trade = v_worst_trade,
    avg_win = v_avg_win,
    avg_loss = v_avg_loss,
    last_updated = NOW();

  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;