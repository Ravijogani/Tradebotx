import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { TrendingUp, LogOut, LayoutDashboard, Settings, Calculator, FileText, Gift, BarChart3, Layers, Menu, X } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { StrategySelector } from "./StrategySelector";
import { TradesList } from "./TradesList";
import { StatsOverview } from "./StatsOverview";
import { RiskCalculator } from "./RiskCalculator";
import { UserSettings } from "./UserSettings";
import { cn } from "@/lib/utils";

export const DashboardLayout = ({ user }: { user: any }) => {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [accountSize, setAccountSize] = useState(10000);
  const [sidebarOpen, setSidebarOpen] = useState(false);
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

  const navItems = [
    { id: "dashboard", label: "Overview", icon: LayoutDashboard },
    { id: "strategies", label: "Strategies", icon: Layers },
    { id: "calculator", label: "Risk Calculator", icon: Calculator },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Animated Background Mesh */}
      <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
      
      {/* Header */}
      <header className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-50 shadow-sm">
        <div className="container mx-auto px-4 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setSidebarOpen(!sidebarOpen)}
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </Button>
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

      <div className="flex relative">
        {/* Sidebar Navigation */}
        <aside 
          className={cn(
            "fixed lg:sticky top-16 left-0 h-[calc(100vh-4rem)] w-64 bg-card/30 backdrop-blur-xl border-r border-border/50 transition-transform duration-300 z-40",
            sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          )}
        >
          <nav className="p-4 space-y-2">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setSidebarOpen(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200",
                  activeTab === item.id
                    ? "bg-primary text-primary-foreground shadow-md"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                <item.icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
              </button>
            ))}
          </nav>

          {/* Quick Actions - Mobile Only */}
          <div className="lg:hidden p-4 border-t border-border/50 space-y-2 mt-4">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => navigate("/payment-history")}
              className="w-full justify-start"
            >
              <FileText className="w-4 h-4 mr-2" />
              Payments
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => navigate("/referral-program")}
              className="w-full justify-start"
            >
              <Gift className="w-4 h-4 mr-2" />
              Referrals
            </Button>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => navigate("/pl-reports")}
              className="w-full justify-start"
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              Reports
            </Button>
          </div>
        </aside>

        {/* Backdrop for mobile */}
        {sidebarOpen && (
          <div 
            className="fixed inset-0 bg-background/80 backdrop-blur-sm z-30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main Content */}
        <main className="flex-1 p-4 lg:p-8 relative">
          <div className="max-w-7xl mx-auto">
            {activeTab === "dashboard" && (
              <div className="space-y-8 animate-fade-in">
                <div>
                  <h1 className="text-3xl font-bold tracking-tight mb-2">Dashboard Overview</h1>
                  <p className="text-muted-foreground">Monitor your trading performance and activity</p>
                </div>
                <StatsOverview />
                <TradesList />
              </div>
            )}

            {activeTab === "strategies" && (
              <div className="animate-fade-in">
                <div className="mb-8">
                  <h1 className="text-3xl font-bold tracking-tight mb-2">Trading Strategies</h1>
                  <p className="text-muted-foreground">Select and manage your automated trading strategies</p>
                </div>
                <StrategySelector />
              </div>
            )}

            {activeTab === "calculator" && (
              <div className="animate-fade-in">
                <div className="mb-8">
                  <h1 className="text-3xl font-bold tracking-tight mb-2">Risk Calculator</h1>
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
  );
};
