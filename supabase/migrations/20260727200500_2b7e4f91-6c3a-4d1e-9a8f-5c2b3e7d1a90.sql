-- SupportTicketsManagement's handleUpdateStatus() writes resolved_at/closed_at
-- when an admin marks a ticket resolved or closed, but those columns never
-- existed on support_tickets — the update payload was being sent with fields
-- that don't exist on the table, which fails against PostgREST. Adding them
-- rather than removing the (reasonable) intent to track those timestamps.
ALTER TABLE public.support_tickets
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;
