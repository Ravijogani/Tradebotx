-- trades.INSERT/UPDATE for `authenticated` was added as a "require ownership
-- for any client write" safety net, but no feature in the app actually
-- writes to trades from the client — trade sync is done exclusively by the
-- Python bot via the service-role key, which bypasses RLS regardless of
-- these policies. Leaving them in place only gives an authenticated user a
-- way to falsify their own profit_loss/exit_price directly via the Supabase
-- client, which would corrupt P&L reports, referral payouts, and admin
-- analytics. Read access for a user's own trades is untouched.
DROP POLICY IF EXISTS "Users can insert their own trades" ON public.trades;
DROP POLICY IF EXISTS "Users can update their own trades" ON public.trades;
