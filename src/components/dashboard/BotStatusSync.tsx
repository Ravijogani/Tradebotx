import { useEffect, useRef } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

/**
 * Background component that syncs bot health status with user_strategies
 * If bot crashes or goes stale, this updates the database to show correct button state
 * Also syncs initial equity from MT5 heartbeat when first connected
 */
export const BotStatusSync = () => {
  const { toast } = useToast();
  const equitySyncedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const syncBotStatus = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get all user's strategies (including stopped ones to check if they're actually running)
      const { data: strategies } = await supabase
        .from("user_strategies")
        .select("id, strategy_id, user_id, status, is_running, bot_pid, started_at")
        .eq("user_id", user.id);

      if (!strategies || strategies.length === 0) return;

      // Check heartbeat for each strategy
      for (const strategy of strategies) {
        const { data: heartbeat } = await supabase
          .from("bot_heartbeats")
          .select("last_heartbeat, status, pid, balance, equity")
          .eq("user_id", strategy.user_id)
          .eq("strategy_id", strategy.strategy_id)
          .maybeSingle();

        // ONLY sync initial equity from MT5 on FIRST run ever (when no trades have been made)
        // This prevents resetting initial balance on bot restarts
        if (heartbeat && heartbeat.equity && heartbeat.equity > 0) {
          const syncKey = `${strategy.user_id}_${strategy.strategy_id}`;
          
          if (!equitySyncedRef.current.has(syncKey)) {
            // Check if strategy_performance exists AND has zero trades (first time running)
            const { data: perf } = await supabase
              .from("strategy_performance")
              .select("initial_balance, total_trades")
              .eq("user_id", strategy.user_id)
              .eq("strategy_id", strategy.strategy_id)
              .maybeSingle();

            // ONLY update initial balance if:
            // 1. Total trades is 0 (first time ever running - no trades made yet)
            // 2. AND initial_balance differs significantly from MT5 equity (user entered wrong value)
            const isFirstRun = perf && perf.total_trades === 0;
            const hasMismatch = perf && Math.abs(perf.initial_balance - heartbeat.equity) > perf.initial_balance * 0.5;
            
            if (isFirstRun && hasMismatch) {
              console.log(`💰 First run - syncing initial equity from MT5: ${heartbeat.equity} (was ${perf.initial_balance})`);
              
              // Update strategy_performance with correct initial balance from MT5
              await supabase
                .from("strategy_performance")
                .update({ 
                  initial_balance: heartbeat.equity,
                  current_balance: heartbeat.equity
                })
                .eq("user_id", strategy.user_id)
                .eq("strategy_id", strategy.strategy_id);

              // Also update user_setup account_size to match reality
              await supabase
                .from("user_setup")
                .update({ account_size: heartbeat.equity })
                .eq("user_id", strategy.user_id);

              toast({
                title: "💰 Account Balance Synced",
                description: `Initial balance updated to $${heartbeat.equity.toFixed(2)} from MT5`,
              });
            } else if (!isFirstRun && hasMismatch) {
              console.log(`ℹ️ Balance mismatch detected but trades exist (${perf?.total_trades}) - preserving initial balance for accurate P&L`);
            }
            
            equitySyncedRef.current.add(syncKey);
          }
        }

        if (!heartbeat) {
          // No heartbeat exists - check if it's a recent start
          if (strategy.status === 'starting' && strategy.started_at) {
            const startedAt = new Date(strategy.started_at).getTime();
            const now = Date.now();
            const secondsSinceStart = (now - startedAt) / 1000;
            
            // Give 2 minutes for bot to spin up and send first heartbeat
            if (secondsSinceStart < 120) {
              console.log(`Strategy ${strategy.strategy_id} is starting, waiting for first heartbeat (${secondsSinceStart.toFixed(0)}s since start)`);
              continue; // Don't mark as stopped yet
            }
          }
          
          // If running or starting for too long without heartbeat, mark as stopped
          if (strategy.is_running || strategy.status === 'running' || strategy.status === 'starting') {
            console.log(`No heartbeat for strategy ${strategy.strategy_id}, marking as stopped`);
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
          continue;
        }

        const lastBeat = new Date(heartbeat.last_heartbeat).getTime();
        const now = Date.now();
        const diffSeconds = (now - lastBeat) / 1000;

        console.log(`Strategy ${strategy.strategy_id}: Last heartbeat ${diffSeconds.toFixed(0)}s ago, Status: ${heartbeat.status}, PID: ${heartbeat.pid}, DB Status: ${strategy.status}`);

        // Check if heartbeat is fresh (< 90 seconds to match edge function threshold)
        const isHeartbeatFresh = diffSeconds < 90;
        
        // Bot is actually running if heartbeat is fresh and has PID
        if (isHeartbeatFresh && heartbeat.pid && heartbeat.status === 'running') {
          // But database thinks it's stopped - FIX THIS
          if (!strategy.is_running || strategy.status !== 'running') {
            console.log(`✅ Bot is actually running but DB shows stopped - fixing for strategy ${strategy.strategy_id}`);
            await supabase
              .from("user_strategies")
              .update({
                is_running: true,
                status: 'running',
                bot_pid: heartbeat.pid,
                started_at: strategy.started_at || new Date().toISOString()
              })
              .eq("id", strategy.id);
            
            toast({
              title: "✅ Bot Status Synced",
              description: "Trading bot is running and connected.",
            });
          }
          continue;
        }

        // Heartbeat is stale or bot is stopped
        if (!isHeartbeatFresh || !heartbeat.pid) {
          if (strategy.is_running || strategy.status === 'running' || strategy.status === 'starting') {
            console.log(`🛑 Bot stopped/stale for strategy ${strategy.strategy_id}`);
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
