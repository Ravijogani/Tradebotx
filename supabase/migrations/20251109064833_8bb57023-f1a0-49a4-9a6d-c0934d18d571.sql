-- Create table for AI insights and recommendations
CREATE TABLE IF NOT EXISTS public.ai_insights (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  insight_type TEXT NOT NULL CHECK (insight_type IN ('trade_recommendation', 'sentiment_analysis', 'predictive_analytics', 'strategy_optimization')),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  confidence_score NUMERIC(3, 2) CHECK (confidence_score >= 0 AND confidence_score <= 1),
  data JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'implemented')),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
  expires_at TIMESTAMP WITH TIME ZONE,
  metadata JSONB DEFAULT '{}'
);

-- Create index for faster queries
CREATE INDEX idx_ai_insights_user_id ON public.ai_insights(user_id);
CREATE INDEX idx_ai_insights_type ON public.ai_insights(insight_type);
CREATE INDEX idx_ai_insights_created_at ON public.ai_insights(created_at DESC);
CREATE INDEX idx_ai_insights_status ON public.ai_insights(status);

-- Enable RLS
ALTER TABLE public.ai_insights ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own AI insights"
  ON public.ai_insights
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own AI insights"
  ON public.ai_insights
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own AI insights"
  ON public.ai_insights
  FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own AI insights"
  ON public.ai_insights
  FOR DELETE
  USING (auth.uid() = user_id);

-- Create table for AI analysis history
CREATE TABLE IF NOT EXISTS public.ai_analysis_history (
  id UUID NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  analysis_type TEXT NOT NULL,
  input_data JSONB NOT NULL,
  output_data JSONB NOT NULL,
  processing_time_ms INTEGER,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Create index
CREATE INDEX idx_ai_analysis_user_id ON public.ai_analysis_history(user_id);
CREATE INDEX idx_ai_analysis_created_at ON public.ai_analysis_history(created_at DESC);

-- Enable RLS
ALTER TABLE public.ai_analysis_history ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view their own analysis history"
  ON public.ai_analysis_history
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own analysis history"
  ON public.ai_analysis_history
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);