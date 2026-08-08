import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { 
  Brain, 
  TrendingUp, 
  BarChart3, 
  Sparkles, 
  Target,
  Activity,
  Loader2,
  CheckCircle,
  Archive,
  RefreshCw
} from "lucide-react";

// ai_insights.data is JSONB — this is the shape the AI analysis edge
// function writes per insight_type (trade_recommendation / sentiment_analysis).
interface InsightData {
  entry?: string;
  stopLoss?: string;
  takeProfit?: string;
  factors?: string[];
}

interface AIInsight {
  id: string;
  insight_type: string;
  title: string;
  description: string;
  confidence_score: number;
  data: InsightData;
  status: string;
  created_at: string;
  expires_at?: string;
}

export const AIInsightsDashboard = () => {
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadInsights();
  }, []);

  const loadInsights = async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('ai_insights')
        .select('*')
        .eq('status', 'active')
        .order('created_at', { ascending: false })
        .limit(50);

      if (error) throw error;
      // data is JSONB (Json in the generated types); its per-insight-type
      // shape is defined by the AI analysis edge function that writes it.
      setInsights((data || []) as AIInsight[]);
    } catch (error) {
      console.error('Error loading insights:', error);
      toast({
        title: "Error",
        description: "Failed to load AI insights",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const generateInsights = async (analysisType: string) => {
    setAnalyzing(analysisType);
    setLoading(true);

    try {
      const { data, error } = await supabase.functions.invoke('generate-ai-insights', {
        body: {
          analysisType,
          contextData: {}
        }
      });

      if (error) throw error;

      toast({
        title: "Analysis Complete",
        description: `Generated ${data.insights?.length || 0} new insights`,
      });

      await loadInsights();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('Error generating insights:', error);
      toast({
        title: "Analysis Failed",
        description: message || "Failed to generate AI insights",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      setAnalyzing(null);
    }
  };

  const updateInsightStatus = async (insightId: string, newStatus: string) => {
    try {
      const { error } = await supabase
        .from('ai_insights')
        .update({ status: newStatus })
        .eq('id', insightId);

      if (error) throw error;

      toast({
        title: "Updated",
        description: "Insight status updated successfully",
      });

      await loadInsights();
    } catch (error) {
      console.error('Error updating insight:', error);
      toast({
        title: "Error",
        description: "Failed to update insight status",
        variant: "destructive",
      });
    }
  };

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'trade_recommendation': return <Target className="w-5 h-5" />;
      case 'sentiment_analysis': return <Activity className="w-5 h-5" />;
      case 'predictive_analytics': return <BarChart3 className="w-5 h-5" />;
      case 'strategy_optimization': return <Sparkles className="w-5 h-5" />;
      default: return <Brain className="w-5 h-5" />;
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.8) return "text-success";
    if (score >= 0.6) return "text-warning";
    return "text-muted-foreground";
  };

  const filterInsights = (type: string) => {
    return insights.filter(i => i.insight_type === type);
  };

  return (
    <div className="space-y-4 sm:space-y-6 animate-fade-in overflow-x-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mb-1 sm:mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
            AI-Powered Insights
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Advanced AI analysis for smarter trading decisions
          </p>
        </div>
        <Button
          onClick={() => loadInsights()}
          variant="outline"
          size="sm"
          disabled={loading}
          className="self-start sm:self-auto"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Analysis Triggers */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-primary/20">
          <CardContent className="p-4 sm:p-6">
            <Button
              onClick={() => generateInsights('trade_recommendation')}
              disabled={loading || analyzing !== null}
              className="w-full h-auto flex-col py-4 sm:py-6 gap-2 sm:gap-3 bg-gradient-to-br from-primary to-primary/80"
            >
              {analyzing === 'trade_recommendation' ? (
                <Loader2 className="w-6 h-6 sm:w-8 sm:h-8 animate-spin" />
              ) : (
                <Target className="w-6 h-6 sm:w-8 sm:h-8" />
              )}
              <span className="text-xs sm:text-sm font-medium">Trade Recommendations</span>
            </Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-accent/20">
          <CardContent className="p-4 sm:p-6">
            <Button
              onClick={() => generateInsights('sentiment_analysis')}
              disabled={loading || analyzing !== null}
              className="w-full h-auto flex-col py-4 sm:py-6 gap-2 sm:gap-3 bg-gradient-to-br from-accent to-accent/80"
            >
              {analyzing === 'sentiment_analysis' ? (
                <Loader2 className="w-6 h-6 sm:w-8 sm:h-8 animate-spin" />
              ) : (
                <Activity className="w-6 h-6 sm:w-8 sm:h-8" />
              )}
              <span className="text-xs sm:text-sm font-medium">Sentiment Analysis</span>
            </Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-primary/20">
          <CardContent className="p-4 sm:p-6">
            <Button
              onClick={() => generateInsights('predictive_analytics')}
              disabled={loading || analyzing !== null}
              className="w-full h-auto flex-col py-4 sm:py-6 gap-2 sm:gap-3 bg-gradient-to-br from-primary to-accent"
            >
              {analyzing === 'predictive_analytics' ? (
                <Loader2 className="w-6 h-6 sm:w-8 sm:h-8 animate-spin" />
              ) : (
                <BarChart3 className="w-6 h-6 sm:w-8 sm:h-8" />
              )}
              <span className="text-xs sm:text-sm font-medium">Predictive Analytics</span>
            </Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-accent/20">
          <CardContent className="p-4 sm:p-6">
            <Button
              onClick={() => generateInsights('strategy_optimization')}
              disabled={loading || analyzing !== null}
              className="w-full h-auto flex-col py-4 sm:py-6 gap-2 sm:gap-3 bg-gradient-to-br from-accent to-primary"
            >
              {analyzing === 'strategy_optimization' ? (
                <Loader2 className="w-6 h-6 sm:w-8 sm:h-8 animate-spin" />
              ) : (
                <Sparkles className="w-6 h-6 sm:w-8 sm:h-8" />
              )}
              <span className="text-xs sm:text-sm font-medium">Strategy Optimization</span>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Insights Display */}
      {loading && insights.length === 0 ? (
        <LoadingSkeleton />
      ) : (
        <Tabs defaultValue="all" className="w-full">
          <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
            <TabsList className="inline-flex w-full sm:w-auto min-w-full sm:min-w-0 h-auto flex-nowrap sm:flex-wrap gap-1 p-1">
              <TabsTrigger value="all" className="flex-shrink-0 text-xs sm:text-sm px-2 sm:px-3 py-1.5">
                All ({insights.length})
              </TabsTrigger>
              <TabsTrigger value="trade_recommendation" className="flex-shrink-0 text-xs sm:text-sm px-2 sm:px-3 py-1.5 whitespace-nowrap">
                Trades ({filterInsights('trade_recommendation').length})
              </TabsTrigger>
              <TabsTrigger value="sentiment_analysis" className="flex-shrink-0 text-xs sm:text-sm px-2 sm:px-3 py-1.5 whitespace-nowrap">
                Sentiment ({filterInsights('sentiment_analysis').length})
              </TabsTrigger>
              <TabsTrigger value="predictive_analytics" className="flex-shrink-0 text-xs sm:text-sm px-2 sm:px-3 py-1.5 whitespace-nowrap">
                Predictions ({filterInsights('predictive_analytics').length})
              </TabsTrigger>
              <TabsTrigger value="strategy_optimization" className="flex-shrink-0 text-xs sm:text-sm px-2 sm:px-3 py-1.5 whitespace-nowrap">
                Optimization ({filterInsights('strategy_optimization').length})
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="all" className="space-y-3 sm:space-y-4 mt-4 sm:mt-6">
            {insights.length === 0 ? (
              <Card>
                <CardContent className="p-8 sm:p-12 text-center">
                  <Brain className="w-12 h-12 sm:w-16 sm:h-16 mx-auto mb-3 sm:mb-4 text-muted-foreground" />
                  <p className="text-sm sm:text-base text-muted-foreground">
                    No AI insights yet. Click one of the buttons above to generate insights.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-3 sm:gap-4">
                {insights.map((insight) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    getInsightIcon={getInsightIcon}
                    getConfidenceColor={getConfidenceColor}
                    updateInsightStatus={updateInsightStatus}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          {['trade_recommendation', 'sentiment_analysis', 'predictive_analytics', 'strategy_optimization'].map((type) => (
            <TabsContent key={type} value={type} className="space-y-3 sm:space-y-4 mt-4 sm:mt-6">
              {filterInsights(type).length === 0 ? (
                <Card>
                  <CardContent className="p-8 sm:p-12 text-center">
                    <Brain className="w-12 h-12 sm:w-16 sm:h-16 mx-auto mb-3 sm:mb-4 text-muted-foreground" />
                    <p className="text-sm sm:text-base text-muted-foreground">
                      No {type.replace('_', ' ')} insights yet.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-3 sm:gap-4">
                  {filterInsights(type).map((insight) => (
                    <InsightCard
                      key={insight.id}
                      insight={insight}
                      getInsightIcon={getInsightIcon}
                      getConfidenceColor={getConfidenceColor}
                      updateInsightStatus={updateInsightStatus}
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>
      )}
    </div>
  );
};

const LoadingSkeleton = () => (
  <div className="space-y-4">
    <div className="flex items-center justify-center py-8">
      <Loader2 className="w-8 h-8 animate-spin text-primary" />
    </div>
    <div className="grid gap-4">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardHeader>
            <div className="flex items-start gap-3">
              <Skeleton className="w-10 h-10 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-4 w-full" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
);

interface InsightCardProps {
  insight: AIInsight;
  getInsightIcon: (type: string) => JSX.Element;
  getConfidenceColor: (score: number) => string;
  updateInsightStatus: (insightId: string, newStatus: string) => void;
}

const InsightCard = ({ insight, getInsightIcon, getConfidenceColor, updateInsightStatus }: InsightCardProps) => (
  <Card className="hover:shadow-lg transition-all duration-300">
    <CardHeader className="p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex items-start gap-2 sm:gap-3 min-w-0 flex-1">
          <div className="p-2 rounded-lg bg-primary/10 flex-shrink-0">
            {getInsightIcon(insight.insight_type)}
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base sm:text-lg break-words">{insight.title}</CardTitle>
            <CardDescription className="mt-1 text-xs sm:text-sm break-words">{insight.description}</CardDescription>
          </div>
        </div>
        <Badge variant="outline" className={`${getConfidenceColor(insight.confidence_score)} flex-shrink-0 self-start text-xs`}>
          {Math.round(insight.confidence_score * 100)}%
        </Badge>
      </div>
    </CardHeader>
    <CardContent className="p-4 sm:p-6 pt-0">
      <div className="space-y-3 sm:space-y-4">
        {/* Display insight data based on type */}
        {insight.insight_type === 'trade_recommendation' && insight.data.entry && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 p-3 sm:p-4 bg-muted/50 rounded-lg">
            <div>
              <p className="text-xs sm:text-sm text-muted-foreground">Entry</p>
              <p className="text-sm sm:text-base font-semibold truncate">{insight.data.entry}</p>
            </div>
            <div>
              <p className="text-xs sm:text-sm text-muted-foreground">Stop Loss</p>
              <p className="text-sm sm:text-base font-semibold text-destructive truncate">{insight.data.stopLoss}</p>
            </div>
            <div>
              <p className="text-xs sm:text-sm text-muted-foreground">Take Profit</p>
              <p className="text-sm sm:text-base font-semibold text-success truncate">{insight.data.takeProfit}</p>
            </div>
          </div>
        )}

        {insight.insight_type === 'sentiment_analysis' && insight.data.factors && (
          <div className="space-y-2">
            <p className="text-xs sm:text-sm font-medium">Key Factors:</p>
            <ul className="list-disc list-inside space-y-1">
              {insight.data.factors.map((factor: string, idx: number) => (
                <li key={idx} className="text-xs sm:text-sm text-muted-foreground break-words">{factor}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-3 sm:pt-4 border-t">
          <p className="text-xs text-muted-foreground">
            Generated {new Date(insight.created_at).toLocaleString()}
          </p>
          <div className="flex gap-2 flex-wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() => updateInsightStatus(insight.id, 'implemented')}
              className="text-xs"
            >
              <CheckCircle className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
              Implemented
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => updateInsightStatus(insight.id, 'archived')}
              className="text-xs"
            >
              <Archive className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
              Archive
            </Button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
);