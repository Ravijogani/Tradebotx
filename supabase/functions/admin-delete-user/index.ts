import { createClient } from "npm:@supabase/supabase-js@2";
import { getAuthUser, userHasRole, unauthorized, forbidden } from "../_shared/auth.ts";
import { handleError } from "../_shared/error-handler.ts";
import { corsHeaders } from "../_shared/cors.ts";

// The admin panel's "Delete User" button previously called
// supabase.auth.admin.deleteUser() directly from the browser client, which
// only ever holds the anon key — that call always failed, since the admin
// API requires the service-role key. This function does it properly:
// verify the caller is an admin, then use the service-role client
// server-side. Dependent rows (profiles, user_setup, user_subscriptions,
// etc.) are cleaned up via each table's ON DELETE CASCADE on user_id/id
// referencing auth.users.
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const authUser = await getAuthUser(req);
    if (!authUser) return unauthorized(corsHeaders);

    const isAdmin = await userHasRole(authUser.id, "admin");
    if (!isAdmin) return forbidden(corsHeaders);

    const { userId } = await req.json();
    if (!userId || typeof userId !== "string") {
      return new Response(JSON.stringify({ error: "userId is required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (userId === authUser.id) {
      return new Response(JSON.stringify({ error: "You cannot delete your own account from here" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const adminClient = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    );

    const { error: deleteError } = await adminClient.auth.admin.deleteUser(userId);
    if (deleteError) throw deleteError;

    await adminClient.from("admin_activity_logs").insert({
      admin_user_id: authUser.id,
      action_type: "user_deleted",
      target_user_id: userId,
      description: "User account deleted by admin",
    });

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (error) {
    return handleError(error, corsHeaders);
  }
});
