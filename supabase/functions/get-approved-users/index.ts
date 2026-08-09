import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { timingSafeEqual } from "../_shared/auth.ts";
import { handleError } from "../_shared/error-handler.ts";

import { corsHeadersWithCustomAuth as corsHeaders } from "../_shared/cors.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Verify bot manager secret
    const authHeader = req.headers.get("x-custom-auth");
    const botManagerSecret = Deno.env.get("BOT_MANAGER_SECRET");

    if (!authHeader || !botManagerSecret || !timingSafeEqual(authHeader, botManagerSecret)) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    const { data, error } = await supabase
      .from("user_setup")
      .select("user_id")
      .eq("admin_approved", true)
      .eq("is_completed", true);

    if (error) throw error;

    return new Response(JSON.stringify({ users: data }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return handleError(err, corsHeaders);
  }
});
