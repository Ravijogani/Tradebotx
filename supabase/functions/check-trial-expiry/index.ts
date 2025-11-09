import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";
import { getEmailTemplate, trialExpiryContent } from "../_shared/email-templates.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    console.log("Checking for expiring trials...");

    const now = new Date();
    const sevenDaysFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    const threeDaysFromNow = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);
    const oneDayFromNow = new Date(now.getTime() + 1 * 24 * 60 * 60 * 1000);

    // Get all active trial subscriptions expiring in 7, 3, or 1 days
    const { data: subscriptions, error: subError } = await supabase
      .from("user_subscriptions")
      .select(`
        *,
        profiles!inner(id, email, full_name),
        plans!inner(id, name, price)
      `)
      .eq("status", "trial")
      .not("trial_ends_at", "is", null);

    if (subError) {
      console.error("Error fetching subscriptions:", subError);
      throw subError;
    }

    console.log(`Found ${subscriptions?.length || 0} trial subscriptions`);

    const sentEmails = [];

    for (const sub of subscriptions || []) {
      const trialEndDate = new Date(sub.trial_ends_at);
      const daysRemaining = Math.ceil((trialEndDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

      console.log(`User ${sub.user_id} trial ends in ${daysRemaining} days`);

      // Send reminder at 7, 3, and 1 day marks
      if (daysRemaining === 7 || daysRemaining === 3 || daysRemaining === 1) {
        // Check if we already sent a reminder for this day
        const { data: existingNotif } = await supabase
          .from("user_notifications")
          .select("id")
          .eq("user_id", sub.user_id)
          .eq("type", "warning")
          .eq("title", `Trial Expires in ${daysRemaining} Day${daysRemaining > 1 ? 's' : ''}`)
          .gte("created_at", new Date(now.getTime() - 12 * 60 * 60 * 1000).toISOString())
          .maybeSingle();

        if (existingNotif) {
          console.log(`Already sent ${daysRemaining}-day reminder to user ${sub.user_id}`);
          continue;
        }

        const profile = sub.profiles;
        const plan = sub.plans;

        // Create in-app notification
        await supabase
          .from("user_notifications")
          .insert({
            user_id: sub.user_id,
            type: "warning",
            title: `Trial Expires in ${daysRemaining} Day${daysRemaining > 1 ? 's' : ''}`,
            message: `Your trial ends soon. Upgrade to ${plan.name} to continue trading.`,
            metadata: { subscription_id: sub.id, days_remaining: daysRemaining }
          });

        // Send email via edge function
        const emailContent = trialExpiryContent(
          profile.full_name || profile.email,
          daysRemaining,
          plan.name,
          plan.price
        );

        const emailHtml = getEmailTemplate(
          emailContent,
          `Your TradeBotX trial expires in ${daysRemaining} day${daysRemaining > 1 ? 's' : ''}`
        );

        const { error: emailError } = await supabase.functions.invoke("send-custom-email", {
          body: {
            to: profile.email,
            subject: `⏰ Trial Expires in ${daysRemaining} Day${daysRemaining > 1 ? 's' : ''} - Upgrade to Continue`,
            html: emailHtml
          }
        });

        if (emailError) {
          console.error(`Error sending email to ${profile.email}:`, emailError);
        } else {
          console.log(`Sent ${daysRemaining}-day reminder to ${profile.email}`);
          sentEmails.push({ email: profile.email, days_remaining: daysRemaining });
        }
      }
    }

    return new Response(
      JSON.stringify({ 
        success: true, 
        checked: subscriptions?.length || 0,
        sent_emails: sentEmails.length,
        details: sentEmails
      }),
      {
        status: 200,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    console.error("Error in check-trial-expiry:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});