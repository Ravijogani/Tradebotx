import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";
import { getEmailTemplate, welcomeEmailContent } from "../_shared/email-templates.ts";
import { handleError } from "../_shared/error-handler.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { to, userName } = await req.json();

    if (!to || !userName) {
      throw new Error('Email (to) and userName are required');
    }

    console.log('Sending welcome email to:', to);

    // Get SMTP configuration
    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = parseInt(Deno.env.get('SMTP_PORT') || '587');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM') || smtpUser || 'noreply@tradebotx.com';

    if (!smtpHost || !smtpUser || !smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = 'Welcome to TradeBotX - Your Trading Journey Begins!';
    const preheader = 'Get started with automated trading in minutes';
    const emailBody = getEmailTemplate(
      welcomeEmailContent(userName),
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
        to: to,
        subject: subject,
        content: emailBody,
        html: emailBody,
      });
      
      console.log('Welcome email sent successfully to:', to);
      
      await client.close();
      
      // Send admin alert about new user signup (don't block welcome email on failure)
      try {
        const adminEmail = Deno.env.get('ADMIN_EMAIL');
        if (adminEmail) {
          const adminSmtpClient = new SMTPClient({
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
          
          const timestamp = new Date().toLocaleString('en-US', {
          dateStyle: 'full', 
          timeStyle: 'long' 
        });

        const adminEmailBody = `
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
                      <span class="label">Email:</span> ${to}
                    </div>
                    <div class="detail-row" style="border-bottom: none;">
                      <span class="label">Signup Time:</span> ${timestamp}
                    </div>
                  </div>
                  <p style="color: #6c757d; font-size: 14px;">
                    The user will need to complete their setup before they can start trading. You'll receive another notification once they submit their setup for approval.
                  </p>
                </div>
                <div class="footer">
                  <p>TradeBotX Admin System | Automated Notification</p>
                </div>
              </div>
            </body>
          </html>
        `;

        await adminSmtpClient.send({
          from: smtpFrom,
          to: adminEmail,
          subject: `🎉 New User Signup: ${userName}`,
          html: adminEmailBody,
        });
        
          await adminSmtpClient.close();
          console.log('New user alert sent to admin');
        } else {
          console.log('ADMIN_EMAIL not configured, skipping admin alert');
        }
      } catch (adminAlertError) {
        console.error('Failed to send admin alert (non-blocking):', adminAlertError);
      }
      
    } catch (emailError: any) {
      console.error('SMTP send error:', emailError);
      throw new Error(`Failed to send email: ${emailError?.message || 'Unknown error'}`);
    }

    return new Response(
      JSON.stringify({ 
        success: true, 
        message: 'Welcome email sent successfully'
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    return handleError(error, corsHeaders);
  }
});
