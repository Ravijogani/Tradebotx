import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Users, Package, TrendingUp, Shield, LogOut, LayoutDashboard, Activity, UserCog, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AdminUsers } from "@/components/admin/AdminUsers";
import { AdminSubscriptions } from "@/components/admin/AdminSubscriptions";
import { AdminAnalytics } from "@/components/admin/AdminAnalytics";
import { AdminActivityLogs } from "@/components/admin/AdminActivityLogs";
import { RoleManagement } from "@/components/admin/RoleManagement";
import { AdminStrategies } from "@/components/admin/AdminStrategies";

const AdminDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [user, setUser] = useState<any>(null);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkAdminAccess();
  }, []);

  const checkAdminAccess = async () => {
    try {
      // Check if user is authenticated
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

      // Check if user has admin role
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
    <div className="min-h-screen bg-background">
      {/* Background gradient */}
      <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />

      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-lg sticky top-0 z-40 relative">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-hero flex items-center justify-center shadow-glow">
                <Shield className="w-6 h-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
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
                className="gap-2"
              >
                <LayoutDashboard className="w-4 h-4" />
                User Dashboard
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={handleLogout}
                className="gap-2"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 relative">
        <div className="space-y-6">
          {/* Welcome Section */}
          <div className="bg-gradient-hero p-6 rounded-lg shadow-glow">
            <h2 className="text-2xl font-bold text-primary-foreground mb-2">
              Welcome to Admin Panel
            </h2>
            <p className="text-primary-foreground/80">
              Manage users, subscriptions, and view analytics from this central hub.
            </p>
          </div>

          {/* Tabs Section */}
          <Tabs defaultValue="users" className="space-y-6">
            <TabsList className="grid w-full grid-cols-6 lg:w-[900px] bg-card/50 backdrop-blur-sm">
              <TabsTrigger value="users" className="gap-2">
                <Users className="w-4 h-4" />
                <span className="hidden sm:inline">Users</span>
              </TabsTrigger>
              <TabsTrigger value="roles" className="gap-2">
                <UserCog className="w-4 h-4" />
                <span className="hidden sm:inline">Roles</span>
              </TabsTrigger>
              <TabsTrigger value="strategies" className="gap-2">
                <Zap className="w-4 h-4" />
                <span className="hidden sm:inline">Strategies</span>
              </TabsTrigger>
              <TabsTrigger value="subscriptions" className="gap-2">
                <Package className="w-4 h-4" />
                <span className="hidden sm:inline">Plans</span>
              </TabsTrigger>
              <TabsTrigger value="analytics" className="gap-2">
                <TrendingUp className="w-4 h-4" />
                <span className="hidden sm:inline">Analytics</span>
              </TabsTrigger>
              <TabsTrigger value="logs" className="gap-2">
                <Activity className="w-4 h-4" />
                <span className="hidden sm:inline">Logs</span>
              </TabsTrigger>
            </TabsList>

            <TabsContent value="users" className="space-y-4">
              <AdminUsers />
            </TabsContent>

            <TabsContent value="roles" className="space-y-4">
              <RoleManagement />
            </TabsContent>

            <TabsContent value="strategies" className="space-y-4">
              <AdminStrategies />
            </TabsContent>

            <TabsContent value="subscriptions" className="space-y-4">
              <AdminSubscriptions />
            </TabsContent>

            <TabsContent value="analytics" className="space-y-4">
              <AdminAnalytics />
            </TabsContent>

            <TabsContent value="logs" className="space-y-4">
              <AdminActivityLogs />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
