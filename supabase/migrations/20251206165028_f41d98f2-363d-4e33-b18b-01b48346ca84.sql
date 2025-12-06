-- 1. Multi-Account Management for Enterprise users
CREATE TABLE IF NOT EXISTS public.user_mt5_accounts (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  account_name TEXT NOT NULL DEFAULT 'Primary Account',
  mt5_account TEXT NOT NULL,
  mt5_password TEXT,
  mt5_server TEXT NOT NULL,
  broker_name TEXT,
  account_size NUMERIC DEFAULT 10000,
  is_primary BOOLEAN DEFAULT false,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- 2. Custom Strategy Development - Strategy builder blocks
CREATE TABLE IF NOT EXISTS public.custom_strategies (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  strategy_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active BOOLEAN DEFAULT false,
  is_approved BOOLEAN DEFAULT false,
  approved_by UUID,
  approved_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- 3. Strategy builder blocks library (reusable components)
CREATE TABLE IF NOT EXISTS public.strategy_blocks (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  block_type TEXT NOT NULL, -- 'indicator', 'condition', 'action', 'filter'
  name TEXT NOT NULL,
  description TEXT,
  category TEXT, -- 'technical', 'price', 'volume', 'risk', 'time'
  config_schema JSONB NOT NULL DEFAULT '{}'::jsonb, -- JSON Schema for configuration
  default_config JSONB NOT NULL DEFAULT '{}'::jsonb,
  icon TEXT,
  is_premium BOOLEAN DEFAULT false,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- 4. Advanced Audit Logging
CREATE TABLE IF NOT EXISTS public.advanced_audit_logs (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  action_category TEXT NOT NULL, -- 'auth', 'trading', 'settings', 'bot', 'account'
  action_type TEXT NOT NULL,
  action_description TEXT NOT NULL,
  resource_type TEXT, -- 'strategy', 'trade', 'account', 'settings'
  resource_id UUID,
  old_values JSONB,
  new_values JSONB,
  ip_address TEXT,
  user_agent TEXT,
  session_id TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- 5. Weekly email report tracking
CREATE TABLE IF NOT EXISTS public.weekly_report_settings (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL UNIQUE,
  is_enabled BOOLEAN DEFAULT true,
  send_day TEXT DEFAULT 'monday', -- day to send report
  last_sent_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS on all new tables
ALTER TABLE public.user_mt5_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.custom_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.strategy_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.advanced_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weekly_report_settings ENABLE ROW LEVEL SECURITY;

-- RLS Policies for user_mt5_accounts
CREATE POLICY "Users can manage their own MT5 accounts"
ON public.user_mt5_accounts FOR ALL
USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all MT5 accounts"
ON public.user_mt5_accounts FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for custom_strategies
CREATE POLICY "Users can manage their own custom strategies"
ON public.custom_strategies FOR ALL
USING (auth.uid() = user_id);

CREATE POLICY "Admins can manage all custom strategies"
ON public.custom_strategies FOR ALL
USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for strategy_blocks (read-only for users)
CREATE POLICY "Everyone can view active strategy blocks"
ON public.strategy_blocks FOR SELECT
USING (is_active = true);

CREATE POLICY "Admins can manage strategy blocks"
ON public.strategy_blocks FOR ALL
USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for advanced_audit_logs
CREATE POLICY "Users can view their own audit logs"
ON public.advanced_audit_logs FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all audit logs"
ON public.advanced_audit_logs FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "System can insert audit logs"
ON public.advanced_audit_logs FOR INSERT
WITH CHECK (true);

-- RLS Policies for weekly_report_settings
CREATE POLICY "Users can manage their own report settings"
ON public.weekly_report_settings FOR ALL
USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all report settings"
ON public.weekly_report_settings FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Insert default strategy blocks for the visual builder
INSERT INTO public.strategy_blocks (block_type, name, description, category, config_schema, default_config, icon) VALUES
-- Indicators
('indicator', 'Moving Average', 'Simple or Exponential Moving Average', 'technical', 
  '{"properties":{"period":{"type":"number","minimum":1,"maximum":500},"type":{"type":"string","enum":["SMA","EMA"]},"source":{"type":"string","enum":["close","open","high","low"]}}}',
  '{"period":20,"type":"SMA","source":"close"}', 'TrendingUp'),
('indicator', 'RSI', 'Relative Strength Index', 'technical',
  '{"properties":{"period":{"type":"number","minimum":2,"maximum":100},"overbought":{"type":"number"},"oversold":{"type":"number"}}}',
  '{"period":14,"overbought":70,"oversold":30}', 'Activity'),
('indicator', 'MACD', 'Moving Average Convergence Divergence', 'technical',
  '{"properties":{"fast":{"type":"number"},"slow":{"type":"number"},"signal":{"type":"number"}}}',
  '{"fast":12,"slow":26,"signal":9}', 'BarChart'),
('indicator', 'Bollinger Bands', 'Volatility bands around moving average', 'technical',
  '{"properties":{"period":{"type":"number"},"stdDev":{"type":"number"}}}',
  '{"period":20,"stdDev":2}', 'AlignVerticalJustifyCenter'),
('indicator', 'ATR', 'Average True Range for volatility', 'technical',
  '{"properties":{"period":{"type":"number"}}}',
  '{"period":14}', 'ArrowUpDown'),

-- Conditions
('condition', 'Price Crossover', 'When price crosses above/below indicator', 'price',
  '{"properties":{"direction":{"type":"string","enum":["above","below"]},"indicator":{"type":"string"}}}',
  '{"direction":"above","indicator":""}', 'Crosshair'),
('condition', 'Indicator Value', 'When indicator reaches specific value', 'technical',
  '{"properties":{"operator":{"type":"string","enum":[">","<",">=","<=","=="]},"value":{"type":"number"}}}',
  '{"operator":">","value":0}', 'Target'),
('condition', 'Time Filter', 'Trade only during specific hours', 'time',
  '{"properties":{"startHour":{"type":"number"},"endHour":{"type":"number"},"timezone":{"type":"string"}}}',
  '{"startHour":9,"endHour":17,"timezone":"UTC"}', 'Clock'),
('condition', 'Candle Pattern', 'Detect candlestick patterns', 'price',
  '{"properties":{"pattern":{"type":"string","enum":["engulfing","doji","hammer","shooting_star"]}}}',
  '{"pattern":"engulfing"}', 'CandlestickChart'),

-- Actions
('action', 'Market Order', 'Execute market buy/sell', 'trading',
  '{"properties":{"side":{"type":"string","enum":["buy","sell"]},"lotSize":{"type":"number"}}}',
  '{"side":"buy","lotSize":0.01}', 'ShoppingCart'),
('action', 'Set Stop Loss', 'Set stop loss level', 'risk',
  '{"properties":{"type":{"type":"string","enum":["fixed","atr","percentage"]},"value":{"type":"number"}}}',
  '{"type":"percentage","value":2}', 'Shield'),
('action', 'Set Take Profit', 'Set take profit level', 'risk',
  '{"properties":{"type":{"type":"string","enum":["fixed","atr","percentage","rr_ratio"]},"value":{"type":"number"}}}',
  '{"type":"rr_ratio","value":2}', 'Target'),
('action', 'Close Position', 'Close current position', 'trading',
  '{"properties":{"percentage":{"type":"number","minimum":1,"maximum":100}}}',
  '{"percentage":100}', 'XCircle'),

-- Filters
('filter', 'Trend Filter', 'Only trade in direction of trend', 'technical',
  '{"properties":{"indicator":{"type":"string","enum":["MA","ADX"]},"period":{"type":"number"}}}',
  '{"indicator":"MA","period":200}', 'TrendingUp'),
('filter', 'Volatility Filter', 'Trade only in specific volatility', 'technical',
  '{"properties":{"minATR":{"type":"number"},"maxATR":{"type":"number"}}}',
  '{"minATR":0,"maxATR":100}', 'Activity');

-- Add triggers for updated_at
CREATE TRIGGER update_user_mt5_accounts_updated_at
BEFORE UPDATE ON public.user_mt5_accounts
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_custom_strategies_updated_at
BEFORE UPDATE ON public.custom_strategies
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_weekly_report_settings_updated_at
BEFORE UPDATE ON public.weekly_report_settings
FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Function to log advanced audit entries
CREATE OR REPLACE FUNCTION public.log_audit_action(
  p_user_id UUID,
  p_action_category TEXT,
  p_action_type TEXT,
  p_action_description TEXT,
  p_resource_type TEXT DEFAULT NULL,
  p_resource_id UUID DEFAULT NULL,
  p_old_values JSONB DEFAULT NULL,
  p_new_values JSONB DEFAULT NULL,
  p_ip_address TEXT DEFAULT NULL,
  p_user_agent TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_log_id UUID;
BEGIN
  INSERT INTO advanced_audit_logs (
    user_id, action_category, action_type, action_description,
    resource_type, resource_id, old_values, new_values,
    ip_address, user_agent
  ) VALUES (
    p_user_id, p_action_category, p_action_type, p_action_description,
    p_resource_type, p_resource_id, p_old_values, p_new_values,
    p_ip_address, p_user_agent
  ) RETURNING id INTO v_log_id;
  
  RETURN v_log_id;
END;
$$;