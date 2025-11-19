-- Fix SECURITY DEFINER functions missing search_path protection
-- This prevents schema hijacking attacks by ensuring functions only use the public schema

-- Fix notify_trial_expiring function
CREATE OR REPLACE FUNCTION public.notify_trial_expiring()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- This function can be called by a cron job to send trial expiry notifications
  -- For now it's a placeholder - notifications will be sent via edge function
  NULL;
END;
$$;

-- Fix notify_bot_started function
CREATE OR REPLACE FUNCTION public.notify_bot_started()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.is_running = true AND (OLD IS NULL OR OLD.is_running = false) THEN
    -- Check if notification already exists in last 5 minutes
    IF NOT EXISTS (
      SELECT 1 FROM public.user_notifications
      WHERE user_id = NEW.user_id
        AND type = 'success'
        AND title = 'Trading Bot Started'
        AND created_at > NOW() - INTERVAL '5 minutes'
        AND metadata->>'user_strategy_id' = NEW.id::text
    ) THEN
      INSERT INTO public.user_notifications (user_id, title, message, type, metadata)
      SELECT 
        NEW.user_id,
        'Trading Bot Started',
        'Your ' || s.name || ' bot is now running',
        'success',
        jsonb_build_object('strategy_id', NEW.strategy_id, 'user_strategy_id', NEW.id)
      FROM public.strategies s
      WHERE s.id = NEW.strategy_id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

-- Fix notify_new_trade function
CREATE OR REPLACE FUNCTION public.notify_new_trade()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Check if notification already exists for this trade
  IF NOT EXISTS (
    SELECT 1 FROM public.user_notifications
    WHERE user_id = NEW.user_id
      AND type = 'trade'
      AND metadata->>'trade_id' = NEW.id::text
  ) THEN
    INSERT INTO public.user_notifications (user_id, title, message, type, metadata)
    VALUES (
      NEW.user_id,
      'New Trade Executed',
      'New ' || NEW.trade_type || ' trade on ' || NEW.symbol,
      'trade',
      jsonb_build_object('trade_id', NEW.id, 'symbol', NEW.symbol, 'type', NEW.trade_type)
    );
  END IF;
  RETURN NEW;
END;
$$;

-- Fix notify_trade_closed function
CREATE OR REPLACE FUNCTION public.notify_trade_closed()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  profit_or_loss TEXT;
BEGIN
  IF NEW.status = 'closed' AND (OLD.status IS NULL OR OLD.status != 'closed') THEN
    profit_or_loss := CASE 
      WHEN NEW.profit_loss > 0 THEN 'Profit: $' || NEW.profit_loss::TEXT
      ELSE 'Loss: $' || NEW.profit_loss::TEXT
    END;
    
    -- Check if notification already exists for this trade close
    IF NOT EXISTS (
      SELECT 1 FROM public.user_notifications
      WHERE user_id = NEW.user_id
        AND type IN ('success', 'warning')
        AND title = 'Trade Closed'
        AND metadata->>'trade_id' = NEW.id::text
        AND metadata->>'event' = 'closed'
    ) THEN
      INSERT INTO public.user_notifications (user_id, title, message, type, metadata)
      VALUES (
        NEW.user_id,
        'Trade Closed',
        NEW.symbol || ' trade closed - ' || profit_or_loss,
        CASE WHEN NEW.profit_loss > 0 THEN 'success' ELSE 'warning' END,
        jsonb_build_object('trade_id', NEW.id, 'symbol', NEW.symbol, 'profit_loss', NEW.profit_loss, 'event', 'closed')
      );
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

-- Fix update_strategy_performance function
CREATE OR REPLACE FUNCTION public.update_strategy_performance()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  perf_record RECORD;
BEGIN
  IF NEW.status = 'closed' AND (OLD.status IS NULL OR OLD.status != 'closed') THEN
    -- Get or create performance record
    INSERT INTO public.strategy_performance (
      user_id, strategy_id, initial_balance, current_balance
    )
    SELECT 
      NEW.user_id, 
      NEW.strategy_id,
      COALESCE(us.account_size, 10000),
      COALESCE(us.account_size, 10000)
    FROM public.user_setup us
    WHERE us.user_id = NEW.user_id
    ON CONFLICT (user_id, strategy_id) DO NOTHING;
    
    -- Update performance metrics
    UPDATE public.strategy_performance
    SET
      total_trades = total_trades + 1,
      winning_trades = winning_trades + CASE WHEN NEW.profit_loss > 0 THEN 1 ELSE 0 END,
      losing_trades = losing_trades + CASE WHEN NEW.profit_loss <= 0 THEN 1 ELSE 0 END,
      total_profit_loss = total_profit_loss + NEW.profit_loss,
      current_balance = current_balance + NEW.profit_loss,
      best_trade = GREATEST(best_trade, NEW.profit_loss),
      worst_trade = LEAST(worst_trade, NEW.profit_loss),
      win_rate = CASE 
        WHEN total_trades + 1 > 0 
        THEN ((winning_trades + CASE WHEN NEW.profit_loss > 0 THEN 1 ELSE 0 END)::NUMERIC / (total_trades + 1)::NUMERIC * 100)
        ELSE 0 
      END,
      avg_win = CASE 
        WHEN winning_trades + CASE WHEN NEW.profit_loss > 0 THEN 1 ELSE 0 END > 0
        THEN (SELECT AVG(profit_loss) FROM trades WHERE user_id = NEW.user_id AND strategy_id = NEW.strategy_id AND status = 'closed' AND profit_loss > 0)
        ELSE 0
      END,
      avg_loss = CASE 
        WHEN losing_trades + CASE WHEN NEW.profit_loss <= 0 THEN 1 ELSE 0 END > 0
        THEN (SELECT AVG(profit_loss) FROM trades WHERE user_id = NEW.user_id AND strategy_id = NEW.strategy_id AND status = 'closed' AND profit_loss <= 0)
        ELSE 0
      END,
      last_updated = now()
    WHERE user_id = NEW.user_id AND strategy_id = NEW.strategy_id;
  END IF;
  RETURN NEW;
END;
$$;