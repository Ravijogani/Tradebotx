import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { StrategyBuilder } from "@/components/strategy-builder/StrategyBuilder";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/dashboard/AppSidebar";
import { ThemeToggle } from "@/components/dashboard/ThemeToggle";
import { UserProfileDropdown } from "@/components/dashboard/UserProfileDropdown";
import { Loader2, Crown, Lock, ArrowLeft } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import logo from "@/assets/tradebotx-logo.png";
import logoWhite from "@/assets/tradebotx-logo-white.png";
import { useTheme } from "@/components/theme-provider";

const StrategyBuilderPage = () => {
  const [loading, setLoading] = useState(true);
  const [hasAccess, setHasAccess] = useState(false);
  const [planType, setPlanType] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);
  const navigate = useNavigate();
  const { toast } = useToast();
  const { theme } = useTheme();

  useEffect(() => {
    checkAccess();
  }, []);

  const checkAccess = async () => {
    try {
      const { data: { user: authUser } } = await supabase.auth.getUser();
      if (!authUser) {
        navigate("/auth/login");
        return;
      }
      setUser(authUser);

      // Check subscription plan
      const { data: subscription } = await supabase
        .from("user_subscriptions")
        .select("*, plans(*)")
        .eq("user_id", authUser.id)
        .single();

      const userPlanType = (subscription?.plans as any)?.plan_type;
      setPlanType(userPlanType);

      // Enterprise users only
      if (userPlanType === "enterprise") {
        setHasAccess(true);
      }
    } catch (error: any) {
      toast({
        title: "Error checking access",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const effectiveTheme = theme === "system" 
    ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : theme;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <Card className="max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <Crown className="h-8 w-8 text-primary" />
            </div>
            <CardTitle>Enterprise Feature</CardTitle>
            <CardDescription>
              Custom Strategy Development is available exclusively for Enterprise plan subscribers
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-center gap-2">
              <Badge variant="secondary">{planType || "Free"} Plan</Badge>
              <Lock className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>With Enterprise, you get:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Visual drag-drop strategy builder</li>
                <li>Custom indicator combinations</li>
                <li>Personal strategy approval</li>
                <li>Unlimited strategy templates</li>
              </ul>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => navigate("/dashboard")}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
              <Button className="flex-1" onClick={() => navigate("/pricing")}>
                Upgrade to Enterprise
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="min-h-screen flex w-full bg-background">
        <AppSidebar activeTab="strategy-builder" onTabChange={(tab) => {
          if (tab === "dashboard") navigate("/dashboard");
        }} />
        <main className="flex-1 flex flex-col">
          {/* Header */}
          <header className="h-16 border-b border-border flex items-center justify-between px-4 bg-card">
            <div className="flex items-center gap-4">
              <SidebarTrigger />
              <img 
                src={effectiveTheme === "dark" ? logoWhite : logo} 
                alt="TradeBotX" 
                className="h-8"
              />
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <UserProfileDropdown user={user} onSettingsClick={() => navigate("/dashboard")} />
            </div>
          </header>
          
          {/* Strategy Builder */}
          <div className="flex-1">
            <StrategyBuilder />
          </div>
        </main>
      </div>
    </SidebarProvider>
  );
};

export default StrategyBuilderPage;