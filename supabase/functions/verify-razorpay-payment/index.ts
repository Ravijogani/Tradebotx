import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { createHmac } from "https://deno.land/std@0.177.0/node/crypto.ts";
import { handleError } from "../_shared/error-handler.ts";
import { getAuthUser, unauthorized, forbidden, timingSafeEqual } from "../_shared/auth.ts";

import { corsHeaders } from "../_shared/cors.ts";

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const authUser = await getAuthUser(req);
    if (!authUser) return unauthorized(corsHeaders);

    const { razorpay_order_id, razorpay_payment_id, razorpay_signature, userId, planId } = await req.json();

    // Caller must own the subscription being upgraded — prevents cross-user replay attacks
    if (userId !== authUser.id) return forbidden(corsHeaders);

    const razorpayKeySecret = Deno.env.get('RAZORPAY_KEY_SECRET');

    if (!razorpayKeySecret) {
      throw new Error('Razorpay configuration is missing');
    }

    // Verify signature
    const text = `${razorpay_order_id}|${razorpay_payment_id}`;
    const generatedSignature = createHmac('sha256', razorpayKeySecret)
      .update(text)
      .digest('hex');

    if (!timingSafeEqual(generatedSignature, razorpay_signature)) {
      throw new Error('Invalid payment signature');
    }

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Fetch the plan to record the correct charged amount and to reject unknown plans
    const { data: plan, error: planError } = await supabase
      .from('plans')
      .select('price')
      .eq('id', planId)
      .single();

    if (planError || !plan) {
      throw new Error('Invalid plan ID');
    }

    // Idempotency guard: claim this razorpay_payment_id exactly once via a unique
    // index on payment_history.razorpay_payment_id. If the insert conflicts, this
    // payment was already processed — return success without re-extending the
    // subscription, instead of trusting the client to only call this once.
    const { error: insertError } = await supabase
      .from('payment_history')
      .insert({
        user_id: userId,
        plan_id: planId,
        amount: plan.price,
        currency: 'INR',
        status: 'completed',
        razorpay_order_id,
        razorpay_payment_id,
        description: 'Subscription payment',
      });

    if (insertError) {
      // 23505 = unique_violation — this payment was already recorded/processed.
      if (insertError.code === '23505') {
        console.log('Payment already processed, ignoring replay:', razorpay_payment_id);
        return new Response(JSON.stringify({ success: true, message: 'Payment already verified' }), {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }
      throw insertError;
    }

    // Update user subscription to active
    const { error: updateError } = await supabase
      .from('user_subscriptions')
      .update({
        status: 'active',
        trial_ends_at: null,
        subscription_ends_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days
      })
      .eq('user_id', userId)
      .eq('plan_id', planId);

    if (updateError) throw updateError;

    console.log('Payment verified and subscription activated for user:', userId);

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error) {
    return handleError(error, corsHeaders);
  }
});
