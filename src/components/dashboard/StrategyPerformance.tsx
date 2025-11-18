import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Target, DollarSign } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

interface PerformanceData {
  strategy_name: string;
  initial_balance: number;
  current_balance: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_profit_loss: number;
  win_rate: number;
  best_trade: number;
  worst_trade: number;
  avg_win: number;
  avg_loss: number;
}

export const StrategyPerformance = () => {
  const [performances, setPerformances] = useState<PerformanceData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPerformances();

    // Real-time subscription for live performance updates
    const channel = supabase
      .channel('strategy-performance')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'strategy_performance' },
        () => loadPerformances()
      )
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'trades' },
        () => loadPerformances()
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadPerformances = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Fetch performance data
      const { data, error } = await supabase
        .from("strategy_performance")
        .select(`
          *,
          strategies (name, id)
        `)
        .eq("user_id", user.id)
        .order("total_profit_loss", { ascending: false });

      if (error) throw error;

      // Get real-time balance from bot_heartbeats
      const { data: heartbeats } = await supabase
        .from("bot_heartbeats")
        .select("equity, balance, strategy_id")
        .eq("user_id", user.id);

      // Get open trades count
      const { data: openTrades } = await supabase
        .from("trades")
        .select("strategy_id")
        .eq("user_id", user.id)
        .eq("status", "open");

      const formatted = data?.map((p: any) => {
        // Find matching heartbeat for real-time balance
        const heartbeat = heartbeats?.find(h => h.strategy_id === p.strategy_id);
        const liveBalance = heartbeat?.equity || heartbeat?.balance || parseFloat(p.current_balance);
        
        // Count open trades for this strategy
        const openTradeCount = openTrades?.filter(t => t.strategy_id === p.strategy_id).length || 0;
        const totalTradesIncludingOpen = p.total_trades + openTradeCount;

        return {
          strategy_name: p.strategies?.name || "Unknown",
          initial_balance: parseFloat(p.initial_balance),
          current_balance: liveBalance, // Use real-time balance
          total_trades: totalTradesIncludingOpen, // Include open trades
          winning_trades: p.winning_trades,
          losing_trades: p.losing_trades,
          total_profit_loss: parseFloat(p.total_profit_loss) + (liveBalance - parseFloat(p.current_balance)), // Add unrealized P&L
          win_rate: parseFloat(p.win_rate),
          best_trade: parseFloat(p.best_trade),
          worst_trade: parseFloat(p.worst_trade),
          avg_win: parseFloat(p.avg_win),
          avg_loss: parseFloat(p.avg_loss),
        };
      }) || [];

      setPerformances(formatted);
    } catch (error) {
      console.error("Error loading performance:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-muted rounded w-1/3"></div>
            <div className="h-8 bg-muted rounded"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (performances.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Strategy Performance</CardTitle>
          <CardDescription>No strategy performance data yet</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            Start a trading bot to see detailed performance metrics
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm w-full min-w-0">
      <CardHeader className="p-3 sm:p-4 md:p-6">
        <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
          <Target className="w-4 h-4 sm:w-5 sm:w-5 text-primary" />
          Strategy Performance
        </CardTitle>
        <CardDescription className="text-xs sm:text-sm">
          Detailed performance metrics for each strategy
        </CardDescription>
      </CardHeader>
      <CardContent className="p-3 sm:p-4 md:p-6 pt-0 space-y-4 sm:space-y-6">
        {performances.map((perf, idx) => (
          <div key={idx} className="p-3 sm:p-4 md:p-6 border border-border/50 rounded-xl bg-gradient-to-br from-card to-card/50 hover:shadow-lg transition-all">
            <div className="flex items-center justify-between mb-3 sm:mb-4 flex-wrap gap-2">
              <h3 className="font-semibold text-sm sm:text-base md:text-lg">{perf.strategy_name}</h3>
              <Badge 
                variant={perf.total_profit_loss >= 0 ? "default" : "destructive"}
                className="text-xs sm:text-sm"
              >
                {perf.total_profit_loss >= 0 ? (
                  <TrendingUp className="w-3 h-3 mr-1" />
                ) : (
                  <TrendingDown className="w-3 h-3 mr-1" />
                )}
                ${Math.abs(perf.total_profit_loss).toFixed(2)}
              </Badge>
            </div>

            {/* Balance Progress */}
            <div className="mb-3 sm:mb-4">
              <div className="flex flex-col sm:flex-row justify-between text-xs sm:text-sm mb-2 gap-1">
                <span className="text-muted-foreground">Initial: ${perf.initial_balance.toLocaleString()}</span>
                <span className="font-semibold">Current: ${perf.current_balance.toLocaleString()}</span>
              </div>
              <Progress 
                value={Math.min((perf.current_balance / perf.initial_balance) * 100, 100)} 
                className="h-2"
              />
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 sm:gap-4">
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Total Trades</p>
                <p className="text-base sm:text-lg font-bold">{perf.total_trades}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Win Rate</p>
                <p className="text-base sm:text-lg font-bold text-green-500">{perf.win_rate.toFixed(1)}%</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Winning</p>
                <p className="text-base sm:text-lg font-bold text-green-500">{perf.winning_trades}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Losing</p>
                <p className="text-base sm:text-lg font-bold text-red-500">{perf.losing_trades}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Best Trade</p>
                <p className="text-base sm:text-lg font-bold text-green-500">${perf.best_trade.toFixed(2)}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Worst Trade</p>
                <p className="text-base sm:text-lg font-bold text-red-500">${perf.worst_trade.toFixed(2)}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Avg Win</p>
                <p className="text-base sm:text-lg font-bold text-green-500">${perf.avg_win.toFixed(2)}</p>
              </div>
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Avg Loss</p>
                <p className="text-base sm:text-lg font-bold text-red-500">${perf.avg_loss.toFixed(2)}</p>
              </div>
            </div>

            {/* ROI Calculation */}
            <div className="mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-border/50">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="text-xs sm:text-sm text-muted-foreground">Return on Investment</span>
                <span className={`text-base sm:text-lg font-bold ${
                  perf.total_profit_loss >= 0 ? 'text-green-500' : 'text-red-500'
                }`}>
                  {((perf.total_profit_loss / perf.initial_balance) * 100).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};