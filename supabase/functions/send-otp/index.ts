import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, otpType = 'signup' } = await req.json();

    if (!email) {
      throw new Error('Email is required');
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Generate OTP
    const { data: otpData, error: otpError } = await supabase
      .rpc('generate_otp', {
        p_email: email,
        p_otp_type: otpType
      });

    if (otpError) {
      console.error('Error generating OTP:', otpError);
      throw otpError;
    }

    const otpCode = otpData[0]?.otp_code;
    console.log('OTP generated for:', email, 'Type:', otpType);

    // Get SMTP configuration
    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = parseInt(Deno.env.get('SMTP_PORT') || '587');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM') || smtpUser || 'noreply@algotradex.com';

    if (!smtpHost || !smtpUser || !smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const subject = otpType === 'signup' ? 'Verify Your Email - AlgoTradeX' : 'Login Verification Code - AlgoTradeX';
    const emailBody = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }
          .container { max-width: 600px; margin: 0 auto; padding: 20px; }
          .header { background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
          .content { background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }
          .otp-box { background: white; border: 2px solid #4F46E5; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }
          .otp-code { font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 8px; }
          .warning { color: #dc2626; font-size: 14px; margin-top: 20px; }
          .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #6b7280; }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>🚀 AlgoTradeX</h1>
            <p>${otpType === 'signup' ? 'Email Verification' : 'Login Verification'}</p>
          </div>
          <div class="content">
            <p>Hello,</p>
            <p>${otpType === 'signup' ? 'Thank you for signing up with AlgoTradeX!' : 'You are attempting to log in to your AlgoTradeX account.'}</p>
            <p>Your verification code is:</p>
            
            <div class="otp-box">
              <div class="otp-code">${otpCode}</div>
            </div>
            
            <p><strong>This code will expire in 2 minutes.</strong></p>
            
            <div class="warning">
              ⚠️ If you didn't request this code, please ignore this email and ensure your account is secure.
            </div>
            
            <p>Best regards,<br>The AlgoTradeX Team</p>
          </div>
          <div class="footer">
            <p>This is an automated message, please do not reply.</p>
            <p>&copy; ${new Date().getFullYear()} AlgoTradeX. All rights reserved.</p>
          </div>
        </div>
      </body>
      </html>
    `;

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
      
      console.log('OTP email sent successfully to:', email);
      
      await client.close();
    } catch (emailError: any) {
      console.error('SMTP send error:', emailError);
      throw new Error(`Failed to send email: ${emailError?.message || 'Unknown error'}`);
    }

    return new Response(
      JSON.stringify({ 
        success: true, 
        message: 'OTP sent successfully',
        expiresIn: '2 minutes'
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  } catch (error: any) {
    console.error('Error sending OTP email:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});
