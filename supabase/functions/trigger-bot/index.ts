import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
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
    // Handle both encrypted and plain text passwords for backwards compatibility
    let decryptedPassword: string;
    try {
      decryptedPassword = await decrypt(setup.mt5_password);
      console.log('MT5 password decrypted successfully');
    } catch (decryptError) {
      // If decryption fails, it might be a plain text password (legacy)
      console.warn('Failed to decrypt MT5 password, assuming plain text:', decryptError);
      
      // Check if it looks like encrypted data (base64 format with sufficient length)
      const isLikelyEncrypted = setup.mt5_password.length > 40 && /^[A-Za-z0-9+/=]+$/.test(setup.mt5_password);
      
      if (isLikelyEncrypted) {
        // If it looks encrypted but failed to decrypt, throw error
        throw new Error('Failed to decrypt MT5 credentials. Please update your setup with new credentials.');
      }
      
      // Use plain text password (legacy support)
      decryptedPassword = setup.mt5_password;
      console.log('Using plain text MT5 password (legacy mode). Consider re-encrypting via setup update.');
    }

    // Extract user's current session token from request
    const authHeader = req.headers.get('Authorization');
    const userToken = authHeader?.replace('Bearer ', '');
    
    if (!userToken) {
      throw new Error('Authentication token required');
    }

    // Prepare bot configuration
    // Bot manager expects supabase_service_key for database operations
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
      supabase_service_key: Deno.env.get('SUPABASE_SERVICE_ROLE_KEY'), // Required by bot manager
      gemini_api_key: Deno.env.get('GEMINI_API_KEY'),
      action: action
    };

    // Send command to AWS Lightsail bot manager
    const LIGHTSAIL_BOT_MANAGER_URL = Deno.env.get('LIGHTSAIL_BOT_MANAGER_URL');
    const BOT_MANAGER_SECRET = Deno.env.get('BOT_MANAGER_SECRET');
    
    if (LIGHTSAIL_BOT_MANAGER_URL) {
      try {
        console.log(`Attempting HTTP to ${LIGHTSAIL_BOT_MANAGER_URL}/bot/${action}`);
        console.log(`Bot manager auth: ${BOT_MANAGER_SECRET ? 'configured' : 'missing'}`);
        
        const response = await fetch(`${LIGHTSAIL_BOT_MANAGER_URL}/bot/${action}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${BOT_MANAGER_SECRET}` // Shared secret
          },
          body: JSON.stringify(botConfig)
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.warn(`Bot manager HTTP error (${response.status}): ${errorText}`);
          throw new Error(`Bot manager returned ${response.status}`);
        }

        const result = await response.json();
        console.log('Bot command sent via HTTP successfully:', result);
        
        return new Response(
          JSON.stringify({
            success: true,
            message: `Bot ${action} command sent successfully`,
            method: 'http',
            data: result
          }),
          {
            status: 200,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      } catch (httpError: any) {
        console.warn(`Failed to reach bot manager via HTTP: ${httpError.message}. Falling back to database queue...`);
        // Continue to database fallback below
      }
    }

    // Fallback: Database-based queue (if no direct HTTP connection or HTTP failed)
    // Store command in database for bot manager to poll
    console.log(`Queueing bot ${action} command in database for user ${user.id}`);
    
    const { data: queuedCommand, error: queueError } = await supabaseClient
      .from('bot_commands')
      .insert({
        user_id: user.id,
        strategy_id: strategyId,
        action: action,
        config: botConfig,
        status: 'pending'
      })
      .select()
      .single();

    if (queueError) {
      console.error('Failed to queue command:', queueError);
      throw new Error('Failed to queue bot command. Please try again.');
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: `Bot ${action} command queued successfully. It will be processed shortly.`,
        method: 'database_queue',
        command_id: queuedCommand.id
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
