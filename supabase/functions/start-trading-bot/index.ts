import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

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

    const { strategyId, strategyName } = await req.json();

    if (!strategyId) {
      throw new Error('Strategy ID is required');
    }

    console.log(`Starting trading bot for user ${user.id}, strategy ${strategyId}`);

    // Verify user setup is approved
    const { data: setup, error: setupError } = await supabaseClient
      .from('user_setup')
      .select('admin_approved, mt5_account, mt5_password, mt5_server, account_size, risk_per_trade, telegram_chat_id')
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
      .select('*')
      .eq('id', strategyId)
      .single();

    if (strategyError) throw strategyError;

    if (!strategy.is_active) {
      throw new Error('This strategy is currently inactive');
    }

    // Check if strategy is already running for this user
    const { data: existingStrategy } = await supabaseClient
      .from('user_strategies')
      .select('*')
      .eq('user_id', user.id)
      .eq('strategy_id', strategyId)
      .eq('is_running', true)
      .maybeSingle();

    if (existingStrategy) {
      throw new Error('This strategy is already running');
    }

    // Create or update user_strategy record
    const { data: userStrategy, error: userStrategyError } = await supabaseClient
      .from('user_strategies')
      .upsert({
        user_id: user.id,
        strategy_id: strategyId,
        is_running: true,
        started_at: new Date().toISOString(),
        stopped_at: null,
      }, {
        onConflict: 'user_id,strategy_id'
      })
      .select()
      .single();

    if (userStrategyError) throw userStrategyError;

    console.log(`User strategy record created/updated: ${userStrategy.id}`);

    // TODO: In production, this is where you would:
    // 1. Deploy Python script to execution environment
    // 2. Initialize MT5 connection with user's credentials
    // 3. Start the trading bot process
    // 4. Set up monitoring and health checks
    
    // For now, we'll just log and send a notification
    console.log(`Would start Python script: ${strategy.python_script_path}`);
    console.log(`MT5 Config: ${setup.mt5_server}, Account: ${setup.mt5_account}`);
    console.log(`Risk per trade: ${setup.risk_per_trade}%, Account size: $${setup.account_size}`);

    // Send notification (if Telegram is configured)
    if (setup.telegram_chat_id && Deno.env.get('TELEGRAM_BOT_TOKEN')) {
      try {
        await supabaseClient.functions.invoke('send-telegram-notification', {
          body: {
            chatId: setup.telegram_chat_id,
            message: `🤖 Trading bot started!\n\nStrategy: ${strategyName}\nAccount: ${setup.mt5_account}\nServer: ${setup.mt5_server}`,
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
