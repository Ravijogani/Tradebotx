import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

interface AIInsight {
  id: string;
  insight_type: string;
  title: string;
  description: string;
  confidence_score: number;
  data: any;
  status: string;
  created_at: string;
  expires_at?: string;
}

export const AIInsightsDashboard = () => {
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadInsights();
  }, []);

  const loadInsights = async () => {
    try {
      const { data, error } = await supabase
        .from('ai_insights')
        .select('*')
        .eq('status', 'active')
        .order('created_at', { ascending: false })
        .limit(50);

      if (error) throw error;
      setInsights(data || []);
    } catch (error: any) {
      console.error('Error loading insights:', error);
      toast({
        title: "Error",
        description: "Failed to load AI insights",
        variant: "destructive",
      });
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
    } catch (error: any) {
      console.error('Error generating insights:', error);
      toast({
        title: "Analysis Failed",
        description: error.message || "Failed to generate AI insights",
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
    } catch (error: any) {
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
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
            AI-Powered Insights
          </h1>
          <p className="text-muted-foreground">
            Advanced AI analysis for smarter trading decisions
          </p>
        </div>
        <Button
          onClick={() => loadInsights()}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Analysis Triggers */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-primary/20">
          <CardContent className="p-6">
            <Button
              onClick={() => generateInsights('trade_recommendation')}
              disabled={loading}
              className="w-full h-auto flex-col py-6 gap-3 bg-gradient-to-br from-primary to-primary/80"
            >
              {analyzing === 'trade_recommendation' ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <Target className="w-8 h-8" />
              )}
              <span className="text-sm font-medium">Trade Recommendations</span>
            </Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-accent/20">
          <CardContent className="p-6">
            <Button
              onClick={() => generateInsights('sentiment_analysis')}
              disabled={loading}
              className="w-full h-auto flex-col py-6 gap-3 bg-gradient-to-br from-accent to-accent/80"
            >
              {analyzing === 'sentiment_analysis' ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <Activity className="w-8 h-8" />
              )}
              <span className="text-sm font-medium">Sentiment Analysis</span>
            </Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-primary/20">
          <CardContent className="p-6">
            <Button
              onClick={() => generateInsights('predictive_analytics')}
              disabled={loading}
              className="w-full h-auto flex-col py-6 gap-3 bg-gradient-to-br from-primary to-accent"
            >
              {analyzing === 'predictive_analytics' ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <BarChart3 className="w-8 h-8" />
              )}
              <span className="text-sm font-medium">Predictive Analytics</span>
            </Button>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:shadow-lg transition-all duration-300 border-accent/20">
          <CardContent className="p-6">
            <Button
              onClick={() => generateInsights('strategy_optimization')}
              disabled={loading}
              className="w-full h-auto flex-col py-6 gap-3 bg-gradient-to-br from-accent to-primary"
            >
              {analyzing === 'strategy_optimization' ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <Sparkles className="w-8 h-8" />
              )}
              <span className="text-sm font-medium">Strategy Optimization</span>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Insights Display */}
      <Tabs defaultValue="all" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="all">All ({insights.length})</TabsTrigger>
          <TabsTrigger value="trade_recommendation">
            Trades ({filterInsights('trade_recommendation').length})
          </TabsTrigger>
          <TabsTrigger value="sentiment_analysis">
            Sentiment ({filterInsights('sentiment_analysis').length})
          </TabsTrigger>
          <TabsTrigger value="predictive_analytics">
            Predictions ({filterInsights('predictive_analytics').length})
          </TabsTrigger>
          <TabsTrigger value="strategy_optimization">
            Optimization ({filterInsights('strategy_optimization').length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="all" className="space-y-4 mt-6">
          {insights.length === 0 ? (
            <Card>
              <CardContent className="p-12 text-center">
                <Brain className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
                <p className="text-muted-foreground">
                  No AI insights yet. Click one of the buttons above to generate insights.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
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
          <TabsContent key={type} value={type} className="space-y-4 mt-6">
            {filterInsights(type).length === 0 ? (
              <Card>
                <CardContent className="p-12 text-center">
                  <Brain className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    No {type.replace('_', ' ')} insights yet.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4">
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
    </div>
  );
};

const InsightCard = ({ insight, getInsightIcon, getConfidenceColor, updateInsightStatus }: any) => (
  <Card className="hover:shadow-lg transition-all duration-300">
    <CardHeader>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            {getInsightIcon(insight.insight_type)}
          </div>
          <div>
            <CardTitle className="text-lg">{insight.title}</CardTitle>
            <CardDescription className="mt-1">{insight.description}</CardDescription>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={getConfidenceColor(insight.confidence_score)}>
            {Math.round(insight.confidence_score * 100)}% confidence
          </Badge>
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        {/* Display insight data based on type */}
        {insight.insight_type === 'trade_recommendation' && insight.data.entry && (
          <div className="grid grid-cols-3 gap-4 p-4 bg-muted/50 rounded-lg">
            <div>
              <p className="text-sm text-muted-foreground">Entry</p>
              <p className="font-semibold">{insight.data.entry}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Stop Loss</p>
              <p className="font-semibold text-destructive">{insight.data.stopLoss}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Take Profit</p>
              <p className="font-semibold text-success">{insight.data.takeProfit}</p>
            </div>
          </div>
        )}

        {insight.insight_type === 'sentiment_analysis' && insight.data.factors && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Key Factors:</p>
            <ul className="list-disc list-inside space-y-1">
              {insight.data.factors.map((factor: string, idx: number) => (
                <li key={idx} className="text-sm text-muted-foreground">{factor}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex items-center justify-between pt-4 border-t">
          <p className="text-xs text-muted-foreground">
            Generated {new Date(insight.created_at).toLocaleString()}
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => updateInsightStatus(insight.id, 'implemented')}
            >
              <CheckCircle className="w-4 h-4 mr-1" />
              Implemented
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => updateInsightStatus(insight.id, 'archived')}
            >
              <Archive className="w-4 h-4 mr-1" />
              Archive
            </Button>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
);