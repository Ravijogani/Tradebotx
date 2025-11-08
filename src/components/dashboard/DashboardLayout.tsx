import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { TrendingUp, LogOut, Play, Square, LayoutDashboard, Settings, Calculator, FileText, Gift, BarChart3 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import { StrategySelector } from "./StrategySelector";
import { TradesList } from "./TradesList";
import { StatsOverview } from "./StatsOverview";
import { RiskCalculator } from "./RiskCalculator";

export const DashboardLayout = ({ user }: { user: any }) => {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [accountSize, setAccountSize] = useState(10000); // Default account size
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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-lg sticky top-0 z-40">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-lg bg-gradient-hero flex items-center justify-center shadow-glow">
                <TrendingUp className="w-6 h-6 text-primary-foreground" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                AlgoTradeX
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground hidden md:inline">{user.email}</span>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate("/payment-history")}
              >
                <FileText className="w-4 h-4 md:mr-2" />
                <span className="hidden md:inline">Payments</span>
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate("/referral-program")}
              >
                <Gift className="w-4 h-4 md:mr-2" />
                <span className="hidden md:inline">Referrals</span>
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => navigate("/pl-reports")}
              >
                <BarChart3 className="w-4 h-4 md:mr-2" />
                <span className="hidden md:inline">Reports</span>
              </Button>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 md:mr-2" />
                <span className="hidden md:inline">Logout</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-8 border-b border-border">
          {[
            { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
            { id: "strategies", label: "Strategies", icon: Play },
            { id: "calculator", label: "Risk Calculator", icon: Calculator },
            { id: "settings", label: "Settings", icon: Settings },
          ].map((tab) => (
            <Button
              key={tab.id}
              variant={activeTab === tab.id ? "default" : "ghost"}
              onClick={() => setActiveTab(tab.id)}
              className="rounded-b-none"
            >
              <tab.icon className="w-4 h-4 mr-2" />
              {tab.label}
            </Button>
          ))}
        </div>

        {/* Content */}
        {activeTab === "dashboard" && (
          <div className="space-y-8">
            <StatsOverview />
            <TradesList />
          </div>
        )}

        {activeTab === "strategies" && <StrategySelector />}

        {activeTab === "calculator" && (
          <div className="max-w-4xl mx-auto">
            <RiskCalculator 
              accountSize={accountSize}
              onLotSizeChange={(lotSize) => {
                console.log("Calculated lot size:", lotSize);
              }}
            />
          </div>
        )}

        {activeTab === "settings" && (
          <div className="max-w-2xl">
            <h2 className="text-2xl font-bold mb-4">Account Settings</h2>
            <p className="text-muted-foreground">Settings panel coming soon...</p>
          </div>
        )}
      </div>
    </div>
  );
};
