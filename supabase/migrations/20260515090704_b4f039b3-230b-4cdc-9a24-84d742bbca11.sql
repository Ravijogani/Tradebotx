
-- Replace the permissive ALL policy on user_setup with column-safe policies

DROP POLICY IF EXISTS "Users can manage their own setup" ON public.user_setup;

CREATE POLICY "Users can view their own setup"
ON public.user_setup
FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own setup"
ON public.user_setup
FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own setup"
ON public.user_setup
FOR DELETE
USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own setup"
ON public.user_setup
FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- Trigger to prevent non-admins from changing admin-only approval fields
CREATE OR REPLACE FUNCTION public.prevent_user_setup_self_approval()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Allow service role and admins to do anything
  IF auth.uid() IS NULL OR public.has_role(auth.uid(), 'admin'::app_role) THEN
    RETURN NEW;
  END IF;

  IF NEW.admin_approved IS DISTINCT FROM OLD.admin_approved
     OR NEW.approval_notes IS DISTINCT FROM OLD.approval_notes THEN
    RAISE EXCEPTION 'Only admins can modify approval fields';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_user_setup_self_approval ON public.user_setup;
CREATE TRIGGER trg_prevent_user_setup_self_approval
BEFORE UPDATE ON public.user_setup
FOR EACH ROW
EXECUTE FUNCTION public.prevent_user_setup_self_approval();
