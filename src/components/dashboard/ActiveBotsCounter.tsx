import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent } from "@/components/ui/card";
import { Bot, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export const ActiveBotsCounter = () => {
  const [activeBots, setActiveBots] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActiveBots();
    
    // Realtime subscription for bot changes
    const channel = supabase
      .channel('active-bots-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'user_strategies' },
        () => loadActiveBots()
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadActiveBots = async () => {
    try {
      // Bot is running ONLY if bot_pid exists (not null)
      const { data, error } = await supabase
        .from("user_strategies")
        .select("id, bot_pid, user_id, strategy_id")
        .not("bot_pid", "is", null);

      if (error) throw error;
      
      // Double check with heartbeat freshness
      let activeCount = 0;
      if (data && data.length > 0) {
        for (const strategy of data) {
          const { data: heartbeat } = await supabase
            .from("bot_heartbeats")
            .select("last_heartbeat, pid")
            .eq("user_id", strategy.user_id)
            .eq("strategy_id", strategy.strategy_id)
            .maybeSingle();

          if (heartbeat?.pid) {
            const diffSeconds = (Date.now() - new Date(heartbeat.last_heartbeat).getTime()) / 1000;
            // Increased threshold to 60s to account for network/DB latency
            if (diffSeconds <= 60) {
              activeCount++;
            }
          }
        }
      }
      
      setActiveBots(activeCount);
    } catch (error) {
      console.error("Error loading active bots:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-border/50 bg-gradient-to-br from-card/50 to-card/30 backdrop-blur-sm hover:shadow-glow transition-all duration-300 overflow-hidden relative group">
      {/* Animated background pulse */}
      <div className="absolute inset-0 bg-gradient-primary opacity-0 group-hover:opacity-10 transition-opacity duration-500" />
      
      <CardContent className="p-6 relative">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-primary flex items-center justify-center shadow-glow">
                <Bot className="w-7 h-7 text-primary-foreground" />
              </div>
              {activeBots > 0 && (
                <div className="absolute -top-1 -right-1">
                  <span className="relative flex h-4 w-4">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-4 w-4 bg-green-500 border-2 border-background"></span>
                  </span>
                </div>
              )}
            </div>
            <div>
              <p className="text-sm text-muted-foreground font-medium mb-1">Live Bots</p>
              <p className="text-3xl font-bold bg-gradient-primary bg-clip-text text-transparent">
                {loading ? "..." : activeBots}
              </p>
            </div>
          </div>
          {activeBots > 0 && (
            <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20 gap-1.5">
              <Zap className="w-3 h-3" />
              Active
            </Badge>
          )}
        </div>
        {!loading && activeBots === 0 && (
          <p className="text-xs text-muted-foreground mt-3">No bots running</p>
        )}
      </CardContent>
    </Card>
  );
};