-- Create table to track onboarding email sequence
CREATE TABLE public.onboarding_emails (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL,
  email_sequence INTEGER NOT NULL DEFAULT 1,
  sent_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  email_type TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create unique constraint to prevent duplicate emails
CREATE UNIQUE INDEX idx_onboarding_emails_unique ON public.onboarding_emails(user_id, email_sequence);

-- Enable RLS
ALTER TABLE public.onboarding_emails ENABLE ROW LEVEL SECURITY;

-- Allow system to manage onboarding emails
CREATE POLICY "System can manage onboarding emails" 
ON public.onboarding_emails 
FOR ALL 
USING (true);

-- Allow admins to view all onboarding emails
CREATE POLICY "Admins can view all onboarding emails" 
ON public.onboarding_emails 
FOR SELECT 
USING (has_role(auth.uid(), 'admin'::app_role));