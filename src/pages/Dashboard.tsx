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
    // Set up auth state listener first
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        setSession(session);
        setUser(session?.user ?? null);
        
        if (!session) {
          navigate("/auth/login");
          setLoading(false);
          return;
        }

        // Check setup completion when user is authenticated
        try {
          const { data: setup, error: setupError } = await supabase
            .from("user_setup")
            .select("is_completed, admin_approved")
            .eq("user_id", session.user.id)
            .maybeSingle();

          if (setupError) {
            console.error("Error loading setup:", setupError);
          }

          if (!setup || !setup.is_completed) {
            setShowSetup(true);
          }
        } catch (error: any) {
          console.error("Setup check error:", error);
        }
        
        setLoading(false);
      }
    );

    // Check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setUser(session?.user ?? null);
      
      if (!session) {
        navigate("/auth/login");
        setLoading(false);
      }
    });

    return () => subscription.unsubscribe();
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
