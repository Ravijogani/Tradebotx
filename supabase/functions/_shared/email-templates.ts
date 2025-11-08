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
</head>
<body style="margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif; background: linear-gradient(135deg, #1a1f2e 0%, #2d1b4e 100%); min-height: 100vh;">
  ${preheader ? `<div id="preheader" style="display: none; max-height: 0px; overflow: hidden;">${preheader}</div>` : ''}
  
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin: 0; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" cellpadding="0" cellspacing="0" width="600" style="max-width: 600px; background: rgba(34, 40, 58, 0.95); border-radius: 16px; overflow: hidden; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 40px rgba(79, 70, 229, 0.2); backdrop-filter: blur(10px); border: 1px solid rgba(79, 70, 229, 0.2);">
          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); padding: 40px 30px; text-align: center;">
              <div style="display: inline-block; background: rgba(255, 255, 255, 0.1); padding: 15px 25px; border-radius: 12px; backdrop-filter: blur(10px);">
                <h1 style="margin: 0; font-size: 32px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);">
                  🤖 TradeBotX
                </h1>
              </div>
            </td>
          </tr>
          
          <!-- Content -->
          <tr>
            <td style="padding: 40px 30px;">
              ${content}
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="padding: 30px; background: rgba(26, 31, 46, 0.8); border-top: 1px solid rgba(79, 70, 229, 0.2);">
              <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="text-align: center; padding-bottom: 15px;">
                    <p style="margin: 0; font-size: 14px; color: #9ca3af; line-height: 1.5;">
                      This is an automated message from TradeBotX.<br>
                      Please do not reply to this email.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="text-align: center; padding-top: 15px; border-top: 1px solid rgba(79, 70, 229, 0.1);">
                    <p style="margin: 0; font-size: 12px; color: #6b7280;">
                      &copy; ${new Date().getFullYear()} TradeBotX. All rights reserved.<br>
                      <a href="mailto:support@tradebotx.com" style="color: #4F46E5; text-decoration: none;">support@tradebotx.com</a>
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
  const titles = {
    'signup': 'Email Verification',
    'login': 'Login Verification',
    'forgot-password': 'Password Reset'
  };
  
  const descriptions = {
    'signup': 'Thank you for signing up with TradeBotX! Your automated trading journey starts here.',
    'login': 'You are attempting to log in to your TradeBotX account.',
    'forgot-password': 'We received a request to reset your password.'
  };
  
  return `
    <div style="text-align: center;">
      <div style="display: inline-block; background: rgba(79, 70, 229, 0.1); padding: 12px 24px; border-radius: 8px; margin-bottom: 30px;">
        <p style="margin: 0; font-size: 18px; font-weight: 600; color: #4F46E5;">${titles[type]}</p>
      </div>
    </div>
    
    <p style="margin: 0 0 20px 0; font-size: 16px; color: #e5e7eb; line-height: 1.6;">Hello,</p>
    
    <p style="margin: 0 0 30px 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">${descriptions[type]}</p>
    
    <p style="margin: 0 0 20px 0; font-size: 16px; color: #e5e7eb; line-height: 1.6; font-weight: 600;">Your verification code is:</p>
    
    <div style="background: linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(124, 58, 237, 0.1) 100%); border: 2px solid #4F46E5; border-radius: 12px; padding: 30px; margin: 30px 0; text-align: center; box-shadow: 0 4px 16px rgba(79, 70, 229, 0.2);">
      <div style="font-size: 48px; font-weight: 800; color: #4F46E5; letter-spacing: 12px; text-shadow: 0 2px 10px rgba(79, 70, 229, 0.3);">${otpCode}</div>
    </div>
    
    <div style="background: rgba(220, 38, 38, 0.1); border-left: 4px solid #dc2626; padding: 15px 20px; border-radius: 8px; margin: 30px 0;">
      <p style="margin: 0; font-size: 14px; color: #fca5a5; line-height: 1.6;">
        ⚠️ <strong>Important:</strong> This code will expire in 2 minutes. If you didn't request this code, please ignore this email and ensure your account is secure.
      </p>
    </div>
    
    <p style="margin: 30px 0 0 0; font-size: 16px; color: #d1d5db; line-height: 1.6;">
      Best regards,<br>
      <strong style="color: #e5e7eb;">The TradeBotX Team</strong>
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
