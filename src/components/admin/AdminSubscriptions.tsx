import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2, TrendingUp, TrendingDown, Users, DollarSign } from "lucide-react";

export const AdminSubscriptions = () => {
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    trial: 0,
    revenue: 0,
  });
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    loadSubscriptions();
  }, []);

  const loadSubscriptions = async () => {
    try {
      // Load subscriptions
      const { data: subscriptions, error } = await supabase
        .from("user_subscriptions")
        .select("*, plans(name, price)")
        .order("created_at", { ascending: false });

      if (error) throw error;

      // Load user profiles
      const userIds = subscriptions?.map(s => s.user_id) || [];
      const { data: profiles } = await supabase
        .from("profiles")
        .select("id, email, full_name")
        .in("id", userIds);

      const profileMap = new Map(profiles?.map(p => [p.id, p]));
      const subsWithProfiles = subscriptions?.map(sub => ({
        ...sub,
        profiles: profileMap.get(sub.user_id),
      }));

      setSubscriptions(subsWithProfiles || []);

      // Calculate stats
      const active = subsWithProfiles?.filter(s => s.status === "active").length || 0;
      const trial = subsWithProfiles?.filter(s => s.status === "trial").length || 0;
      const revenue = subsWithProfiles
        ?.filter(s => s.status === "active")
        .reduce((sum, s) => sum + (s.plans?.price || 0), 0) || 0;

      setStats({
        total: subsWithProfiles?.length || 0,
        active,
        trial,
        revenue,
      });
    } catch (error: any) {
      toast({
        title: "Error loading subscriptions",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
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
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total</p>
                <p className="text-2xl font-bold">{stats.total}</p>
              </div>
              <Users className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Active</p>
                <p className="text-2xl font-bold text-green-500">{stats.active}</p>
              </div>
              <TrendingUp className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Trial</p>
                <p className="text-2xl font-bold text-orange-500">{stats.trial}</p>
              </div>
              <TrendingDown className="w-8 h-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">MRR</p>
                <p className="text-2xl font-bold">${stats.revenue}</p>
              </div>
              <DollarSign className="w-8 h-8 text-primary" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Subscriptions Table */}
      <Card>
        <CardHeader>
          <CardTitle>Subscription Details</CardTitle>
          <CardDescription>
            Detailed view of all user subscriptions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead>Trial Ends</TableHead>
                  <TableHead>Started</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subscriptions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      No subscriptions found
                    </TableCell>
                  </TableRow>
                ) : (
                  subscriptions.map((sub) => (
                    <TableRow key={sub.id}>
                      <TableCell className="font-medium">
                        {sub.profiles?.email || "N/A"}
                      </TableCell>
                      <TableCell>{sub.plans?.name || "N/A"}</TableCell>
                      <TableCell>
                        <Badge
                          variant={sub.status === "active" ? "default" : "secondary"}
                        >
                          {sub.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{sub.subscription_tier}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {sub.trial_ends_at
                          ? new Date(sub.trial_ends_at).toLocaleDateString()
                          : "N/A"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(sub.created_at).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
