-- The Strategy Builder is meant to be an Enterprise-only feature, but the
-- RLS policy on custom_strategies only ever checked ownership (auth.uid() =
-- user_id) — any authenticated user could insert rows directly via the
-- Supabase client and use the paid feature for free. The React-side check in
-- StrategyBuilderPage was the only gate, which isn't enforcement.

CREATE OR REPLACE FUNCTION public.user_has_enterprise_plan(p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.user_subscriptions us
    JOIN public.plans p ON p.id = us.plan_id
    WHERE us.user_id = p_user_id
    AND p.plan_type = 'enterprise'
    AND us.status IN ('active', 'trial')
  )
$$;

DROP POLICY IF EXISTS "Users can manage their own custom strategies" ON public.custom_strategies;

-- Viewing/deleting your own strategies is fine even if you've since downgraded.
CREATE POLICY "Users can view their own custom strategies"
ON public.custom_strategies FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own custom strategies"
ON public.custom_strategies FOR DELETE
USING (auth.uid() = user_id);

-- Creating/editing strategies requires an active (or trialing) Enterprise plan.
CREATE POLICY "Enterprise users can create custom strategies"
ON public.custom_strategies FOR INSERT
WITH CHECK (auth.uid() = user_id AND public.user_has_enterprise_plan(auth.uid()));

CREATE POLICY "Enterprise users can update their own custom strategies"
ON public.custom_strategies FOR UPDATE
USING (auth.uid() = user_id AND public.user_has_enterprise_plan(auth.uid()));
