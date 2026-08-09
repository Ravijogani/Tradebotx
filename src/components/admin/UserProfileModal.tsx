import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { 
  Loader2, User, Mail, Phone, Calendar, DollarSign, 
  TrendingUp, Activity, Settings, Trash2, Save 
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Tables, Database } from "@/integrations/supabase/types";

interface UserProfileModalProps {
  userId: string | null;
  open: boolean;
  onClose: () => void;
}

type UserSubscriptionWithPlan = Tables<"user_subscriptions"> & {
  plans?: Pick<Tables<"plans">, "name" | "plan_type" | "price"> | null;
};
type UserStrategyWithStrategy = Tables<"user_strategies"> & {
  strategies?: Pick<Tables<"strategies">, "name"> | null;
};
type UserPerformance = Database["public"]["Functions"]["get_user_performance"]["Returns"][number];

interface UserProfileData extends Omit<Tables<"profiles">, "referral_code"> {
  user_subscriptions: UserSubscriptionWithPlan[];
  user_setup: Tables<"user_setup">[];
  user_roles: Pick<Tables<"user_roles">, "role">[];
  user_strategies: UserStrategyWithStrategy[];
  payment_history: Tables<"payment_history">[];
  // Shadows profiles.referral_code (the user's own code string) with the
  // joined referral_codes row — that's what loadUserData() actually builds
  // (the object spread order means the joined value wins), not a typo.
  referral_code: Tables<"referral_codes"> | null;
}

