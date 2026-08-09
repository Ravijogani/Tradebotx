import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { encrypt } from "../_shared/crypto-utils.ts";
import { handleError } from "../_shared/error-handler.ts";

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

    // Verify authentication
    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    if (userError || !user) {
      throw new Error('Not authenticated');
    }

    const { password, accountData } = await req.json();

    if (!password) {
      throw new Error('Password is required');
    }

    if (!accountData || !accountData.mt5_account || !accountData.mt5_server) {
      throw new Error('Account data is required');
    }

    // Encrypt the password
    const encryptedPassword = await encrypt(password);

    console.log(`Encrypting MT5 password for account ${accountData.mt5_account}`);

    // If setting as primary, unset other primary accounts first
    if (accountData.is_primary) {
      await supabaseClient
        .from('user_mt5_accounts')
        .update({ is_primary: false })
        .eq('user_id', user.id);
    }

    // Check if this is the first account (auto-set as primary)
    const { data: existingAccounts } = await supabaseClient
      .from('user_mt5_accounts')
      .select('id')
      .eq('user_id', user.id);

    const isFirstAccount = !existingAccounts || existingAccounts.length === 0;

    // Save account with encrypted password
    const { data, error } = await supabaseClient
      .from('user_mt5_accounts')
      .insert({
        user_id: user.id,
        account_name: accountData.account_name,
        mt5_account: accountData.mt5_account,
        mt5_password: encryptedPassword,
        mt5_server: accountData.mt5_server,
        broker_name: accountData.broker_name,
        account_size: accountData.account_size,
        is_primary: accountData.is_primary || isFirstAccount,
        is_active: true
      })
      .select()
      .single();

    if (error) throw error;

    console.log(`MT5 account encrypted and saved for user ${user.id}`);

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Account saved securely',
        account_id: data.id
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error) {
    return handleError(error, corsHeaders);
  }
});