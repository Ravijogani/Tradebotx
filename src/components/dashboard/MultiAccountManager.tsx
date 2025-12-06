import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { Plus, Trash2, Star, Building2, Server, Loader2 } from "lucide-react";

interface MT5Account {
  id: string;
  account_name: string;
  mt5_account: string;
  mt5_server: string;
  broker_name: string | null;
  account_size: number | null;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
}

const brokers = [
  "XM", "Vantage", "PepperStone", "IC Markets", "OANDA", 
  "FXCM", "Forex.com", "IG", "Saxo Bank", "Other"
];

export const MultiAccountManager = () => {
  const [accounts, setAccounts] = useState<MT5Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    account_name: "",
    mt5_account: "",
    mt5_password: "",
    mt5_server: "",
    broker_name: "",
    account_size: "10000",
    is_primary: false
  });
  const { toast } = useToast();

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data, error } = await supabase
        .from("user_mt5_accounts")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: true });

      if (error) throw error;
      setAccounts(data || []);
    } catch (error: any) {
      toast({
        title: "Error loading accounts",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      // Use the encrypt-mt5-account edge function to securely store the password
      const { data, error } = await supabase.functions.invoke('encrypt-mt5-account', {
        body: {
          password: formData.mt5_password,
          accountData: {
            account_name: formData.account_name,
            mt5_account: formData.mt5_account,
            mt5_server: formData.mt5_server,
            broker_name: formData.broker_name,
            account_size: parseFloat(formData.account_size),
            is_primary: formData.is_primary || accounts.length === 0
          }
        }
      });

      if (error) throw error;
      if (data?.error) throw new Error(data.error);

      toast({ title: "Account added successfully" });
      setDialogOpen(false);
      setFormData({
        account_name: "",
        mt5_account: "",
        mt5_password: "",
        mt5_server: "",
        broker_name: "",
        account_size: "10000",
        is_primary: false
      });
      loadAccounts();
    } catch (error: any) {
      toast({
        title: "Error adding account",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this account?")) return;

    try {
      const { error } = await supabase
        .from("user_mt5_accounts")
        .delete()
        .eq("id", id);

      if (error) throw error;
      toast({ title: "Account deleted" });
      loadAccounts();
    } catch (error: any) {
      toast({
        title: "Error deleting account",
        description: error.message,
        variant: "destructive"
      });
    }
  };

  const handleSetPrimary = async (id: string) => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Unset all primary
      await supabase
        .from("user_mt5_accounts")
        .update({ is_primary: false })
        .eq("user_id", user.id);

      // Set new primary
      await supabase
        .from("user_mt5_accounts")
        .update({ is_primary: true })
        .eq("id", id);

      toast({ title: "Primary account updated" });
      loadAccounts();
    } catch (error: any) {
      toast({
        title: "Error updating primary account",
        description: error.message,
        variant: "destructive"
      });
    }
  };

  const toggleActive = async (id: string, isActive: boolean) => {
    try {
      const { error } = await supabase
        .from("user_mt5_accounts")
        .update({ is_active: isActive })
        .eq("id", id);

      if (error) throw error;
      loadAccounts();
    } catch (error: any) {
      toast({
        title: "Error updating account",
        description: error.message,
        variant: "destructive"
      });
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Multi-Account Management
            </CardTitle>
            <CardDescription>
              Manage multiple MT5 trading accounts from one dashboard
            </CardDescription>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Account
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Add MT5 Account</DialogTitle>
                <DialogDescription>
                  Connect a new MT5 trading account
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>Account Name</Label>
                  <Input
                    value={formData.account_name}
                    onChange={(e) => setFormData({ ...formData, account_name: e.target.value })}
                    placeholder="e.g., Main Trading Account"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>MT5 Account ID</Label>
                    <Input
                      value={formData.mt5_account}
                      onChange={(e) => setFormData({ ...formData, mt5_account: e.target.value })}
                      placeholder="12345678"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input
                      type="password"
                      value={formData.mt5_password}
                      onChange={(e) => setFormData({ ...formData, mt5_password: e.target.value })}
                      placeholder="••••••••"
                      required
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>MT5 Server</Label>
                  <Input
                    value={formData.mt5_server}
                    onChange={(e) => setFormData({ ...formData, mt5_server: e.target.value })}
                    placeholder="e.g., XMGlobal-MT5"
                    required
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Broker</Label>
                    <Select
                      value={formData.broker_name}
                      onValueChange={(value) => setFormData({ ...formData, broker_name: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select broker" />
                      </SelectTrigger>
                      <SelectContent>
                        {brokers.map((broker) => (
                          <SelectItem key={broker} value={broker}>
                            {broker}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Account Size ($)</Label>
                    <Input
                      type="number"
                      value={formData.account_size}
                      onChange={(e) => setFormData({ ...formData, account_size: e.target.value })}
                      placeholder="10000"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={formData.is_primary}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_primary: checked })}
                  />
                  <Label>Set as primary account</Label>
                </div>
                <Button type="submit" className="w-full" disabled={saving}>
                  {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                  Add Account
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {accounts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Building2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No accounts added yet</p>
            <p className="text-sm">Add your first MT5 account to get started</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {accounts.map((account) => (
              <div
                key={account.id}
                className={`flex items-center justify-between p-4 rounded-lg border ${
                  account.is_primary ? "border-accent bg-accent/5" : "border-border"
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Server className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{account.account_name}</span>
                      {account.is_primary && (
                        <Badge variant="default" className="text-xs">
                          <Star className="h-3 w-3 mr-1" />
                          Primary
                        </Badge>
                      )}
                      {!account.is_active && (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {account.broker_name} • {account.mt5_account} • {account.mt5_server}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Balance: ${account.account_size?.toLocaleString() || "N/A"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={account.is_active}
                    onCheckedChange={(checked) => toggleActive(account.id, checked)}
                  />
                  {!account.is_primary && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSetPrimary(account.id)}
                    >
                      <Star className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(account.id)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};