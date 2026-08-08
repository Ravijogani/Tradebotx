import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { SMTPClient } from "https://deno.land/x/denomailer@1.6.0/mod.ts";

import { corsHeaders } from "../_shared/cors.ts";

// Email sequence configuration (hours after signup)
const EMAIL_SEQUENCE = [
  { sequence: 1, hoursAfterSignup: 24, type: 'reminder', subject: 'Complete Your TradeBotX Setup - Just a Few Steps Away!' },
  { sequence: 2, hoursAfterSignup: 48, type: 'value_prop', subject: 'Your Trading Bot is Waiting - Here\'s What You\'re Missing' },
  { sequence: 3, hoursAfterSignup: 72, type: 'support', subject: 'Need Help? We\'re Here for You - TradeBotX Support' },
  { sequence: 4, hoursAfterSignup: 120, type: 'urgency', subject: 'Don\'t Miss Out - Start Automated Trading Today!' },
  { sequence: 5, hoursAfterSignup: 168, type: 'final', subject: 'Final Reminder: Your TradeBotX Account Awaits' },
];

function getEmailTemplate(sequence: number, userName: string): string {
  const templates: Record<number, string> = {
    1: `
      <!DOCTYPE html>
      <html>
        <head>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.8; color: #333; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center; }
            .content { padding: 40px 30px; background: #ffffff; }
            .cta-button { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .steps { background: #f8f9fa; padding: 25px; border-radius: 10px; margin: 25px 0; }
            .step { display: flex; align-items: flex-start; margin: 15px 0; }
            .step-number { background: #667eea; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 15px; flex-shrink: 0; }
            .footer { background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }
            .support-box { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; border-radius: 10px; margin: 25px 0; text-align: center; }
            .support-box a { color: white; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">Welcome to TradeBotX! 🚀</h1>
              <p style="margin: 15px 0 0 0; opacity: 0.9; font-size: 16px;">Your automated trading journey is just a few steps away</p>
            </div>
            <div class="content">
              <p>Hi ${userName},</p>
              <p>We noticed you signed up for TradeBotX but haven't completed your setup yet. Don't worry - it only takes a few minutes!</p>
              
              <div class="steps">
                <h3 style="margin-top: 0; color: #667eea;">Complete Your Setup in 3 Easy Steps:</h3>
                <div class="step">
                  <div class="step-number">1</div>
                  <div><strong>Connect Your MT5 Account</strong><br/>Enter your MT5 credentials to link your trading account</div>
                </div>
                <div class="step">
                  <div class="step-number">2</div>
                  <div><strong>Set Your Risk Parameters</strong><br/>Choose your risk per trade and maximum positions</div>
                </div>
                <div class="step">
                  <div class="step-number">3</div>
                  <div><strong>Choose a Strategy</strong><br/>Select from our AI-powered trading strategies</div>
                </div>
              </div>

              <div style="text-align: center;">
                <a href="https://tradebotx.com/dashboard" class="cta-button">Complete My Setup →</a>
              </div>

              <div class="support-box">
                <p style="margin: 0; font-size: 16px;">💬 Need help? Contact our support team on Telegram!</p>
                <p style="margin: 10px 0 0 0;"><a href="https://t.me/tradebotxsuppo">@tradebotxsuppo</a></p>
              </div>
            </div>
            <div class="footer">
              <p>TradeBotX - Automated Trading Made Simple</p>
              <p style="font-size: 12px; color: #adb5bd;">You're receiving this because you signed up for TradeBotX.</p>
            </div>
          </div>
        </body>
      </html>
    `,
    
    2: `
      <!DOCTYPE html>
      <html>
        <head>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.8; color: #333; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center; }
            .content { padding: 40px 30px; background: #ffffff; }
            .cta-button { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .benefit-card { background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 15px 0; border-left: 4px solid #667eea; }
            .footer { background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }
            .support-box { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; border-radius: 10px; margin: 25px 0; text-align: center; }
            .support-box a { color: white; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">You're Missing Out! 📈</h1>
              <p style="margin: 15px 0 0 0; opacity: 0.9; font-size: 16px;">Here's what other traders are achieving with TradeBotX</p>
            </div>
            <div class="content">
              <p>Hi ${userName},</p>
              <p>Your TradeBotX account is set up and ready - but you haven't activated your trading bot yet!</p>
              <p>Here's what you're missing:</p>
              
              <div class="benefit-card">
                <h4 style="margin-top: 0; color: #667eea;">🤖 24/7 Automated Trading</h4>
                <p style="margin-bottom: 0;">Our AI-powered bot trades even while you sleep, capturing opportunities around the clock.</p>
              </div>
              
              <div class="benefit-card">
                <h4 style="margin-top: 0; color: #667eea;">📊 Advanced AI Analysis</h4>
                <p style="margin-bottom: 0;">Gemini AI analyzes market sentiment while our confluence engine ensures technical precision.</p>
              </div>
              
              <div class="benefit-card">
                <h4 style="margin-top: 0; color: #667eea;">🛡️ Risk Management</h4>
                <p style="margin-bottom: 0;">Automated position sizing and stop-losses protect your capital.</p>
              </div>
              
              <div class="benefit-card">
                <h4 style="margin-top: 0; color: #667eea;">📱 Real-time Alerts</h4>
                <p style="margin-bottom: 0;">Get instant Telegram notifications for every trade executed.</p>
              </div>

              <div style="text-align: center;">
                <a href="https://tradebotx.com/dashboard" class="cta-button">Start Trading Now →</a>
              </div>

              <div class="support-box">
                <p style="margin: 0; font-size: 16px;">💬 Questions? Our team is here to help!</p>
                <p style="margin: 10px 0 0 0;"><a href="https://t.me/tradebotxsuppo">Chat with us on Telegram →</a></p>
              </div>
            </div>
            <div class="footer">
              <p>TradeBotX - Automated Trading Made Simple</p>
            </div>
          </div>
        </body>
      </html>
    `,
    
    3: `
      <!DOCTYPE html>
      <html>
        <head>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.8; color: #333; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 40px 30px; text-align: center; }
            .content { padding: 40px 30px; background: #ffffff; }
            .cta-button { display: inline-block; background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white !important; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .help-box { background: #e8f5e9; padding: 25px; border-radius: 10px; margin: 25px 0; border: 1px solid #c8e6c9; }
            .faq-item { margin: 20px 0; padding-bottom: 20px; border-bottom: 1px solid #e9ecef; }
            .faq-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
            .footer { background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">We're Here to Help! 🤝</h1>
              <p style="margin: 15px 0 0 0; opacity: 0.9; font-size: 16px;">Let us guide you through the setup process</p>
            </div>
            <div class="content">
              <p>Hi ${userName},</p>
              <p>We noticed you haven't completed your TradeBotX setup. Is there something holding you back? We're here to help!</p>
              
              <div class="help-box">
                <h3 style="margin-top: 0; color: #28a745;">💬 Get Personal Assistance</h3>
                <p>Reach out to our support team directly on Telegram. We'll walk you through every step!</p>
                <p style="font-size: 18px; font-weight: bold; margin: 0;"><a href="https://t.me/tradebotxsuppo" style="color: #28a745;">@tradebotxsuppo</a></p>
              </div>
              
              <h3>Common Questions:</h3>
              
              <div class="faq-item">
                <strong>❓ Where do I find my MT5 credentials?</strong>
                <p style="margin-bottom: 0;">Check your broker email or log into your broker's portal. Look for MT5 server, login, and password.</p>
              </div>
              
              <div class="faq-item">
                <strong>❓ How do I get my Telegram Chat ID?</strong>
                <p style="margin-bottom: 0;">Search for @userinfobot on Telegram, send /start, and copy the ID shown.</p>
              </div>
              
              <div class="faq-item">
                <strong>❓ Is my account data secure?</strong>
                <p style="margin-bottom: 0;">Yes! All credentials are encrypted with industry-standard security protocols.</p>
              </div>

              <div style="text-align: center;">
                <a href="https://t.me/tradebotxsuppo" class="cta-button">Get Help on Telegram →</a>
              </div>
            </div>
            <div class="footer">
              <p>TradeBotX - Automated Trading Made Simple</p>
            </div>
          </div>
        </body>
      </html>
    `,
    
    4: `
      <!DOCTYPE html>
      <html>
        <head>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.8; color: #333; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%); color: white; padding: 40px 30px; text-align: center; }
            .content { padding: 40px 30px; background: #ffffff; }
            .cta-button { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .urgency-box { background: #fff3cd; padding: 25px; border-radius: 10px; margin: 25px 0; border-left: 4px solid #ffc107; }
            .footer { background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }
            .support-box { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; padding: 20px; border-radius: 10px; margin: 25px 0; text-align: center; }
            .support-box a { color: white; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">Time is Ticking! ⏰</h1>
              <p style="margin: 15px 0 0 0; opacity: 0.9; font-size: 16px;">Don't let opportunities pass you by</p>
            </div>
            <div class="content">
              <p>Hi ${userName},</p>
              <p>It's been 5 days since you signed up, and your trading bot is still waiting to be activated!</p>
              
              <div class="urgency-box">
                <h3 style="margin-top: 0; color: #856404;">⚡ Every Day You Wait...</h3>
                <p style="margin-bottom: 0;">...is another day of potential trading opportunities missed. Our AI analyzes markets 24/7 and executes trades with precision timing.</p>
              </div>
              
              <p>Setting up takes less than 5 minutes. Here's all you need:</p>
              <ul>
                <li>Your MT5 login credentials (from your broker)</li>
                <li>Your Telegram Chat ID (for trade alerts)</li>
                <li>Your preferred risk settings</li>
              </ul>
              
              <p><strong>That's it!</strong> Once configured, the bot handles everything else automatically.</p>

              <div style="text-align: center;">
                <a href="https://tradebotx.com/dashboard" class="cta-button">Complete Setup Now →</a>
              </div>

              <div class="support-box">
                <p style="margin: 0; font-size: 16px;">💬 Stuck somewhere? Let us help!</p>
                <p style="margin: 10px 0 0 0;"><a href="https://t.me/tradebotxsuppo">@tradebotxsuppo on Telegram</a></p>
              </div>
            </div>
            <div class="footer">
              <p>TradeBotX - Automated Trading Made Simple</p>
            </div>
          </div>
        </body>
      </html>
    `,
    
    5: `
      <!DOCTYPE html>
      <html>
        <head>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.8; color: #333; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 0 auto; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px 30px; text-align: center; }
            .content { padding: 40px 30px; background: #ffffff; }
            .cta-button { display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white !important; padding: 16px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }
            .final-box { background: #e3f2fd; padding: 25px; border-radius: 10px; margin: 25px 0; border: 2px solid #667eea; text-align: center; }
            .footer { background: #f8f9fa; padding: 30px; text-align: center; color: #6c757d; font-size: 14px; }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <h1 style="margin: 0; font-size: 28px;">Final Reminder 📬</h1>
              <p style="margin: 15px 0 0 0; opacity: 0.9; font-size: 16px;">We don't want to see you miss out</p>
            </div>
            <div class="content">
              <p>Hi ${userName},</p>
              <p>This is our last reminder about your TradeBotX account. We truly believe in the value our platform can bring to your trading journey.</p>
              
              <div class="final-box">
                <h2 style="margin-top: 0; color: #667eea;">Your Account is Ready</h2>
                <p>All you need to do is complete the setup and start automated trading.</p>
                <a href="https://tradebotx.com/dashboard" class="cta-button">Complete Setup →</a>
              </div>
              
              <p>If you have any questions, concerns, or feedback about why you haven't completed the setup, we'd genuinely love to hear from you.</p>
              
              <p style="text-align: center; font-size: 18px;">
                <strong>Contact us anytime:</strong><br/>
                <a href="https://t.me/tradebotxsuppo" style="color: #667eea; text-decoration: none;">💬 @tradebotxsuppo on Telegram</a>
              </p>
              
              <p>Wishing you success in your trading journey!</p>
              
              <p>Best regards,<br/><strong>The TradeBotX Team</strong></p>
            </div>
            <div class="footer">
              <p>TradeBotX - Automated Trading Made Simple</p>
              <p style="font-size: 12px; color: #adb5bd;">This is the last email in our onboarding sequence.</p>
            </div>
          </div>
        </body>
      </html>
    `,
  };
  
  return templates[sequence] || templates[1];
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const cronSecret = Deno.env.get('CRON_SECRET');
    const auth = req.headers.get('Authorization');
    if (!cronSecret || auth !== `Bearer ${cronSecret}`) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM');

    if (!smtpHost || !smtpPort || !smtpUser || !smtpPass || !smtpFrom) {
      throw new Error('SMTP configuration is missing');
    }

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

    // Get all users who haven't completed setup
    const { data: incompleteUsers, error: usersError } = await supabase
      .from('user_setup')
      .select(`
        user_id,
        created_at,
        is_completed
      `)
      .eq('is_completed', false);

    if (usersError) {
      throw usersError;
    }

    console.log(`Found ${incompleteUsers?.length || 0} users with incomplete setup`);

    let emailsSent = 0;
    const now = new Date();

    for (const userSetup of incompleteUsers || []) {
      // Get user profile
      const { data: profile } = await supabase
        .from('profiles')
        .select('email, full_name')
        .eq('id', userSetup.user_id)
        .single();

      if (!profile?.email) {
        console.log(`No email found for user ${userSetup.user_id}`);
        continue;
      }

      const signupTime = new Date(userSetup.created_at);
      const hoursSinceSignup = (now.getTime() - signupTime.getTime()) / (1000 * 60 * 60);

      // Get already sent emails for this user
      const { data: sentEmails } = await supabase
        .from('onboarding_emails')
        .select('email_sequence')
        .eq('user_id', userSetup.user_id);

      const sentSequences = new Set(sentEmails?.map(e => e.email_sequence) || []);

      // Find which email to send
      for (const emailConfig of EMAIL_SEQUENCE) {
        // Skip if already sent
        if (sentSequences.has(emailConfig.sequence)) {
          continue;
        }

        // Check if it's time to send this email
        if (hoursSinceSignup >= emailConfig.hoursAfterSignup) {
          // Check if previous emails in sequence were sent (don't skip ahead)
          if (emailConfig.sequence > 1 && !sentSequences.has(emailConfig.sequence - 1)) {
            // Send the previous one first
            continue;
          }

          const userName = profile.full_name || 'Trader';
          const emailHtml = getEmailTemplate(emailConfig.sequence, userName);

          try {
            await client.send({
              from: smtpFrom,
              to: [profile.email],
              subject: emailConfig.subject,
              html: emailHtml,
            });

            // Log the sent email
            await supabase.from('onboarding_emails').insert({
              user_id: userSetup.user_id,
              email_sequence: emailConfig.sequence,
              email_type: emailConfig.type,
            });

            console.log(`Sent email ${emailConfig.sequence} (${emailConfig.type}) to ${profile.email}`);
            emailsSent++;

            // Only send one email per user per run
            break;
          } catch (sendError) {
            console.error(`Failed to send email to ${profile.email}:`, sendError);
          }
        }
      }
    }

    await client.close();

    console.log(`Onboarding nurture completed. Sent ${emailsSent} emails.`);

    return new Response(
      JSON.stringify({ success: true, emailsSent }),
      { 
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );

  } catch (error: any) {
    console.error('Error in onboarding nurture:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});