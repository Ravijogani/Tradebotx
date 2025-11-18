import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { supabase } from "@/integrations/supabase/client";
import { 
  TrendingUp, 
  Shield, 
  Target, 
  Wallet,
  AlertTriangle
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

export const AccountHealth = () => {
  const [accountData, setAccountData] = useState({
    balance: 0,
    dailyPL: 0,
    riskExposure: 0,
    maxDrawdown: 0,
  });

  useEffect(() => {
    loadAccountHealth();
  }, []);

  const loadAccountHealth = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    // Get setup data for account balance
    const { data: setup } = await supabase
      .from("user_setup")
      .select("account_size")
      .eq("user_id", user.id)
      .single();

    // Get today's trades for daily P&L
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const { data: todayTrades } = await supabase
      .from("trades")
      .select("profit_loss")
      .eq("user_id", user.id)
      .gte("opened_at", today.toISOString());

    // Get all trades for risk calculation
    const { data: allTrades } = await supabase
      .from("trades")
      .select("profit_loss, entry_price, quantity")
      .eq("user_id", user.id);

    let dailyPL = 0;
    if (todayTrades) {
      dailyPL = todayTrades.reduce((sum, trade) => 
        sum + parseFloat(String(trade.profit_loss || 0)), 0
      );
    }

    // Calculate risk exposure (open positions value / account size)
    const { data: openTrades } = await supabase
      .from("trades")
      .select("entry_price, quantity")
      .eq("user_id", user.id)
      .in("status", ["pending", "executed", "OPEN"]);

    let riskExposure = 0;
    if (openTrades && setup) {
      const openValue = openTrades.reduce((sum, trade) => 
        sum + (parseFloat(String(trade.entry_price)) * parseFloat(String(trade.quantity))), 0
      );
      riskExposure = (openValue / (setup.account_size || 10000)) * 100;
    }

    // Calculate max drawdown
    let maxDrawdown = 0;
    if (allTrades && allTrades.length > 0) {
      let peak = 0;
      let cumulative = 0;
      
      allTrades.forEach(trade => {
        cumulative += parseFloat(String(trade.profit_loss || 0));
        peak = Math.max(peak, cumulative);
        const drawdown = ((peak - cumulative) / peak) * 100;
        maxDrawdown = Math.max(maxDrawdown, drawdown);
      });
    }

    setAccountData({
      balance: setup?.account_size || 10000,
      dailyPL,
      riskExposure: Math.min(riskExposure, 100),
      maxDrawdown: Math.min(maxDrawdown, 100),
    });
  };

  const getRiskLevel = (exposure: number) => {
    if (exposure < 30) return { label: "Low", color: "text-success" };
    if (exposure < 60) return { label: "Medium", color: "text-warning" };
    return { label: "High", color: "text-destructive" };
  };

  const riskLevel = getRiskLevel(accountData.riskExposure);

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Account Balance Card */}
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Account Balance</CardTitle>
              <CardDescription>Current trading capital</CardDescription>
            </div>
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Wallet className="w-5 h-5 text-primary" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="text-3xl font-bold">
              ${accountData.balance.toLocaleString()}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Today's P&L:</span>
              <span
                className={`text-sm font-semibold ${
                  accountData.dailyPL >= 0 ? "text-success" : "text-destructive"
                }`}
              >
                {accountData.dailyPL >= 0 ? "+" : ""}${accountData.dailyPL.toFixed(2)}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Risk Exposure Card */}
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Risk Exposure</CardTitle>
              <CardDescription>Current market exposure</CardDescription>
            </div>
            <div className="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-warning" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className={`text-2xl font-bold ${riskLevel.color}`}>
                {accountData.riskExposure.toFixed(1)}%
              </span>
              <Badge variant={riskLevel.label === "Low" ? "default" : "destructive"}>
                {riskLevel.label} Risk
              </Badge>
            </div>
            <Progress value={accountData.riskExposure} className="h-2" />
            {accountData.riskExposure > 70 && (
              <div className="flex items-center gap-2 text-sm text-destructive">
                <AlertTriangle className="w-4 h-4" />
                <span>High exposure detected</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Max Drawdown Card */}
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Max Drawdown</CardTitle>
              <CardDescription>Peak to trough decline</CardDescription>
            </div>
            <div className="w-10 h-10 rounded-lg bg-destructive/10 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-destructive rotate-180" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="text-2xl font-bold text-destructive">
              {accountData.maxDrawdown.toFixed(1)}%
            </div>
            <Progress value={accountData.maxDrawdown} className="h-2" />
            <p className="text-xs text-muted-foreground">
              Keep drawdown below 20% for optimal risk management
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Risk Management Tips */}
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Risk Tips</CardTitle>
              <CardDescription>Improve your trading health</CardDescription>
            </div>
            <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
              <Target className="w-5 h-5 text-accent" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2">
              <span className="text-success mt-0.5">✓</span>
              <span>Risk no more than 1-2% per trade</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-success mt-0.5">✓</span>
              <span>Maintain total exposure under 50%</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-success mt-0.5">✓</span>
              <span>Set stop-loss on every position</span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
};
