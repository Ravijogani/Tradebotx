import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2, LogOut, LayoutDashboard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { AdminUsers } from "@/components/admin/AdminUsers";
import { AdminSubscriptions } from "@/components/admin/AdminSubscriptions";
import { AdminAnalytics } from "@/components/admin/AdminAnalytics";
import { AdminActivityLogs } from "@/components/admin/AdminActivityLogs";
import { RoleManagement } from "@/components/admin/RoleManagement";
import { AdminStrategies } from "@/components/admin/AdminStrategies";
import { EmailTemplatesManager } from "@/components/admin/EmailTemplatesManager";
import { PlatformAnalytics } from "@/components/admin/PlatformAnalytics";
import { ReferralProgramDashboard } from "@/components/admin/ReferralProgramDashboard";
import { InvoiceBuilder } from "@/components/admin/InvoiceBuilder";
import { PlatformSettings } from "@/components/admin/PlatformSettings";
import { SupportTicketsManagement } from "@/components/admin/SupportTicketsManagement";
import { BotMonitoringDashboard } from "@/components/admin/BotMonitoringDashboard";
import { AIInsightsDashboard } from "@/components/admin/AIInsightsDashboard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const AdminDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const activeTab = searchParams.get('tab') || 'ai-insights';

  useEffect(() => {
    checkAdminAccess();
  }, []);

  const checkAdminAccess = async () => {
    try {
      const { data: { session }, error: sessionError } = await supabase.auth.getSession();
      
      if (sessionError) throw sessionError;

      if (!session?.user) {
        toast({
          title: "Authentication Required",
          description: "Please login to access the admin dashboard",
          variant: "destructive",
        });
        navigate("/admin");
        return;
      }

      setUser(session.user);

      const { data: roleData, error: roleError } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", session.user.id)
        .eq("role", "admin")
        .maybeSingle();

      if (roleError) {
        console.error("Role check error:", roleError);
        throw new Error("Failed to verify admin access");
      }

      if (!roleData) {
        toast({
          title: "Access Denied",
          description: "You don't have permission to access the admin dashboard",
          variant: "destructive",
        });
        navigate("/dashboard");
        return;
      }

      setIsAdmin(true);
    } catch (error: any) {
      console.error("Admin access check error:", error);
      toast({
        title: "Error",
        description: error.message || "Failed to verify access",
        variant: "destructive",
      });
      navigate("/admin");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await supabase.auth.signOut();
      toast({
        title: "Logged Out",
        description: "You have been logged out successfully",
      });
      navigate("/admin");
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'ai-insights':
        return <AIInsightsDashboard />;
      case 'botmonitor':
        return <BotMonitoringDashboard />;
      case 'users':
        return <AdminUsers />;
      case 'support':
        return <SupportTicketsManagement />;
      case 'roles':
        return <RoleManagement />;
      case 'strategies':
        return <AdminStrategies />;
      case 'subscriptions':
        return <AdminSubscriptions />;
      case 'analytics':
        return <AdminAnalytics />;
      case 'platform':
        return <PlatformAnalytics />;
      case 'referrals':
        return <ReferralProgramDashboard />;
      case 'invoices':
        return <InvoiceBuilder />;
      case 'emails':
        return <EmailTemplatesManager />;
      case 'settings':
        return <PlatformSettings />;
      case 'logs':
        return <AdminActivityLogs />;
      default:
        return <AIInsightsDashboard />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto" />
          <p className="text-muted-foreground">Verifying admin access...</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="min-h-screen flex w-full bg-background">
        {/* Background gradient mesh */}
        <div className="fixed inset-0 bg-gradient-mesh opacity-30 pointer-events-none -z-10" />
        
        {/* Sidebar */}
        <AdminSidebar />

        {/* Main Content */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <header className="sticky top-0 z-40 border-b border-border bg-card/80 backdrop-blur-lg">
            <div className="flex items-center justify-between h-16 px-6">
              <div className="flex items-center gap-4">
                <SidebarTrigger className="-ml-2" />
                <div>
                  <h1 className="text-lg font-bold text-foreground">
                    Admin Dashboard
                  </h1>
                  <p className="text-xs text-muted-foreground">
                    {user?.email}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => navigate("/dashboard")}
                  className="gap-2 hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  <LayoutDashboard className="w-4 h-4" />
                  <span className="hidden sm:inline">User Dashboard</span>
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={handleLogout}
                  className="gap-2 hover:bg-destructive/10 hover:text-destructive transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span className="hidden sm:inline">Logout</span>
                </Button>
              </div>
            </div>
          </header>

          {/* Main Content Area */}
          <main className="flex-1 overflow-auto">
            <div className="container mx-auto p-6 space-y-6 animate-fade-in">
              {/* Welcome Banner */}
              {activeTab === 'ai-insights' && (
                <Card className="border-none bg-gradient-to-br from-primary/10 via-accent/5 to-background shadow-glow">
                  <CardHeader>
                    <CardTitle className="text-2xl">Welcome to Admin Control Center</CardTitle>
                    <CardDescription className="text-base">
                      Monitor, manage, and optimize your trading platform from this central hub.
                    </CardDescription>
                  </CardHeader>
                </Card>
              )}

              {/* Active Tab Content */}
              <div className="animate-fade-in">
                {renderContent()}
              </div>
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};

export default AdminDashboard;
