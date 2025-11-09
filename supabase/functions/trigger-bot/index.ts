import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { decrypt } from "../_shared/crypto-utils.ts";

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

    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    if (userError || !user) {
      throw new Error('Not authenticated');
    }

    const { action, strategyId, strategyName } = await req.json();

    console.log(`Bot ${action} request from user ${user.id} for strategy ${strategyId}`);

    // Get user setup
    const { data: setup, error: setupError } = await supabaseClient
      .from('user_setup')
      .select('admin_approved, mt5_account, mt5_password, mt5_server, account_size, risk_per_trade, max_positions, telegram_chat_id')
      .eq('user_id', user.id)
      .single();

    if (setupError) throw setupError;

    if (!setup?.admin_approved) {
      throw new Error('Account setup not approved');
    }

    // CRITICAL: Decrypt MT5 password before sending to bot
    let decryptedPassword: string;
    try {
      decryptedPassword = await decrypt(setup.mt5_password);
      console.log('MT5 password decrypted successfully');
    } catch (decryptError) {
      console.error('Failed to decrypt MT5 password:', decryptError);
      throw new Error('Failed to decrypt MT5 credentials. Please update your setup.');
    }

    // SECURITY FIX: Use user token instead of service role key
    // Extract user's current session token from request
    const authHeader = req.headers.get('Authorization');
    const userToken = authHeader?.replace('Bearer ', '');
    
    if (!userToken) {
      throw new Error('Authentication token required');
    }

    // Prepare bot configuration with user-scoped authentication
    // This replaces the previous service role key which bypassed RLS
    const botConfig = {
      user_id: user.id,
      strategy_id: strategyId,
      strategy_name: strategyName,
      mt5_account: setup.mt5_account,
      mt5_password: decryptedPassword,
      mt5_server: setup.mt5_server,
      account_size: setup.account_size,
      risk_per_trade: setup.risk_per_trade,
      max_positions: setup.max_positions || 3,
      telegram_chat_id: setup.telegram_chat_id,
      telegram_bot_token: Deno.env.get('TELEGRAM_BOT_TOKEN'),
      supabase_url: Deno.env.get('SUPABASE_URL'),
      supabase_anon_key: Deno.env.get('SUPABASE_ANON_KEY'),
      supabase_user_token: userToken, // User's session token (respects RLS)
      gemini_api_key: Deno.env.get('GEMINI_API_KEY'),
      action: action
    };

    // Send command to AWS Lightsail bot manager
    const LIGHTSAIL_BOT_MANAGER_URL = Deno.env.get('LIGHTSAIL_BOT_MANAGER_URL');
    
    if (LIGHTSAIL_BOT_MANAGER_URL) {
      const response = await fetch(`${LIGHTSAIL_BOT_MANAGER_URL}/bot/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${Deno.env.get('BOT_MANAGER_SECRET')}` // Shared secret
        },
        body: JSON.stringify(botConfig)
      });

      if (!response.ok) {
        throw new Error(`Bot manager error: ${await response.text()}`);
      }

      const result = await response.json();
      
      return new Response(
        JSON.stringify({
          success: true,
          message: `Bot ${action} command sent successfully`,
          data: result
        }),
        {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // Option 2: Database-based queue (if no direct HTTP connection)
    // Store command in database for bot manager to poll
    await supabaseClient.from('bot_commands').insert({
      user_id: user.id,
      strategy_id: strategyId,
      action: action,
      config: botConfig,
      status: 'pending'
    });

    return new Response(
      JSON.stringify({
        success: true,
        message: `Bot ${action} command queued`,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error: any) {
    console.error('Error in trigger-bot:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message || 'Failed to trigger bot',
      }),
      {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