export const UserProfileModal = ({ userId, open, onClose }: UserProfileModalProps) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [userData, setUserData] = useState<UserProfileData | null>(null);
  const [performance, setPerformance] = useState<UserPerformance | null>(null);
  const [trades, setTrades] = useState<Tables<"trades">[]>([]);
  const [activity, setActivity] = useState<Tables<"admin_activity_logs">[]>([]);
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    phone: "",
  });

  useEffect(() => {
    if (open && userId) {
      loadUserData();
    }
  }, [open, userId]);

  const loadUserData = async () => {
    try {
      setLoading(true);

      // Load user profile
      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("*")
        .eq("id", userId)
        .single();

      if (profileError) throw profileError;

      // Load user subscription
      const { data: subscription } = await supabase
        .from("user_subscriptions")
        .select("*, plans(name, plan_type, price)")
        .eq("user_id", userId)
        .single();

      // Load user setup
      const { data: setup } = await supabase
        .from("user_setup")
        .select("*")
        .eq("user_id", userId)
        .single();

      // Load user roles
      const { data: roles } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", userId);

      // Load user strategies
      const { data: strategies } = await supabase
        .from("user_strategies")
        .select("*, strategies(name)")
        .eq("user_id", userId);

      // Load payment history
      const { data: payments } = await supabase
        .from("payment_history")
        .select("*")
        .eq("user_id", userId)
        .order("created_at", { ascending: false })
        .limit(5);

      // Load referral code
      const { data: referralCode } = await supabase
        .from("referral_codes")
        .select("*")
        .eq("user_id", userId)
        .maybeSingle();

      // Combine all data
      const userData = {
        ...profile,
        user_subscriptions: subscription ? [subscription] : [],
        user_setup: setup ? [setup] : [],
        user_roles: roles || [],
        user_strategies: strategies || [],
        payment_history: payments || [],
        referral_code: referralCode,
      };

      setUserData(userData);
      setFormData({
        full_name: profile.full_name || "",
        email: profile.email || "",
        phone: profile.phone || "",
      });

      // Load performance metrics
      const { data: perfData, error: perfError } = await supabase
        .rpc("get_user_performance", { p_user_id: userId });

      if (!perfError && perfData && perfData.length > 0) {
        setPerformance(perfData[0]);
      }

      // Load recent trades
      const { data: tradesData, error: tradesError } = await supabase
        .from("trades")
        .select("*")
        .eq("user_id", userId)
        .order("opened_at", { ascending: false })
        .limit(10);

      if (!tradesError) setTrades(tradesData || []);

      // Load recent activity
      const { data: activityData, error: activityError } = await supabase
        .from("admin_activity_logs")
        .select("*")
        .eq("target_user_id", userId)
        .order("created_at", { ascending: false })
        .limit(10);

      if (!activityError) setActivity(activityData || []);

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);

      const { error } = await supabase
        .from("profiles")
        .update({
          full_name: formData.full_name,
          phone: formData.phone,
        })
        .eq("id", userId);

      if (error) throw error;

      // Log activity
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        await supabase.from("admin_activity_logs").insert({
          admin_user_id: user.id,
          action_type: "user_profile_updated",
          target_user_id: userId,
          description: `Updated profile for ${formData.email}`,
        });
      }

      toast({ title: "Success", description: "User profile updated" });
      loadUserData();
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

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this user? This action cannot be undone.")) {
      return;
    }

    try {
      setSaving(true);

      // supabase.auth.admin.* requires the service-role key, which this
      // browser client never has — goes through an edge function that
      // verifies admin access and does the delete server-side instead.
      const { error } = await supabase.functions.invoke("admin-delete-user", {
        body: { userId },
      });
      if (error) throw error;

      toast({ title: "Success", description: "User deleted successfully" });
      onClose();
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

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="w-5 h-5" />
            User Profile Management
          </DialogTitle>
          <DialogDescription>
            View and edit user details, performance, and activity
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : (
          <Tabs defaultValue="details" className="space-y-4">
            <TabsList className="grid w-full grid-cols-6">
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="setup">Setup</TabsTrigger>
              <TabsTrigger value="subscription">Subscription</TabsTrigger>
              <TabsTrigger value="performance">Performance</TabsTrigger>
              <TabsTrigger value="trades">Trades</TabsTrigger>
              <TabsTrigger value="activity">Activity</TabsTrigger>
            </TabsList>

            <TabsContent value="details" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Profile Information</CardTitle>
                  <CardDescription>Update user's basic information</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Full Name</Label>
                      <Input
                        value={formData.full_name}
                        onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label>Email (Read Only)</Label>
                      <Input value={formData.email} disabled />
                    </div>
                    <div>
                      <Label>Phone</Label>
                      <Input
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      />
                    </div>
                    <div>
                      <Label>Subscription</Label>
                      <Input
                        value={userData?.user_subscriptions?.[0]?.plans?.name || "No Plan"}
                        disabled
                      />
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button onClick={handleSave} disabled={saving}>
                      {saving ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Save className="w-4 h-4 mr-2" />
                          Save Changes
                        </>
                      )}
                    </Button>
                    <Button variant="destructive" onClick={handleDelete} disabled={saving}>
                      <Trash2 className="w-4 h-4 mr-2" />
                      Delete User
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>User Roles</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2">
                    {userData?.user_roles?.length > 0 ? (
                      userData.user_roles.map((role, idx: number) => (
                        <Badge key={idx} variant="secondary">{role.role}</Badge>
                      ))
                    ) : (
                      <p className="text-muted-foreground">No roles assigned</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>User Strategies</CardTitle>
                </CardHeader>
                <CardContent>
                  {userData?.user_strategies?.length > 0 ? (
                    <div className="space-y-2">
                      {userData.user_strategies.map((strategy) => (
                        <div key={strategy.id} className="flex items-center justify-between p-2 border rounded">
                          <span>{strategy.strategies?.name || "Unknown"}</span>
                          <Badge variant={strategy.is_running ? "default" : "secondary"}>
                            {strategy.is_running ? "Running" : "Stopped"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground">No strategies configured</p>
                  )}
                </CardContent>
              </Card>

              {userData?.referral_code && (
                <Card>
                  <CardHeader>
                    <CardTitle>Referral Program</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <Label className="text-muted-foreground">Referral Code</Label>
                        <p className="font-mono">{userData.referral_code.code}</p>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">Total Referrals</Label>
                        <p>{userData.referral_code.total_referrals}</p>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">Total Earnings</Label>
                        <p>${userData.referral_code.total_earnings}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="setup" className="space-y-4">
              {userData?.user_setup?.[0] ? (
                <>
                  <Card>
                    <CardHeader>
                      <CardTitle>Broker Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-muted-foreground">Broker Name</Label>
                          <p className="font-medium">{userData.user_setup[0].broker_name || "N/A"}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Broker Account ID</Label>
                          <p className="font-mono">{userData.user_setup[0].broker_account_id || "N/A"}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Broker Referral Code</Label>
                          <p className="font-mono">{userData.user_setup[0].broker_referral_code || "N/A"}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>MT5 Configuration</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-muted-foreground">MT5 Account</Label>
                          <p className="font-mono">{userData.user_setup[0].mt5_account || "N/A"}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">MT5 Server</Label>
                          <p className="font-mono">{userData.user_setup[0].mt5_server || "N/A"}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">MT5 Password</Label>
                          <p className="font-mono">
                            {userData.user_setup[0].mt5_password ? "••••••••" : "N/A"}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Risk Management</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <Label className="text-muted-foreground">Account Size</Label>
                          <p className="font-medium text-lg">${userData.user_setup[0].account_size || 0}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Risk Per Trade</Label>
                          <p className="font-medium text-lg">{userData.user_setup[0].risk_per_trade || 0}%</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Max Positions</Label>
                          <p className="font-medium text-lg">{userData.user_setup[0].max_positions || 0}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Notifications</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div>
                        <Label className="text-muted-foreground">Telegram Chat ID</Label>
                        <p className="font-mono">{userData.user_setup[0].telegram_chat_id || "Not configured"}</p>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Setup Status</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-muted-foreground">Setup Completed</Label>
                          <Badge variant={userData.user_setup[0].is_completed ? "default" : "secondary"}>
                            {userData.user_setup[0].is_completed ? "Yes" : "No"}
                          </Badge>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Admin Approved</Label>
                          <Badge variant={userData.user_setup[0].admin_approved ? "default" : "destructive"}>
                            {userData.user_setup[0].admin_approved ? "Approved" : "Pending"}
                          </Badge>
                        </div>
                        {userData.user_setup[0].submitted_for_approval_at && (
                          <div>
                            <Label className="text-muted-foreground">Submitted At</Label>
                            <p>{new Date(userData.user_setup[0].submitted_for_approval_at).toLocaleString()}</p>
                          </div>
                        )}
                        {userData.user_setup[0].approval_notes && (
                          <div className="col-span-2">
                            <Label className="text-muted-foreground">Approval Notes</Label>
                            <p className="text-sm mt-1">{userData.user_setup[0].approval_notes}</p>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </>
              ) : (
                <Alert>
                  <AlertDescription>User has not completed setup yet.</AlertDescription>
                </Alert>
              )}
            </TabsContent>

            <TabsContent value="subscription" className="space-y-4">
              {userData?.user_subscriptions?.[0] ? (
                <>
                  <Card>
                    <CardHeader>
                      <CardTitle>Subscription Details</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-muted-foreground">Plan</Label>
                          <p className="font-medium">{userData.user_subscriptions[0].plans?.name || "N/A"}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Plan Type</Label>
                          <Badge>{userData.user_subscriptions[0].plans?.plan_type || "N/A"}</Badge>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Status</Label>
                          <Badge variant={userData.user_subscriptions[0].status === 'active' ? 'default' : 'secondary'}>
                            {userData.user_subscriptions[0].status}
                          </Badge>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Subscription Tier</Label>
                          <p>{userData.user_subscriptions[0].subscription_tier || "N/A"}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Account Balance</Label>
                          <p className="font-medium text-lg">${userData.user_subscriptions[0].account_balance || 0}</p>
                        </div>
                        <div>
                          <Label className="text-muted-foreground">Price</Label>
                          <p className="font-medium">${userData.user_subscriptions[0].plans?.price || 0}</p>
                        </div>
                        {userData.user_subscriptions[0].trial_ends_at && (
                          <div>
                            <Label className="text-muted-foreground">Trial Ends</Label>
                            <p>{new Date(userData.user_subscriptions[0].trial_ends_at).toLocaleDateString()}</p>
                          </div>
                        )}
                        {userData.user_subscriptions[0].subscription_ends_at && (
                          <div>
                            <Label className="text-muted-foreground">Subscription Ends</Label>
                            <p>{new Date(userData.user_subscriptions[0].subscription_ends_at).toLocaleDateString()}</p>
                          </div>
                        )}
                        {userData.user_subscriptions[0].last_payment_date && (
                          <div>
                            <Label className="text-muted-foreground">Last Payment</Label>
                            <p>{new Date(userData.user_subscriptions[0].last_payment_date).toLocaleDateString()}</p>
                          </div>
                        )}
                        {userData.user_subscriptions[0].payment_method && (
                          <div>
                            <Label className="text-muted-foreground">Payment Method</Label>
                            <p>{userData.user_subscriptions[0].payment_method}</p>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Payment History</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {userData?.payment_history?.length > 0 ? (
                        <div className="space-y-2">
                          {userData.payment_history.map((payment) => (
                            <div key={payment.id} className="flex items-center justify-between p-3 border rounded">
                              <div>
                                <p className="font-medium">${payment.amount} {payment.currency}</p>
                                <p className="text-sm text-muted-foreground">
                                  {new Date(payment.created_at).toLocaleDateString()}
                                </p>
                                {payment.description && (
                                  <p className="text-xs text-muted-foreground">{payment.description}</p>
                                )}
                              </div>
                              <Badge variant={payment.status === 'success' ? 'default' : 'secondary'}>
                                {payment.status}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-muted-foreground">No payment history</p>
                      )}
                    </CardContent>
                  </Card>
                </>
              ) : (
                <Alert>
                  <AlertDescription>No subscription information available.</AlertDescription>
                </Alert>
              )}
            </TabsContent>

            <TabsContent value="performance" className="space-y-4">
              {performance ? (
                <div className="grid grid-cols-3 gap-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Total PnL</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className={`text-2xl font-bold ${Number(performance.total_pnl) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                        ${Number(performance.total_pnl).toFixed(2)}
                      </p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Win Rate</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold">{Number(performance.win_rate).toFixed(1)}%</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Total Trades</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold">{performance.total_trades}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Winning Trades</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold text-green-500">{performance.winning_trades}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Losing Trades</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold text-red-500">{performance.losing_trades}</p>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Best Trade</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-2xl font-bold text-green-500">${Number(performance.best_trade).toFixed(2)}</p>
                    </CardContent>
                  </Card>
                </div>
              ) : (
                <Alert>
                  <AlertDescription>No trading performance data available yet.</AlertDescription>
                </Alert>
              )}
            </TabsContent>

            <TabsContent value="trades" className="space-y-2">
              {trades.length > 0 ? (
                trades.map((trade) => (
                  <Card key={trade.id}>
                    <CardContent className="pt-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{trade.symbol} - {trade.trade_type}</p>
                          <p className="text-sm text-muted-foreground">
                            {new Date(trade.opened_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="text-right">
                          <Badge variant={Number(trade.profit_loss) >= 0 ? "default" : "destructive"}>
                            {trade.status}
                          </Badge>
                          {trade.profit_loss && (
                            <p className={`font-bold ${Number(trade.profit_loss) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                              ${Number(trade.profit_loss).toFixed(2)}
                            </p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Alert>
                  <AlertDescription>No trades found for this user.</AlertDescription>
                </Alert>
              )}
            </TabsContent>

            <TabsContent value="activity" className="space-y-2">
              {activity.length > 0 ? (
                activity.map((log) => (
                  <Card key={log.id}>
                    <CardContent className="pt-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium capitalize">{log.action_type.replace(/_/g, ' ')}</p>
                          <p className="text-sm text-muted-foreground">{log.description}</p>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {new Date(log.created_at).toLocaleString()}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                ))
              ) : (
                <Alert>
                  <AlertDescription>No activity logs found for this user.</AlertDescription>
                </Alert>
              )}
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
};
