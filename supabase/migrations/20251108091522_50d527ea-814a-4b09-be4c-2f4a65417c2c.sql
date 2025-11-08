-- Create storage bucket for trade screenshots
INSERT INTO storage.buckets (id, name, public)
VALUES ('trade-screenshots', 'trade-screenshots', false);

-- Create trade_notes table for trading journal
CREATE TABLE IF NOT EXISTS public.trade_notes (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  trade_id UUID NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  notes TEXT,
  tags TEXT[] DEFAULT '{}',
  screenshot_urls TEXT[] DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Enable RLS on trade_notes
ALTER TABLE public.trade_notes ENABLE ROW LEVEL SECURITY;

-- RLS policies for trade_notes
CREATE POLICY "Users can view their own trade notes"
  ON public.trade_notes
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own trade notes"
  ON public.trade_notes
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own trade notes"
  ON public.trade_notes
  FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own trade notes"
  ON public.trade_notes
  FOR DELETE
  USING (auth.uid() = user_id);

-- Create index for faster queries
CREATE INDEX idx_trade_notes_user_id ON public.trade_notes(user_id);
CREATE INDEX idx_trade_notes_trade_id ON public.trade_notes(trade_id);

-- Storage policies for trade screenshots
CREATE POLICY "Users can view their own screenshots"
  ON storage.objects
  FOR SELECT
  USING (bucket_id = 'trade-screenshots' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can upload their own screenshots"
  ON storage.objects
  FOR INSERT
  WITH CHECK (bucket_id = 'trade-screenshots' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can update their own screenshots"
  ON storage.objects
  FOR UPDATE
  USING (bucket_id = 'trade-screenshots' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can delete their own screenshots"
  ON storage.objects
  FOR DELETE
  USING (bucket_id = 'trade-screenshots' AND auth.uid()::text = (storage.foldername(name))[1]);

-- Trigger to update updated_at
CREATE TRIGGER update_trade_notes_updated_at
  BEFORE UPDATE ON public.trade_notes
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();