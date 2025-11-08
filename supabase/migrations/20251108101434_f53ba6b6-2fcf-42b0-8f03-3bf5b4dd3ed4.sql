-- Add Razorpay payment tracking to invoices
ALTER TABLE public.invoices 
ADD COLUMN IF NOT EXISTS razorpay_order_id TEXT,
ADD COLUMN IF NOT EXISTS razorpay_payment_id TEXT,
ADD COLUMN IF NOT EXISTS payment_verified_at TIMESTAMP WITH TIME ZONE;

-- Create index for payment tracking
CREATE INDEX IF NOT EXISTS idx_invoices_razorpay_order_id ON public.invoices(razorpay_order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_payment_status ON public.invoices(status) WHERE status IN ('awaiting_payment', 'paid');