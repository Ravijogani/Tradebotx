import { serve } from "https://deno.land/std@0.190.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface TrialExpiryRequest {
  email: string;
  userName: string;
  planName: string;
  daysLeft: number;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, userName, planName, daysLeft }: TrialExpiryRequest = await req.json();

    const smtpFrom = Deno.env.get('SMTP_FROM') || 'noreply@algotradex.com';
    const smtpPass = Deno.env.get('SMTP_PASS');

    if (!smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = daysLeft === 0 
      ? `Your AlgoTradeX Trial Has Expired`
      : `Your AlgoTradeX Trial Expires in ${daysLeft} Day${daysLeft > 1 ? 's' : ''}`;

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
          .warning { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; }
          .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>${daysLeft === 0 ? 'Trial Expired' : 'Trial Ending Soon'}</h1>
          </div>
          <div class="content">
            <p>Hello ${userName},</p>
            ${daysLeft === 0 
              ? `<div class="warning"><strong>Your trial period for the ${planName} plan has ended.</strong></div>
                 <p>To continue using AlgoTradeX and keep your trading bots running, please upgrade to a paid plan.</p>`
              : `<div class="warning"><strong>Your trial period for the ${planName} plan will expire in ${daysLeft} day${daysLeft > 1 ? 's' : ''}.</strong></div>
                 <p>Don't let your automated trading stop! Upgrade now to continue enjoying:</p>`
            }
            <ul>
              <li>24/7 automated trading</li>
              <li>Advanced AI strategies</li>
              <li>Real-time performance analytics</li>
              <li>Priority support</li>
            </ul>
            <center>
              <a href="${Deno.env.get('SUPABASE_URL')?.replace('.supabase.co', '')}/pricing" class="button">Upgrade Now</a>
            </center>
            <p>Questions? Our support team is here to help!</p>
            <p>Best regards,<br>The AlgoTradeX Team</p>
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
        subject: subject,
        html_body: emailBody,
      }),
    });

    const result = await emailResponse.json();
    console.log('Trial expiry email sent successfully:', result);

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  } catch (error: any) {
    console.error('Error sending trial expiry email:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
