import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { isCronAuthorized, getAuthUser, userHasRole } from "../_shared/auth.ts";
import { corsHeaders } from "../_shared/cors.ts";

// Server-side bot health monitor. Run this on a schedule (every 5 minutes).
//
// The gap this closes: crash detection lived entirely in the browser.
// src/components/dashboard/BotStatusSync.tsx polls bot_heartbeats every 10s
// and emails the user when a heartbeat goes stale -- but ONLY while that user
// has the dashboard open. No server-side job watched heartbeats at all
// (every other function that touches bot_heartbeats only reads the latest
// equity value; none check freshness). So a bot that died at 3am was
// discovered whenever its owner next happened to open the app, and nobody
// operating the platform was told at all.
//
// This runs independently of any browser: finds bots marked running whose
// heartbeat has gone stale, reconciles their DB state, notifies the owner,
// and sends the operator a single digest so an incident is visible without
// anyone querying tables by hand.
//
// Deliberately idempotent: a bot already reconciled to 'crashed' is not
// re-alerted on the next tick, so a persistent outage produces one alert per
// bot rather than one every five minutes.
const STALE_AFTER_MINUTES = 5;   // heartbeat interval is ~60s; 5x that is dead, not slow

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Cron secret, or an admin running it by hand from the panel.
    let authorized = isCronAuthorized(req);
    if (!authorized) {
      const authUser = await getAuthUser(req);
      authorized = !!authUser && await userHasRole(authUser.id, "admin");
    }
    if (!authorized) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const cutoff = new Date(Date.now() - STALE_AFTER_MINUTES * 60 * 1000).toISOString();

    const { data: running, error: runErr } = await supabase
      .from("user_strategies")
      .select("id, user_id, strategy_id, status, started_at, strategies(name)")
      .eq("is_running", true);
    if (runErr) throw runErr;

    const stale: Array<Record<string, unknown>> = [];

    for (const bot of running ?? []) {
      // send-bot-stopped takes an email address, not a user id.
      const { data: profile } = await supabase
        .from("profiles")
        .select("email")
        .eq("id", bot.user_id)
        .maybeSingle();

      const { data: hb } = await supabase
        .from("bot_heartbeats")
        .select("last_heartbeat, status, mt5_connected, error_message")
        .eq("user_id", bot.user_id)
        .eq("strategy_id", bot.strategy_id)
        .order("last_heartbeat", { ascending: false })
        .limit(1)
        .maybeSingle();

      // A bot that has only just started may not have sent its first
      // heartbeat yet -- don't call that a crash.
      const startedAt = bot.started_at ? new Date(bot.started_at).getTime() : 0;
      const graceOver = Date.now() - startedAt > STALE_AFTER_MINUTES * 60 * 1000;
      if (!graceOver) continue;

      const isStale = !hb || !hb.last_heartbeat || hb.last_heartbeat < cutoff;
      if (!isStale) continue;

      // Idempotency: already reconciled and alerted on a previous tick.
      if (bot.status === "crashed") continue;

      const strategyName = (bot.strategies as { name?: string } | null)?.name ?? "Unknown strategy";
      stale.push({
        userStrategyId: bot.id,
        userId: bot.user_id,
        strategy: strategyName,
        lastHeartbeat: hb?.last_heartbeat ?? null,
        lastError: hb?.error_message ?? null,
      });

      // Reconcile: the process is gone, so the dashboard should not keep
      // showing it as live. is_running=false is also what the bots
      // themselves now treat as authoritative (python_scripts/bot_control.py),
      // so if the process is somehow alive but wedged, this stops it too.
      await supabase
        .from("user_strategies")
        .update({ is_running: false, status: "crashed", bot_pid: null, stopped_at: new Date().toISOString() })
        .eq("id", bot.id);

      await supabase.from("bot_audit_logs").insert({
        user_id: bot.user_id,
        strategy_id: bot.strategy_id,
        action: "crash",
        metadata: {
          detected_by: "monitor-bot-health",
          last_heartbeat: hb?.last_heartbeat ?? null,
          stale_after_minutes: STALE_AFTER_MINUTES,
          last_error: hb?.error_message ?? null,
        },
      });

      await supabase.from("user_notifications").insert({
        user_id: bot.user_id,
        title: "Your bot stopped unexpectedly",
        message: `${strategyName} stopped sending status updates and has been marked as stopped. `
          + `Any open positions are still held at your broker and are not being managed. `
          + `Check your account, then start the bot again when you're ready.`,
        type: "error",
      });

      // Best-effort email; a mail failure must not abort the sweep.
      try {
        if (profile?.email) {
          await supabase.functions.invoke("send-bot-stopped", {
            body: {
              email: profile.email,
              strategyName,
              reason: "No status updates received for several minutes (possible crash)",
            },
          });
        }
      } catch (_) { /* notification row above is the durable record */ }
    }

    // One operator digest per sweep, only when there is something to say.
    if (stale.length > 0) {
      try {
        await supabase.functions.invoke("send-admin-alert", {
          body: {
            actionType: "bots_crashed",
            performedBy: "monitor-bot-health (scheduled)",
            details: `${stale.length} bot(s) stopped sending heartbeats and were marked crashed:\n`
              + stale.map((s) => `- ${s.strategy} (user ${s.userId}), last seen ${s.lastHeartbeat ?? "never"}`
                + (s.lastError ? `, last error: ${s.lastError}` : "")).join("\n"),
          },
        });
      } catch (_) { /* logged below regardless */ }
    }

    console.log(`monitor-bot-health: checked ${running?.length ?? 0} running bot(s), ${stale.length} stale`);

    return new Response(
      JSON.stringify({ checked: running?.length ?? 0, stale: stale.length, details: stale }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (error) {
    console.error("monitor-bot-health failed:", error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : String(error) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  }
});
