import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface ExecuteStrategyRequest {
  userId: string;
  strategyId: string;
  action: 'start' | 'stop';
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { userId, strategyId, action }: ExecuteStrategyRequest = await req.json();

    console.log(`Strategy ${action} request:`, { userId, strategyId });

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Get user setup
    const { data: userSetup, error: setupError } = await supabase
      .from('user_setup')
      .select('*')
      .eq('user_id', userId)
      .single();

    if (setupError || !userSetup) {
      throw new Error('User setup not found. Please complete your account setup first.');
    }

    if (!userSetup.is_completed) {
      throw new Error('Please complete your account setup before starting strategies.');
    }

    // Get strategy details
    const { data: strategy, error: strategyError } = await supabase
      .from('strategies')
      .select('*')
      .eq('id', strategyId)
      .single();

    if (strategyError || !strategy) {
      throw new Error('Strategy not found.');
    }

    if (action === 'start') {
      // Check if user already has a running strategy
      const { data: existingStrategy } = await supabase
        .from('user_strategies')
        .select('*')
        .eq('user_id', userId)
        .eq('is_running', true)
        .single();

      if (existingStrategy) {
        throw new Error('Please stop your current strategy before starting a new one.');
      }

      // Create or update user strategy
      const { data: userStrategy, error: userStrategyError } = await supabase
        .from('user_strategies')
        .upsert({
          user_id: userId,
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

      console.log('Strategy started:', userStrategy);

      // Here you would execute the Python script
      // For now, we'll simulate it with a log
      // In production, you would:
      // 1. Use Deno.run() to execute Python script with user's MT5 credentials
      // 2. Pass strategy parameters and risk settings
      // 3. Monitor the process and log output
      
      console.log(`Executing Python script: ${strategy.python_script_path}`);
      console.log('MT5 Account:', userSetup.mt5_account);
      console.log('Risk per trade:', userSetup.risk_per_trade);
      console.log('Max positions:', userSetup.max_positions);

      // Simulate Python script execution
      // In production, replace this with actual Python script execution:
      /*
      const pythonProcess = Deno.run({
        cmd: [
          "python3",
          strategy.python_script_path,
          "--account", userSetup.mt5_account,
          "--password", userSetup.mt5_password,
          "--server", userSetup.mt5_server,
          "--risk", userSetup.risk_per_trade.toString(),
          "--max_positions", userSetup.max_positions.toString(),
        ],
        stdout: "piped",
        stderr: "piped",
      });
      */

      return new Response(
        JSON.stringify({ 
          success: true, 
          message: 'Strategy started successfully',
          strategyName: strategy.name,
        }),
        {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );

    } else if (action === 'stop') {
      // Update user strategy to stopped
      const { error: stopError } = await supabase
        .from('user_strategies')
        .update({
          is_running: false,
          stopped_at: new Date().toISOString(),
        })
        .eq('user_id', userId)
        .eq('strategy_id', strategyId);

      if (stopError) throw stopError;

      console.log('Strategy stopped for user:', userId);

      // Here you would kill the Python process
      // In production, you would maintain a process registry and kill the appropriate process

      return new Response(
        JSON.stringify({ 
          success: true, 
          message: 'Strategy stopped successfully',
        }),
        {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    throw new Error('Invalid action. Use "start" or "stop".');

  } catch (error: any) {
    console.error('Error executing strategy:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});
