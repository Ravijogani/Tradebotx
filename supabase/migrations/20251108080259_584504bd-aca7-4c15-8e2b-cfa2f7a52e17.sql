-- Add trial and subscription tracking fields to user_subscriptions
ALTER TABLE user_subscriptions 
ADD COLUMN IF NOT EXISTS account_balance NUMERIC DEFAULT 0,
ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'starter',
ADD COLUMN IF NOT EXISTS last_payment_date TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS payment_method TEXT;

-- Add account size to user_setup for risk calculator
ALTER TABLE user_setup
ADD COLUMN IF NOT EXISTS account_size NUMERIC DEFAULT 10000;

-- Add Telegram integration field
ALTER TABLE user_setup
ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT;

-- Create index for faster trial expiration queries
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_trial_ends 
ON user_subscriptions(trial_ends_at) 
WHERE trial_ends_at IS NOT NULL;

-- Create index for subscription status
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status 
ON user_subscriptions(status);

-- Update existing records to have starter tier if null
UPDATE user_subscriptions 
SET subscription_tier = 'starter' 
WHERE subscription_tier IS NULL;

COMMENT ON COLUMN user_subscriptions.account_balance IS 'Current account balance for trading';
COMMENT ON COLUMN user_subscriptions.subscription_tier IS 'Subscription tier: starter, pro, premium, enterprise';
COMMENT ON COLUMN user_setup.account_size IS 'Account size for risk calculator';
COMMENT ON COLUMN user_setup.telegram_chat_id IS 'Telegram chat ID for notifications';