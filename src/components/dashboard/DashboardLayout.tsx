import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { TrendingUp, LogOut, FileText, Gift, BarChart3 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { StrategySelector } from "./StrategySelector";
import { TradesListEnhanced } from "./TradesListEnhanced";
import { StatsOverview } from "./StatsOverview";
import { RiskCalculator } from "./RiskCalculator";
import { UserSettings } from "./UserSettings";
import { PerformanceChart } from "./PerformanceChart";
import { NotificationsCenter } from "./NotificationsCenter";
import { ActivityTimeline } from "./ActivityTimeline";
import { AccountHealth } from "./AccountHealth";
import { ThemeToggle } from "./ThemeToggle";

export const DashboardLayout = ({ user }: { user: any }) => {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [accountSize, setAccountSize] = useState(10000);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    // Load account size from user_setup if available
    const loadAccountSize = async () => {
      const { data } = await supabase
        .from("user_setup")
        .select("account_size")
        .eq("user_id", user.id)
        .single();
      
      if (data?.account_size) {
        setAccountSize(data.account_size);
      }
    };
    
    loadAccountSize();
  }, [user.id]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    toast({
      title: "Logged out successfully",
    });
    navigate("/");
  };

  return (
    <SidebarProvider defaultOpen>
      <div className="min-h-screen flex w-full bg-background relative">
        {/* Animated Background Mesh */}
        <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
        
        {/* Sidebar */}
        <AppSidebar activeTab={activeTab} onTabChange={setActiveTab} />
        
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col relative">
          {/* Header */}
          <header className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-40 shadow-sm">
            <div className="container mx-auto px-4 lg:px-8">
              <div className="flex items-center justify-between h-16">
                <div className="flex items-center gap-3">
                  <SidebarTrigger className="-ml-1" />
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-primary flex items-center justify-center shadow-glow">
                      <TrendingUp className="w-6 h-6 text-primary-foreground" />
                    </div>
                    <span className="text-xl font-bold bg-gradient-primary bg-clip-text text-transparent">
                      TradeBotX
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <ThemeToggle />
                  <NotificationsCenter />
                  <span className="text-sm text-muted-foreground hidden md:inline px-3 py-1.5 rounded-full bg-muted/50">
                    {user.email}
                  </span>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => navigate("/payment-history")}
                    className="hidden sm:flex"
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Payments
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => navigate("/referral-program")}
                    className="hidden sm:flex"
                  >
                    <Gift className="w-4 h-4 mr-2" />
                    Referrals
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => navigate("/pl-reports")}
                    className="hidden sm:flex"
                  >
                    <BarChart3 className="w-4 h-4 mr-2" />
                    Reports
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleLogout}>
                    <LogOut className="w-4 h-4 lg:mr-2" />
                    <span className="hidden lg:inline">Logout</span>
                  </Button>
                </div>
              </div>
            </div>
          </header>

          {/* Main Content */}
          <main className="flex-1 p-4 lg:p-8 overflow-auto">
            <div className="max-w-7xl mx-auto">
              {activeTab === "dashboard" && (
                <div className="space-y-6 animate-fade-in">
                  <div>
                    <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Dashboard Overview
                    </h1>
                    <p className="text-muted-foreground">Monitor your trading performance and activity</p>
                  </div>
                  
                  {/* Stats Overview */}
                  <StatsOverview />
                  
                  {/* Performance Chart */}
                  <PerformanceChart />
                  
                  {/* Enhanced Trades List */}
                  <TradesListEnhanced />
                  
                  {/* Two Column Layout */}
                  <div className="grid lg:grid-cols-2 gap-6">
                    <ActivityTimeline />
                  </div>
                  
                  {/* Account Health */}
                  <AccountHealth />
                </div>
              )}

              {activeTab === "strategies" && (
                <div className="animate-fade-in">
                  <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Trading Strategies
                    </h1>
                    <p className="text-muted-foreground">Select and manage your automated trading strategies</p>
                  </div>
                  <StrategySelector />
                </div>
              )}

              {activeTab === "activity" && (
                <div className="animate-fade-in">
                  <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Activity Feed
                    </h1>
                    <p className="text-muted-foreground">Live feed of all your trading actions</p>
                  </div>
                  <div className="grid lg:grid-cols-2 gap-6">
                    <ActivityTimeline />
                    <div className="space-y-6">
                      <PerformanceChart />
                      <AccountHealth />
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "calculator" && (
                <div className="animate-fade-in">
                  <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Risk Calculator
                    </h1>
                    <p className="text-muted-foreground">Calculate optimal position sizes and manage risk</p>
                  </div>
                  <div className="max-w-4xl mx-auto">
                    <RiskCalculator 
                      accountSize={accountSize}
                      onLotSizeChange={(lotSize) => {
                        console.log("Calculated lot size:", lotSize);
                      }}
                    />
                  </div>
                </div>
              )}

              {activeTab === "settings" && (
                <div className="animate-fade-in">
                  <UserSettings user={user} />
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};
