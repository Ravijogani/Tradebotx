import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface EmailRequest {
  to: string;
  userName: string;
  planName: string;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { to, userName, planName }: EmailRequest = await req.json();

    // SMTP configuration - will be set up by user
    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM') || 'noreply@algotradex.com';

    if (!smtpHost || !smtpUser || !smtpPass) {
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
          .button { display: inline-block; background: #1e40af; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
          .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Welcome to AlgoTradeX!</h1>
          </div>
          <div class="content">
            <p>Hello ${userName},</p>
            <p>Thank you for joining AlgoTradeX! We're excited to have you on board.</p>
            <p>You've successfully signed up for the <strong>${planName}</strong> plan.</p>
            <p>Here's what you can do next:</p>
            <ul>
              <li>Complete your account setup by connecting your MT5 account</li>
              <li>Configure your risk management parameters</li>
              <li>Select a trading strategy that matches your goals</li>
              <li>Start automated trading and watch your profits grow</li>
            </ul>
            <center>
              <a href="${Deno.env.get('SUPABASE_URL')?.replace('.supabase.co', '')}/dashboard" class="button">Go to Dashboard</a>
            </center>
            <p>If you have any questions, feel free to reach out to our support team.</p>
            <p>Happy Trading!<br>The AlgoTradeX Team</p>
          </div>
          <div class="footer">
            <p>© ${new Date().getFullYear()} AlgoTradeX. All rights reserved.</p>
            <p>This is an automated message, please do not reply.</p>
          </div>
        </div>
      </body>
      </html>
    `;

    // Send email using SMTP
    const emailResponse = await fetch(`https://api.smtp2go.com/v3/email/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Smtp2go-Api-Key': smtpPass,
      },
      body: JSON.stringify({
        sender: smtpFrom,
        to: [to],
        subject: `Welcome to AlgoTradeX - ${planName}`,
        html_body: emailBody,
      }),
    });

    const result = await emailResponse.json();
    console.log('Email sent successfully:', result);

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error: any) {
    console.error('Error sending email:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
