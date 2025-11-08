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

interface UserProfileModalProps {
  userId: string | null;
  open: boolean;
  onClose: () => void;
}

export const UserProfileModal = ({ userId, open, onClose }: UserProfileModalProps) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [userData, setUserData] = useState<any>(null);
  const [performance, setPerformance] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);
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
        .select(`
          *,
          user_subscriptions (
            status,
            subscription_tier,
            account_balance,
            plans (name, plan_type)
          ),
          user_setup (*)
        `)
        .eq("id", userId)
        .single();

      if (profileError) throw profileError;
      setUserData(profile);
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

    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
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
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
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

      const { error } = await supabase.auth.admin.deleteUser(userId!);
      if (error) throw error;

      toast({ title: "Success", description: "User deleted successfully" });
      onClose();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
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
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="details">Details</TabsTrigger>
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

              {userData?.user_setup?.[0] && (
                <Card>
                  <CardHeader>
                    <CardTitle>Trading Setup</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-muted-foreground">Broker</Label>
                        <p>{userData.user_setup[0].broker_name || "N/A"}</p>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">MT5 Account</Label>
                        <p>{userData.user_setup[0].mt5_account || "N/A"}</p>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">Account Size</Label>
                        <p>${userData.user_setup[0].account_size || 0}</p>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">Risk Per Trade</Label>
                        <p>{userData.user_setup[0].risk_per_trade || 0}%</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
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
