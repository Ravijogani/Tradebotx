
-- Create trigger to update strategy performance when trades are closed
CREATE TRIGGER update_strategy_performance_on_trade_close
  AFTER UPDATE ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION public.update_strategy_performance();

-- Recalculate strategy performance for existing closed trades
UPDATE public.strategy_performance sp
SET
  total_trades = (SELECT COUNT(*) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed'),
  winning_trades = (SELECT COUNT(*) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed' AND profit_loss > 0),
  losing_trades = (SELECT COUNT(*) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed' AND profit_loss <= 0),
  total_profit_loss = (SELECT COALESCE(SUM(profit_loss), 0) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed'),
  current_balance = initial_balance + (SELECT COALESCE(SUM(profit_loss), 0) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed'),
  win_rate = CASE 
    WHEN (SELECT COUNT(*) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed') > 0 
    THEN (SELECT COUNT(*) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed' AND profit_loss > 0)::NUMERIC / 
         (SELECT COUNT(*) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed')::NUMERIC * 100
    ELSE 0 
  END,
  avg_win = (SELECT COALESCE(AVG(profit_loss), 0) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed' AND profit_loss > 0),
  avg_loss = (SELECT COALESCE(AVG(profit_loss), 0) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed' AND profit_loss <= 0),
  best_trade = (SELECT COALESCE(MAX(profit_loss), 0) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed'),
  worst_trade = (SELECT COALESCE(MIN(profit_loss), 0) FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed'),
  last_updated = now()
WHERE EXISTS (SELECT 1 FROM trades WHERE user_id = sp.user_id AND strategy_id = sp.strategy_id AND status = 'closed');
