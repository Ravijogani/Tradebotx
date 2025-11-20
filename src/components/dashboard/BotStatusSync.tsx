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

      // Get ALL user's strategies to check against heartbeats
      // This ensures we catch bots that are actually running but DB status is outdated
      const { data: activeStrategies } = await supabase
        .from("user_strategies")
        .select("id, strategy_id, user_id, status, is_running, bot_pid")
        .eq("user_id", user.id);

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

        console.log(`Strategy ${strategy.strategy_id}: Last heartbeat ${diffSeconds.toFixed(0)}s ago, Status: ${heartbeat.status}, PID: ${heartbeat.pid}`);

        // 1. If PID is missing, the process is definitely dead
        if (!heartbeat.pid) {
          console.log(`🛑 Bot stopped (No PID found) for strategy ${strategy.strategy_id}`);
          await supabase
            .from("user_strategies")
            .update({
              is_running: false,
              status: 'stopped',
              stopped_at: new Date().toISOString(),
              bot_pid: null
            })
            .eq("id", strategy.id);
          
          await supabase
            .from("bot_heartbeats")
            .update({ pid: null, status: 'stopped' })
            .eq("user_id", strategy.user_id)
            .eq("strategy_id", strategy.strategy_id);
          continue;
        }

        // 2. If PID exists but heartbeat is stale (>60s), process is frozen/dead
        // Increased threshold to account for network/database latency
        const isStale = diffSeconds > 60;
        if (isStale) {
          console.warn(`⚠️ STALE HEARTBEAT: Strategy ${strategy.strategy_id} - Last beat: ${diffSeconds.toFixed(0)}s ago (PID: ${heartbeat.pid})`);
          
          await supabase
            .from("user_strategies")
            .update({
              is_running: false,
              status: 'stopped',
              stopped_at: new Date().toISOString(),
              bot_pid: null
            })
            .eq("id", strategy.id);
          
          // Clear PID in heartbeat table
          await supabase
            .from("bot_heartbeats")
            .update({ pid: null, status: 'stopped' })
            .eq("user_id", strategy.user_id)
            .eq("strategy_id", strategy.strategy_id);

          // Don't show aggressive toast - let UI components show status naturally
          continue;
        }

        // 3. Bot is healthy - PID exists AND heartbeat is fresh
        // Handle transitions
        if (heartbeat.status === 'running' && strategy.status === 'starting') {
          console.log(`✅ Bot confirmed running for strategy ${strategy.strategy_id}, PID: ${heartbeat.pid}`);
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
        }

        // Edge case: DB says stopped but PID/Heartbeat are active - fix UI
        if (heartbeat.status === 'running' && !strategy.is_running) {
          console.log(`🔄 Fixing inconsistent state: Heartbeat active but DB says stopped for strategy ${strategy.strategy_id}`);
          await supabase
            .from("user_strategies")
            .update({
              is_running: true,
              status: 'running',
              bot_pid: heartbeat.pid
            })
            .eq("id", strategy.id);
        }

        // Update PID if it's missing in user_strategies but exists in heartbeat
        if (heartbeat.status === 'running' && strategy.status === 'running' && heartbeat.pid) {
          const { data: currentStrategy } = await supabase
            .from("user_strategies")
            .select("bot_pid")
            .eq("id", strategy.id)
            .single();

          if (currentStrategy && !currentStrategy.bot_pid) {
            console.log(`🔄 Syncing PID ${heartbeat.pid} to user_strategies for strategy ${strategy.strategy_id}`);
            await supabase
              .from("user_strategies")
              .update({ bot_pid: heartbeat.pid })
              .eq("id", strategy.id);
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