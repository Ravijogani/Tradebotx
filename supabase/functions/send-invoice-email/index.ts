import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

import { corsHeaders } from "../_shared/cors.ts";

interface InvoiceEmailRequest {
  to: string;
  invoiceNumber: string;
  amount: number;
  dueDate?: string;
  pdfBase64: string;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      {
        global: {
          headers: { Authorization: req.headers.get('Authorization')! },
        },
      }
    );

    // Verify admin access
    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    
    if (userError || !user) {
      throw new Error('Unauthorized');
    }

    const { data: roleData } = await supabaseClient
      .from('user_roles')
      .select('role')
      .eq('user_id', user.id)
      .eq('role', 'admin')
      .maybeSingle();

    if (!roleData) {
      throw new Error('Unauthorized - Admin access required');
    }

    const { to, invoiceNumber, amount, dueDate, pdfBase64 }: InvoiceEmailRequest = await req.json();

    console.log('Sending invoice email to:', to);

    // Get SMTP configuration
    const smtpHost = Deno.env.get('SMTP_HOST');
    const smtpPort = Deno.env.get('SMTP_PORT');
    const smtpUser = Deno.env.get('SMTP_USER');
    const smtpPass = Deno.env.get('SMTP_PASS');
    const smtpFrom = Deno.env.get('SMTP_FROM');

    if (!smtpHost || !smtpPort || !smtpUser || !smtpPass || !smtpFrom) {
      throw new Error('SMTP configuration not found');
    }

    // Email HTML template
    const emailHtml = `
<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
    .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
    .invoice-details { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }
    .amount { font-size: 32px; font-weight: bold; color: #667eea; margin: 10px 0; }
    .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Invoice from TradeBotX</h1>
    </div>
    <div class="content">
      <h2>Invoice #${invoiceNumber}</h2>
      <p>Thank you for your business. Please find your invoice attached to this email.</p>
      
      <div class="invoice-details">
        <p><strong>Invoice Number:</strong> ${invoiceNumber}</p>
        <p><strong>Amount Due:</strong></p>
        <div class="amount">₹${amount.toFixed(2)}</div>
        ${dueDate ? `<p><strong>Due Date:</strong> ${new Date(dueDate).toLocaleDateString()}</p>` : ''}
      </div>

      <p>The invoice is attached as a PDF file. Please review it and process the payment at your earliest convenience.</p>
      
      <p>If you have any questions about this invoice, please don't hesitate to contact us.</p>
      
      <p>Best regards,<br>TradeBotX Team</p>
    </div>
    <div class="footer">
      <p>This is an automated email. Please do not reply to this message.</p>
    </div>
  </div>
</body>
</html>
    `;

    // Convert base64 PDF to bytes
    const pdfBytes = Uint8Array.from(atob(pdfBase64.split(',')[1]), c => c.charCodeAt(0));

    // Send email using SMTP (simplified - in production use a proper SMTP library)
    const response = await fetch(`https://${smtpHost}:${smtpPort}/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${btoa(`${smtpUser}:${smtpPass}`)}`,
      },
      body: JSON.stringify({
        from: smtpFrom,
        to: to,
        subject: `Invoice #${invoiceNumber} from TradeBotX`,
        html: emailHtml,
        attachments: [{
          filename: `invoice-${invoiceNumber}.pdf`,
          content: pdfBase64.split(',')[1],
          encoding: 'base64',
        }],
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to send email');
    }

    console.log('Invoice email sent successfully to:', to);

    return new Response(
      JSON.stringify({ 
        success: true,
        message: 'Invoice email sent successfully'
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 200 
      }
    );
  } catch (error) {
    console.error('Error in send-invoice-email function:', error);
    return new Response(
      JSON.stringify({ 
        error: error instanceof Error ? error.message : 'Unknown error',
        success: false
      }),
      { 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        status: 400
      }
    );
  }
});