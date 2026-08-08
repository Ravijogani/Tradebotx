import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

import { getAuthUser, isCronAuthorized, unauthorized, forbidden } from "../_shared/auth.ts";

import { corsHeaders } from "../_shared/cors.ts";

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    // Auth: server-side calls with CRON_SECRET, or an admin user JWT
    if (!isCronAuthorized(req)) {
      const authUser = await getAuthUser(req);
      if (!authUser) return unauthorized(corsHeaders);
      const { userHasRole } = await import("../_shared/auth.ts");
      const isAdmin = await userHasRole(authUser.id, 'admin');
      if (!isAdmin) return forbidden(corsHeaders);
    }
    // --- AUTH OK ---

    const botManagerUrl = Deno.env.get('LIGHTSAIL_BOT_MANAGER_URL');
    const botManagerSecret = Deno.env.get('BOT_MANAGER_SECRET');

    if (!botManagerUrl || !botManagerSecret) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Bot manager not configured',
          configured: false,
        }),
        {
          status: 200,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // Test health endpoint
    console.log(`Testing bot manager at: ${botManagerUrl}/health`);
    
    const healthResponse = await fetch(`${botManagerUrl}/health`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${botManagerSecret}`,
      },
      signal: AbortSignal.timeout(5000), // 5 second timeout
    });

    if (!healthResponse.ok) {
      throw new Error(`Health check failed: ${healthResponse.status}`);
    }

    const healthData = await healthResponse.json();

    return new Response(
      JSON.stringify({
        success: true,
        configured: true,
        healthy: true,
        url: botManagerUrl,
        response: healthData,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('Bot manager verification failed:', error);
    return new Response(
      JSON.stringify({
        success: false,
        configured: true,
        healthy: false,
        error: message,
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );
  }
});