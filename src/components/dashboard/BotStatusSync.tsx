import { useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

/**
 * Background component that syncs bot status with user_strategies
 * Simple rule: PID exists in bot_heartbeats = running, no PID = stopped
 */
export const BotStatusSync = () => {
  const { toast } = useToast();

  useEffect(() => {
    const syncBotStatus = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get all user strategies
      const { data: strategies } = await supabase
        .from("user_strategies")
        .select("id, strategy_id, user_id, status, is_running, bot_pid, started_at")
        .eq("user_id", user.id);

      if (!strategies || strategies.length === 0) return;

      // Check each strategy's heartbeat for PID
      for (const strategy of strategies) {
        const { data: heartbeat } = await supabase
          .from("bot_heartbeats")
          .select("pid")
          .eq("user_id", strategy.user_id)
          .eq("strategy_id", strategy.strategy_id)
          .maybeSingle();

        // Simple logic: PID exists = running, no PID = stopped
        const hasPID = heartbeat?.pid !== null && heartbeat?.pid !== undefined;
        
        console.log(`Strategy ${strategy.strategy_id}: PID=${heartbeat?.pid || 'none'}, Should be: ${hasPID ? 'running' : 'stopped'}`);

        if (hasPID && !strategy.is_running) {
          // Bot is running but DB says stopped - fix it
          console.log(`✅ Bot is running (PID: ${heartbeat.pid}) - updating status to running`);
          await supabase
            .from("user_strategies")
            .update({
              is_running: true,
              status: 'running',
              bot_pid: heartbeat.pid,
              started_at: strategy.started_at || new Date().toISOString()
            })
            .eq("id", strategy.id);
            
          if (strategy.status === 'starting') {
            toast({
              title: "✅ Bot Started",
              description: "Trading bot is now running with live market data.",
            });
          }
        } else if (!hasPID && strategy.is_running) {
          // Bot is stopped but DB says running - fix it
          console.log(`🛑 Bot is stopped (no PID) - updating status to stopped`);
          await supabase
            .from("user_strategies")
            .update({
              is_running: false,
              status: 'stopped',
              stopped_at: new Date().toISOString(),
              bot_pid: null
            })
            .eq("id", strategy.id);
        }
      }
    };

    // Run immediately on mount
    syncBotStatus();

    // Set up polling interval (check every 5 seconds)
    const pollInterval = setInterval(syncBotStatus, 5000);

    // Listen for real-time changes in bot_heartbeats
    const channel = supabase
      .channel("bot_heartbeats_changes")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "bot_heartbeats",
        },
        (payload) => {
          console.log("Heartbeat changed:", payload);
          syncBotStatus();
        }
      )
      .subscribe();

    return () => {
      clearInterval(pollInterval);
      supabase.removeChannel(channel);
    };
  }, [toast]);

  return null;
};
