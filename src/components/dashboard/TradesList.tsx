import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import type { Tables } from "@/integrations/supabase/types";

export const TradesList = () => {
  const [trades, setTrades] = useState<Tables<"trades">[]>([]);

  useEffect(() => {
    loadTrades();

    // Add realtime subscription for live updates
    const setupRealtime = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const channel = supabase
        .channel('trades-list-changes')
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'trades',
            filter: `user_id=eq.${user.id}`
          },
          () => loadTrades()
        )
        .subscribe();

      return () => {
        supabase.removeChannel(channel);
      };
    };

    const cleanup = setupRealtime();
    return () => {
      cleanup.then(fn => fn?.());
    };
  }, []);

  const loadTrades = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .eq("status", "closed")
      .order("closed_at", { ascending: false })
      .limit(10);

    setTrades(data || []);
  };

  return (
    <Card className="p-6 border-border/50 bg-card/50 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-semibold">Recent Trades</h3>
          <p className="text-sm text-muted-foreground mt-1">Your latest trading activity</p>
        </div>
      </div>
      
      {trades.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
            <ArrowUpRight className="w-8 h-8 text-muted-foreground" />
          </div>
          <p className="text-muted-foreground">
            No trades yet. Start a strategy to begin trading.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {trades.map((trade) => (
            <div
              key={trade.id}
              className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-muted/30 transition-all duration-200 group"
            >
              <div className="flex items-center gap-4">
                {trade.profit_loss && trade.profit_loss >= 0 ? (
                  <div className="w-11 h-11 rounded-xl bg-success/10 flex items-center justify-center group-hover:bg-success/20 transition-colors">
                    <ArrowUpRight className="w-5 h-5 text-success" />
                  </div>
                ) : (
                  <div className="w-11 h-11 rounded-xl bg-destructive/10 flex items-center justify-center group-hover:bg-destructive/20 transition-colors">
                    <ArrowDownRight className="w-5 h-5 text-destructive" />
                  </div>
                )}
                
                <div>
                  <div className="font-semibold text-foreground group-hover:text-primary transition-colors">
                    {trade.symbol}
                  </div>
                  <div className="text-sm text-muted-foreground flex items-center gap-2">
                    <span className="font-medium">{trade.trade_type}</span>
                    <span>•</span>
                    <span>{new Date(trade.opened_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>

              <div className="text-right flex items-center gap-3">
                {trade.profit_loss && (
                  <div
                    className={`text-lg font-bold ${
                      trade.profit_loss >= 0
                        ? "text-success"
                        : "text-destructive"
                    }`}
                  >
                    {trade.profit_loss >= 0 ? "+" : ""}
                    ${trade.profit_loss.toFixed(2)}
                  </div>
                )}
                <Badge 
                  variant={trade.status === "executed" ? "default" : "secondary"}
                  className="min-w-[80px] justify-center"
                >
                  {trade.status}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
