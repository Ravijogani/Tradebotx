import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2, Users, DollarSign, TrendingUp, Gift } from "lucide-react";

export const ReferralProgramDashboard = () => {
  const [loading, setLoading] = useState(true);
  const [referralData, setReferralData] = useState<any[]>([]);
  const [stats, setStats] = useState({
    totalReferrals: 0,
    totalEarnings: 0,
    activeReferrers: 0,
    completedReferrals: 0,
  });
  const { toast } = useToast();

  useEffect(() => {
    loadReferralData();
  }, []);

  const loadReferralData = async () => {
    try {
      // Load referral codes
      const { data: codes, error: codesError } = await supabase
        .from("referral_codes")
        .select("*")
        .order("total_earnings", { ascending: false });

      if (codesError) throw codesError;

      // Get user profiles separately
      const userIds = codes?.map(code => code.user_id) || [];
      const { data: profiles } = await supabase
        .from("profiles")
        .select("id, email, full_name")
        .in("id", userIds);

      const profileMap = new Map(profiles?.map(p => [p.id, p]));
      const codesWithProfiles = codes?.map(code => ({
        ...code,
        profiles: profileMap.get(code.user_id),
      }));

      setReferralData(codesWithProfiles || []);

      // Calculate stats
      const totalReferrals = codes?.reduce((sum, code) => sum + code.total_referrals, 0) || 0;
      const totalEarnings = codes?.reduce((sum, code) => sum + Number(code.total_earnings), 0) || 0;
      const activeReferrers = codes?.filter(code => code.is_active).length || 0;

      // Load completed transactions
      const { data: transactions } = await supabase
        .from("referral_transactions")
        .select("*", { count: "exact", head: true })
        .eq("status", "completed");

      setStats({
        totalReferrals,
        totalEarnings,
        activeReferrers,
        completedReferrals: transactions?.length || 0,
      });
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Referrals</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalReferrals}</div>
            <p className="text-xs text-muted-foreground">
              {stats.completedReferrals} completed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Earnings</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.totalEarnings.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">
              Paid to referrers
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Referrers</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeReferrers}</div>
            <p className="text-xs text-muted-foreground">
              Users with active codes
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Earnings</CardTitle>
            <Gift className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              ${stats.activeReferrers > 0 ? (stats.totalEarnings / stats.activeReferrers).toFixed(2) : '0.00'}
            </div>
            <p className="text-xs text-muted-foreground">
              Per referrer
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Referral Codes Table */}
      <Card>
        <CardHeader>
          <CardTitle>Referral Codes</CardTitle>
          <CardDescription>Overview of all referral codes and their performance</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Referrer</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Total Referrals</TableHead>
                <TableHead>Total Earnings</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {referralData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No referral codes found
                  </TableCell>
                </TableRow>
              ) : (
                referralData.map((referral) => (
                  <TableRow key={referral.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{referral.profiles?.full_name || "N/A"}</p>
                        <p className="text-sm text-muted-foreground">{referral.profiles?.email}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono">
                        {referral.code}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">{referral.total_referrals}</TableCell>
                    <TableCell className="font-medium text-green-500">
                      ${Number(referral.total_earnings).toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={referral.is_active ? "default" : "secondary"}>
                        {referral.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(referral.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};
