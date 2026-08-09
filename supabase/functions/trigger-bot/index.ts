import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { decrypt } from "../_shared/crypto-utils.ts";

import { corsHeaders } from "../_shared/cors.ts";

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

    const ALLOWED_ACTIONS = new Set(['start', 'stop']);
    if (!ALLOWED_ACTIONS.has(action)) {
      throw new Error(`Invalid action: ${action}`);
    }

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

    // Get strategy details including python script path
    const { data: strategy, error: strategyError } = await supabaseClient
      .from('strategies')
      .select('python_script_path')
      .eq('id', strategyId)
      .single();

    if (strategyError) {
      console.warn('Could not fetch strategy details:', strategyError);
    }

    // Map strategy to the correct Python script
    const scriptPath = strategy?.python_script_path || 'hybrid_trading_bot_multiuser.py';
    console.log(`Strategy ${strategyName} will use script: ${scriptPath}`);

    // Decrypt MT5 password before sending to the bot manager. There is
    // deliberately no plaintext fallback here: a password that fails to
    // decrypt is never forwarded as-is (that would ship an unencrypted
    // credential to the bot manager). The user must re-save their MT5
    // credentials via Settings so it gets re-encrypted with the current key.
    let decryptedPassword: string;
    try {
      decryptedPassword = await decrypt(setup.mt5_password);
    } catch (decryptError) {
      console.error('Failed to decrypt MT5 password:', decryptError);
      throw new Error('Failed to decrypt MT5 credentials. Please update your MT5 password in Settings and try again.');
    }

    // Prepare bot configuration with script path
    const botConfig = {
      user_id: user.id,
      strategy_id: strategyId,
      strategy_name: strategyName,
      script_path: scriptPath,
      mt5_account: setup.mt5_account,
      mt5_password: decryptedPassword,
      mt5_server: setup.mt5_server,
      account_size: setup.account_size,
      risk_per_trade: setup.risk_per_trade,
      max_positions: setup.max_positions || 3,
      telegram_chat_id: setup.telegram_chat_id,
      telegram_bot_token: Deno.env.get('TELEGRAM_BOT_TOKEN'),
      supabase_url: Deno.env.get('SUPABASE_URL'),
      supabase_service_key: Deno.env.get('SUPABASE_SERVICE_ROLE_KEY'),
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
        
        // Add timeout to prevent edge function from hanging
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 second timeout
        
        try {
          const response = await fetch(`${LIGHTSAIL_BOT_MANAGER_URL}/bot/${action}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${BOT_MANAGER_SECRET}`
            },
            body: JSON.stringify(botConfig),
            signal: controller.signal
          });
          
          clearTimeout(timeoutId);

          const responseText = await response.text();
          let result;
          try {
            result = JSON.parse(responseText);
          } catch {
            result = { message: responseText };
          }

          // Handle "already running" as a success case - bot is in desired state
          if (!response.ok) {
            console.error(`Bot manager HTTP error (${response.status}): ${responseText}`);
            
            // Check if this is an "already running" error - treat as success
            const isAlreadyRunning = responseText.toLowerCase().includes('already running');
            
            if (isAlreadyRunning && action === 'start') {
              console.log('Bot already running on server - syncing state');
              
              // Create service client to update database state
              const serviceClient = createClient(
                Deno.env.get('SUPABASE_URL') ?? '',
                Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
              );
              
              // Update user_strategies to reflect running state
              await serviceClient
                .from('user_strategies')
                .upsert({
                  user_id: user.id,
                  strategy_id: strategyId,
                  is_running: true,
                  status: 'running',
                  started_at: new Date().toISOString(),
                  stopped_at: null,
                }, {
                  onConflict: 'user_id,strategy_id'
                });
              
              return new Response(
                JSON.stringify({
                  success: true,
                  message: 'Bot is already running - state synced',
                  method: 'http',
                  already_running: true,
                  data: result
                }),
                {
                  status: 200,
                  headers: { ...corsHeaders, 'Content-Type': 'application/json' },
                }
              );
            }
            
            throw new Error(`Bot manager returned ${response.status}: ${responseText}`);
          }

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
        } catch (fetchError) {
          clearTimeout(timeoutId);

          if (fetchError instanceof Error && fetchError.name === 'AbortError') {
            console.error(`Bot manager request timed out after 8 seconds`);
            throw new Error('Bot manager request timed out - server may be down');
          }
          throw fetchError;
        }
      } catch (httpError) {
        const httpMessage = httpError instanceof Error ? httpError.message : String(httpError);
        console.error(`Failed to reach bot manager via HTTP: ${httpMessage}`);
        
        // Return error immediately instead of falling back to queue silently
        // This gives user clear feedback that bot manager is unreachable
        return new Response(
          JSON.stringify({
            success: false,
            error: `Bot manager unreachable: ${httpMessage}. Please check if the trading server is running.`,
            method: 'http_failed'
          }),
          {
            status: 503,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      }
    }

    // Fallback: Database-based queue (if no direct HTTP connection or HTTP failed)
    // Store command in database for bot manager to poll
    console.log(`Queueing bot ${action} command in database for user ${user.id}`);
    
    const safeQueueConfig = {
      user_id: botConfig.user_id,
      strategy_id: botConfig.strategy_id,
      strategy_name: botConfig.strategy_name,
      script_path: botConfig.script_path,
      mt5_account: botConfig.mt5_account,
      mt5_server: botConfig.mt5_server,
      account_size: botConfig.account_size,
      risk_per_trade: botConfig.risk_per_trade,
      max_positions: botConfig.max_positions,
      telegram_chat_id: botConfig.telegram_chat_id,
      action: botConfig.action,
    };

    const { data: queuedCommand, error: queueError } = await supabaseClient
      .from('bot_commands')
      .insert({
        user_id: user.id,
        strategy_id: strategyId,
        action: action,
        config: safeQueueConfig,
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

  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to trigger bot';
    console.error('Error in trigger-bot:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: message,
      }),
      {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
