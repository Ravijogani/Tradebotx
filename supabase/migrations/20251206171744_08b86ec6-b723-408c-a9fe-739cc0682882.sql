-- Drop existing admin policy first then recreate
DROP POLICY IF EXISTS "Admins can view all invoices" ON storage.objects;

-- Add proper RLS policies for invoices bucket - Admins can view all invoices
CREATE POLICY "Admins can view all invoices"
ON storage.objects FOR SELECT
USING (
  bucket_id = 'invoices' AND 
  EXISTS (SELECT 1 FROM user_roles WHERE user_id = auth.uid() AND role = 'admin')
);