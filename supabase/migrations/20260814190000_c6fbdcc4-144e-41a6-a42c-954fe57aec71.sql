-- trade_lessons: makes the bot's AI post-mortem on losing trades visible to
-- users. Previously, analyze_loss_with_ai()/save_ai_lesson() in
-- hybrid_trading_bot_multiuser.py wrote every lesson ONLY to a local JSON
-- file on the bot's own server (ai_trading_lessons.json) -- never queried by
-- anything user-facing. "The bot shows its own mistakes honestly" isn't a
-- real product differentiator if the only reader of that honesty is the bot
-- itself. This table is the destination trade_db.log_lesson() now writes to
-- alongside that local file (which is unchanged and still what
-- check_trade_against_lessons() reads back for its own advisory check).
--
-- Same ownership/security shape as trades: the Python bot authenticates
-- with the Supabase service role key (SUPABASE_SERVICE_KEY), which bypasses
-- RLS automatically, so no INSERT policy is needed or added here -- same
-- reasoning the most recent trades-table migration already tightened
-- (service role writes, users only ever read their own rows).
CREATE TABLE public.trade_lessons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  strategy_id UUID REFERENCES public.strategies(id),
  ticket BIGINT,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,
  lesson TEXT NOT NULL,
  loss_amount DECIMAL(20,8) NOT NULL,
  context JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.trade_lessons ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own trade lessons"
  ON public.trade_lessons FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Admins can view all trade lessons"
  ON public.trade_lessons FOR SELECT
  USING (public.has_role(auth.uid(), 'admin'));

CREATE INDEX idx_trade_lessons_user_id ON public.trade_lessons(user_id);
CREATE INDEX idx_trade_lessons_created_at ON public.trade_lessons(created_at DESC);

-- Live-update a "recent mistakes" dashboard feed without polling.
ALTER PUBLICATION supabase_realtime ADD TABLE public.trade_lessons;
