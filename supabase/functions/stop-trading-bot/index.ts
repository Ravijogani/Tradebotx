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

    const { userStrategyId } = await req.json();

    if (!userStrategyId) {
      throw new Error('User strategy ID is required');
    }

    console.log(`Stopping trading bot for user ${user.id}, user strategy ${userStrategyId}`);

    // Get user strategy details
    const { data: userStrategy, error: userStrategyError } = await supabaseClient
      .from('user_strategies')
      .select(`
        *,
        strategies (name, python_script_path)
      `)
      .eq('id', userStrategyId)
      .eq('user_id', user.id)
      .single();

    if (userStrategyError) throw userStrategyError;

    // If already stopped, still try to clean up on remote server but don't throw error
    const alreadyStopped = !userStrategy.is_running;

    // Update user_strategy record (only if not already stopped)
    if (!alreadyStopped) {
      const { error: updateError } = await supabaseClient
        .from('user_strategies')
        .update({
          is_running: false,
          status: 'stopped',
          bot_pid: null,
          stopped_at: new Date().toISOString(),
        })
        .eq('id', userStrategyId);

      if (updateError) throw updateError;
      console.log(`User strategy stopped in database: ${userStrategyId}`);
    } else {
      console.log(`User strategy was already stopped in database: ${userStrategyId}`);
    }

    // Call the Lightsail bot manager to actually stop the Python bot
    const botManagerUrl = Deno.env.get('LIGHTSAIL_BOT_MANAGER_URL');
    const botManagerSecret = Deno.env.get('BOT_MANAGER_SECRET');
    
    if (botManagerUrl && botManagerSecret) {
      try {
        console.log(`Calling bot manager to stop bot: ${botManagerUrl}`);
        
        const stopResponse = await fetch(`${botManagerUrl}/bot/stop`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${botManagerSecret}`,
          },
          body: JSON.stringify({
            user_id: user.id,
            strategy_id: userStrategy.strategy_id,
            user_strategy_id: userStrategyId,
          }),
        });

        if (!stopResponse.ok) {
          const errorText = await stopResponse.text();
          console.error(`Bot manager stop failed: ${stopResponse.status} - ${errorText}`);
          throw new Error(`Failed to stop bot on remote server: ${errorText}`);
        }

        const stopResult = await stopResponse.json();
        console.log(`Bot stopped successfully on Lightsail:`, stopResult);
      } catch (fetchError: any) {
        console.error('Error calling bot manager:', fetchError);
        // Don't throw - database already updated, just log the error
        // The bot might have already crashed or stopped on its own
        console.warn('Bot manager communication failed, but database updated. Bot may need manual cleanup.');
      }
    } else {
      console.warn('LIGHTSAIL_BOT_MANAGER_URL or BOT_MANAGER_SECRET not configured. Bot stop only updated database.');
    }

    // Get user setup and profile for notifications
    const { data: setup } = await supabaseClient
      .from('user_setup')
      .select('telegram_chat_id')
      .eq('user_id', user.id)
      .single();

    const { data: profile } = await supabaseClient
      .from('profiles')
      .select('email')
      .eq('id', user.id)
      .single();

    // Get strategy performance for email
    const { data: perfData } = await supabaseClient
      .from('strategy_performance')
      .select('total_trades, total_profit_loss')
      .eq('user_id', user.id)
      .eq('strategy_id', userStrategy.strategy_id)
      .single();

    console.log(`Strategy stopped for user ${user.id}`);

    // Log to audit trail
    const serviceClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    );
    
    await serviceClient.from('bot_audit_logs').insert({
      user_id: user.id,
      strategy_id: userStrategy.strategy_id,
      action: 'stop',
      performed_by: user.id,
      metadata: {
        timestamp: new Date().toISOString()
      }
    });

    // Clear heartbeat so BotStatusSync doesn't re-mark as running
    await serviceClient.from('bot_heartbeats')
      .update({ status: 'stopped', pid: null })
      .eq('user_id', user.id)
      .eq('strategy_id', userStrategy.strategy_id);

    // Send EMAIL notification for bot stop
    if (profile?.email) {
      try {
        await supabaseClient.functions.invoke('send-bot-stopped', {
          body: {
            email: profile.email,
            strategyName: userStrategy.strategies?.name || 'Unknown Strategy',
            reason: 'User requested stop',
            totalTrades: perfData?.total_trades || 0,
            totalPnL: perfData?.total_profit_loss || 0
          }
        });
        console.log(`Bot stopped email sent to ${profile.email}`);
      } catch (emailError) {
        console.error('Failed to send bot stopped email:', emailError);
      }
    }

    // Send TELEGRAM notification (if configured)
    if (setup?.telegram_chat_id && Deno.env.get('TELEGRAM_BOT_TOKEN')) {
      try {
        await supabaseClient.functions.invoke('send-telegram-notification', {
          body: {
            chatId: setup.telegram_chat_id,
            message: `⏹️ Trading bot stopped\n\nStrategy: ${userStrategy.strategies?.name}\nTotal Trades: ${perfData?.total_trades || 0}\nTotal P&L: $${(perfData?.total_profit_loss || 0).toFixed(2)}\nStopped at: ${new Date().toLocaleString()}`,
          }
        });
      } catch (telegramError) {
        console.error('Failed to send Telegram notification:', telegramError);
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: alreadyStopped ? 'Trading bot was already stopped' : 'Trading bot stopped successfully',
        already_stopped: alreadyStopped,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error: any) {
    console.error('Error stopping trading bot:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message || 'Failed to stop trading bot',
      }),
      {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
