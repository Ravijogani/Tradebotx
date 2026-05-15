
UPDATE storage.buckets SET public = false WHERE id = 'invoices';

DROP POLICY IF EXISTS "Users can view own invoices" ON storage.objects;
DROP POLICY IF EXISTS "Admins can view all invoices files" ON storage.objects;

CREATE POLICY "Users can view own invoices"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'invoices'
  AND (auth.uid())::text = (storage.foldername(name))[1]
);

CREATE POLICY "Admins can view all invoices files"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'invoices' AND has_role(auth.uid(), 'admin'::app_role)
);
