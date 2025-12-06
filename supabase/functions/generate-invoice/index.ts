import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { getEmailTemplate, invoiceEmailContent } from "../_shared/email-templates.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Get authorization header
    const authHeader = req.headers.get('Authorization');
    if (!authHeader) {
      throw new Error('Authorization header required');
    }

    // Create client with user's JWT for authentication
    const supabaseAuth = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      {
        global: {
          headers: { Authorization: authHeader }
        }
      }
    );

    // Verify user is authenticated and is an admin
    const { data: { user }, error: authError } = await supabaseAuth.auth.getUser();
    if (authError || !user) {
      throw new Error('Not authenticated');
    }

    // Check if user is admin
    const { data: adminRole, error: roleError } = await supabaseAuth
      .from('user_roles')
      .select('role')
      .eq('user_id', user.id)
      .eq('role', 'admin')
      .single();

    if (roleError || !adminRole) {
      throw new Error('Admin access required to generate invoices');
    }

    const { user_id, subscription_id, amount, plan_name } = await req.json();

    if (!user_id || !subscription_id) {
      return new Response(
        JSON.stringify({ error: "Missing required fields" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Use service role key for database operations
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    console.log(`Admin ${user.email} generating invoice for user ${user_id}, subscription ${subscription_id}`);

    // Get user profile
    const { data: profile, error: profileError } = await supabase
      .from("profiles")
      .select("*")
      .eq("id", user_id)
      .single();

    if (profileError || !profile) {
      throw new Error("User not found");
    }

    // Generate invoice number
    const invoiceNumber = `INV-${Date.now()}-${user_id.substring(0, 8).toUpperCase()}`;
    const invoiceDate = new Date().toISOString().split("T")[0];

    // Create simple invoice HTML for PDF generation
    const invoiceHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
    .header { display: flex; justify-content: space-between; margin-bottom: 40px; }
    .logo { font-size: 28px; font-weight: bold; color: #10b981; }
    .invoice-info { text-align: right; }
    .invoice-number { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
    .section { margin: 30px 0; }
    .section-title { font-size: 16px; font-weight: bold; margin-bottom: 15px; color: #10b981; }
    .info-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }
    .total-row { display: flex; justify-content: space-between; padding: 20px 0; margin-top: 20px; border-top: 2px solid #10b981; font-size: 20px; font-weight: bold; }
    .footer { margin-top: 50px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; color: #666; font-size: 12px; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="logo">TradeBotX</div>
      <div style="color: #666; margin-top: 5px;">Institutional-Grade Algorithmic Trading</div>
    </div>
    <div class="invoice-info">
      <div class="invoice-number">INVOICE #${invoiceNumber}</div>
      <div>Date: ${invoiceDate}</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Bill To:</div>
    <div><strong>${profile.full_name || 'Customer'}</strong></div>
    <div>${profile.email}</div>
    ${profile.phone ? `<div>${profile.phone}</div>` : ''}
  </div>

  <div class="section">
    <div class="section-title">Invoice Details</div>
    <div class="info-row">
      <span>Description</span>
      <span>Amount</span>
    </div>
    <div class="info-row">
      <span>${plan_name || 'TradeBotX Subscription'}</span>
      <span>$${amount.toFixed(2)}</span>
    </div>
  </div>

  <div class="total-row">
    <span>Total Amount</span>
    <span style="color: #10b981;">$${amount.toFixed(2)}</span>
  </div>

  <div class="footer">
    <p><strong>TradeBotX</strong> - Professional Trading Solutions</p>
    <p>Support: support@tradebotx.com | Security: security@tradebotx.com</p>
    <p>© ${new Date().getFullYear()} TradeBotX. All rights reserved.</p>
    <p style="margin-top: 15px; font-size: 10px;">
      <strong>Risk Warning:</strong> Trading involves substantial risk. Past performance does not guarantee future results.
    </p>
  </div>
</body>
</html>
    `;

    // Store invoice in user-specific folder for RLS
    const invoiceFileName = `${user_id}/${invoiceNumber}.html`;
    const { data: uploadData, error: uploadError } = await supabase.storage
      .from("invoices")
      .upload(invoiceFileName, new Blob([invoiceHtml], { type: "text/html" }), {
        contentType: "text/html",
        upsert: true
      });

    if (uploadError) {
      console.error("Upload error:", uploadError);
      throw uploadError;
    }

    // Generate a signed URL instead of public URL (valid for 7 days)
    const { data: signedUrlData, error: signedUrlError } = await supabase.storage
      .from("invoices")
      .createSignedUrl(invoiceFileName, 60 * 60 * 24 * 7); // 7 days

    if (signedUrlError) {
      console.error("Signed URL error:", signedUrlError);
      throw signedUrlError;
    }

    const invoiceUrl = signedUrlData.signedUrl;

    console.log("Invoice generated with signed URL");

    // Send invoice email
    const emailContent = invoiceEmailContent(
      invoiceNumber,
      profile.full_name || profile.email,
      plan_name || "TradeBotX Subscription",
      amount,
      invoiceDate,
      invoiceUrl
    );

    const emailHtml = getEmailTemplate(
      emailContent,
      `Your TradeBotX Invoice #${invoiceNumber}`
    );

    const { error: emailError } = await supabase.functions.invoke("send-custom-email", {
      body: {
        to: profile.email,
        subject: `📄 Invoice #${invoiceNumber} - TradeBotX Subscription`,
        html: emailHtml
      }
    });

    if (emailError) {
      console.error("Error sending invoice email:", emailError);
      // Don't fail the whole request if email fails
    }

    // Create notification
    await supabase
      .from("user_notifications")
      .insert({
        user_id: user_id,
        type: "success",
        title: "Invoice Generated",
        message: `Invoice #${invoiceNumber} for $${amount.toFixed(2)} has been generated`,
        metadata: { invoice_number: invoiceNumber, invoice_url: invoiceUrl }
      });

    return new Response(
      JSON.stringify({ 
        success: true, 
        invoice_number: invoiceNumber,
        invoice_url: invoiceUrl,
        email_sent: !emailError
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("Error generating invoice:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});