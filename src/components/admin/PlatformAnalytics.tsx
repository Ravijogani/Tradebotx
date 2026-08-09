import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Users, TrendingUp, DollarSign, Activity, Target, Award } from "lucide-react";
import type { Database } from "@/integrations/supabase/types";

type PlatformPnlOverview = Database["public"]["Functions"]["get_platform_pnl_overview"]["Returns"][number];
type StrategyPerformance = Database["public"]["Functions"]["get_strategy_performance"]["Returns"][number];

export const PlatformAnalytics = () => {
  const [loading, setLoading] = useState(true);
  const [platformData, setPlatformData] = useState<PlatformPnlOverview | null>(null);
  const [strategyData, setStrategyData] = useState<StrategyPerformance[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      // Load platform PnL overview
      const { data: pnlData, error: pnlError } = await supabase
        .rpc("get_platform_pnl_overview");

      if (!pnlError && pnlData && pnlData.length > 0) {
        setPlatformData(pnlData[0]);
      }

      // Load strategy performance
      const { data: stratData, error: stratError } = await supabase
        .rpc("get_strategy_performance");

      if (!stratError) {
        setStrategyData(stratData || []);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
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
      {/* Platform Overview */}
      <div>
        <h2 className="text-2xl font-bold mb-4">Platform PnL Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{platformData?.total_users || 0}</div>
              <p className="text-xs text-muted-foreground">
                {platformData?.active_traders || 0} active traders
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Trades</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{platformData?.total_trades || 0}</div>
              <p className="text-xs text-muted-foreground">
                Across all users
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Platform PnL</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${Number(platformData?.total_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${Number(platformData?.total_pnl || 0).toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground">
                Total profit/loss
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg PnL/User</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${Number(platformData?.avg_pnl_per_user || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${Number(platformData?.avg_pnl_per_user || 0).toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground">
                Per active trader
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Profitable Users</CardTitle>
              <Award className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">
                {platformData?.profitable_users || 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Users in profit
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Losing Users</CardTitle>
              <Target className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-500">
                {platformData?.losing_users || 0}
              </div>
              <p className="text-xs text-muted-foreground">
                Users in loss
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Strategy Performance */}
      <div>
        <h2 className="text-2xl font-bold mb-4">Strategy Performance</h2>
        <div className="grid grid-cols-1 gap-4">
          {strategyData.map((strategy) => (
            <Card key={strategy.strategy_id}>
              <CardHeader>
                <CardTitle>{strategy.strategy_name}</CardTitle>
                <CardDescription>
                  {strategy.total_users} total users • {strategy.active_users} active users
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Trades</p>
                    <p className="text-2xl font-bold">{strategy.total_trades}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Total PnL</p>
                    <p className={`text-2xl font-bold ${Number(strategy.total_pnl) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${Number(strategy.total_pnl).toFixed(2)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Win Rate</p>
                    <p className="text-2xl font-bold">{Number(strategy.win_rate).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Trade PnL</p>
                    <p className={`text-2xl font-bold ${Number(strategy.avg_trade_pnl) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${Number(strategy.avg_trade_pnl).toFixed(2)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          {strategyData.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No strategy performance data available yet
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
