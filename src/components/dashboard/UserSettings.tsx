import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2, User, Mail, Building2, CreditCard, Settings as SettingsIcon, Palette } from "lucide-react";
import type { User as SupabaseUser } from "@supabase/supabase-js";
import { useTheme, type Theme } from "@/components/theme-provider";
import type { Tables } from "@/integrations/supabase/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TelegramNotificationSettings } from "./TelegramNotificationSettings";

export const UserSettings = ({ user }: { user: SupabaseUser }) => {
  const [loading, setLoading] = useState(false);
  const [setupData, setSetupData] = useState<Tables<"user_setup"> | null>(null);
  const { toast } = useToast();
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    loadSetupData();
  }, []);

  const loadSetupData = async () => {
    const { data } = await supabase
      .from("user_setup")
      .select("*")
      .eq("user_id", user.id)
      .single();
    
    if (data) {
      setSetupData(data);
    }
  };

  const handleUpdateAccount = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData(e.currentTarget);
    // user_setup's column is risk_per_trade, not risk_percentage — using the
    // wrong name here made every save of this form fail with a Postgres
    // "column does not exist" error while the account_size half silently
    // went through in the same update call.
    const updates = {
      account_size: parseFloat(formData.get("account_size") as string),
      risk_per_trade: parseFloat(formData.get("risk_per_trade") as string),
    };

    const { error } = await supabase
      .from("user_setup")
      .update(updates)
      .eq("user_id", user.id);

    if (error) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } else {
      toast({
        title: "Settings updated",
        description: "Your account settings have been saved successfully.",
      });
      loadSetupData();
    }

    setLoading(false);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
          Account Settings
        </h2>
        <p className="text-muted-foreground mt-2">
          Manage your trading account preferences and configuration
        </p>
      </div>

      <div className="grid gap-6">
        {/* Appearance Settings */}
        <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <Palette className="w-5 h-5 text-accent" />
              </div>
              <div>
                <CardTitle>Appearance</CardTitle>
                <CardDescription>Customize how TradeBotX looks</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="theme">Theme</Label>
              <Select value={theme} onValueChange={(value: Theme) => setTheme(value)}>
                <SelectTrigger id="theme">
                  <SelectValue placeholder="Select theme" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="light">Light</SelectItem>
                  <SelectItem value="dark">Dark</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Choose your preferred theme or sync with your system settings
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Account Information */}
        <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <User className="w-5 h-5 text-primary" />
              </div>
              <div>
                <CardTitle>Account Information</CardTitle>
                <CardDescription>Your personal account details</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label className="text-muted-foreground">Email Address</Label>
              <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/50 border border-border/50">
                <Mail className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">{user.email}</span>
              </div>
            </div>
            <div className="grid gap-2">
              <Label className="text-muted-foreground">User ID</Label>
              <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/50 border border-border/50">
                <CreditCard className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-mono">{user.id.slice(0, 20)}...</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Broker Information */}
        {setupData && (
          <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Building2 className="w-5 h-5 text-accent" />
                </div>
                <div>
                  <CardTitle>Broker Configuration</CardTitle>
                  <CardDescription>Your connected trading broker details</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label className="text-muted-foreground">Broker Name</Label>
                  <div className="px-3 py-2 rounded-md bg-muted/50 border border-border/50">
                    <span className="text-sm font-semibold">{setupData.broker_name || "N/A"}</span>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label className="text-muted-foreground">Account ID</Label>
                  <div className="px-3 py-2 rounded-md bg-muted/50 border border-border/50">
                    <span className="text-sm font-mono">{setupData.broker_account_id || "N/A"}</span>
                  </div>
                </div>
              </div>
              <div className="grid gap-2">
                <Label className="text-muted-foreground">MT5 Server</Label>
                <div className="px-3 py-2 rounded-md bg-muted/50 border border-border/50">
                  <span className="text-sm">{setupData.mt5_server || "N/A"}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 p-3 rounded-lg bg-success/5 border border-success/20">
                <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
                <span className="text-sm text-success">
                  {setupData.admin_approved ? "Account Approved" : "Pending Approval"}
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Telegram Notifications */}
        <TelegramNotificationSettings userId={user.id} />

        {/* Trading Configuration */}
        {setupData && (
          <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-chart-2/10 flex items-center justify-center">
                  <SettingsIcon className="w-5 h-5 text-chart-2" />
                </div>
                <div>
                  <CardTitle>Trading Preferences</CardTitle>
                  <CardDescription>Configure your trading parameters</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleUpdateAccount} className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="account_size">Account Size ($)</Label>
                    <Input
                      id="account_size"
                      name="account_size"
                      type="number"
                      step="0.01"
                      defaultValue={setupData.account_size || 10000}
                      required
                      className="bg-background/50"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="risk_per_trade">Risk per Trade (%)</Label>
                    <Input
                      id="risk_per_trade"
                      name="risk_per_trade"
                      type="number"
                      step="0.1"
                      max="100"
                      defaultValue={setupData.risk_per_trade || 2}
                      required
                      className="bg-background/50"
                    />
                  </div>
                </div>
                <Separator />
                <Button type="submit" disabled={loading} className="w-full md:w-auto">
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};