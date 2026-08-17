import { createClient } from "npm:@supabase/supabase-js@2";
import { getAuthUser, userHasRole, unauthorized, forbidden } from "../_shared/auth.ts";
import { handleError } from "../_shared/error-handler.ts";
import { corsHeaders } from "../_shared/cors.ts";

// Admin-side bot stop — the real one.
//
// The admin panel's per-bot "Stop" and platform-wide "Emergency Stop All"
// previously did nothing but `UPDATE user_strategies SET is_running=false`
// straight from the browser client. That relabelled the dashboard while
// every Python subprocess kept running and kept placing real trades: the
// bots polled `bot_commands.kill_switch` (a column that has never existed
// in that table) and never read `is_running` at all.
//
// Two things fix that, and both are needed:
//   1. The bots now treat `user_strategies.is_running` as authoritative and
//      poll it every cycle (see python_scripts/bot_control.py).
//   2. This function, so an admin stop ALSO signals the bot manager
//      immediately instead of waiting for the next poll.
//
// The existing `stop-trading-bot` function can't serve the admin case: it
// scopes its lookup with `.eq('user_id', user.id)`, so an admin invoking it
// against another user's bot gets zero rows. This one verifies the caller
// is an admin, then acts with the service-role client across users.
//
// Accepts either:
//   { userStrategyId: "<uuid>" }  -> stop one bot
//   { all: true }                 -> stop every running bot on the platform
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const authUser = await getAuthUser(req);
    if (!authUser) return unauthorized(corsHeaders);

    const isAdmin = await userHasRole(authUser.id, "admin");
    if (!isAdmin) return forbidden(corsHeaders);

    const { userStrategyId, all } = await req.json();
    if (!userStrategyId && all !== true) {
      return new Response(
        JSON.stringify({ error: "Pass either userStrategyId or all: true" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const adminClient = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    // Resolve the target set BEFORE flipping any flag, so we still know
    // which bots to signal after the update.
    let query = adminClient
      .from("user_strategies")
      .select("id, user_id, strategy_id, bot_pid")
      .eq("is_running", true);
    if (userStrategyId) query = query.eq("id", userStrategyId);

    const { data: targets, error: selectError } = await query;
    if (selectError) throw selectError;

    if (!targets || targets.length === 0) {
      return new Response(
        JSON.stringify({ success: true, stopped: 0, message: "No running bots matched" }),
        { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    const ids = targets.map((t) => t.id);

    // 1. Flip the authoritative flag the bots poll. Even if every bot-manager
    //    call below fails, this alone now stops them within one cycle.
    const { error: updateError } = await adminClient
      .from("user_strategies")
      .update({
        is_running: false,
        status: "stopped",
        bot_pid: null,
        stopped_at: new Date().toISOString(),
      })
      .in("id", ids);
    if (updateError) throw updateError;

    // 2. Signal the bot manager so the processes die now rather than on
    //    their next poll. Best-effort per bot: one unreachable manager must
    //    not abort the rest of an emergency stop.
    const botManagerUrl = Deno.env.get("LIGHTSAIL_BOT_MANAGER_URL");
    const botManagerSecret = Deno.env.get("BOT_MANAGER_SECRET");
    let signalled = 0;
    const signalErrors: string[] = [];

    if (botManagerUrl && botManagerSecret) {
      await Promise.all(
        targets.map(async (t) => {
          try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 8000);
            const res = await fetch(`${botManagerUrl}/bot/stop`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "x-custom-auth": botManagerSecret,
              },
              body: JSON.stringify({ user_id: t.user_id, strategy_id: t.strategy_id }),
              signal: controller.signal,
            });
            clearTimeout(timeout);
            if (res.ok) signalled++;
            else signalErrors.push(`${t.id}: manager returned ${res.status}`);
          } catch (e) {
            signalErrors.push(`${t.id}: ${e instanceof Error ? e.message : String(e)}`);
          }
        }),
      );
    } else {
      signalErrors.push("bot manager URL/secret not configured");
    }

    await adminClient.from("admin_activity_logs").insert({
      admin_user_id: authUser.id,
      action_type: all === true ? "emergency_stop_all" : "bot_stopped",
      description:
        `Admin stopped ${ids.length} bot(s); ${signalled} signalled directly` +
        (signalErrors.length ? `; issues: ${signalErrors.join(" | ")}` : ""),
    });

    return new Response(
      JSON.stringify({
        success: true,
        stopped: ids.length,
        signalled,
        // Surfaced, not swallowed: if the manager was unreachable the bots
        // still stop on their next poll, but the admin should know the
        // difference between "killed now" and "will stop shortly".
        warnings: signalErrors.length ? signalErrors : undefined,
      }),
      { status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (error) {
    return handleError(error, corsHeaders);
  }
});
