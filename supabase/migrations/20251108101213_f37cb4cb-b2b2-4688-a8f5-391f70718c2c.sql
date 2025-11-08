-- Create invoices storage bucket
INSERT INTO storage.buckets (id, name, public)
VALUES ('invoices', 'invoices', true)
ON CONFLICT (id) DO NOTHING;

-- Create storage policies for invoices
CREATE POLICY "Admins can upload invoices"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'invoices' 
  AND EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);

CREATE POLICY "Admins can view all invoices"
ON storage.objects
FOR SELECT
TO authenticated
USING (
  bucket_id = 'invoices'
  AND EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);

CREATE POLICY "Admins can delete invoices"
ON storage.objects
FOR DELETE
TO authenticated
USING (
  bucket_id = 'invoices'
  AND EXISTS (
    SELECT 1 FROM public.user_roles
    WHERE user_id = auth.uid() AND role = 'admin'
  )
);

CREATE POLICY "Users can view their own invoices"
ON storage.objects
FOR SELECT
TO authenticated
USING (
  bucket_id = 'invoices'
  AND (storage.foldername(name))[1] = auth.uid()::text
);