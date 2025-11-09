# TradeBotX Email System Documentation

## Overview

TradeBotX has a comprehensive email notification system with professional templates, automated reminders, and invoice generation capabilities.

## Email Templates

### 1. **Trial Expiry Reminders** 
Automated emails sent at three critical points before trial expiration:

- **7 Days Before**: Early reminder with upgrade encouragement
- **3 Days Before**: Urgent reminder highlighting premium benefits  
- **1 Day Before**: Final notice with immediate upgrade CTA

**Template Features:**
- Dynamic urgency indicators (emoji, colors)
- Personalized content with user name
- Recommended plan information
- Clear list of premium benefits
- Direct upgrade link to pricing page

### 2. **Invoice Emails**
Professional invoice notifications sent after successful payments:

**Template Features:**
- Invoice number and date
- Itemized billing details
- Plan name and amount
- Download link for invoice document
- Billing support contact information

### 3. **Other Email Templates**
- **OTP Verification**: Login/signup verification codes
- **Welcome Email**: Account creation confirmation with quick start guide
- **Login Alert**: Security notification for new logins
- **Bot Started**: Trading bot activation confirmation
- **Trade Notifications**: Real-time trade execution alerts
- **Emergency Stop**: Critical risk management alerts

## Automated Systems

### Trial Expiry Monitoring (Cron Job)

**Schedule**: Every 6 hours
**Function**: `check-trial-expiry`

The system automatically:
1. Checks all active trial subscriptions
2. Calculates days remaining until expiry
3. Sends reminder emails at 7-day, 3-day, and 1-day marks
4. Creates in-app notifications
5. Prevents duplicate notifications within 12-hour windows

**Cron Configuration:**
```sql
SELECT cron.schedule(
  'check-trial-expiry-job',
  '0 */6 * * *', -- Every 6 hours
  -- Calls the check-trial-expiry edge function
);
```

### Invoice Generation

**Function**: `generate-invoice`
**Trigger**: Manual or payment webhook

The system:
1. Generates unique invoice numbers
2. Creates formatted invoice HTML
3. Stores invoice in Supabase Storage
4. Sends invoice email with download link
5. Creates in-app notification

**Usage:**
```javascript
const { data } = await supabase.functions.invoke('generate-invoice', {
  body: {
    user_id: 'user-uuid',
    subscription_id: 'subscription-uuid',
    amount: 99.00,
    plan_name: 'Professional Plan'
  }
});
```

## Email Template System

### Base Template Structure

All emails use a consistent base template with:
- Professional dark theme design
- TradeBotX branding and logo
- Responsive layout (mobile-optimized)
- Footer with contact links and legal info
- Risk warning disclaimer

### Creating Custom Email Content

Email content functions are exported from `supabase/functions/_shared/email-templates.ts`:

```typescript
// Example: Trial expiry email
export const trialExpiryContent = (
  userName: string,
  daysRemaining: number,
  planName: string,
  planPrice: number
) => {
  // Returns formatted HTML content
};

// Wrap content in base template
const html = getEmailTemplate(
  trialExpiryContent(userName, days, plan, price),
  'Preheader text'
);
```

## Storage & Deliverability

### Invoice Storage
- **Bucket**: `invoices` (public)
- **Format**: HTML (can be extended to PDF)
- **Naming**: `INV-{timestamp}-{user_id}.html`

### Email Delivery
- Uses `send-custom-email` edge function
- SMTP configuration via environment variables
- Error handling and logging
- Retry logic for failed sends

## Monitoring & Debugging

### Logs
Check edge function logs for:
```bash
# Trial expiry checker
supabase functions logs check-trial-expiry

# Invoice generation
supabase functions logs generate-invoice
```

### Common Issues

**Emails not sending:**
1. Verify SMTP credentials are configured
2. Check rate limits
3. Review edge function logs
4. Confirm email template rendering

**Cron job not running:**
1. Verify `pg_cron` extension is enabled
2. Check cron schedule syntax
3. Review database logs
4. Test edge function manually

**Invoice generation failing:**
1. Verify storage bucket exists and is public
2. Check user permissions
3. Confirm required parameters
4. Review storage quota

## Future Enhancements

Potential improvements:
- PDF invoice generation using jsPDF
- Email templates in multiple languages
- A/B testing for email content
- Advanced analytics tracking
- Custom email preferences per user
- Drip email campaigns
- Re-engagement emails for churned users

## Testing

### Manual Testing

**Test trial expiry emails:**
```javascript
// Set a trial to expire soon
UPDATE user_subscriptions 
SET trial_ends_at = NOW() + INTERVAL '1 day'
WHERE user_id = 'test-user-id';

// Manually trigger check
supabase.functions.invoke('check-trial-expiry')
```

**Test invoice generation:**
```javascript
supabase.functions.invoke('generate-invoice', {
  body: {
    user_id: 'test-user-id',
    subscription_id: 'test-sub-id',
    amount: 99.00,
    plan_name: 'Test Plan'
  }
});
```

## Security Considerations

- Email templates sanitized to prevent injection
- User data properly escaped in HTML
- Invoice URLs are time-limited (can add expiry)
- Rate limiting on email sends
- Audit logging for all email activities

## Support

For issues or questions about the email system:
- Technical: support@tradebotx.com
- Security: security@tradebotx.com

---

**Last Updated**: 2025
**Version**: 1.0
**Maintained By**: TradeBotX Development Team
