-- Prevent Razorpay payment replay: a given razorpay_payment_id must only ever
-- be recorded once in payment_history. verify-razorpay-payment now inserts a
-- row here before extending a subscription, and treats a unique-violation as
-- "already processed" instead of granting another 30 days.
CREATE UNIQUE INDEX IF NOT EXISTS payment_history_razorpay_payment_id_unique
  ON public.payment_history (razorpay_payment_id)
  WHERE razorpay_payment_id IS NOT NULL;

-- Same guard for one-off invoice payments (verify-invoice-payment already
-- checks invoice.status before updating, this is a schema-level backstop).
CREATE UNIQUE INDEX IF NOT EXISTS invoices_razorpay_payment_id_unique
  ON public.invoices (razorpay_payment_id)
  WHERE razorpay_payment_id IS NOT NULL;
