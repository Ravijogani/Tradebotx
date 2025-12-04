import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { TrendingUp, DollarSign, Activity, Target } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

export const StatsOverview = () => {
  const [stats, setStats] = useState({
    totalProfit: 0,
    todayPL: 0,
    activeTrades: 0,
    winRate: 0,
    totalTrades: 0,
  });

  useEffect(() => {
    loadStats();

    // Realtime subscription with debounce to prevent excessive reloads
    let debounceTimer: NodeJS.Timeout;
    
    const setupRealtime = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const channel = supabase
        .channel('stats-overview')
        .on(
          'postgres_changes',
          { event: '*', schema: 'public', table: 'trades' },
          async (payload) => {
            // Only reload if this trade belongs to the current user
            const tradeUserId = (payload.new as any)?.user_id || (payload.old as any)?.user_id;
            if (tradeUserId === user.id) {
              // Debounce stats reload to once every 2 seconds
              clearTimeout(debounceTimer);
              debounceTimer = setTimeout(() => loadStats(), 2000);
            }
          }
        )
        .subscribe();

      return () => {
        clearTimeout(debounceTimer);
        supabase.removeChannel(channel);
      };
    };

    const cleanup = setupRealtime();

    return () => {
      cleanup.then(fn => fn?.());
    };
  }, []);

  const loadStats = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data: trades } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id);

    if (trades) {
      // Calculate total P&L including running profit for open trades
      const totalProfit = trades.reduce((sum, trade) => {
        if (trade.status === 'open') {
          // Use running_profit from metadata for open trades
          const metadata = typeof trade.metadata === 'object' && trade.metadata !== null ? trade.metadata as any : {};
          const runningProfit = metadata.running_profit || 0;
          return sum + parseFloat(String(runningProfit));
        }
        return sum + parseFloat(String(trade.profit_loss || 0));
      }, 0);

      // Calculate today's P&L
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const todayTrades = trades.filter(t => new Date(t.opened_at) >= today);
      const todayPL = todayTrades.reduce((sum, trade) => {
        if (trade.status === 'open') {
          const metadata = typeof trade.metadata === 'object' && trade.metadata !== null ? trade.metadata as any : {};
          return sum + (metadata.running_profit || 0);
        }
        return sum + parseFloat(String(trade.profit_loss || 0));
      }, 0);

      // Count open trades correctly (status = 'open' or 'OPEN')
      const activeTrades = trades.filter(t => 
        t.status?.toLowerCase() === "open"
      ).length;

      // Calculate win rate from closed trades
      const closedTrades = trades.filter(t => t.status === "closed");
      const winningTrades = closedTrades.filter(t => parseFloat(String(t.profit_loss || 0)) > 0);
      const winRate = closedTrades.length > 0 
        ? (winningTrades.length / closedTrades.length) * 100 
        : 0;

      setStats({
        totalProfit,
        todayPL,
        activeTrades,
        winRate,
        totalTrades: trades.length,
      });
    }
  };

  const statCards = [
    {
      title: "Total Profit/Loss",
      value: `$${stats.totalProfit.toFixed(2)}`,
      icon: DollarSign,
      trend: stats.totalProfit >= 0 ? "up" : "down",
      colorClass: stats.totalProfit >= 0 ? "text-success" : "text-destructive",
      bgClass: stats.totalProfit >= 0 ? "bg-success/20" : "bg-destructive/20",
    },
    {
      title: "Today's P&L",
      value: `$${stats.todayPL.toFixed(2)}`,
      icon: TrendingUp,
      trend: stats.todayPL >= 0 ? "up" : "down",
      colorClass: stats.todayPL >= 0 ? "text-success" : "text-destructive",
      bgClass: stats.todayPL >= 0 ? "bg-success/20" : "bg-destructive/20",
    },
    {
      title: "Active Trades",
      value: stats.activeTrades,
      icon: Activity,
      colorClass: "text-primary",
      bgClass: "bg-primary/20",
    },
    {
      title: "Win Rate",
      value: `${stats.winRate.toFixed(1)}%`,
      icon: Target,
      colorClass: "text-accent",
      bgClass: "bg-accent/20",
    },
    {
      title: "Total Trades",
      value: stats.totalTrades,
      icon: TrendingUp,
      colorClass: "text-foreground",
      bgClass: "bg-muted",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 lg:gap-6 w-full">
      {statCards.map((stat, idx) => (
        <Card 
          key={idx} 
          className="p-4 sm:p-6 border-border/50 bg-card/50 backdrop-blur-sm hover:shadow-lg transition-all duration-300 group min-w-0"
        >
          <div className="flex items-start justify-between mb-4">
            <div className={`w-12 h-12 rounded-xl ${stat.bgClass} flex items-center justify-center group-hover:scale-110 transition-transform`}>
              <stat.icon className={`w-6 h-6 ${stat.colorClass}`} />
            </div>
          </div>
          <div className="min-w-0">
            <p className="text-xs sm:text-sm text-muted-foreground mb-1 sm:mb-2 font-medium truncate">{stat.title}</p>
            <p className={`text-2xl sm:text-3xl font-bold ${stat.colorClass} tracking-tight break-all`}>{stat.value}</p>
          </div>
        </Card>
      ))}
    </div>
  );
};
