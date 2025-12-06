-- Add admin policies to manage user data

-- Admins can delete profiles
CREATE POLICY "Admins can delete profiles"
ON public.profiles
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can view all user_setup
CREATE POLICY "Admins can view all user_setup"
ON public.user_setup
FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can update all user_setup
CREATE POLICY "Admins can update all user_setup"
ON public.user_setup
FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can delete user_setup
CREATE POLICY "Admins can delete user_setup"
ON public.user_setup
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can manage user_subscriptions
CREATE POLICY "Admins can update user_subscriptions"
ON public.user_subscriptions
FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can delete user_subscriptions"
ON public.user_subscriptions
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can manage user_strategies
CREATE POLICY "Admins can view all user_strategies"
ON public.user_strategies
FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can update all user_strategies"
ON public.user_strategies
FOR UPDATE
USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can delete user_strategies"
ON public.user_strategies
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));

-- Admins can manage referral_codes
CREATE POLICY "Admins can view all referral_codes"
ON public.referral_codes
FOR SELECT
USING (has_role(auth.uid(), 'admin'::app_role));

CREATE POLICY "Admins can delete referral_codes"
ON public.referral_codes
FOR DELETE
USING (has_role(auth.uid(), 'admin'::app_role));