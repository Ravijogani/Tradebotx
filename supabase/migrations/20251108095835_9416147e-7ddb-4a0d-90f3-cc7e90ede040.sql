-- Create storage bucket for Python strategy scripts
INSERT INTO storage.buckets (id, name, public) 
VALUES ('strategy-scripts', 'strategy-scripts', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for strategy scripts (admin only)
CREATE POLICY "Admins can upload strategy scripts"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'strategy-scripts' 
  AND (SELECT has_role(auth.uid(), 'admin'::app_role))
);

CREATE POLICY "Admins can view strategy scripts"
ON storage.objects
FOR SELECT
TO authenticated
USING (
  bucket_id = 'strategy-scripts' 
  AND (SELECT has_role(auth.uid(), 'admin'::app_role))
);

CREATE POLICY "Admins can update strategy scripts"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
  bucket_id = 'strategy-scripts' 
  AND (SELECT has_role(auth.uid(), 'admin'::app_role))
);

CREATE POLICY "Admins can delete strategy scripts"
ON storage.objects
FOR DELETE
TO authenticated
USING (
  bucket_id = 'strategy-scripts' 
  AND (SELECT has_role(auth.uid(), 'admin'::app_role))
);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_strategies_plan_type ON strategies(plan_type) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_user_strategies_user_id ON user_strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_user_strategies_running ON user_strategies(is_running) WHERE is_running = true;