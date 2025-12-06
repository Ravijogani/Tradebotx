import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, TrendingUp, Activity, DollarSign, Users } from "lucide-react";
import { Sparkline } from "@/components/dashboard/Sparkline";

export const AdminAnalytics = () => {
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState({
    totalUsers: 0,
    activeUsers: 0,
    totalTrades: 0,
    totalProfitLoss: 0,
    userGrowth: [] as number[],
    tradeVolume: [] as number[],
  });
  const { toast } = useToast();

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      // Get user count
      const { count: totalUsers } = await supabase
        .from("profiles")
        .select("*", { count: "exact", head: true });

      // Get active subscriptions
      const { count: activeUsers } = await supabase
        .from("user_subscriptions")
        .select("*", { count: "exact", head: true })
        .eq("status", "active");

      // Get trade statistics
      const { data: trades } = await supabase
        .from("trades")
        .select("profit_loss, opened_at");

      const totalTrades = trades?.length || 0;
      const totalProfitLoss = trades?.reduce((sum, trade) => 
        sum + (Number(trade.profit_loss) || 0), 0) || 0;

      // Get real user growth data (last 7 days)
      const userGrowth: number[] = [];
      const tradeVolume: number[] = [];
      
      for (let i = 6; i >= 0; i--) {
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - i);
        startDate.setHours(0, 0, 0, 0);
        
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + 1);
        
        // Count users created on this day
        const { count: usersOnDay } = await supabase
          .from("profiles")
          .select("*", { count: "exact", head: true })
          .gte("created_at", startDate.toISOString())
          .lt("created_at", endDate.toISOString());
        
        userGrowth.push(usersOnDay || 0);
        
        // Count trades on this day
        const { count: tradesOnDay } = await supabase
          .from("trades")
          .select("*", { count: "exact", head: true })
          .gte("opened_at", startDate.toISOString())
          .lt("opened_at", endDate.toISOString());
        
        tradeVolume.push(tradesOnDay || 0);
      }

      setAnalytics({
        totalUsers: totalUsers || 0,
        activeUsers: activeUsers || 0,
        totalTrades,
        totalProfitLoss,
        userGrowth,
        tradeVolume,
      });
    } catch (error: any) {
      toast({
        title: "Error loading analytics",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Users
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="text-2xl font-bold">{analytics.totalUsers}</div>
              <Users className="w-4 h-4 text-muted-foreground" />
            </div>
            <Sparkline data={analytics.userGrowth} height={40} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Subscriptions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="text-2xl font-bold text-green-500">{analytics.activeUsers}</div>
              <TrendingUp className="w-4 h-4 text-green-500" />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {((analytics.activeUsers / analytics.totalUsers) * 100 || 0).toFixed(1)}% conversion rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Trades
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="text-2xl font-bold">{analytics.totalTrades}</div>
              <Activity className="w-4 h-4 text-muted-foreground" />
            </div>
            <Sparkline data={analytics.tradeVolume} height={40} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total P&L
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className={`text-2xl font-bold ${analytics.totalProfitLoss >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${analytics.totalProfitLoss.toFixed(2)}
              </div>
              <DollarSign className="w-4 h-4 text-muted-foreground" />
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              Across all users
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Platform Overview</CardTitle>
          <CardDescription>
            Key metrics and performance indicators
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <p className="font-medium">Average Trades per User</p>
                <p className="text-sm text-muted-foreground">
                  {(analytics.totalTrades / analytics.totalUsers || 0).toFixed(2)} trades
                </p>
              </div>
              <Activity className="w-8 h-8 text-primary" />
            </div>

            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <p className="font-medium">Active User Rate</p>
                <p className="text-sm text-muted-foreground">
                  {((analytics.activeUsers / analytics.totalUsers) * 100 || 0).toFixed(1)}%
                </p>
              </div>
              <Users className="w-8 h-8 text-green-500" />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
