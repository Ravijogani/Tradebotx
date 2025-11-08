-- Create support tickets table
CREATE TABLE IF NOT EXISTS public.support_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  subject TEXT NOT NULL,
  description TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  priority TEXT NOT NULL DEFAULT 'medium',
  status TEXT NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create ticket messages table
CREATE TABLE IF NOT EXISTS public.ticket_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id UUID NOT NULL REFERENCES public.support_tickets(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  message TEXT NOT NULL,
  is_admin BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create user notifications table
CREATE TABLE IF NOT EXISTS public.user_notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'info',
  read BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create strategy performance tracking table
CREATE TABLE IF NOT EXISTS public.strategy_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID NOT NULL REFERENCES public.strategies(id) ON DELETE CASCADE,
  initial_balance NUMERIC NOT NULL,
  current_balance NUMERIC NOT NULL,
  total_trades INTEGER NOT NULL DEFAULT 0,
  winning_trades INTEGER NOT NULL DEFAULT 0,
  losing_trades INTEGER NOT NULL DEFAULT 0,
  total_profit_loss NUMERIC NOT NULL DEFAULT 0,
  win_rate NUMERIC NOT NULL DEFAULT 0,
  best_trade NUMERIC NOT NULL DEFAULT 0,
  worst_trade NUMERIC NOT NULL DEFAULT 0,
  avg_win NUMERIC NOT NULL DEFAULT 0,
  avg_loss NUMERIC NOT NULL DEFAULT 0,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_updated TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, strategy_id)
);

-- Enable RLS
ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ticket_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_performance ENABLE ROW LEVEL SECURITY;

-- RLS Policies for support_tickets
CREATE POLICY "Users can view own tickets"
  ON public.support_tickets FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create own tickets"
  ON public.support_tickets FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own tickets"
  ON public.support_tickets FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all tickets"
  ON public.support_tickets FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can update all tickets"
  ON public.support_tickets FOR UPDATE
  USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for ticket_messages
CREATE POLICY "Users can view messages for own tickets"
  ON public.ticket_messages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.support_tickets
      WHERE id = ticket_messages.ticket_id
      AND user_id = auth.uid()
    )
  );

CREATE POLICY "Users can create messages for own tickets"
  ON public.ticket_messages FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.support_tickets
      WHERE id = ticket_messages.ticket_id
      AND user_id = auth.uid()
    )
  );

CREATE POLICY "Admins can view all messages"
  ON public.ticket_messages FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can create all messages"
  ON public.ticket_messages FOR INSERT
  WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for user_notifications
CREATE POLICY "Users can view own notifications"
  ON public.user_notifications FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can update own notifications"
  ON public.user_notifications FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own notifications"
  ON public.user_notifications FOR DELETE
  USING (auth.uid() = user_id);

CREATE POLICY "System can insert notifications"
  ON public.user_notifications FOR INSERT
  WITH CHECK (true);

-- RLS Policies for strategy_performance
CREATE POLICY "Users can view own performance"
  ON public.strategy_performance FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "System can manage performance"
  ON public.strategy_performance FOR ALL
  USING (true);

CREATE POLICY "Admins can view all performance"
  ON public.strategy_performance FOR SELECT
  USING (has_role(auth.uid(), 'admin'::app_role));

-- Create indexes for better performance
CREATE INDEX idx_support_tickets_user_id ON public.support_tickets(user_id);
CREATE INDEX idx_support_tickets_status ON public.support_tickets(status);
CREATE INDEX idx_ticket_messages_ticket_id ON public.ticket_messages(ticket_id);
CREATE INDEX idx_user_notifications_user_id ON public.user_notifications(user_id);
CREATE INDEX idx_user_notifications_read ON public.user_notifications(read);
CREATE INDEX idx_strategy_performance_user_id ON public.strategy_performance(user_id);
CREATE INDEX idx_strategy_performance_strategy_id ON public.strategy_performance(strategy_id);

-- Enable realtime for notifications
ALTER PUBLICATION supabase_realtime ADD TABLE public.user_notifications;
ALTER PUBLICATION supabase_realtime ADD TABLE public.support_tickets;
ALTER PUBLICATION supabase_realtime ADD TABLE public.ticket_messages;

-- Function to create notification for bot start
CREATE OR REPLACE FUNCTION notify_bot_started()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.is_running = true AND (OLD IS NULL OR OLD.is_running = false) THEN
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
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to create notification for new trades
CREATE OR REPLACE FUNCTION notify_new_trade()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_notifications (user_id, title, message, type, metadata)
  VALUES (
    NEW.user_id,
    'New Trade Executed',
    'New ' || NEW.trade_type || ' trade on ' || NEW.symbol,
    'trade',
    jsonb_build_object('trade_id', NEW.id, 'symbol', NEW.symbol, 'type', NEW.trade_type)
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to create notification for closed trades
CREATE OR REPLACE FUNCTION notify_trade_closed()
RETURNS TRIGGER AS $$
DECLARE
  profit_or_loss TEXT;
BEGIN
  IF NEW.status = 'closed' AND (OLD.status IS NULL OR OLD.status != 'closed') THEN
    profit_or_loss := CASE 
      WHEN NEW.profit_loss > 0 THEN 'Profit: $' || NEW.profit_loss::TEXT
      ELSE 'Loss: $' || NEW.profit_loss::TEXT
    END;
    
    INSERT INTO public.user_notifications (user_id, title, message, type, metadata)
    VALUES (
      NEW.user_id,
      'Trade Closed',
      NEW.symbol || ' trade closed - ' || profit_or_loss,
      CASE WHEN NEW.profit_loss > 0 THEN 'success' ELSE 'warning' END,
      jsonb_build_object('trade_id', NEW.id, 'symbol', NEW.symbol, 'profit_loss', NEW.profit_loss)
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update strategy performance on trade close
CREATE OR REPLACE FUNCTION update_strategy_performance()
RETURNS TRIGGER AS $$
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
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create triggers
DROP TRIGGER IF EXISTS on_user_strategy_start ON public.user_strategies;
CREATE TRIGGER on_user_strategy_start
  AFTER INSERT OR UPDATE ON public.user_strategies
  FOR EACH ROW
  EXECUTE FUNCTION notify_bot_started();

DROP TRIGGER IF EXISTS on_new_trade ON public.trades;
CREATE TRIGGER on_new_trade
  AFTER INSERT ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION notify_new_trade();

DROP TRIGGER IF EXISTS on_trade_closed ON public.trades;
CREATE TRIGGER on_trade_closed
  AFTER UPDATE ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION notify_trade_closed();

DROP TRIGGER IF EXISTS on_trade_performance ON public.trades;
CREATE TRIGGER on_trade_performance
  AFTER UPDATE ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION update_strategy_performance();