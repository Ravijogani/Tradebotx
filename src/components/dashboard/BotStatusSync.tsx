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
    const syncBotStatus = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get all user's strategies that are starting or running
      const { data: activeStrategies } = await supabase
        .from("user_strategies")
        .select("id, strategy_id, user_id, status, is_running")
        .eq("user_id", user.id)
        .in("status", ["starting", "running"]);

      if (!activeStrategies || activeStrategies.length === 0) return;

      // Check heartbeat for each active strategy
      for (const strategy of activeStrategies) {
        const { data: heartbeat } = await supabase
          .from("bot_heartbeats")
          .select("last_heartbeat, status, pid")
          .eq("user_id", strategy.user_id)
          .eq("strategy_id", strategy.strategy_id)
          .maybeSingle();

        // If no heartbeat exists yet and status is 'starting', wait for bot to start
        if (!heartbeat && strategy.status === 'starting') {
          continue; // Bot is still starting up
        }

        // If no heartbeat but status is 'running', something is wrong
        if (!heartbeat && strategy.status === 'running') {
          console.log(`No heartbeat for running strategy ${strategy.strategy_id}, marking as crashed`);
          await supabase
            .from("user_strategies")
            .update({
              is_running: false,
              status: 'crashed',
              stopped_at: new Date().toISOString(),
              bot_pid: null
            })
            .eq("id", strategy.id);
          continue;
        }

        if (!heartbeat) continue;

        const lastBeat = new Date(heartbeat.last_heartbeat).getTime();
        const now = Date.now();
        const diffSeconds = (now - lastBeat) / 1000;
        const diffMinutes = (diffSeconds / 60).toFixed(1);

        console.log(`Strategy ${strategy.strategy_id}: Last heartbeat ${diffSeconds.toFixed(0)}s (${diffMinutes}min) ago, Status: ${heartbeat.status}, PID: ${heartbeat.pid}`);

        // If heartbeat shows 'running' and bot was 'starting', update to running
        if (heartbeat.status === 'running' && strategy.status === 'starting') {
          console.log(`Bot confirmed running for strategy ${strategy.strategy_id}, PID: ${heartbeat.pid}`);
          await supabase
            .from("user_strategies")
            .update({
              is_running: true,
              status: 'running',
              bot_pid: heartbeat.pid
            })
            .eq("id", strategy.id);
          
          toast({
            title: "✅ Bot Started",
            description: "Trading bot is now running with live market data.",
          });
          continue;
        }

        // If heartbeat is stale (>40 seconds) or status is crashed/stopped
        const isStale = diffSeconds > 40;
        const isCrashed = heartbeat.status === 'crashed' || heartbeat.status === 'stopped';
        
        if (isStale) {
          console.warn(`⚠️ STALE HEARTBEAT DETECTED: Strategy ${strategy.strategy_id} - Last beat: ${diffSeconds.toFixed(0)}s ago (threshold: 40s)`);
        }

        if (isStale || isCrashed) {
          // Auto-stop the strategy in database
          console.log(`🛑 Auto-stopping ${isCrashed ? 'crashed' : 'stale'} bot for strategy ${strategy.strategy_id}. Last heartbeat: ${diffMinutes}min ago`);
          
          await supabase
            .from("user_strategies")
            .update({
              is_running: false,
              status: isCrashed ? 'crashed' : 'stopped',
              stopped_at: new Date().toISOString(),
              bot_pid: null
            })
            .eq("id", strategy.id);

          // Show notification
          if (isCrashed) {
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
    syncBotStatus();

    // Check every 10 seconds for faster feedback
    const interval = setInterval(syncBotStatus, 10000);

    // Also listen for heartbeat changes in real-time
    const channel = supabase
      .channel('bot-status-sync')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'bot_heartbeats'
        },
        (payload) => {
          console.log('Heartbeat changed:', payload);
          syncBotStatus(); // Sync immediately when heartbeat changes
        }
      )
      .subscribe();

    return () => {
      clearInterval(interval);
      supabase.removeChannel(channel);
    };
  }, [toast]);

  return null; // This is a background component with no UI
};