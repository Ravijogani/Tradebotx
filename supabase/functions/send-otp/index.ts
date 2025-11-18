import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";
import { getEmailTemplate, otpEmailContent } from "../_shared/email-templates.ts";
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
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    const { email, otpType = 'signup' } = await req.json();

    // Rate limiting: 5 OTP requests per 60 seconds per IP
    const clientIp = req.headers.get('x-forwarded-for') || req.headers.get('x-real-ip') || 'unknown';
    const rateLimitKey = `otp:${clientIp}`;
    
    const { data: rateLimitCheck, error: rateLimitError } = await supabase
      .rpc('check_rate_limit', {
        p_key: rateLimitKey,
        p_max_requests: 5,
        p_window_seconds: 60
      });

    if (rateLimitError) {
      console.error('Rate limit check failed:', rateLimitError);
    } else if (rateLimitCheck && rateLimitCheck.length > 0 && !rateLimitCheck[0].allowed) {
      return new Response(
        JSON.stringify({ error: 'Too many requests. Please try again later.' }),
        {
          status: 429,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    // Email-based rate limiting: 3 OTPs per email per hour
    const emailRateLimitKey = `otp:email:${email}`;
    const { data: emailRateLimitCheck } = await supabase
      .rpc('check_rate_limit', {
        p_key: emailRateLimitKey,
        p_max_requests: 3,
        p_window_seconds: 3600
      });

    if (emailRateLimitCheck && emailRateLimitCheck.length > 0 && !emailRateLimitCheck[0].allowed) {
      return new Response(
        JSON.stringify({ error: 'Too many OTP requests for this email. Please try again later.' }),
        {
          status: 429,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        }
      );
    }

    if (!email) {
      throw new Error('Email is required');
    }

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
    const smtpFrom = Deno.env.get('SMTP_FROM') || smtpUser || 'noreply@tradebotx.com';

    if (!smtpHost || !smtpUser || !smtpPass) {
      throw new Error('SMTP configuration is missing');
    }

    const subjects = {
      'signup': 'Verify Your Email - TradeBotX',
      'login': 'Login Verification - TradeBotX',
      'forgot-password': 'Password Reset - TradeBotX'
    };
    
    const preheaders = {
      'signup': 'Complete your TradeBotX account setup with this verification code',
      'login': 'Your TradeBotX login verification code',
      'forgot-password': 'Reset your TradeBotX password'
    };
    
    const subject = subjects[otpType as keyof typeof subjects] || 'Verification Code - TradeBotX';
    const preheader = preheaders[otpType as keyof typeof preheaders] || 'Your verification code';
    const emailBody = getEmailTemplate(
      otpEmailContent(otpCode, otpType as 'signup' | 'login' | 'forgot-password'),
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
    return handleError(error, corsHeaders);
  }
});
