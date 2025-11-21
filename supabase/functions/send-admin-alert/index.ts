import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface AdminAlertRequest {
  actionType: string;
  performedBy: string;
  targetUser?: string;
  details: string;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { actionType, performedBy, targetUser, details }: AdminAlertRequest = await req.json();
    const adminEmail = Deno.env.get('ADMIN_EMAIL') || "tradebotxsuppo@gmail.com";
    const adminEmailCC = Deno.env.get('ADMIN_EMAIL_CC');

    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM');

    if (!smtpHost || !smtpPort || !smtpUser || !smtpPass || !smtpFrom) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = `Admin Alert: ${actionType}`;
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
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }
            .content { background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }
            .alert-box { background: white; border-left: 4px solid #667eea; padding: 20px; margin: 20px 0; border-radius: 4px; }
            .detail-row { padding: 8px 0; border-bottom: 1px solid #e9ecef; }
            .label { font-weight: 600; color: #667eea; }
            .footer { text-align: center; margin-top: 30px; color: #6c757d; font-size: 12px; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0;">🔔 Admin Action Alert</h1>
              <p style="margin: 10px 0 0 0; opacity: 0.9;">TradeBotX Admin Notification</p>
            </div>
            <div class="content">
              <div class="alert-box">
                <h2 style="margin-top: 0; color: #667eea;">${actionType}</h2>
                <div class="detail-row">
                  <span class="label">Performed By:</span> ${performedBy}
                </div>
                ${targetUser ? `<div class="detail-row"><span class="label">Target User:</span> ${targetUser}</div>` : ''}
                <div class="detail-row">
                  <span class="label">Timestamp:</span> ${timestamp}
                </div>
                <div class="detail-row" style="border-bottom: none;">
                  <span class="label">Details:</span><br/>
                  ${details}
                </div>
              </div>
              <p style="color: #6c757d; font-size: 14px; margin-top: 20px;">
                This is an automated notification for critical admin actions performed on your TradeBotX platform.
              </p>
            </div>
            <div class="footer">
              <p>TradeBotX Admin System | Automated Alert</p>
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

    // Prepare recipients
    const recipients = [adminEmail];
    if (adminEmailCC) {
      recipients.push(adminEmailCC);
    }

    // Send to all admin emails
    await client.send({
      from: smtpFrom,
      to: recipients.join(', '),
      subject: subject,
      html: emailBody,
    });

    await client.close();

    console.log('Admin alert email sent successfully to:', recipients.join(', '));

    return new Response(
      JSON.stringify({ success: true, message: 'Admin alert sent to all admins' }),
      { 
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error sending admin alert:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});
