import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { createHmac } from "https://deno.land/std@0.177.0/node/crypto.ts";

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
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    );

    const { razorpay_order_id, razorpay_payment_id, razorpay_signature } = await req.json();

    console.log('Verifying invoice payment:', { razorpay_order_id, razorpay_payment_id });

    // Verify signature
    const keySecret = Deno.env.get('RAZORPAY_KEY_SECRET');
    if (!keySecret) {
      throw new Error('Razorpay key secret not configured');
    }

    const generatedSignature = createHmac('sha256', keySecret)
      .update(`${razorpay_order_id}|${razorpay_payment_id}`)
      .digest('hex');

    if (generatedSignature !== razorpay_signature) {
      throw new Error('Invalid payment signature');
    }

    // Find invoice by razorpay_order_id
    const { data: invoice, error: invoiceError } = await supabaseClient
      .from('invoices')
      .select('*')
      .eq('razorpay_order_id', razorpay_order_id)
      .single();

    if (invoiceError || !invoice) {
      throw new Error('Invoice not found');
    }

    // Update invoice status
    const { error: updateError } = await supabaseClient
      .from('invoices')
      .update({
        status: 'paid',
        razorpay_payment_id,
        paid_at: new Date().toISOString(),
        payment_verified_at: new Date().toISOString(),
      })
      .eq('id', invoice.id);

    if (updateError) {
      throw updateError;
    }

    // Create payment history record
    await supabaseClient
      .from('payment_history')
      .insert({
        user_id: invoice.user_id,
        amount: invoice.amount,
        currency: invoice.currency,
        status: 'completed',
        razorpay_order_id,
        razorpay_payment_id,
        description: `Payment for Invoice #${invoice.invoice_number}`,
        invoice_url: invoice.pdf_url,
      });

    // Send payment confirmation email
    try {
      const { data: userData } = await supabaseClient
        .from('profiles')
        .select('email, full_name')
        .eq('id', invoice.user_id)
        .single();

      if (userData) {
        await supabaseClient.functions.invoke('send-custom-email', {
          body: {
            to: [userData.email],
            subject: `Payment Confirmed - Invoice #${invoice.invoice_number}`,
            message: `
Dear ${userData.full_name},

Your payment for Invoice #${invoice.invoice_number} has been successfully processed.

Amount Paid: ₹${invoice.amount.toFixed(2)}
Payment ID: ${razorpay_payment_id}
Date: ${new Date().toLocaleString()}

Thank you for your payment!

Best regards,
TradeBotX Team
            `,
          },
        });
      }
    } catch (emailError) {
      console.error('Failed to send payment confirmation email:', emailError);
    }

    console.log('Invoice payment verified and updated successfully');

    return new Response(
      JSON.stringify({ 
        success: true,
        message: 'Payment verified successfully'
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200 
      }
    );
  } catch (error) {
    console.error('Error in verify-invoice-payment function:', error);
    return new Response(
      JSON.stringify({ 
        error: error instanceof Error ? error.message : 'Unknown error',
        success: false
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 400
      }
    );
  }
});