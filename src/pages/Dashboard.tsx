import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { SetupDialog } from "@/components/dashboard/SetupDialog";
import { TrialExpiredModal } from "@/components/dashboard/TrialExpiredModal";
import type { Session } from "@supabase/supabase-js";

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [session, setSession] = useState<Session | null>(null);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    let mounted = true;

    const checkAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        
        if (!mounted) return;
        
        if (!session) {
          navigate("/auth/login");
          setLoading(false);
          return;
        }

        setSession(session);
        setUser(session.user);

        // Check setup completion
        const { data: setup } = await supabase
          .from("user_setup")
          .select("is_completed, admin_approved")
          .eq("user_id", session.user.id)
          .maybeSingle();

        if (!mounted) return;

        if (!setup || !setup.is_completed) {
          setShowSetup(true);
        }

        setLoading(false);
      } catch (error) {
        console.error("Auth check error:", error);
        if (mounted) {
          setLoading(false);
        }
      }
    };

    checkAuth();

    // Set up auth state listener
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        if (!mounted) return;
        
        setSession(session);
        setUser(session?.user ?? null);
        
        if (!session) {
          navigate("/auth/login");
          return;
        }

        // Check setup on auth changes
        try {
          const { data: setup } = await supabase
            .from("user_setup")
            .select("is_completed, admin_approved")
            .eq("user_id", session.user.id)
            .maybeSingle();

          if (mounted && (!setup || !setup.is_completed)) {
            setShowSetup(true);
          }
        } catch (error) {
          console.error("Setup check error:", error);
        }
      }
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <DashboardLayout user={user} />
      <TrialExpiredModal />
      {showSetup && <SetupDialog open={showSetup} onComplete={() => setShowSetup(false)} />}
    </>
  );
};

export default Dashboard;
