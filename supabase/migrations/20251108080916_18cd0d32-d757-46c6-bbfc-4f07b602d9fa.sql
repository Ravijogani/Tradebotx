-- Payment History Table
CREATE TABLE IF NOT EXISTS payment_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount NUMERIC NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  payment_method TEXT,
  payment_id TEXT,
  razorpay_payment_id TEXT,
  razorpay_order_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  plan_id UUID REFERENCES plans(id),
  invoice_url TEXT,
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Referral Codes Table
CREATE TABLE IF NOT EXISTS referral_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  code TEXT NOT NULL UNIQUE,
  total_referrals INTEGER DEFAULT 0,
  total_earnings NUMERIC DEFAULT 0,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Referral Transactions Table
CREATE TABLE IF NOT EXISTS referral_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  referrer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  referred_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  referral_code TEXT NOT NULL,
  reward_amount NUMERIC DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending',
  completed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Notification Log Table
CREATE TABLE IF NOT EXISTS notification_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  notification_type TEXT NOT NULL,
  channel TEXT NOT NULL,
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  status TEXT DEFAULT 'sent',
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE payment_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE referral_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE referral_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;

-- RLS Policies for payment_history
CREATE POLICY "Users can view own payment history"
ON payment_history FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all payments"
ON payment_history FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for referral_codes
CREATE POLICY "Users can view own referral code"
ON referral_codes FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Users can create own referral code"
ON referral_codes FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own referral code"
ON referral_codes FOR UPDATE
TO authenticated
USING (auth.uid() = user_id);

-- RLS Policies for referral_transactions
CREATE POLICY "Users can view own referral transactions"
ON referral_transactions FOR SELECT
TO authenticated
USING (auth.uid() = referrer_id OR auth.uid() = referred_user_id);

CREATE POLICY "Admins can view all referral transactions"
ON referral_transactions FOR SELECT
TO authenticated
USING (has_role(auth.uid(), 'admin'::app_role));

-- RLS Policies for notification_log
CREATE POLICY "Users can view own notifications"
ON notification_log FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_payment_history_user_id ON payment_history(user_id);
CREATE INDEX IF NOT EXISTS idx_payment_history_created_at ON payment_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_referral_codes_user_id ON referral_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);
CREATE INDEX IF NOT EXISTS idx_referral_transactions_referrer ON referral_transactions(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referral_transactions_referred ON referral_transactions(referred_user_id);
CREATE INDEX IF NOT EXISTS idx_notification_log_user_id ON notification_log(user_id);

-- Trigger for updated_at
CREATE TRIGGER update_payment_history_updated_at
BEFORE UPDATE ON payment_history
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_referral_codes_updated_at
BEFORE UPDATE ON referral_codes
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Function to generate unique referral code
CREATE OR REPLACE FUNCTION generate_referral_code(user_id_param UUID)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  new_code TEXT;
  code_exists BOOLEAN;
BEGIN
  LOOP
    -- Generate 8 character alphanumeric code
    new_code := upper(substring(md5(random()::text || user_id_param::text) from 1 for 8));
    
    -- Check if code exists
    SELECT EXISTS(SELECT 1 FROM referral_codes WHERE code = new_code) INTO code_exists;
    
    EXIT WHEN NOT code_exists;
  END LOOP;
  
  RETURN new_code;
END;
$$;

-- Function to handle referral signup
CREATE OR REPLACE FUNCTION process_referral_signup(referred_user_id_param UUID, referral_code_param TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  referrer_user_id UUID;
  reward_amount NUMERIC := 100; -- $100 reward per referral
BEGIN
  -- Get referrer user ID
  SELECT user_id INTO referrer_user_id
  FROM referral_codes
  WHERE code = referral_code_param AND is_active = true;
  
  IF referrer_user_id IS NULL THEN
    RETURN false;
  END IF;
  
  -- Don't allow self-referral
  IF referrer_user_id = referred_user_id_param THEN
    RETURN false;
  END IF;
  
  -- Create referral transaction
  INSERT INTO referral_transactions (referrer_id, referred_user_id, referral_code, reward_amount, status)
  VALUES (referrer_user_id, referred_user_id_param, referral_code_param, reward_amount, 'completed');
  
  -- Update referral code stats
  UPDATE referral_codes
  SET total_referrals = total_referrals + 1,
      total_earnings = total_earnings + reward_amount
  WHERE user_id = referrer_user_id;
  
  RETURN true;
END;
$$;

COMMENT ON TABLE payment_history IS 'Stores all payment transactions for users';
COMMENT ON TABLE referral_codes IS 'Unique referral codes for each user';
COMMENT ON TABLE referral_transactions IS 'Tracks referral rewards and transactions';
COMMENT ON TABLE notification_log IS 'Logs all notifications sent to users';