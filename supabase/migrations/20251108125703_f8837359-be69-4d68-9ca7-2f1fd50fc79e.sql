-- Fix notification trigger order and add deduplication

-- Drop existing triggers to recreate them in correct order
DROP TRIGGER IF EXISTS notify_bot_started_trigger ON public.user_strategies;
DROP TRIGGER IF EXISTS notify_new_trade_trigger ON public.trades;
DROP TRIGGER IF EXISTS notify_trade_closed_trigger ON public.trades;

-- Recreate notify_bot_started function with deduplication
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

-- Recreate notify_new_trade function with deduplication
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

-- Recreate notify_trade_closed function with deduplication
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

-- Recreate triggers in correct order
CREATE TRIGGER notify_bot_started_trigger
  AFTER UPDATE ON public.user_strategies
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_bot_started();

CREATE TRIGGER notify_new_trade_trigger
  AFTER INSERT ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_new_trade();

CREATE TRIGGER notify_trade_closed_trigger
  AFTER UPDATE ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_trade_closed();

-- Add index for better notification query performance
CREATE INDEX IF NOT EXISTS idx_user_notifications_user_created 
  ON public.user_notifications(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_notifications_read 
  ON public.user_notifications(user_id, read) 
  WHERE read = false;