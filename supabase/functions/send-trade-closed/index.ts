import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";
import { getEmailTemplate, tradeClosedContent } from "../_shared/email-templates.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, symbol, tradeType, entryPrice, exitPrice, profitLoss, profitLossPercent } = await req.json();

    if (!email || !symbol || !tradeType || profitLoss === undefined) {
      throw new Error('Email, symbol, tradeType, and profitLoss are required');
    }

    console.log('Sending trade closed email to:', email);

    // Get SMTP configuration
    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = parseInt(Deno.env.get('SMTP_PORT') || '587');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM') || smtpUser || 'trades@tradebotx.com';

    if (!smtpHost || !smtpUser || !smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const isProfit = profitLoss > 0;
    const subject = isProfit 
      ? `🎉 Profitable Trade Closed: ${symbol} (+$${profitLoss.toFixed(2)})`
      : `📉 Trade Closed: ${symbol} (-$${Math.abs(profitLoss).toFixed(2)})`;
    const preheader = `Your ${tradeType} trade closed with ${isProfit ? 'profit' : 'loss'} of $${profitLoss.toFixed(2)}`;
    const emailBody = getEmailTemplate(
      tradeClosedContent(symbol, tradeType, entryPrice, exitPrice, profitLoss, profitLossPercent),
      preheader
    );

    // Create SMTP client and send email
    const client = new SMTPClient({
      connection: {
        hostname: smtpHost,
        port: smtpPort,
        tls: true,
        auth: {
          username: smtpUser,
          password: smtpPass,
        },
      },
    });

    try {
      await client.send({
        from: smtpFrom,
        to: email,
        subject: subject,
        content: emailBody,
        html: emailBody,
      });
      
      console.log('Trade closed email sent successfully to:', email);
      
      await client.close();
    } catch (emailError: any) {
      console.error('SMTP send error:', emailError);
      throw new Error(`Failed to send email: ${emailError?.message || 'Unknown error'}`);
    }

    return new Response(
      JSON.stringify({ 
        success: true, 
        message: 'Trade closed email sent successfully'
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error sending trade closed email:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});