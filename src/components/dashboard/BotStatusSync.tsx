import { useEffect, useRef } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

/**
 * Background component that syncs bot health status with user_strategies
 * If bot crashes or goes stale, this updates the database to show correct button state
 * Also syncs initial equity from MT5 heartbeat when first connected
 * Sends email notifications ONLY when state is confirmed via heartbeat
 */
export const BotStatusSync = () => {
  const { toast } = useToast();
  const equitySyncedRef = useRef<Set<string>>(new Set());
  // Track which strategies we've sent "started" emails for (to avoid duplicates)
  const startedEmailSentRef = useRef<Set<string>>(new Set());
  // Track which strategies have been confirmed running (to know when to send crash emails)
  const confirmedRunningRef = useRef<Set<string>>(new Set());

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

        // Is this a launch that simply hasn't reported in yet?
        //
        // This grace used to live ONLY inside the `if (!heartbeat)` branch
        // below, which made it useless in practice: bot_heartbeats keeps one
        // row per (user, strategy) forever, so after a strategy's very first
        // run a heartbeat row always exists and the grace was skipped every
        // time. Control fell through to the stale-heartbeat branch, which had
        // no grace at all -- it saw status 'starting' plus an old heartbeat
        // and wrote is_running=false/status='stopped' on the very next poll.
        //
        // With a 61-day-old heartbeat row on this account, pressing Start
        // marked the bot stopped ~7 seconds later, before the Python process
        // had even finished importing. The bot then read that as a genuine
        // dashboard Stop and shut itself down. Harmless while nothing obeyed
        // is_running; fatal once the bots did.
        //
        // Hoisted here so it guards BOTH branches: while a strategy is
        // 'starting' and inside the window, this tab reports nothing and
        // writes nothing. The bot's own confirm_bot_started() flips the row
        // to 'running', which is what should end the wait -- not a stale row
        // written by a process that died two months ago.
        const STARTUP_GRACE_SECONDS = 120;
        if (strategy.status === 'starting' && strategy.started_at) {
          const secondsSinceStart =
            (Date.now() - new Date(strategy.started_at).getTime()) / 1000;
          if (secondsSinceStart < STARTUP_GRACE_SECONDS) {
            console.log(
              `Strategy ${strategy.strategy_id} is starting ` +
              `(${secondsSinceStart.toFixed(0)}s) - waiting for it to confirm, not touching its row`
            );
            continue;
          }
        }

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
          // The startup grace that used to be duplicated here now runs above,
          // before the heartbeat is even considered, so it covers this branch
          // and the stale-heartbeat branch alike. Reaching this point means
          // the strategy is either not 'starting' or is past the window.

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
          const strategyKey = `${strategy.user_id}_${strategy.strategy_id}`;
          
          // Mark this strategy as confirmed running
          confirmedRunningRef.current.add(strategyKey);
          
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
            
            // Send "Bot Started" email ONLY when we confirm it's running
            // (not when user clicks button - this avoids false positive emails)
            if (!startedEmailSentRef.current.has(strategyKey)) {
              const { data: strategyData } = await supabase
                .from("strategies")
                .select("name")
                .eq("id", strategy.strategy_id)
                .single();

              const { data: setupData } = await supabase
                .from("user_setup")
                .select("account_size, risk_per_trade")
                .eq("user_id", strategy.user_id)
                .single();

              try {
                await supabase.functions.invoke('send-bot-start-alert', {
                  body: {
                    email: user.email,
                    strategyName: strategyData?.name || 'Trading Bot',
                    accountSize: setupData?.account_size || 0,
                    riskPerTrade: setupData?.risk_per_trade || 1
                  }
                });
                console.log(`📧 Bot started email sent for strategy ${strategy.strategy_id}`);
                startedEmailSentRef.current.add(strategyKey);
              } catch (emailError) {
                console.error('Failed to send bot started email:', emailError);
              }
            }
            
            toast({
              title: "✅ Bot Running",
              description: "Trading bot confirmed running. Email notification sent.",
            });
          }
          continue;
        }

        // Heartbeat is stale or bot is stopped - BOT CRASHED
        if (!isHeartbeatFresh || !heartbeat.pid) {
          if (strategy.is_running || strategy.status === 'running' || strategy.status === 'starting') {
            const strategyKey = `${strategy.user_id}_${strategy.strategy_id}`;
            console.log(`🛑 Bot crashed/stale for strategy ${strategy.strategy_id}`);
            
            // Update database status
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

            // Get strategy name for notification
            const { data: strategyData } = await supabase
              .from("strategies")
              .select("name")
              .eq("id", strategy.strategy_id)
              .single();

            // ONLY send crash email if bot was previously CONFIRMED running
            // This prevents false "crash" emails when bot never started successfully
            const wasConfirmedRunning = confirmedRunningRef.current.has(strategyKey);
            
            if (wasConfirmedRunning) {
              // Get performance data for email
              const { data: perfData } = await supabase
                .from("strategy_performance")
                .select("total_trades, total_profit_loss")
                .eq("user_id", strategy.user_id)
                .eq("strategy_id", strategy.strategy_id)
                .single();

              // Send crash notification email via edge function
              try {
                await supabase.functions.invoke('send-bot-stopped', {
                  body: {
                    email: user.email,
                    strategyName: strategyData?.name || 'Trading Bot',
                    reason: 'Bot stopped responding (possible crash or connection issue)',
                    totalTrades: perfData?.total_trades || 0,
                    totalPnL: perfData?.total_profit_loss || 0
                  }
                });
                console.log(`📧 Crash notification email sent for strategy ${strategy.strategy_id}`);
              } catch (emailError) {
                console.error('Failed to send crash notification email:', emailError);
              }

              // Show toast to user
              toast({
                title: "⚠️ Bot Stopped",
                description: `${strategyData?.name || 'Trading bot'} stopped unexpectedly. Email notification sent.`,
                variant: "destructive"
              });
              
              // Clear the refs so new cycle can start fresh
              confirmedRunningRef.current.delete(strategyKey);
              startedEmailSentRef.current.delete(strategyKey);
            } else {
              // Bot never confirmed running - just show toast, no email
              console.log(`ℹ️ Bot ${strategy.strategy_id} failed to start (was never confirmed running)`);
              toast({
                title: "⚠️ Bot Failed to Start",
                description: `${strategyData?.name || 'Trading bot'} could not connect. Check server status.`,
                variant: "destructive"
              });
            }
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
