import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { Tables } from "@/integrations/supabase/types";
import { useLiveData } from "@/hooks/useLiveData";

type Trade = Tables<"trades">;
// metadata is JSONB — this is the shape the bot writes into it for a live
// running position, asserted here since the DB type can't verify it.
interface TradeMetadata {
  running_profit?: number;
  profit?: number;
  current_price?: number;
}

export const OpenPositions = () => {
  const [positions, setPositions] = useState<Trade[]>([]);
  const [totalPnL, setTotalPnL] = useState(0);
  const { toast } = useToast();

  // Realtime when the socket is up, polling when it is not, and always a
  // refetch when the tab wakes. The old code subscribed and hoped; if the
  // channel never joined, this panel showed the positions you had at page
  // load and nothing else, with nothing to say so.
  const [userId, setUserId] = useState<string | null>(null);
  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUserId(data.user?.id ?? null));
  }, []);

  const live = useLiveData(loadPositions, {
    tables: ["trades"],
    userId,
    channel: "open-positions-realtime",
    // Running P&L moves every few seconds, so a stale panel is obvious and
    // annoying here in a way it is not elsewhere -- poll harder.
    healthyPollMs: 30_000,
    degradedPollMs: 5_000,
    enabled: !!userId,
  });

  async function loadPositions() {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data, error } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .in("status", ["open", "OPEN"])
      .order("opened_at", { ascending: false });

    if (error) {
      console.error('[OpenPositions] Error loading positions:', error);
      return;
    }

    // Announce genuinely new positions. This used to hang off the realtime
    // INSERT event, so it never fired when the socket was down -- and a
    // silently-opened position is exactly what you want to be told about.
    setPositions((prev) => {
      const seen = new Set(prev.map((p) => p.id));
      for (const row of data || []) {
        if (prev.length && !seen.has(row.id)) {
          toast({
            title: "New Position Opened",
            description: `${row.symbol} - ${row.trade_type}`,
          });
        }
      }
      return data || [];
    });
  }

  // Recalculate total P&L whenever positions change
  useEffect(() => {
    const total = positions.reduce((sum, pos) => {
      const metadata: TradeMetadata = typeof pos.metadata === 'object' && pos.metadata !== null ? pos.metadata as TradeMetadata : {};
      const runningProfit = metadata.running_profit || pos.profit_loss || 0;
      return sum + runningProfit;
    }, 0);
    setTotalPnL(total);
  }, [positions]);

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm w-full min-w-0">
      <CardHeader className="p-3 sm:p-4 md:p-6">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
                <Activity className="h-4 w-4 sm:h-5 sm:w-5" />
                Open Positions
              </CardTitle>
              <CardDescription className="mt-1 text-xs sm:text-sm">
                {positions.length} active {positions.length === 1 ? 'position' : 'positions'}
              </CardDescription>
            </div>
            <div className="text-right">
              <div className="flex items-center justify-end gap-1.5 text-xs text-muted-foreground">
                {/* Say which mode the panel is in. A dashboard that has quietly
                    stopped updating is worse than one that admits it. */}
                <span
                  aria-hidden
                  className={`inline-block h-1.5 w-1.5 rounded-full ${
                    live === "live" ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                />
                <span>{live === "live" ? "Live" : "Updating"}</span>
              </div>
              <div className="text-xs text-muted-foreground">Total P&L</div>
              <div className={`text-lg sm:text-2xl font-bold ${totalPnL >= 0 ? 'text-success' : 'text-destructive'}`}>
                {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-3 sm:p-4 md:p-6 pt-0">
        {positions.length === 0 ? (
          <div className="text-center py-8 sm:py-12">
            <div className="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-3 sm:mb-4">
              <Activity className="w-6 h-6 sm:w-8 sm:h-8 text-muted-foreground" />
            </div>
            <p className="text-sm sm:text-base text-muted-foreground">No open positions</p>
          </div>
        ) : (
          <div className="space-y-2 sm:space-y-3">
            {positions.map((position) => {
              const metadata: TradeMetadata = typeof position.metadata === 'object' && position.metadata !== null
                ? position.metadata as TradeMetadata
                : {};
              const currentProfit = metadata.running_profit || metadata.profit || position.profit_loss || 0;
              const currentPrice = metadata.current_price || position.entry_price;
              const hasLiveData = metadata.running_profit !== undefined || metadata.current_price !== undefined;
              
              return (
                <div
                  key={position.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4 p-3 sm:p-4 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/30 transition-all"
                >
                  <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
                    {currentProfit >= 0 ? (
                      <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-success/10 flex items-center justify-center flex-shrink-0">
                        <TrendingUp className="w-4 h-4 sm:w-5 sm:h-5 text-success" />
                      </div>
                    ) : (
                      <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-destructive/10 flex items-center justify-center flex-shrink-0">
                        <TrendingDown className="w-4 h-4 sm:w-5 sm:h-5 text-destructive" />
                      </div>
                    )}
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-semibold text-sm sm:text-base text-foreground">{position.symbol}</span>
                        <Badge variant={position.trade_type === 'BUY' ? 'default' : 'secondary'} className="text-xs">
                          {position.trade_type}
                        </Badge>
                        {!hasLiveData && (
                          <Badge variant="outline" className="text-xs">
                            Awaiting update
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs sm:text-sm text-muted-foreground flex flex-wrap gap-1 sm:gap-3">
                        <span className="whitespace-nowrap">Entry: ${position.entry_price.toFixed(5)}</span>
                        <span className="hidden sm:inline">•</span>
                        <span className="whitespace-nowrap">Current: ${Number(currentPrice).toFixed(5)}</span>
                        <span className="hidden sm:inline">•</span>
                        <span className="whitespace-nowrap">Qty: {position.quantity}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-start gap-2 sm:text-right border-t sm:border-t-0 sm:border-l border-border/30 pt-2 sm:pt-0 sm:pl-4">
                    <div className={`text-lg sm:text-xl font-bold ${currentProfit >= 0 ? 'text-success' : 'text-destructive'}`}>
                      {currentProfit >= 0 ? '+' : ''}${currentProfit.toFixed(2)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(position.opened_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};