// Shared auth helpers for edge functions
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

export interface AuthUser {
  id: string;
  email?: string;
  role?: string;
}

/**
 * Validates a JWT from the Authorization header. Returns the user or null.
 */
export async function getAuthUser(req: Request): Promise<AuthUser | null> {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) return null;
  const token = authHeader.replace("Bearer ", "");

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
  );
  try {
    const { data, error } = await supabase.auth.getUser(token);
    if (error || !data?.user) return null;
    return {
      id: data.user.id,
      email: data.user.email ?? undefined,
      role: (data.user as any).role,
    };
  } catch {
    return null;
  }
}

/**
 * Returns true if the bearer token equals the CRON_SECRET env var.
 */
export function isCronAuthorized(req: Request): boolean {
  const secret = Deno.env.get("CRON_SECRET");
  if (!secret) return false;
  const authHeader = req.headers.get("Authorization") || "";
  return authHeader === `Bearer ${secret}`;
}

/**
 * Checks whether the authenticated user has the given role via user_roles.
 */
export async function userHasRole(userId: string, role: string): Promise<boolean> {
  const admin = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
  const { data, error } = await admin
    .from("user_roles")
    .select("id")
    .eq("user_id", userId)
    .eq("role", role)
    .maybeSingle();
  return !error && !!data;
}

export const unauthorized = (corsHeaders: Record<string, string>) =>
  new Response(JSON.stringify({ error: "Unauthorized" }), {
    status: 401,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

export const forbidden = (corsHeaders: Record<string, string>) =>
  new Response(JSON.stringify({ error: "Forbidden" }), {
    status: 403,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
