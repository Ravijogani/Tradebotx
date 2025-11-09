import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface NewUserAlertRequest {
  userEmail: string;
  userName: string;
  signupTimestamp: string;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { userEmail, userName, signupTimestamp }: NewUserAlertRequest = await req.json();

    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM');
    const adminEmail = Deno.env.get('ADMIN_EMAIL') || 'admin@tradebotx.pro';

    if (!smtpHost || !smtpPort || !smtpUser || !smtpPass || !smtpFrom) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = `🎉 New User Signup: ${userName}`;
    const timestamp = new Date(signupTimestamp).toLocaleString('en-US', { 
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
            .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }
            .content { background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }
            .info-box { background: white; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0; border-radius: 4px; }
            .detail-row { padding: 8px 0; border-bottom: 1px solid #e9ecef; }
            .label { font-weight: 600; color: #10b981; }
            .footer { text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }
            .action-btn { display: inline-block; background: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 20px; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0;">🎉 New User Signup!</h1>
              <p style="margin: 10px 0 0 0; opacity: 0.9;">A new user has joined TradeBotX</p>
            </div>
            <div class="content">
              <div class="info-box">
                <h2 style="margin-top: 0; color: #10b981;">User Details</h2>
                <div class="detail-row">
                  <span class="label">Name:</span> ${userName}
                </div>
                <div class="detail-row">
                  <span class="label">Email:</span> ${userEmail}
                </div>
                <div class="detail-row" style="border-bottom: none;">
                  <span class="label">Signup Time:</span> ${timestamp}
                </div>
              </div>
              <p style="color: #6c757d; font-size: 14px;">
                The user will need to complete their setup before they can start trading. You'll receive another notification once they submit their setup for approval.
              </p>
              <a href="https://tradebotx.pro/admin?tab=users" class="action-btn">View User Dashboard</a>
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

    console.log('New user alert sent to admin:', adminEmail);

    return new Response(
      JSON.stringify({ success: true, message: 'Admin alert sent' }),
      { 
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error sending new user alert:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});