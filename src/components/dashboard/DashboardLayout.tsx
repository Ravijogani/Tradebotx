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
import { QuickStrategyControl } from "./QuickStrategyControl";
import { usePullToRefresh } from "@/hooks/usePullToRefresh";
import { RefreshCw } from "lucide-react";

export const DashboardLayout = ({ user }: { user: any }) => {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [accountSize, setAccountSize] = useState(10000);
  const [effectiveTheme, setEffectiveTheme] = useState<"light" | "dark">("dark");
  const navigate = useNavigate();
  const { toast } = useToast();
  const { theme } = useTheme();
  
  // Pull to refresh handler
  const handleRefresh = async () => {
    // Simulate refresh - reload current data
    await new Promise(resolve => setTimeout(resolve, 1000));
    window.location.reload();
  };
  
  const pullToRefresh = usePullToRefresh({
    onRefresh: handleRefresh,
    threshold: 80
  });
  
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
    <SidebarProvider defaultOpen={false}>
      {/* Background component to sync bot status */}
      <BotStatusSync />
      
      <div className="min-h-screen flex w-full bg-background relative overflow-x-hidden">
        {/* Animated Background Mesh */}
        <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
        
        {/* Sidebar */}
        <AppSidebar activeTab={activeTab} onTabChange={handleTabChange} />
        
        {/* Main Content Area */}
        <div className="flex-1 flex flex-col relative min-w-0">
          {/* Header */}
          <header className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-40 shadow-sm">
            <div className="w-full px-3 sm:px-4 lg:px-8">
              <div className="flex items-center justify-between h-14 sm:h-16">
                {/* Left Side: Sidebar Trigger + Logo */}
                <div className="flex items-center gap-2 sm:gap-3">
                  <SidebarTrigger className="-ml-1" />
                  <img 
                    src={currentLogo} 
                    alt="TradeBotX" 
                    className="h-6 sm:h-8 w-auto object-contain"
                  />
                </div>

                {/* Right Side: Notifications + Theme + Profile */}
                <div className="flex items-center gap-1 sm:gap-2">
                  <NotificationCenter />
                  <ThemeToggle />
                  <UserProfileDropdown user={user} onSettingsClick={() => handleTabChange("settings")} />
                </div>
              </div>
            </div>
          </header>

          {/* Pull to Refresh Indicator */}
          {pullToRefresh.pullDistance > 0 && (
            <div 
              className="absolute top-14 sm:top-16 left-0 right-0 flex justify-center items-center z-50 transition-all duration-200"
              style={{ 
                height: `${Math.min(pullToRefresh.pullDistance, 60)}px`,
                opacity: pullToRefresh.pullProgress 
              }}
            >
              <div className="flex items-center gap-2 text-primary">
                <RefreshCw 
                  className={`w-5 h-5 ${pullToRefresh.isRefreshing ? 'animate-spin' : ''}`}
                  style={{ 
                    transform: `rotate(${pullToRefresh.pullProgress * 360}deg)` 
                  }}
                />
                {pullToRefresh.isRefreshing && <span className="text-sm">Refreshing...</span>}
              </div>
            </div>
          )}

          {/* Main Content */}
          <main 
            ref={pullToRefresh.ref as any}
            className="flex-1 p-3 sm:p-4 md:p-6 lg:p-8 overflow-x-hidden overflow-y-auto"
          >
            <div className="w-full max-w-7xl mx-auto space-y-4 sm:space-y-6">
              {activeTab === "dashboard" && (
                <div className="space-y-4 sm:space-y-6 animate-fade-in w-full min-w-0">
                  <div className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Dashboard Overview
                    </h1>
                    <p className="text-sm sm:text-base text-muted-foreground">Monitor your trading performance and activity</p>
                  </div>
                  
                  {/* Stats Overview */}
                  <StatsOverview />
                  
                  {/* Active Bots Counter */}
                  <ActiveBotsCounter />
                  
                  {/* Quick Strategy Controls */}
                  <QuickStrategyControl />
                  
                  {/* Bot Health & Open Positions */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6 w-full">
                    <div className="lg:col-span-1">
                      <BotHealthIndicator />
                    </div>
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
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 w-full">
                    <ActivityTimeline />
                  </div>
                  
                  {/* Account Health */}
                  <AccountHealth />
                </div>
              )}

              {activeTab === "strategies" && (
                <div className="animate-fade-in space-y-4 sm:space-y-6 w-full min-w-0">
                  <div className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Trading Strategies
                    </h1>
                    <p className="text-sm sm:text-base text-muted-foreground">Select and manage your automated trading strategies</p>
                  </div>
                  <StrategySelection />
                </div>
              )}

              {activeTab === "activity" && (
                <div className="animate-fade-in space-y-4 sm:space-y-6 w-full min-w-0">
                  <div className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Activity Feed
                    </h1>
                    <p className="text-sm sm:text-base text-muted-foreground">Live feed of all your trading actions</p>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 w-full">
                    <ActivityTimeline />
                    <div className="space-y-4 sm:space-y-6">
                      <PerformanceChart />
                      <AccountHealth />
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "calculator" && (
                <div className="animate-fade-in space-y-4 sm:space-y-6 w-full min-w-0">
                  <div className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Risk Calculator
                    </h1>
                    <p className="text-sm sm:text-base text-muted-foreground">Calculate optimal position sizes and manage risk</p>
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
                <div className="animate-fade-in space-y-4 sm:space-y-6 w-full min-w-0">
                  <div className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Support Center
                    </h1>
                    <p className="text-sm sm:text-base text-muted-foreground">Get help from our support team</p>
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
                <div className="animate-fade-in space-y-4 sm:space-y-6 w-full min-w-0">
                  <div className="space-y-2">
                    <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
                      Subscription Management
                    </h1>
                    <p className="text-sm sm:text-base text-muted-foreground">Manage your plan and billing</p>
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
