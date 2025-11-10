import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { TrendingUp, DollarSign, Activity, Target } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

export const StatsOverview = () => {
  const [stats, setStats] = useState({
    totalProfit: 0,
    activeTrades: 0,
    winRate: 0,
    totalTrades: 0,
  });

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    const { data: trades } = await supabase
      .from("trades")
      .select("*");

    if (trades) {
      const totalProfit = trades.reduce((sum, trade) => 
        sum + parseFloat(String(trade.profit_loss || 0)), 0
      );

      const activeTrades = trades.filter(t => t.status === "pending" || t.status === "executed").length;

      const closedTrades = trades.filter(t => t.status === "closed");
      const winningTrades = closedTrades.filter(t => parseFloat(String(t.profit_loss || 0)) > 0);
      const winRate = closedTrades.length > 0 
        ? (winningTrades.length / closedTrades.length) * 100 
        : 0;

      setStats({
        totalProfit,
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
      color: stats.totalProfit >= 0 ? "text-success" : "text-destructive",
    },
    {
      title: "Active Trades",
      value: stats.activeTrades,
      icon: Activity,
      color: "text-primary",
    },
    {
      title: "Win Rate",
      value: `${stats.winRate.toFixed(1)}%`,
      icon: Target,
      color: "text-accent",
    },
    {
      title: "Total Trades",
      value: stats.totalTrades,
      icon: TrendingUp,
      color: "text-foreground",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 lg:gap-6 w-full">
      {statCards.map((stat, idx) => (
        <Card 
          key={idx} 
          className="p-4 sm:p-6 border-border/50 bg-card/50 backdrop-blur-sm hover:shadow-lg transition-all duration-300 group min-w-0"
        >
          <div className="flex items-start justify-between mb-4">
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br from-${stat.color.replace('text-', '')}/20 to-${stat.color.replace('text-', '')}/5 flex items-center justify-center group-hover:scale-110 transition-transform`}>
              <stat.icon className={`w-6 h-6 ${stat.color}`} />
            </div>
          </div>
          <div className="min-w-0">
            <p className="text-xs sm:text-sm text-muted-foreground mb-1 sm:mb-2 font-medium truncate">{stat.title}</p>
            <p className={`text-2xl sm:text-3xl font-bold ${stat.color} tracking-tight break-all`}>{stat.value}</p>
          </div>
        </Card>
      ))}
    </div>
  );
};
