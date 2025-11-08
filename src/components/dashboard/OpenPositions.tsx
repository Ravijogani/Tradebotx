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
    
    // Set up realtime subscription
    const channel = supabase
      .channel('open-positions-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'trades',
          filter: 'status=eq.open'
        },
        (payload) => {
          console.log('Position change:', payload);
          loadPositions();
          
          if (payload.eventType === 'INSERT') {
            toast({
              title: "New Position Opened",
              description: `${payload.new.symbol} - ${payload.new.trade_type}`,
            });
          } else if (payload.eventType === 'UPDATE') {
            // Calculate P&L from metadata
            const profit = payload.new.metadata?.profit || 0;
            toast({
              title: "Position Updated",
              description: `${payload.new.symbol} - P&L: $${profit.toFixed(2)}`,
              variant: profit >= 0 ? "default" : "destructive"
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadPositions = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data } = await supabase
      .from("trades")
      .select("*")
      .eq("user_id", user.id)
      .eq("status", "open" as any)
      .order("opened_at", { ascending: false });

    setPositions(data || []);
    
    // Calculate total P&L from metadata
    const total = (data || []).reduce((sum, pos) => {
      const profit = typeof pos.metadata === 'object' && pos.metadata !== null
        ? (pos.metadata as any).profit || 0
        : 0;
      return sum + profit;
    }, 0);
    setTotalPnL(total);
  };

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Open Positions
            </CardTitle>
            <CardDescription className="mt-1">
              {positions.length} active {positions.length === 1 ? 'position' : 'positions'}
            </CardDescription>
          </div>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">Total P&L</div>
            <div className={`text-2xl font-bold ${totalPnL >= 0 ? 'text-success' : 'text-destructive'}`}>
              {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {positions.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
              <Activity className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground">No open positions</p>
          </div>
        ) : (
          <div className="space-y-3">
            {positions.map((position) => {
              const metadata = typeof position.metadata === 'object' && position.metadata !== null
                ? position.metadata as any
                : {};
              const currentProfit = metadata.profit || 0;
              const currentPrice = metadata.current_price || position.entry_price;
              
              return (
                <div
                  key={position.id}
                  className="flex items-center justify-between p-4 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/30 transition-all"
                >
                  <div className="flex items-center gap-4 flex-1">
                    {currentProfit >= 0 ? (
                      <div className="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center">
                        <TrendingUp className="w-5 h-5 text-success" />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center">
                        <TrendingDown className="w-5 h-5 text-destructive" />
                      </div>
                    )}
                    
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-semibold text-foreground">{position.symbol}</span>
                        <Badge variant={position.trade_type === 'BUY' ? 'default' : 'secondary'}>
                          {position.trade_type}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground space-x-3">
                        <span>Entry: ${parseFloat(position.entry_price).toFixed(5)}</span>
                        <span>•</span>
                        <span>Current: ${parseFloat(currentPrice).toFixed(5)}</span>
                        <span>•</span>
                        <span>Qty: {position.quantity}</span>
                      </div>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className={`text-xl font-bold ${currentProfit >= 0 ? 'text-success' : 'text-destructive'}`}>
                      {currentProfit >= 0 ? '+' : ''}${currentProfit.toFixed(2)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {new Date(position.opened_at).toLocaleTimeString()}
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