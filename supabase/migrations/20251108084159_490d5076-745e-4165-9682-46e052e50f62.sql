-- Add broker account and admin approval fields to user_setup
ALTER TABLE public.user_setup
ADD COLUMN broker_name text,
ADD COLUMN broker_account_id text,
ADD COLUMN broker_referral_code text,
ADD COLUMN admin_approved boolean DEFAULT false,
ADD COLUMN approval_notes text,
ADD COLUMN submitted_for_approval_at timestamp with time zone;

-- Create index for admin approval queries
CREATE INDEX idx_user_setup_admin_approved ON public.user_setup(admin_approved, submitted_for_approval_at);

COMMENT ON COLUMN public.user_setup.broker_name IS 'Broker name for free/starter plan users (XM, Vantage, PepperStone)';
COMMENT ON COLUMN public.user_setup.broker_account_id IS 'User broker account ID provided after registration';
COMMENT ON COLUMN public.user_setup.broker_referral_code IS 'IB referral code used for broker signup';
COMMENT ON COLUMN public.user_setup.admin_approved IS 'Admin approval status for account activation';
COMMENT ON COLUMN public.user_setup.approval_notes IS 'Admin notes for approval/rejection';
COMMENT ON COLUMN public.user_setup.submitted_for_approval_at IS 'Timestamp when setup was submitted for admin approval';