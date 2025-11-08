import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { encrypt } from "../_shared/crypto-utils.ts";

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
      })
      .select()
      .single();

    if (error) throw error;

    console.log(`Password encrypted and saved for user ${user.id}`);

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
    console.error('Error encrypting password:', error);
    return new Response(
      JSON.stringify({
        success: false,
        error: error.message || 'Failed to save setup',
      }),
      {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});