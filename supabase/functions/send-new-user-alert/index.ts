import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";
import { z } from "https://deno.land/x/zod@v3.22.4/mod.ts";
import { handleError } from "../_shared/error-handler.ts";

import { getAuthUser, isCronAuthorized, unauthorized, forbidden } from "../_shared/auth.ts";

import { corsHeaders } from "../_shared/cors.ts";

const newUserAlertSchema = z.object({
  userEmail: z.string().email().max(255),
  userName: z.string().min(1).max(100).regex(/^[a-zA-Z0-9\s\-.]+$/, 'Invalid characters in name'),
  signupTimestamp: z.string()
});

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Auth: server-side calls with CRON_SECRET, or an admin user JWT
    if (!isCronAuthorized(req)) {
      const authUser = await getAuthUser(req);
      if (!authUser) return unauthorized(corsHeaders);
      const { userHasRole } = await import("../_shared/auth.ts");
      const isAdmin = await userHasRole(authUser.id, 'admin');
      if (!isAdmin) return forbidden(corsHeaders);
    }
    // --- AUTH OK ---

    const requestBody = await req.json();
    const { userEmail, userName, signupTimestamp } = newUserAlertSchema.parse(requestBody);

    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM');
    const adminEmail = Deno.env.get('ADMIN_EMAIL') || "tradebotxsuppo@gmail.com";
    const adminEmailCC = Deno.env.get('ADMIN_EMAIL_CC');

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

    console.log('New user alert sent to admins:', recipients.join(', '));

    return new Response(
      JSON.stringify({ success: true, message: 'Admin alert sent to all admins' }),
      { 
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    return handleError(error, corsHeaders);
  }
});