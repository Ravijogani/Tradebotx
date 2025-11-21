import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export const OpenPositions = () => {
  const [positions, setPositions] = useState<any[]>([]);
  const [totalPnL, setTotalPnL] = useState(0);
  const { toast } = useToast();

  useEffect(() => {
    loadPositions();
    
    // Set up realtime subscription with throttling
    let lastUpdateTime = 0;
    const updateThrottle = 5000; // Only show toasts every 5 seconds
    
    const setupRealtime = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const channel = supabase
        .channel('open-positions-changes')
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'trades',
            filter: `user_id=eq.${user.id}`
          },
          async (payload) => {
            // Check if the change is related to open positions
            const newStatus = (payload.new as any)?.status;
            const oldStatus = (payload.old as any)?.status;
            const isOpenRelated = newStatus === 'open' || oldStatus === 'open';
            
            if (!isOpenRelated) return;

            console.log('Position change:', payload);
            loadPositions();
            
            const now = Date.now();
            const shouldShowToast = now - lastUpdateTime > updateThrottle;
            
            if (payload.eventType === 'INSERT') {
              toast({
                title: "New Position Opened",
                description: `${payload.new.symbol} - ${payload.new.trade_type}`,
              });
              lastUpdateTime = now;
            } else if (payload.eventType === 'UPDATE' && shouldShowToast) {
              // Only show update toasts every 5 seconds to prevent spam
              lastUpdateTime = now;
            }
          }
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

  const loadPositions = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      console.log('[OpenPositions] No user found');
      return;
    }

    console.log('[OpenPositions] Loading positions for user:', user.id);
    
    const { data, error } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .eq("status", "open")
      .order("opened_at", { ascending: false });

    console.log('[OpenPositions] Query result:', { data, error, count: data?.length });

    if (error) {
      console.error('[OpenPositions] Error loading positions:', error);
      return;
    }

    setPositions(data || []);
    
    // Calculate total P&L from running_profit in metadata
    const total = (data || []).reduce((sum, pos) => {
      const metadata = typeof pos.metadata === 'object' && pos.metadata !== null ? pos.metadata as any : {};
      const runningProfit = metadata.running_profit || pos.profit_loss || 0;
      return sum + runningProfit;
    }, 0);
    console.log('[OpenPositions] Total P&L:', total);
    setTotalPnL(total);
  };

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
              const metadata = typeof position.metadata === 'object' && position.metadata !== null
                ? position.metadata as any
                : {};
              const currentProfit = metadata.running_profit || metadata.profit || position.profit_loss || 0;
              const currentPrice = metadata.current_price || position.entry_price;
              
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
                      </div>
                      <div className="text-xs sm:text-sm text-muted-foreground flex flex-wrap gap-1 sm:gap-3">
                        <span className="whitespace-nowrap">Entry: ${parseFloat(position.entry_price).toFixed(5)}</span>
                        <span className="hidden sm:inline">•</span>
                        <span className="whitespace-nowrap">Current: ${parseFloat(currentPrice).toFixed(5)}</span>
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