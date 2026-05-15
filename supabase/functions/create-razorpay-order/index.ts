import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { z } from "https://deno.land/x/zod@v3.22.4/mod.ts";
import { getAuthUser, unauthorized, forbidden } from "../_shared/auth.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Require authenticated user
    const authUser = await getAuthUser(req);
    if (!authUser) return unauthorized(corsHeaders);

    // Validate input
    const requestSchema = z.object({
      amount: z.number().positive(),
      planId: z.string().uuid(),
      userId: z.string().uuid(),
    });
    
    const { amount, planId, userId } = requestSchema.parse(await req.json());

    // Caller must own the order they are creating
    if (userId !== authUser.id) return forbidden(corsHeaders);

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL');
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    
    if (!supabaseUrl || !supabaseServiceKey) {
      throw new Error('Supabase configuration is missing');
    }
    
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Fetch actual plan price from database
    const { data: plan, error: planError } = await supabase
      .from('plans')
      .select('price')
      .eq('id', planId)
      .single();

    if (planError || !plan) {
      throw new Error('Invalid plan ID');
    }

    // Validate amount matches plan price (amount is in paise, price is in rupees)
    const expectedAmount = plan.price * 100;
    if (amount !== expectedAmount) {
      throw new Error('Payment amount does not match plan price');
    }

    const razorpayKeyId = Deno.env.get('RAZORPAY_KEY_ID');
    const razorpayKeySecret = Deno.env.get('RAZORPAY_KEY_SECRET');

    if (!razorpayKeyId || !razorpayKeySecret) {
      throw new Error('Razorpay configuration is missing');
    }

    const auth = btoa(`${razorpayKeyId}:${razorpayKeySecret}`);

    const orderResponse = await fetch('https://api.razorpay.com/v1/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${auth}`,
      },
      body: JSON.stringify({
        amount: amount, // amount in paise
        currency: 'INR',
        receipt: `order_${userId}_${Date.now()}`,
        notes: {
          plan_id: planId,
          user_id: userId,
        },
      }),
    });

    const orderData = await orderResponse.json();

    if (!orderResponse.ok) {
      throw new Error(orderData.error?.description || 'Failed to create Razorpay order');
    }

    console.log('Razorpay order created:', orderData.id);

    return new Response(JSON.stringify(orderData), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error: any) {
    console.error('Error creating Razorpay order:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
