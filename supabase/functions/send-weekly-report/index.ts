import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.80.0";

import { corsHeaders } from "../_shared/cors.ts";

interface WeeklyStats {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  totalPnl: number;
  winRate: number;
  bestTrade: number;
  worstTrade: number;
  symbolPerformance: Array<{ symbol: string; pnl: number }>;
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const cronSecret = Deno.env.get("CRON_SECRET");
    const auth = req.headers.get("Authorization");
    if (!cronSecret || auth !== `Bearer ${cronSecret}`) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" }
      });
    }
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const today = new Date();
    const days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    const dayOfWeek = days[today.getDay()];

    // Get all users who should receive report today
    const { data: reportSettings, error: settingsError } = await supabase
      .from("weekly_report_settings")
      .select("*, profiles(*)")
      .eq("is_enabled", true)
      .eq("send_day", dayOfWeek);

    if (settingsError) throw settingsError;

    console.log(`Found ${reportSettings?.length || 0} users to send weekly reports`);

    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

    for (const setting of reportSettings || []) {
      try {
        // Get user's weekly trades
        const { data: trades } = await supabase
          .from("trades")
          .select("*")
          .eq("user_id", setting.user_id)
          .eq("status", "closed")
          .gte("closed_at", oneWeekAgo.toISOString());

        // Calculate stats
        const stats: WeeklyStats = {
          totalTrades: trades?.length || 0,
          winningTrades: trades?.filter(t => t.profit_loss > 0).length || 0,
          losingTrades: trades?.filter(t => t.profit_loss < 0).length || 0,
          totalPnl: trades?.reduce((sum, t) => sum + (t.profit_loss || 0), 0) || 0,
          winRate: 0,
          bestTrade: Math.max(...(trades?.map(t => t.profit_loss || 0) || [0])),
          worstTrade: Math.min(...(trades?.map(t => t.profit_loss || 0) || [0])),
          symbolPerformance: []
        };

        if (stats.totalTrades > 0) {
          stats.winRate = (stats.winningTrades / stats.totalTrades) * 100;
        }

        // Group by symbol
        const symbolMap = new Map<string, number>();
        trades?.forEach(t => {
          const current = symbolMap.get(t.symbol) || 0;
          symbolMap.set(t.symbol, current + (t.profit_loss || 0));
        });
        stats.symbolPerformance = Array.from(symbolMap.entries())
          .map(([symbol, pnl]) => ({ symbol, pnl }))
          .sort((a, b) => b.pnl - a.pnl);

        // Get bot heartbeat info
        const { data: heartbeat } = await supabase
          .from("bot_heartbeats")
          .select("*")
          .eq("user_id", setting.user_id)
          .order("last_heartbeat", { ascending: false })
          .limit(1)
          .single();

        const profile = setting.profiles as { email?: string; full_name?: string } | null;
        const userEmail = profile?.email;
        const userName = profile?.full_name || userEmail?.split("@")[0] || "Trader";

        if (!userEmail) continue;

        // Build email HTML
        const pnlColor = stats.totalPnl >= 0 ? "#22c55e" : "#ef4444";
        const pnlSign = stats.totalPnl >= 0 ? "+" : "";

        const topSymbolsHtml = stats.symbolPerformance.slice(0, 5).map(s => {
          const color = s.pnl >= 0 ? "#22c55e" : "#ef4444";
          const sign = s.pnl >= 0 ? "+" : "";
          return `<tr><td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">${s.symbol}</td><td style="padding: 8px; border-bottom: 1px solid #e5e7eb; color: ${color};">${sign}$${s.pnl.toFixed(2)}</td></tr>`;
        }).join("");

        const emailHtml = `
          <!DOCTYPE html>
          <html>
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
          </head>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
              <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">📊 Weekly Performance Report</h1>
                <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0;">Week ending ${today.toLocaleDateString()}</p>
              </div>
              
              <div style="padding: 30px;">
                <p style="color: #374151; font-size: 16px;">Hi ${userName},</p>
                <p style="color: #6b7280;">Here's your trading performance summary for the past week:</p>
                
                <div style="background: #f9fafb; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
                  <h2 style="margin: 0; color: ${pnlColor}; font-size: 36px;">${pnlSign}$${stats.totalPnl.toFixed(2)}</h2>
                  <p style="color: #6b7280; margin: 5px 0 0 0;">Total P&L</p>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;">
                  <div style="background: #f0fdf4; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #22c55e;">${stats.totalTrades}</div>
                    <div style="color: #6b7280; font-size: 12px;">Total Trades</div>
                  </div>
                  <div style="background: #eff6ff; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #3b82f6;">${stats.winRate.toFixed(1)}%</div>
                    <div style="color: #6b7280; font-size: 12px;">Win Rate</div>
                  </div>
                  <div style="background: #faf5ff; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #8b5cf6;">${stats.winningTrades}/${stats.losingTrades}</div>
                    <div style="color: #6b7280; font-size: 12px;">W/L</div>
                  </div>
                </div>
                
                ${stats.symbolPerformance.length > 0 ? `
                <h3 style="color: #374151; margin-top: 30px;">Top Performing Symbols</h3>
                <table style="width: 100%; border-collapse: collapse;">
                  <thead>
                    <tr style="background: #f9fafb;">
                      <th style="padding: 10px; text-align: left; font-weight: 600;">Symbol</th>
                      <th style="padding: 10px; text-align: left; font-weight: 600;">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${topSymbolsHtml}
                  </tbody>
                </table>
                ` : ""}
                
                ${heartbeat ? `
                <div style="margin-top: 30px; padding: 15px; background: #f0fdf4; border-radius: 8px;">
                  <h4 style="margin: 0 0 10px 0; color: #374151;">Bot Status</h4>
                  <p style="margin: 0; color: #22c55e;">✅ Bot is running</p>
                  <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">Balance: $${heartbeat.balance?.toFixed(2) || 'N/A'} | Equity: $${heartbeat.equity?.toFixed(2) || 'N/A'}</p>
                </div>
                ` : ""}
                
                <div style="margin-top: 30px; text-align: center;">
                  <a href="https://app.tradebotx.com/dashboard" style="display: inline-block; background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; text-decoration: none; padding: 12px 30px; border-radius: 8px; font-weight: 600;">View Full Dashboard</a>
                </div>
              </div>
              
              <div style="background: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                <p style="color: #6b7280; font-size: 12px; margin: 0;">
                  You're receiving this because you enabled weekly reports.<br>
                  <a href="https://app.tradebotx.com/dashboard/settings" style="color: #3b82f6;">Manage preferences</a>
                </p>
              </div>
            </div>
          </body>
          </html>
        `;

        // Send email using Resend
        const resendResponse = await fetch("https://api.resend.com/emails", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${Deno.env.get("RESEND_API_KEY")}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            from: Deno.env.get("SMTP_FROM") || "TradeBotX <noreply@tradebotx.com>",
            to: [userEmail],
            subject: `📊 Your Weekly Trading Report - ${pnlSign}$${stats.totalPnl.toFixed(2)}`,
            html: emailHtml
          })
        });

        if (!resendResponse.ok) {
          console.error(`Failed to send email to ${userEmail}`);
          continue;
        }

        // Update last_sent_at
        await supabase
          .from("weekly_report_settings")
          .update({ last_sent_at: new Date().toISOString() })
          .eq("id", setting.id);

        console.log(`Weekly report sent to ${userEmail}`);

      } catch (userError) {
        console.error(`Error processing user ${setting.user_id}:`, userError);
      }
    }

    return new Response(
      JSON.stringify({ success: true, processed: reportSettings?.length || 0 }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (error) {
    console.error("Error in send-weekly-report:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});