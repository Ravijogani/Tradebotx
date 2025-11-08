import { useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

/**
 * Background component that syncs bot health status with user_strategies
 * If bot crashes or goes stale, this updates the database to show correct button state
 */
export const BotStatusSync = () => {
  const { toast } = useToast();

  useEffect(() => {
    const checkBotHealth = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get all user's running strategies
      const { data: runningStrategies } = await supabase
        .from("user_strategies")
        .select("id, strategy_id, user_id")
        .eq("user_id", user.id)
        .eq("is_running", true);

      if (!runningStrategies || runningStrategies.length === 0) return;

      // Check heartbeat for each running strategy
      for (const strategy of runningStrategies) {
        const { data: heartbeat } = await supabase
          .from("bot_heartbeats")
          .select("last_heartbeat, status")
          .eq("user_id", strategy.user_id)
          .eq("strategy_id", strategy.strategy_id)
          .maybeSingle();

        if (!heartbeat) continue;

        const lastBeat = new Date(heartbeat.last_heartbeat).getTime();
        const now = Date.now();
        const diffSeconds = (now - lastBeat) / 1000;

        // If heartbeat is stale (>60s) or status is crashed/stopped
        const isStale = diffSeconds > 60;
        const isCrashed = heartbeat.status === 'crashed' || heartbeat.status === 'stopped';

        if (isStale || isCrashed) {
          // Auto-stop the strategy in database
          console.log(`Auto-stopping stale/crashed bot for strategy ${strategy.strategy_id}`);
          
          await supabase
            .from("user_strategies")
            .update({
              is_running: false,
              stopped_at: new Date().toISOString()
            })
            .eq("id", strategy.id);

          // Show notification only once
          if (isCrashed && heartbeat.status === 'crashed') {
            toast({
              title: "⚠️ Bot Stopped",
              description: "Bot crashed and has been stopped. You can restart it.",
              variant: "destructive"
            });
          }
        }
      }
    };

    // Check immediately on mount
    checkBotHealth();

    // Check every 30 seconds
    const interval = setInterval(checkBotHealth, 30000);

    // Also listen for heartbeat changes
    const channel = supabase
      .channel('bot-health-sync')
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'bot_heartbeats'
        },
        (payload) => {
          if (payload.new.status === 'crashed' || payload.new.status === 'stopped') {
            checkBotHealth();
          }
        }
      )
      .subscribe();

    return () => {
      clearInterval(interval);
      supabase.removeChannel(channel);
    };
  }, []);

  return null; // This is a background component with no UI
};