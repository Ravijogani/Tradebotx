import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Sparkles, RefreshCw, TrendingUp, AlertTriangle, Users, DollarSign } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import ReactMarkdown from "react-markdown";

// Subset of the admin-ai-insights edge function's systemContext that this
// dashboard actually displays.
interface AdminMetrics {
  totalUsers: number;
  newUsersLast7Days: number;
  pendingApprovals: number;
  openTickets: number;
  totalRevenue: number;
  activeSubscriptions: number;
  winRate: number;
  totalTradePnL: number;
}

export const AIInsightsDashboard = () => {
  const [loading, setLoading] = useState(false);
  const [insights, setInsights] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchInsights = async () => {
    try {
      setLoading(true);
      console.log('Fetching AI insights...');

      const { data, error } = await supabase.functions.invoke('admin-ai-insights');

      if (error) throw error;

      console.log('AI insights received:', data);

      setInsights(data.insights);
      setMetrics(data.metrics);
      setLastUpdated(new Date(data.timestamp).toLocaleString());

      toast({
        title: "AI Insights Updated",
        description: "Fresh insights generated successfully",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('Error fetching insights:', error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Sparkles className="w-6 h-6 text-primary" />
              </div>
              <div>
                <CardTitle className="text-2xl">AI Admin Assistant</CardTitle>
                <CardDescription>
                  Intelligent insights and recommendations powered by AI
                </CardDescription>
              </div>
            </div>
            <Button 
              onClick={fetchInsights} 
              disabled={loading}
              className="gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  Generate Insights
                </>
              )}
            </Button>
          </div>
        </CardHeader>

        {metrics && (
          <CardContent className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-1">
                    <Users className="w-4 h-4" />
                    <span className="text-sm">Total Users</span>
                  </div>
                  <p className="text-2xl font-bold">{metrics.totalUsers}</p>
                  <p className="text-xs text-green-500">
                    +{metrics.newUsersLast7Days} last 7 days
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-1">
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-sm">Pending Actions</span>
                  </div>
                  <p className="text-2xl font-bold">{metrics.pendingApprovals}</p>
                  <p className="text-xs text-muted-foreground">
                    {metrics.openTickets} open tickets
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-1">
                    <DollarSign className="w-4 h-4" />
                    <span className="text-sm">Revenue</span>
                  </div>
                  <p className="text-2xl font-bold">${metrics.totalRevenue}</p>
                  <p className="text-xs text-muted-foreground">
                    {metrics.activeSubscriptions} active subs
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-1">
                    <TrendingUp className="w-4 h-4" />
                    <span className="text-sm">Win Rate</span>
                  </div>
                  <p className="text-2xl font-bold">{metrics.winRate}%</p>
                  <p className="text-xs text-muted-foreground">
                    PnL: ${metrics.totalTradePnL.toFixed(2)}
                  </p>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        )}
      </Card>

      {insights && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              AI-Generated Insights
            </CardTitle>
            {lastUpdated && (
              <CardDescription>Last updated: {lastUpdated}</CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <ReactMarkdown>{insights}</ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      )}

      {!insights && !loading && (
        <Alert>
          <Sparkles className="h-4 w-4" />
          <AlertDescription>
            Click "Generate Insights" to let AI analyze your system and provide actionable recommendations.
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};