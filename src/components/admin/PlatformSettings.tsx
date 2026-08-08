import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Save, Settings } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Tables, Json } from "@/integrations/supabase/types";

// value is genuinely heterogeneous per key (number, boolean, string, or
// string[] for allowed_brokers) — Json (matching the DB column) is the
// honest type; each read below narrows it to what that key actually holds.
type PlatformSetting = Tables<"platform_settings">;

export const PlatformSettings = () => {
  const [settings, setSettings] = useState<PlatformSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  // Trading Parameters
  const [maxPositionsPerUser, setMaxPositionsPerUser] = useState(5);
  const [maxRiskPerTrade, setMaxRiskPerTrade] = useState(2);
  const [minAccountSize, setMinAccountSize] = useState(10000);
  const [maxLeverage, setMaxLeverage] = useState(100);
  const [allowedBrokers, setAllowedBrokers] = useState("");
  
  // System Configuration
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [allowNewSignups, setAllowNewSignups] = useState(true);
  const [requireEmailVerification, setRequireEmailVerification] = useState(true);
  const [requireAdminApproval, setRequireAdminApproval] = useState(true);
  
  // Notifications
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [telegramNotifications, setTelegramNotifications] = useState(true);
  const [adminAlertEmail, setAdminAlertEmail] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const { data, error } = await supabase
        .from("platform_settings")
        .select("*");

      if (error) throw error;

      if (data) {
        setSettings(data);
        
        // Map settings to state
        data.forEach((setting: PlatformSetting) => {
          switch (setting.key) {
            case "max_positions_per_user":
              setMaxPositionsPerUser(setting.value as number);
              break;
            case "max_risk_per_trade":
              setMaxRiskPerTrade(setting.value as number);
              break;
            case "min_account_size":
              setMinAccountSize(setting.value as number);
              break;
            case "max_leverage":
              setMaxLeverage(setting.value as number);
              break;
            case "allowed_brokers":
              setAllowedBrokers((setting.value as string[]).join(", "));
              break;
            case "maintenance_mode":
              setMaintenanceMode(setting.value as boolean);
              break;
            case "allow_new_signups":
              setAllowNewSignups(setting.value as boolean);
              break;
            case "require_email_verification":
              setRequireEmailVerification(setting.value as boolean);
              break;
            case "require_admin_approval":
              setRequireAdminApproval(setting.value as boolean);
              break;
            case "email_notifications":
              setEmailNotifications(setting.value as boolean);
              break;
            case "telegram_notifications":
              setTelegramNotifications(setting.value as boolean);
              break;
            case "admin_alert_email":
              setAdminAlertEmail(setting.value as string);
              break;
          }
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error loading settings",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const updateSetting = async (key: string, value: Json, description: string) => {
    const { data: { user } } = await supabase.auth.getUser();
    
    const existingSetting = settings.find(s => s.key === key);
    
    if (existingSetting) {
      await supabase
        .from("platform_settings")
        .update({ 
          value, 
          description,
          updated_by: user?.id,
          updated_at: new Date().toISOString()
        })
        .eq("key", key);
    } else {
      await supabase
        .from("platform_settings")
        .insert({ 
          key, 
          value, 
          description,
          updated_by: user?.id
        });
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await Promise.all([
        updateSetting("max_positions_per_user", maxPositionsPerUser, "Maximum number of concurrent positions per user"),
        updateSetting("max_risk_per_trade", maxRiskPerTrade, "Maximum risk percentage per trade"),
        updateSetting("min_account_size", minAccountSize, "Minimum account size required"),
        updateSetting("max_leverage", maxLeverage, "Maximum leverage allowed"),
        updateSetting("allowed_brokers", allowedBrokers.split(",").map(b => b.trim()), "List of allowed brokers"),
        updateSetting("maintenance_mode", maintenanceMode, "Platform maintenance mode"),
        updateSetting("allow_new_signups", allowNewSignups, "Allow new user registrations"),
        updateSetting("require_email_verification", requireEmailVerification, "Require email verification for new users"),
        updateSetting("require_admin_approval", requireAdminApproval, "Require admin approval for user setup"),
        updateSetting("email_notifications", emailNotifications, "Enable email notifications"),
        updateSetting("telegram_notifications", telegramNotifications, "Enable Telegram notifications"),
        updateSetting("admin_alert_email", adminAlertEmail, "Admin alert email address"),
      ]);

      // Log activity
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        await supabase.from("admin_activity_logs").insert({
          admin_user_id: user.id,
          action_type: "platform_settings_updated",
          description: "Updated platform settings configuration",
        });
      }

      toast({
        title: "Settings Saved",
        description: "Platform settings have been updated successfully",
      });

      loadSettings();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings className="w-5 h-5" />
          Platform Settings
        </CardTitle>
        <CardDescription>
          Configure system-wide settings and parameters
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="trading" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="trading">Trading Parameters</TabsTrigger>
            <TabsTrigger value="system">System Configuration</TabsTrigger>
            <TabsTrigger value="notifications">Notifications</TabsTrigger>
          </TabsList>

          <TabsContent value="trading" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="maxPositions">Max Positions Per User</Label>
                <Input
                  id="maxPositions"
                  type="number"
                  value={maxPositionsPerUser}
                  onChange={(e) => setMaxPositionsPerUser(parseInt(e.target.value))}
                  className="mt-1.5"
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Maximum concurrent positions allowed per user
                </p>
              </div>

              <div>
                <Label htmlFor="maxRisk">Max Risk Per Trade (%)</Label>
                <Input
                  id="maxRisk"
                  type="number"
                  step="0.1"
                  value={maxRiskPerTrade}
                  onChange={(e) => setMaxRiskPerTrade(parseFloat(e.target.value))}
                  className="mt-1.5"
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Maximum risk percentage per trade
                </p>
              </div>

              <div>
                <Label htmlFor="minAccount">Minimum Account Size (₹)</Label>
                <Input
                  id="minAccount"
                  type="number"
                  value={minAccountSize}
                  onChange={(e) => setMinAccountSize(parseInt(e.target.value))}
                  className="mt-1.5"
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Minimum account size required to start trading
                </p>
              </div>

              <div>
                <Label htmlFor="maxLeverage">Maximum Leverage</Label>
                <Input
                  id="maxLeverage"
                  type="number"
                  value={maxLeverage}
                  onChange={(e) => setMaxLeverage(parseInt(e.target.value))}
                  className="mt-1.5"
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Maximum leverage allowed for trading
                </p>
              </div>
            </div>

            <div>
              <Label htmlFor="brokers">Allowed Brokers</Label>
              <Textarea
                id="brokers"
                value={allowedBrokers}
                onChange={(e) => setAllowedBrokers(e.target.value)}
                placeholder="Enter broker names separated by commas"
                className="mt-1.5"
              />
              <p className="text-sm text-muted-foreground mt-1">
                Comma-separated list of allowed broker names
              </p>
            </div>
          </TabsContent>

          <TabsContent value="system" className="space-y-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label>Maintenance Mode</Label>
                  <p className="text-sm text-muted-foreground">
                    Enable maintenance mode to prevent user access
                  </p>
                </div>
                <Switch
                  checked={maintenanceMode}
                  onCheckedChange={setMaintenanceMode}
                />
              </div>

              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label>Allow New Signups</Label>
                  <p className="text-sm text-muted-foreground">
                    Allow new users to register on the platform
                  </p>
                </div>
                <Switch
                  checked={allowNewSignups}
                  onCheckedChange={setAllowNewSignups}
                />
              </div>

              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label>Require Email Verification</Label>
                  <p className="text-sm text-muted-foreground">
                    Users must verify their email before accessing the platform
                  </p>
                </div>
                <Switch
                  checked={requireEmailVerification}
                  onCheckedChange={setRequireEmailVerification}
                />
              </div>

              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label>Require Admin Approval</Label>
                  <p className="text-sm text-muted-foreground">
                    Users must be approved by admin before trading
                  </p>
                </div>
                <Switch
                  checked={requireAdminApproval}
                  onCheckedChange={setRequireAdminApproval}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="notifications" className="space-y-4">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label>Email Notifications</Label>
                  <p className="text-sm text-muted-foreground">
                    Enable email notifications for system events
                  </p>
                </div>
                <Switch
                  checked={emailNotifications}
                  onCheckedChange={setEmailNotifications}
                />
              </div>

              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label>Telegram Notifications</Label>
                  <p className="text-sm text-muted-foreground">
                    Enable Telegram notifications for trade events
                  </p>
                </div>
                <Switch
                  checked={telegramNotifications}
                  onCheckedChange={setTelegramNotifications}
                />
              </div>

              <div>
                <Label htmlFor="adminEmail">Admin Alert Email</Label>
                <Input
                  id="adminEmail"
                  type="email"
                  value={adminAlertEmail}
                  onChange={(e) => setAdminAlertEmail(e.target.value)}
                  placeholder="admin@example.com"
                  className="mt-1.5"
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Email address for receiving admin alerts
                </p>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end mt-6">
          <Button onClick={handleSaveSettings} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Settings
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};