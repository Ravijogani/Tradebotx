import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      {
        global: {
          headers: { Authorization: req.headers.get('Authorization')! },
        },
      }
    );

    // Get authenticated user
    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    if (userError || !user) {
      throw new Error('Not authenticated');
    }

    const { strategyId } = await req.json();

    if (!strategyId) {
      throw new Error('Strategy ID is required');
    }

    console.log(`Starting trading bot for user ${user.id}, strategy ${strategyId}`);

    // Verify user setup is approved
    const { data: setup, error: setupError } = await supabaseClient
      .from('user_setup')
      .select('admin_approved, mt5_account, mt5_password, mt5_server, account_size, risk_per_trade, max_positions, telegram_chat_id')
      .eq('user_id', user.id)
      .single();

    if (setupError) throw setupError;

    if (!setup?.admin_approved) {
      throw new Error('Your account setup is not yet approved by admin');
    }

    if (!setup.mt5_account || !setup.mt5_password || !setup.mt5_server) {
      throw new Error('MT5 configuration is incomplete');
    }

    // Get strategy details
    const { data: strategy, error: strategyError } = await supabaseClient
      .from('strategies')
      .select('name, is_active')
      .eq('id', strategyId)
      .single();

    if (strategyError) throw strategyError;

    if (!strategy.is_active) {
      throw new Error('This strategy is currently inactive');
    }

    const strategyName = strategy.name;

    // Check actual bot status from heartbeats (source of truth)
    const { data: heartbeat } = await supabaseClient
      .from('bot_heartbeats')
      .select('*')
      .eq('user_id', user.id)
      .eq('strategy_id', strategyId)
      .maybeSingle();

    // Check if bot is actually running (fresh heartbeat within last 90 seconds)
    // Using 90 seconds to account for network delays and heartbeat intervals
    const isActuallyRunning = heartbeat && 
      new Date(heartbeat.last_heartbeat).getTime() > Date.now() - 90000 &&
      heartbeat.status === 'running';

    if (isActuallyRunning) {
      throw new Error('This strategy is already running');
    }

    // Create or update user_strategy record - set status to 'starting', NOT is_running=true
    // Bot will confirm when it actually starts and gets a PID
    const { data: userStrategy, error: userStrategyError } = await supabaseClient
      .from('user_strategies')
      .upsert({
        user_id: user.id,
        strategy_id: strategyId,
        is_running: false, // Don't set to true until bot confirms it started
        status: 'starting', // Indicates bot start command was sent
        started_at: new Date().toISOString(),
        stopped_at: null,
        bot_pid: null, // Will be set by bot when it starts
      }, {
        onConflict: 'user_id,strategy_id'
      })
      .select()
      .single();

    if (userStrategyError) throw userStrategyError;

    console.log(`User strategy record created/updated: ${userStrategy.id}`);

    // Create service client for privileged operations
    const serviceClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    );
    
    // Check if strategy_performance record already exists (to preserve initial_balance)
    const { data: existingPerf } = await serviceClient
      .from('strategy_performance')
      .select('id, initial_balance')
      .eq('user_id', user.id)
      .eq('strategy_id', strategyId)
      .maybeSingle();

    // IMPORTANT: Only set initial_balance on FIRST bot start ever
    // On restart, preserve the original initial_balance for accurate P&L tracking
    if (!existingPerf) {
      // First time starting this strategy - create new performance record
      console.log(`First time starting strategy - setting initial balance to ${setup.account_size}`);
      await serviceClient
        .from('strategy_performance')
        .insert({
          user_id: user.id,
          strategy_id: strategyId,
          initial_balance: setup.account_size || 10000,
          current_balance: setup.account_size || 10000,
          total_trades: 0,
          winning_trades: 0,
          losing_trades: 0,
          total_profit_loss: 0,
          win_rate: 0,
          best_trade: 0,
          worst_trade: 0,
          avg_win: 0,
          avg_loss: 0,
        });
    } else {
      console.log(`Strategy performance exists - preserving initial_balance: ${existingPerf.initial_balance}`);
      // Don't reset anything - just log that we're restarting
    }

    console.log(`Strategy performance check complete for user ${user.id}`);

    // Log to audit trail
    await serviceClient.from('bot_audit_logs').insert({
      user_id: user.id,
      strategy_id: strategyId,
      action: 'start',
      performed_by: user.id,
      metadata: {
        strategy_name: strategyName,
        timestamp: new Date().toISOString()
      }
    });

    // Call trigger-bot edge function instead of direct execution
    const { data: triggerResult, error: triggerError } = await supabaseClient.functions.invoke('trigger-bot', {
      body: {
        action: 'start',
        strategyId,
        strategyName
      }
    });

    if (triggerError) {
      console.error('Failed to trigger bot:', triggerError);
      
      // Try to get the actual error message from trigger-bot response
      let errorMessage = 'Failed to start bot on remote server';
      try {
        if (triggerError.context && typeof triggerError.context.json === 'function') {
          const errorBody = await triggerError.context.json();
          if (errorBody?.error) {
            errorMessage = errorBody.error;
          }
        }
      } catch (parseError) {
        console.error('Could not parse trigger error:', parseError);
      }
      
      throw new Error(errorMessage);
    }
    
    // Also check if trigger returned success: false
    if (triggerResult && triggerResult.success === false) {
      console.error('Trigger bot returned failure:', triggerResult);
      throw new Error(triggerResult.error || 'Bot manager rejected the start request');
    }

    console.log(`Bot start command sent successfully:`, triggerResult);

    // NOTE: Email notification is NOT sent here anymore
    // It will be sent by the frontend BotStatusSync component when the bot 
    // actually confirms it's running via heartbeat (to avoid false positives)
    
    // Send TELEGRAM notification immediately (if configured) - Telegram is instant feedback
    if (setup.telegram_chat_id && Deno.env.get('TELEGRAM_BOT_TOKEN')) {
      try {
        await supabaseClient.functions.invoke('send-telegram-notification', {
          body: {
            userId: user.id,
            type: 'strategy_status',
            title: 'Bot starting',
            message: `Strategy: ${strategyName}\nAccount: ${setup.mt5_account}\nYou'll receive another notification when the bot is confirmed running.`,
          }
        });
      } catch (telegramError) {
        console.error('Failed to send Telegram notification:', telegramError);
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Trading bot started successfully',
        userStrategyId: userStrategy.id,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error: any) {
    console.error('Error starting trading bot:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message || 'Failed to start trading bot',
      }),
      {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
