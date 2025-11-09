import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import logo from "@/assets/tradebotx-logo.png";
import logoWhite from "@/assets/tradebotx-logo-white.png";
import { useTheme } from "@/components/theme-provider";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "./AppSidebar";
import { StrategySelection } from "./StrategySelection";
import { TradesListEnhanced } from "./TradesListEnhanced";
import { StatsOverview } from "./StatsOverview";
import { RiskCalculator } from "./RiskCalculator";
import { UserSettings } from "./UserSettings";
import { PerformanceChart } from "./PerformanceChart";
import { NotificationsCenter } from "./NotificationsCenter";
import { NotificationCenter } from "./NotificationCenter";
import { ActivityTimeline } from "./ActivityTimeline";
import { UserSupport } from "./UserSupport";
import { SubscriptionManager } from "./SubscriptionManager";
import { AccountHealth } from "./AccountHealth";
import { ThemeToggle } from "./ThemeToggle";
import { UserProfileDropdown } from "./UserProfileDropdown";
import { SupportTickets } from "./SupportTickets";
import { FAQ } from "./FAQ";
import { OpenPositions } from "./OpenPositions";
import { BotHealthIndicator } from "./BotHealthIndicator";
import { BotStatusSync } from "./BotStatusSync";
import { ActiveBotsCounter } from "./ActiveBotsCounter";
import { StrategyPerformance } from "./StrategyPerformance";
import { AIInsightsDashboard } from "./AIInsightsDashboard";

export const DashboardLayout = ({ user }: { user: any }) => {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [accountSize, setAccountSize] = useState(10000);
  const [effectiveTheme, setEffectiveTheme] = useState<"light" | "dark">("dark");
  const navigate = useNavigate();
  const { toast } = useToast();
  const { theme } = useTheme();
  
  // Update effective theme when theme setting changes or system preference changes
  useEffect(() => {
    const updateEffectiveTheme = () => {
      if (theme === "light") {
        setEffectiveTheme("light");
      } else if (theme === "dark") {
        setEffectiveTheme("dark");
      } else if (theme === "system") {
        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        setEffectiveTheme(isDark ? "dark" : "light");
      }
    };

    updateEffectiveTheme();

    // Listen for system theme changes
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      if (theme === "system") {
        updateEffectiveTheme();
      }
    };

    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme]);
  
  const currentLogo = effectiveTheme === "light" ? logo : logoWhite;

  useEffect(() => {
    // Load account size from user_setup if available
    const loadAccountSize = async () => {
      const { data } = await supabase
        .from("user_setup")
        .select("account_size")
        .eq("user_id", user.id)
        .maybeSingle();
      
      if (data?.account_size) {
        setAccountSize(data.account_size);
      }
    };
    
    loadAccountSize();
  }, [user.id]);

  // Handle tab changes with smooth scrolling
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    // Scroll to top when changing tabs
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <SidebarProvider defaultOpen>
      {/* Background component to sync bot status */}
      <BotStatusSync />
      
      <div className="min-h-screen flex w-full bg-background relative">
        {/* Animated Background Mesh */}
        <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
        
        {/* Sidebar */}
        <AppSidebar activeTab={activeTab} onTabChange={handleTabChange} />
        
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col relative">
          {/* Header */}
          <header className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-40 shadow-sm">
            <div className="container mx-auto px-4 lg:px-8">
              <div className="flex items-center justify-between h-16">
                {/* Left Side: Sidebar Trigger + Logo */}
                <div className="flex items-center gap-3">
                  <SidebarTrigger className="-ml-1" />
                  <img 
                    src={currentLogo} 
                    alt="TradeBotX" 
                    className="h-8 w-auto object-contain"
                  />
                </div>

                {/* Right Side: Notifications + Theme + Profile */}
                <div className="flex items-center gap-2">
                  <NotificationCenter />
                  <ThemeToggle />
                  <UserProfileDropdown user={user} onSettingsClick={() => handleTabChange("settings")} />
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
                  
                  {/* Active Bots Counter */}
                  <ActiveBotsCounter />
                  
                  {/* Bot Health & Open Positions */}
                  <div className="grid lg:grid-cols-3 gap-6">
                    <BotHealthIndicator />
                    <div className="lg:col-span-2">
                      <OpenPositions />
                    </div>
                  </div>
                  
                  {/* Strategy Performance */}
                  <StrategyPerformance />
                  
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
                  <StrategySelection />
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

              {activeTab === "support" && (
                <div className="animate-fade-in">
                  <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Support Center
                    </h1>
                    <p className="text-muted-foreground">Get help from our support team</p>
                  </div>
                  <UserSupport />
                </div>
              )}

              {activeTab === "ai-insights" && (
                <div className="animate-fade-in">
                  <AIInsightsDashboard />
                </div>
              )}

              {activeTab === "subscription" && (
                <div className="animate-fade-in">
                  <div className="mb-8">
                    <h1 className="text-3xl font-bold tracking-tight mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Subscription Management
                    </h1>
                    <p className="text-muted-foreground">Manage your plan and billing</p>
                  </div>
                  <SubscriptionManager />
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
};
