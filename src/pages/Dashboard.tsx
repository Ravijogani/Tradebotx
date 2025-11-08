import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { SetupDialog } from "@/components/dashboard/SetupDialog";
import { TrialExpiredModal } from "@/components/dashboard/TrialExpiredModal";

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [user, setUser] = useState<any>(null);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      
      if (!session) {
        navigate("/auth/login");
        return;
      }

      setUser(session.user);

      // Check if setup is completed
      const { data: setup } = await supabase
        .from("user_setup")
        .select("is_completed, admin_approved")
        .eq("user_id", session.user.id)
        .single();

      if (!setup || !setup.is_completed) {
        setShowSetup(true);
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

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
