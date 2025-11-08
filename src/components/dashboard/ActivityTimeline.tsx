import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { 
  Activity, 
  TrendingUp, 
  TrendingDown, 
  Play, 
  Square, 
  CheckCircle,
  Clock
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ActivityItem {
  id: string;
  type: "trade" | "strategy" | "approval";
  title: string;
  description: string;
  timestamp: string;
  status?: "success" | "pending" | "error";
}

export const ActivityTimeline = () => {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivities();
    
    // Subscribe to real-time updates
    const tradesChannel = supabase
      .channel("activity-trades")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "trades",
        },
        () => {
          loadActivities();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(tradesChannel);
    };
  }, []);

  const loadActivities = async () => {
    setLoading(true);
    const items: ActivityItem[] = [];

    // Load recent trades
    const { data: trades } = await supabase
      .from("trades")
      .select("*")
      .order("opened_at", { ascending: false })
      .limit(5);

    if (trades) {
      trades.forEach((trade) => {
        const entryPrice = typeof trade.entry_price === 'string' 
          ? parseFloat(trade.entry_price) 
          : trade.entry_price;
        const profitLoss = typeof trade.profit_loss === 'string'
          ? parseFloat(trade.profit_loss)
          : (trade.profit_loss || 0);
          
        items.push({
          id: trade.id,
          type: "trade",
          title: `${trade.trade_type.toUpperCase()} ${trade.symbol}`,
          description: `${trade.status === "closed" ? "Closed" : "Opened"} at $${entryPrice.toFixed(2)}`,
          timestamp: trade.opened_at,
          status: trade.status === "closed" 
            ? (profitLoss >= 0 ? "success" : "error")
            : "pending",
        });
      });
    }

    // Load strategy changes
    const { data: strategies } = await supabase
      .from("user_strategies")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(5);

    if (strategies) {
      strategies.forEach((strategy) => {
        items.push({
          id: strategy.id,
          type: "strategy",
          title: strategy.is_running ? "Strategy Started" : "Strategy Stopped",
          description: `Trading strategy ${strategy.is_running ? "activated" : "deactivated"}`,
          timestamp: strategy.started_at || strategy.created_at,
          status: strategy.is_running ? "success" : undefined,
        });
      });
    }

    // Sort by timestamp
    items.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    setActivities(items.slice(0, 10));
    setLoading(false);
  };

  const getIcon = (type: string, status?: string) => {
    if (type === "trade") {
      if (status === "success") return <TrendingUp className="w-4 h-4 text-success" />;
      if (status === "error") return <TrendingDown className="w-4 h-4 text-destructive" />;
      return <Clock className="w-4 h-4 text-warning" />;
    }
    if (type === "strategy") {
      return status === "success" ? (
        <Play className="w-4 h-4 text-primary" />
      ) : (
        <Square className="w-4 h-4 text-muted-foreground" />
      );
    }
    return <CheckCircle className="w-4 h-4 text-success" />;
  };

  const getTimeAgo = (timestamp: string) => {
    const seconds = Math.floor((new Date().getTime() - new Date(timestamp).getTime()) / 1000);
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-accent" />
          Recent Activity
        </CardTitle>
        <CardDescription>Live feed of your trading actions</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-start gap-4 animate-pulse">
                  <div className="w-10 h-10 rounded-full bg-muted" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-muted rounded w-3/4" />
                    <div className="h-3 bg-muted rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : activities.length === 0 ? (
            <div className="text-center py-12">
              <Activity className="w-12 h-12 mx-auto mb-3 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground">No recent activity</p>
            </div>
          ) : (
            <div className="space-y-4">
              {activities.map((activity, index) => (
                <div key={activity.id} className="flex items-start gap-4 relative">
                  {index < activities.length - 1 && (
                    <div className="absolute left-5 top-10 bottom-0 w-px bg-border" />
                  )}
                  <div className="w-10 h-10 rounded-full bg-muted/50 flex items-center justify-center flex-shrink-0 relative z-10">
                    {getIcon(activity.type, activity.status)}
                  </div>
                  <div className="flex-1 space-y-1 pt-1">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium leading-none">{activity.title}</p>
                      <span className="text-xs text-muted-foreground">
                        {getTimeAgo(activity.timestamp)}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">{activity.description}</p>
                    {activity.status && (
                      <Badge
                        variant={
                          activity.status === "success"
                            ? "default"
                            : activity.status === "error"
                            ? "destructive"
                            : "secondary"
                        }
                        className="text-xs"
                      >
                        {activity.status}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};
