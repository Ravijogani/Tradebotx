// Shared email template system for TradeBotX
// Matches the website theme with proper branding

export const getEmailTemplate = (content: string, preheader?: string) => {
  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TradeBotX</title>
  ${preheader ? `<style type="text/css">#preheader{display:none!important;visibility:hidden;opacity:0;color:transparent;height:0;width:0}</style>` : ''}
  <!--[if mso]>
  <style type="text/css">
    body, table, td {font-family: Arial, Helvetica, sans-serif !important;}
  </style>
  <![endif]-->
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Helvetica Neue', Arial, sans-serif; background: linear-gradient(135deg, #0a0e1a 0%, #1a1f2e 100%);">
  ${preheader ? `<div id="preheader" style="display: none; max-height: 0px; overflow: hidden; font-size: 1px; line-height: 1px; color: transparent; opacity: 0;">${preheader}</div>` : ''}
  
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin: 0; padding: 0; background: linear-gradient(135deg, #0a0e1a 0%, #1a1f2e 100%);">
    <tr>
      <td align="center" style="padding: 50px 20px;">
        <!-- Main Container -->
        <table role="presentation" cellpadding="0" cellspacing="0" width="600" style="max-width: 600px; background: #1a1f2e; border-radius: 24px; overflow: hidden; box-shadow: 0 25px 80px rgba(0, 0, 0, 0.7), 0 0 40px rgba(102, 126, 234, 0.15);">
          
          <!-- Premium Gradient Header with Glass Effect -->
          <tr>
            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; position: relative;">
              <!-- Decorative Elements -->
              <div style="position: absolute; top: -100px; right: -100px; width: 300px; height: 300px; background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%); border-radius: 50%;"></div>
              <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="padding: 60px 40px; text-align: center; position: relative;">
                    <div style="background: rgba(255, 255, 255, 0.12); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 20px; padding: 28px 40px; display: inline-block; border: 2px solid rgba(255, 255, 255, 0.25); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.3);">
                      <h1 style="margin: 0; font-size: 42px; font-weight: 900; color: #ffffff; letter-spacing: -1.5px; text-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3);">
                        <span style="font-size: 48px; display: inline-block; animation: float 3s ease-in-out infinite;">🤖</span> TradeBotX
                      </h1>
                      <p style="margin: 12px 0 0 0; font-size: 13px; color: rgba(255, 255, 255, 0.95); font-weight: 600; letter-spacing: 3px; text-transform: uppercase; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);">AI-Powered Trading Platform</p>
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          
          <!-- Enhanced Content Area -->
          <tr>
            <td style="padding: 56px 48px; background: linear-gradient(180deg, #1a1f2e 0%, #1e2433 100%);">
              ${content}
            </td>
          </tr>
          
          <!-- Enhanced Footer -->
          <tr>
            <td style="padding: 40px 48px; background: #12161f; border-top: 2px solid rgba(102, 126, 234, 0.2);">
              <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="text-align: center; padding-bottom: 24px;">
                    <p style="margin: 0; font-size: 15px; color: #9ca3b5; line-height: 1.8;">
                      This is an automated message from <strong style="color: #667eea;">TradeBotX</strong>.<br>
                      For support, reach out at <a href="mailto:support@tradebotx.com" style="color: #667eea; text-decoration: none; font-weight: 700; border-bottom: 2px solid rgba(102, 126, 234, 0.3); padding-bottom: 2px;">support@tradebotx.com</a>
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="text-align: center; padding-top: 24px; border-top: 1px solid rgba(102, 126, 234, 0.1);">
                    <p style="margin: 0 0 16px 0; font-size: 13px; color: #7b8296;">
                      &copy; ${new Date().getFullYear()} TradeBotX. All rights reserved.
                    </p>
                    <div style="margin-top: 16px;">
                      <a href="https://tradebotx.com" style="display: inline-block; margin: 0 12px; color: #667eea; text-decoration: none; font-size: 13px; font-weight: 600; transition: color 0.2s;">Website</a>
                      <span style="color: #4b5563; font-weight: 300;">•</span>
                      <a href="https://tradebotx.com/terms" style="display: inline-block; margin: 0 12px; color: #667eea; text-decoration: none; font-size: 13px; font-weight: 600; transition: color 0.2s;">Terms</a>
                      <span style="color: #4b5563; font-weight: 300;">•</span>
                      <a href="https://tradebotx.com/privacy" style="display: inline-block; margin: 0 12px; color: #667eea; text-decoration: none; font-size: 13px; font-weight: 600; transition: color 0.2s;">Privacy</a>
                    </div>
                    <p style="margin: 20px 0 0 0; font-size: 11px; color: #5f6575; line-height: 1.5;">
                      You're receiving this because you have an account with TradeBotX.<br>
                      Update your preferences in your <a href="https://tradebotx.com/dashboard/settings" style="color: #667eea; text-decoration: none;">account settings</a>.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
  `.trim();
};

export const otpEmailContent = (otpCode: string, type: 'signup' | 'login' | 'forgot-password') => {
  const icons = {
    'signup': '✨',
    'login': '🔐',
    'forgot-password': '🔑'
  };
  
  const titles = {
    'signup': 'Verify Your Email',
    'login': 'Login Verification',
    'forgot-password': 'Reset Password'
  };
  
  const descriptions = {
    'signup': 'Welcome to TradeBotX! Please verify your email to start your automated trading journey.',
    'login': 'A login attempt was detected on your TradeBotX account. Please verify it\'s you.',
    'forgot-password': 'We received a request to reset your TradeBotX account password.'
  };
  
  return `
    <div style="text-align: center; margin-bottom: 32px;">
      <div style="font-size: 64px; margin-bottom: 16px; line-height: 1;">${icons[type]}</div>
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff; line-height: 1.3;">${titles[type]}</h2>
    </div>
    
    <p style="margin: 0 0 24px 0; font-size: 16px; color: #d1d5db; line-height: 1.7; text-align: center;">
      ${descriptions[type]}
    </p>
    
    <div style="background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%); border: 2px solid #667eea; border-radius: 16px; padding: 40px; margin: 32px 0; text-align: center; box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);">
      <p style="margin: 0 0 16px 0; font-size: 14px; font-weight: 600; color: #a5b4fc; text-transform: uppercase; letter-spacing: 1px;">Your Verification Code</p>
      <div style="font-family: 'Courier New', monospace; font-size: 56px; font-weight: 900; color: #667eea; letter-spacing: 16px; text-shadow: 0 4px 16px rgba(102, 126, 234, 0.4); margin: 8px 0;">${otpCode}</div>
      <p style="margin: 16px 0 0 0; font-size: 13px; color: #9ca3af;">Valid for 2 minutes</p>
    </div>
    
    <div style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%); border-left: 4px solid #ef4444; padding: 20px 24px; border-radius: 12px; margin: 32px 0;">
      <p style="margin: 0; font-size: 14px; color: #fca5a5; line-height: 1.7;">
        <strong style="display: block; margin-bottom: 8px;">⚠️ Security Notice</strong>
        This code expires in 2 minutes. Never share this code with anyone. If you didn't request this, please secure your account immediately.
      </p>
    </div>
    
    <p style="margin: 32px 0 0 0; font-size: 15px; color: #9ca3af; line-height: 1.7; text-align: center;">
      Need help? Contact us at <a href="mailto:support@tradebotx.com" style="color: #667eea; text-decoration: none; font-weight: 600;">support@tradebotx.com</a>
    </p>
  `;
};

export const welcomeEmailContent = (userName: string) => {
  return `
    <div style="text-align: center; margin-bottom: 30px;">
      <div style="font-size: 48px; margin-bottom: 20px;">🎉</div>
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff; line-height: 1.3;">Welcome to TradeBotX!</h2>
    </div>
    
    <p style="margin: 0 0 20px 0; font-size: 16px; color: #e5e7eb; line-height: 1.6;">Hello ${userName},</p>
    
    <p style="margin: 0 0 30px 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">Congratulations! Your TradeBotX account has been successfully created. You are now part of an elite community of automated traders leveraging AI-powered strategies.</p>
    
    <div style="background: linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(124, 58, 237, 0.1) 100%); border-radius: 12px; padding: 25px; margin: 30px 0; border: 1px solid rgba(79, 70, 229, 0.3);">
      <h3 style="margin: 0 0 15px 0; font-size: 18px; font-weight: 600; color: #4F46E5;">🚀 Quick Start Guide</h3>
      <ol style="margin: 0; padding-left: 20px; color: #d1d5db; font-size: 15px; line-height: 2;">
        <li>Complete your MT5 account setup</li>
        <li>Configure your risk parameters</li>
        <li>Select your trading strategies</li>
        <li>Start your first automated bot</li>
      </ol>
    </div>
    
    <div style="text-align: center; margin: 35px 0;">
      <a href="https://tradebotx.com/dashboard" style="display: inline-block; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);">Go to Dashboard</a>
    </div>
    
    <p style="margin: 30px 0 0 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">
      Need help? Our support team is available 24/7 at <a href="mailto:support@tradebotx.com" style="color: #4F46E5; text-decoration: none;">support@tradebotx.com</a>
    </p>
    
    <p style="margin: 20px 0 0 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">
      Happy Trading!<br>
      <strong style="color: #e5e7eb;">The TradeBotX Team</strong>
    </p>
  `;
};

export const loginAlertContent = (ipAddress: string, location: string, timestamp: string) => {
  return `
    <div style="text-align: center; margin-bottom: 30px;">
      <div style="font-size: 48px; margin-bottom: 20px;">🔐</div>
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff; line-height: 1.3;">New Login Detected</h2>
    </div>
    
    <p style="margin: 0 0 20px 0; font-size: 16px; color: #e5e7eb; line-height: 1.6;">Hello,</p>
    
    <p style="margin: 0 0 30px 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">We detected a new login to your TradeBotX account. If this was you, you can ignore this email. If you don't recognize this activity, please secure your account immediately.</p>
    
    <div style="background: rgba(45, 27, 78, 0.5); border-radius: 12px; padding: 25px; margin: 30px 0; border: 1px solid rgba(79, 70, 229, 0.3);">
      <h3 style="margin: 0 0 15px 0; font-size: 18px; font-weight: 600; color: #4F46E5;">Login Details</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 10px 0; color: #9ca3af; font-size: 14px; width: 35%;">Time:</td>
          <td style="padding: 10px 0; color: #e5e7eb; font-size: 14px; font-weight: 500;">${timestamp}</td>
        </tr>
        <tr>
          <td style="padding: 10px 0; color: #9ca3af; font-size: 14px;">Location:</td>
          <td style="padding: 10px 0; color: #e5e7eb; font-size: 14px; font-weight: 500;">${location}</td>
        </tr>
        <tr>
          <td style="padding: 10px 0; color: #9ca3af; font-size: 14px;">IP Address:</td>
          <td style="padding: 10px 0; color: #e5e7eb; font-size: 14px; font-weight: 500;">${ipAddress}</td>
        </tr>
      </table>
    </div>
    
    <div style="background: rgba(220, 38, 38, 0.1); border-left: 4px solid #dc2626; padding: 15px 20px; border-radius: 8px; margin: 30px 0;">
      <p style="margin: 0; font-size: 14px; color: #fca5a5; line-height: 1.6;">
        ⚠️ <strong>Wasn't you?</strong> Change your password immediately and enable two-factor authentication. Contact our security team at <a href="mailto:security@tradebotx.com" style="color: #fca5a5; text-decoration: underline;">security@tradebotx.com</a>
      </p>
    </div>
    
    <p style="margin: 30px 0 0 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">
      Stay secure,<br>
      <strong style="color: #e5e7eb;">The TradeBotX Security Team</strong>
    </p>
  `;
};

export const botStartAlertContent = (strategyName: string, accountSize: number, riskPerTrade: number) => {
  return `
    <div style="text-align: center; margin-bottom: 30px;">
      <div style="font-size: 48px; margin-bottom: 20px;">🤖</div>
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff; line-height: 1.3;">Trading Bot Started</h2>
    </div>
    
    <p style="margin: 0 0 20px 0; font-size: 16px; color: #e5e7eb; line-height: 1.6;">Great news!</p>
    
    <p style="margin: 0 0 30px 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">Your automated trading bot has been successfully started and is now actively monitoring the markets for opportunities.</p>
    
    <div style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%); border-radius: 12px; padding: 25px; margin: 30px 0; border: 1px solid rgba(34, 197, 94, 0.3);">
      <h3 style="margin: 0 0 15px 0; font-size: 18px; font-weight: 600; color: #22c55e;">Bot Configuration</h3>
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 10px 0; color: #9ca3af; font-size: 14px; width: 40%;">Strategy:</td>
          <td style="padding: 10px 0; color: #e5e7eb; font-size: 14px; font-weight: 600;">${strategyName}</td>
        </tr>
        <tr>
          <td style="padding: 10px 0; color: #9ca3af; font-size: 14px;">Account Size:</td>
          <td style="padding: 10px 0; color: #e5e7eb; font-size: 14px; font-weight: 600;">$${accountSize.toLocaleString()}</td>
        </tr>
        <tr>
          <td style="padding: 10px 0; color: #9ca3af; font-size: 14px;">Risk per Trade:</td>
          <td style="padding: 10px 0; color: #e5e7eb; font-size: 14px; font-weight: 600;">${riskPerTrade}%</td>
        </tr>
      </table>
    </div>
    
    <div style="text-align: center; margin: 35px 0;">
      <a href="https://tradebotx.com/dashboard" style="display: inline-block; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);">View Live Dashboard</a>
    </div>
    
    <p style="margin: 30px 0 0 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">
      Happy Trading!<br>
      <strong style="color: #e5e7eb;">The TradeBotX Team</strong>
    </p>
  `;
};

export const forgotPasswordContent = (resetLink: string) => {
  return `
    <div style="text-align: center; margin-bottom: 30px;">
      <div style="font-size: 48px; margin-bottom: 20px;">🔑</div>
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff; line-height: 1.3;">Password Reset Request</h2>
    </div>
    
    <p style="margin: 0 0 20px 0; font-size: 16px; color: #e5e7eb; line-height: 1.6;">Hello,</p>
    
    <p style="margin: 0 0 30px 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">We received a request to reset the password for your TradeBotX account. Click the button below to create a new password:</p>
    
    <div style="text-align: center; margin: 35px 0;">
      <a href="${resetLink}" style="display: inline-block; background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);">Reset Password</a>
    </div>
    
    <p style="margin: 30px 0; font-size: 14px; color: #9ca3af; line-height: 1.6; text-align: center;">Or copy this link: <span style="color: #4F46E5; word-break: break-all;">${resetLink}</span></p>
    
    <div style="background: rgba(220, 38, 38, 0.1); border-left: 4px solid #dc2626; padding: 15px 20px; border-radius: 8px; margin: 30px 0;">
      <p style="margin: 0; font-size: 14px; color: #fca5a5; line-height: 1.6;">
        ⚠️ This link will expire in 1 hour. If you didn't request a password reset, please ignore this email or contact support if you have concerns.
      </p>
    </div>
    
    <p style="margin: 30px 0 0 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">
      Best regards,<br>
      <strong style="color: #e5e7eb;">The TradeBotX Team</strong>
    </p>
  `;
};
