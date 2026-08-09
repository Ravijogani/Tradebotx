import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";
import { getEmailTemplate, loginAlertContent } from "../_shared/email-templates.ts";

import { getAuthUser, isCronAuthorized, unauthorized, forbidden } from "../_shared/auth.ts";

import { corsHeaders } from "../_shared/cors.ts";

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Auth: allow authenticated user whose email matches `email`, or server-side calls with CRON_SECRET
    if (!isCronAuthorized(req)) {
      const authUser = await getAuthUser(req);
      if (!authUser) return unauthorized(corsHeaders);
      const body = await req.clone().json().catch(() => ({}));
      const targetEmail = body.email;
      if (typeof targetEmail === 'string' && targetEmail.toLowerCase() !== (authUser.email || '').toLowerCase()) {
        return forbidden(corsHeaders);
      }
    }
    // --- AUTH OK ---

    const { email, ipAddress, location, timestamp } = await req.json();

    if (!email || !ipAddress) {
      throw new Error('Email and ipAddress are required');
    }

    console.log('Sending login alert to:', email);

    // Get SMTP configuration
    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = parseInt(Deno.env.get('SMTP_PORT') || '587');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM') || smtpUser || 'security@tradebotx.com';

    if (!smtpHost || !smtpUser || !smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = 'New Login Detected - TradeBotX Security Alert';
    const preheader = 'We detected a new login to your TradeBotX account';
    const emailBody = getEmailTemplate(
      loginAlertContent(
        ipAddress,
        location || 'Unknown',
        timestamp || new Date().toLocaleString()
      ),
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
      
      console.log('Login alert sent successfully to:', email);
      
      await client.close();
    } catch (emailError) {
      console.error('SMTP send error:', emailError);
      throw new Error(`Failed to send email: ${emailError?.message || 'Unknown error'}`);
    }

    return new Response(
      JSON.stringify({ 
        success: true, 
        message: 'Login alert sent successfully'
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('Error sending login alert:', error);
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
