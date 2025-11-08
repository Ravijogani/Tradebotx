-- Drop the existing policy
DROP POLICY IF EXISTS "Users can view strategies for their plan" ON strategies;

-- Create new hierarchical access policy for strategies
CREATE POLICY "Users can view strategies based on plan hierarchy"
ON strategies
FOR SELECT
USING (
  is_active = true 
  AND EXISTS (
    SELECT 1
    FROM user_subscriptions us
    JOIN plans p ON us.plan_id = p.id
    WHERE us.user_id = auth.uid()
    AND (
      -- Free users see only free strategies
      (p.plan_type = 'free' AND strategies.plan_type = 'free')
      OR
      -- Pro users see free + pro strategies
      (p.plan_type = 'pro' AND strategies.plan_type IN ('free', 'pro'))
      OR
      -- Enterprise users see all strategies (free + pro + enterprise)
      (p.plan_type = 'enterprise')
    )
  )
);