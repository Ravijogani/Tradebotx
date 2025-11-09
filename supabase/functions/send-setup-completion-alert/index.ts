import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface SetupCompletionAlertRequest {
  userEmail: string;
  userName: string;
  setupDetails: {
    brokerName?: string;
    mt5Account: string;
    accountSize: number;
    planType: string;
  };
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { userEmail, userName, setupDetails }: SetupCompletionAlertRequest = await req.json();

    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM');
    const adminEmail = Deno.env.get('ADMIN_EMAIL') || 'admin@tradebotx.pro';

    if (!smtpHost || !smtpPort || !smtpUser || !smtpPass || !smtpFrom) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = `📋 Setup Completed: ${userName} - Awaiting Approval`;
    const timestamp = new Date().toLocaleString('en-US', { 
      dateStyle: 'full', 
      timeStyle: 'long' 
    });

    const emailBody = `
      <!DOCTYPE html>
      <html>
        <head>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .header { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }
            .content { background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }
            .info-box { background: white; border-left: 4px solid #3b82f6; padding: 20px; margin: 20px 0; border-radius: 4px; }
            .detail-row { padding: 8px 0; border-bottom: 1px solid #e9ecef; }
            .label { font-weight: 600; color: #3b82f6; }
            .warning-box { background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; border-radius: 4px; }
            .footer { text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }
            .action-btn { display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 20px; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0;">📋 Setup Completed - Action Required</h1>
              <p style="margin: 10px 0 0 0; opacity: 0.9;">User has completed their account setup</p>
            </div>
            <div class="content">
              <div class="warning-box">
                <strong>⚠️ Action Required:</strong> This user has completed their setup and is waiting for admin approval before they can start trading.
              </div>
              
              <div class="info-box">
                <h2 style="margin-top: 0; color: #3b82f6;">User Information</h2>
                <div class="detail-row">
                  <span class="label">Name:</span> ${userName}
                </div>
                <div class="detail-row">
                  <span class="label">Email:</span> ${userEmail}
                </div>
                <div class="detail-row">
                  <span class="label">Submission Time:</span> ${timestamp}
                </div>
              </div>
              
              <div class="info-box">
                <h2 style="margin-top: 0; color: #3b82f6;">Trading Setup Details</h2>
                <div class="detail-row">
                  <span class="label">Plan Type:</span> ${setupDetails.planType}
                </div>
                ${setupDetails.brokerName ? `
                <div class="detail-row">
                  <span class="label">Broker:</span> ${setupDetails.brokerName}
                </div>
                ` : ''}
                <div class="detail-row">
                  <span class="label">MT5 Account:</span> ${setupDetails.mt5Account}
                </div>
                <div class="detail-row" style="border-bottom: none;">
                  <span class="label">Account Size:</span> $${setupDetails.accountSize.toLocaleString()}
                </div>
              </div>
              
              <p style="color: #6c757d; font-size: 14px;">
                Please review the user's setup details and approve or reject their application. The user cannot start trading until their setup is approved.
              </p>
              
              <a href="https://tradebotx.pro/admin?tab=users" class="action-btn">Review & Approve Setup</a>
            </div>
            <div class="footer">
              <p>TradeBotX Admin System | Automated Notification</p>
            </div>
          </div>
        </body>
      </html>
    `;

    const client = new SMTPClient({
      connection: {
        hostname: smtpHost,
        port: parseInt(smtpPort),
        tls: true,
        auth: {
          username: smtpUser,
          password: smtpPass,
        },
      },
    });

    await client.send({
      from: smtpFrom,
      to: adminEmail,
      subject: subject,
      html: emailBody,
    });

    await client.close();

    console.log('Setup completion alert sent to admin:', adminEmail);

    return new Response(
      JSON.stringify({ success: true, message: 'Setup completion alert sent' }),
      { 
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error sending setup completion alert:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});