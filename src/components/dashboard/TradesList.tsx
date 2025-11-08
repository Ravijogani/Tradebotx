import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

export const TradesList = () => {
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => {
    loadTrades();
  }, []);

  const loadTrades = async () => {
    const { data } = await supabase
      .from("trades")
      .select("*")
      .order("opened_at", { ascending: false })
      .limit(10);

    setTrades(data || []);
  };

  return (
    <Card className="p-6">
      <h3 className="text-xl font-semibold mb-4">Recent Trades</h3>
      
      {trades.length === 0 ? (
        <p className="text-muted-foreground text-center py-8">
          No trades yet. Start a strategy to begin trading.
        </p>
      ) : (
        <div className="space-y-3">
          {trades.map((trade) => (
            <div
              key={trade.id}
              className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-4">
                {trade.profit_loss && parseFloat(trade.profit_loss) >= 0 ? (
                  <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
                    <ArrowUpRight className="w-5 h-5 text-success" />
                  </div>
                ) : (
                  <div className="w-10 h-10 rounded-full bg-destructive/10 flex items-center justify-center">
                    <ArrowDownRight className="w-5 h-5 text-destructive" />
                  </div>
                )}
                
                <div>
                  <div className="font-semibold">{trade.symbol}</div>
                  <div className="text-sm text-muted-foreground">
                    {trade.trade_type} • {new Date(trade.opened_at).toLocaleDateString()}
                  </div>
                </div>
              </div>

              <div className="text-right">
                {trade.profit_loss && (
                  <div
                    className={`text-lg font-bold ${
                      parseFloat(trade.profit_loss) >= 0
                        ? "text-success"
                        : "text-destructive"
                    }`}
                  >
                    {parseFloat(trade.profit_loss) >= 0 ? "+" : ""}
                    ${parseFloat(trade.profit_loss).toFixed(2)}
                  </div>
                )}
                <Badge variant={trade.status === "executed" ? "default" : "secondary"}>
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
