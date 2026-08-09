import { ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children: ReactNode;
  /** Redirect target when there's no session. Defaults to the main login page. */
  redirectTo?: string;
  /**
   * When set, also requires the signed-in user to hold this role (checked
   * via the has_role() RPC, the same source of truth RLS policies use
   * server-side). Redirects to redirectToOnForbidden if the check fails.
   */
  requireRole?: "admin";
  redirectToOnForbidden?: string;
}

/**
 * Router-level auth guard. Individual pages may still run their own session
 * check as part of loading their data (that's harmless, not a conflict) —
 * this exists so a *new* protected page only needs to be wrapped here
 * instead of every page hand-rolling its own getSession()/navigate()
 * boilerplate. This is a client-side convenience, not the security
 * boundary — RLS policies are what actually enforce access to data.
 */
const ProtectedRoute = ({
  children,
  redirectTo = "/auth/login",
  requireRole,
  redirectToOnForbidden = "/dashboard",
}: ProtectedRouteProps) => {
  const [status, setStatus] = useState<"checking" | "allowed">("checking");
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.user) {
        if (!cancelled) navigate(redirectTo, { replace: true });
        return;
      }

      if (requireRole) {
        const { data: hasRole } = await supabase.rpc("has_role", {
          _user_id: session.user.id,
          _role: requireRole,
        });
        if (!hasRole) {
          if (!cancelled) navigate(redirectToOnForbidden, { replace: true });
          return;
        }
      }

      if (!cancelled) setStatus("allowed");
    };

    check();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return <>{children}</>;
};

// Default export so App.tsx can lazy-load this component itself — it's used
// directly (not lazily) in the Route `element` props, so without this it
// would pull its imports (the Supabase client) into the eager entry bundle
// and undo the route-level code-splitting.
export default ProtectedRoute;
