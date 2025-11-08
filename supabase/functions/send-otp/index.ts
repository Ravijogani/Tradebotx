import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface OTPRequest {
  email: string;
  otp: string;
  type: 'signup' | 'login';
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, otp, type }: OTPRequest = await req.json();

    const smtpFrom = Deno.env.get('SMTP_FROM') || 'noreply@algotradex.com';
    const smtpPass = Deno.env.get('SMTP_PASS');

    if (!smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const emailBody = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
          .content { background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px; }
          .otp-code { background: #1e40af; color: white; font-size: 32px; font-weight: bold; padding: 20px; text-align: center; border-radius: 10px; letter-spacing: 8px; margin: 20px 0; }
          .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Verification Code</h1>
          </div>
          <div class="content">
            <p>Hello,</p>
            <p>Your OTP verification code for ${type === 'signup' ? 'signing up' : 'logging in'} to AlgoTradeX is:</p>
            <div class="otp-code">${otp}</div>
            <p>This code will expire in 10 minutes.</p>
            <p><strong>Important:</strong> Never share this code with anyone. AlgoTradeX staff will never ask for your OTP.</p>
            <p>If you didn't request this code, please ignore this email.</p>
          </div>
          <div class="footer">
            <p>© ${new Date().getFullYear()} AlgoTradeX. All rights reserved.</p>
          </div>
        </div>
      </body>
      </html>
    `;

    const emailResponse = await fetch(`https://api.smtp2go.com/v3/email/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Smtp2go-Api-Key': smtpPass,
      },
      body: JSON.stringify({
        sender: smtpFrom,
        to: [email],
        subject: `Your AlgoTradeX Verification Code: ${otp}`,
        html_body: emailBody,
      }),
    });

    const result = await emailResponse.json();
    console.log('OTP email sent successfully:', result);

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error: any) {
    console.error('Error sending OTP email:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
