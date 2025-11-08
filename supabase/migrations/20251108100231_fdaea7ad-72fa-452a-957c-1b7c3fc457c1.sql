-- Create email templates table
CREATE TABLE IF NOT EXISTS email_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  variables JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create invoices table
CREATE TABLE IF NOT EXISTS invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_number TEXT NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'draft',
  due_date TIMESTAMP WITH TIME ZONE,
  items JSONB NOT NULL DEFAULT '[]'::jsonb,
  notes TEXT,
  pdf_url TEXT,
  sent_at TIMESTAMP WITH TIME ZONE,
  paid_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create platform settings table
CREATE TABLE IF NOT EXISTS platform_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key TEXT NOT NULL UNIQUE,
  value JSONB NOT NULL,
  description TEXT,
  updated_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create user activity tracking table (enhanced)
CREATE TABLE IF NOT EXISTS user_activity_detailed (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  activity_type TEXT NOT NULL,
  activity_data JSONB DEFAULT '{}'::jsonb,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- RLS Policies for email_templates
ALTER TABLE email_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage email templates"
ON email_templates
FOR ALL
TO authenticated
USING (has_role(auth.uid(), 'admin'::app_role))
WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for invoices
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage all invoices"
ON invoices
FOR ALL
TO authenticated
USING (has_role(auth.uid(), 'admin'::app_role))
WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Users can view their own invoices"
ON invoices
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- RLS Policies for platform_settings
ALTER TABLE platform_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage platform settings"
ON platform_settings
FOR ALL
TO authenticated
USING (has_role(auth.uid(), 'admin'::app_role))
WITH CHECK (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for user_activity_detailed
ALTER TABLE user_activity_detailed ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view all user activity"
ON user_activity_detailed
FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Users can view their own activity"
ON user_activity_detailed
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Create function to get user performance metrics
CREATE OR REPLACE FUNCTION get_user_performance(p_user_id UUID)
RETURNS TABLE(
  total_trades BIGINT,
  winning_trades BIGINT,
  losing_trades BIGINT,
  total_pnl NUMERIC,
  win_rate NUMERIC,
  avg_profit NUMERIC,
  avg_loss NUMERIC,
  best_trade NUMERIC,
  worst_trade NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(*)::BIGINT as total_trades,
    COUNT(CASE WHEN profit_loss > 0 THEN 1 END)::BIGINT as winning_trades,
    COUNT(CASE WHEN profit_loss < 0 THEN 1 END)::BIGINT as losing_trades,
    COALESCE(SUM(profit_loss), 0) as total_pnl,
    CASE 
      WHEN COUNT(*) > 0 THEN (COUNT(CASE WHEN profit_loss > 0 THEN 1 END)::NUMERIC / COUNT(*)::NUMERIC * 100)
      ELSE 0 
    END as win_rate,
    COALESCE(AVG(CASE WHEN profit_loss > 0 THEN profit_loss END), 0) as avg_profit,
    COALESCE(AVG(CASE WHEN profit_loss < 0 THEN profit_loss END), 0) as avg_loss,
    COALESCE(MAX(profit_loss), 0) as best_trade,
    COALESCE(MIN(profit_loss), 0) as worst_trade
  FROM trades
  WHERE user_id = p_user_id AND status = 'closed';
END;
$$;

-- Create function to get platform PnL overview
CREATE OR REPLACE FUNCTION get_platform_pnl_overview()
RETURNS TABLE(
  total_users BIGINT,
  active_traders BIGINT,
  total_trades BIGINT,
  total_pnl NUMERIC,
  avg_pnl_per_user NUMERIC,
  profitable_users BIGINT,
  losing_users BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT
    COUNT(DISTINCT p.id)::BIGINT as total_users,
    COUNT(DISTINCT t.user_id)::BIGINT as active_traders,
    COUNT(t.id)::BIGINT as total_trades,
    COALESCE(SUM(t.profit_loss), 0) as total_pnl,
    CASE 
      WHEN COUNT(DISTINCT t.user_id) > 0 
      THEN COALESCE(SUM(t.profit_loss), 0) / COUNT(DISTINCT t.user_id)
      ELSE 0 
    END as avg_pnl_per_user,
    COUNT(DISTINCT CASE WHEN user_pnl.pnl > 0 THEN user_pnl.user_id END)::BIGINT as profitable_users,
    COUNT(DISTINCT CASE WHEN user_pnl.pnl < 0 THEN user_pnl.user_id END)::BIGINT as losing_users
  FROM profiles p
  LEFT JOIN trades t ON p.id = t.user_id AND t.status = 'closed'
  LEFT JOIN (
    SELECT user_id, SUM(profit_loss) as pnl
    FROM trades
    WHERE status = 'closed'
    GROUP BY user_id
  ) user_pnl ON p.id = user_pnl.user_id;
END;
$$;

-- Create function to get strategy performance
CREATE OR REPLACE FUNCTION get_strategy_performance()
RETURNS TABLE(
  strategy_id UUID,
  strategy_name TEXT,
  total_users BIGINT,
  active_users BIGINT,
  total_trades BIGINT,
  total_pnl NUMERIC,
  win_rate NUMERIC,
  avg_trade_pnl NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id as strategy_id,
    s.name as strategy_name,
    COUNT(DISTINCT us.user_id)::BIGINT as total_users,
    COUNT(DISTINCT CASE WHEN us.is_running THEN us.user_id END)::BIGINT as active_users,
    COUNT(t.id)::BIGINT as total_trades,
    COALESCE(SUM(t.profit_loss), 0) as total_pnl,
    CASE 
      WHEN COUNT(t.id) > 0 
      THEN (COUNT(CASE WHEN t.profit_loss > 0 THEN 1 END)::NUMERIC / COUNT(t.id)::NUMERIC * 100)
      ELSE 0 
    END as win_rate,
    CASE 
      WHEN COUNT(t.id) > 0 
      THEN COALESCE(SUM(t.profit_loss), 0) / COUNT(t.id)
      ELSE 0 
    END as avg_trade_pnl
  FROM strategies s
  LEFT JOIN user_strategies us ON s.id = us.strategy_id
  LEFT JOIN trades t ON us.user_id = t.user_id AND t.strategy_id = s.id AND t.status = 'closed'
  WHERE s.is_active = true
  GROUP BY s.id, s.name
  ORDER BY total_pnl DESC;
END;
$$;

-- Add triggers for updated_at
CREATE TRIGGER update_email_templates_updated_at
  BEFORE UPDATE ON email_templates
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoices_updated_at
  BEFORE UPDATE ON invoices
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_platform_settings_updated_at
  BEFORE UPDATE ON platform_settings
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_user_activity_detailed_user_id ON user_activity_detailed(user_id);
CREATE INDEX IF NOT EXISTS idx_user_activity_detailed_created_at ON user_activity_detailed(created_at DESC);