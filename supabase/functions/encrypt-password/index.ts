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

    const { password, setupData } = await req.json();

    if (!password) {
      throw new Error('Password is required');
    }

    // Encrypt the password
    const encryptedPassword = await encrypt(password);

    // Save setup data with encrypted password
    const { data, error } = await supabaseClient
      .from('user_setup')
      .upsert({
        user_id: user.id,
        ...setupData,
        mt5_password: encryptedPassword,
        is_completed: true,
        submitted_for_approval_at: new Date().toISOString()
      }, {
        onConflict: 'user_id'
      })
      .select()
      .single();

    if (error) throw error;

    console.log(`Password encrypted and saved for user ${user.id}`);

    // Send admin alert about setup completion
    try {
      const { data: profileData } = await supabaseClient
        .from('profiles')
        .select('email, full_name')
        .eq('id', user.id)
        .single();

      const { data: subscriptionData } = await supabaseClient
        .from('user_subscriptions')
        .select('plans(plan_type)')
        .eq('user_id', user.id)
        .single();

      if (profileData) {
        const planType = (subscriptionData?.plans as any)?.plan_type || 'free';
        
        await supabaseClient.functions.invoke('send-setup-completion-alert', {
          body: {
            userEmail: profileData.email,
            userName: profileData.full_name || 'User',
            setupDetails: {
              brokerName: setupData.broker_name,
              mt5Account: setupData.mt5_account,
              accountSize: setupData.account_size,
              planType: planType
            }
          }
        });
      }
    } catch (alertError) {
      console.error('Failed to send setup completion alert:', alertError);
      // Don't fail the setup if alert fails
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: 'Setup saved securely',
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error: any) {
    return handleError(error, corsHeaders);
  }
});