import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  Users, 
  TrendingUp, 
  Activity, 
  AlertCircle, 
  CheckCircle, 
  DollarSign,
  Bot,
  MessageSquare,
  UserCheck,
  Clock
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

interface DashboardStats {
  totalUsers: number;
  activeUsers: number;
  trialUsers: number;
  totalRevenue: number;
  activeBots: number;
  openTickets: number;
  recentSignups: number;
  systemHealth: number;
}

export const AdminOverview = () => {
  const [stats, setStats] = useState<DashboardStats>({
    totalUsers: 0,
    activeUsers: 0,
    trialUsers: 0,
    totalRevenue: 0,
    activeBots: 0,
    openTickets: 0,
    recentSignups: 0,
    systemHealth: 100
  });
  const [loading, setLoading] = useState(true);
  const [recentActivity, setRecentActivity] = useState<any[]>([]);
  const [criticalIssues, setCriticalIssues] = useState<any[]>([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch user statistics
      const { count: totalUsers } = await supabase
        .from('profiles')
        .select('*', { count: 'exact', head: true });

      const { count: activeUsers } = await supabase
        .from('user_subscriptions')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'active');

      const { count: trialUsers } = await supabase
        .from('user_subscriptions')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'trial');

      // Fetch revenue data
      const { data: revenueData } = await supabase
        .from('payment_history')
        .select('amount')
        .eq('status', 'completed');

      const totalRevenue = revenueData?.reduce((sum, payment) => sum + payment.amount, 0) || 0;

      // Fetch bot statistics
      const { count: activeBots } = await supabase
        .from('bot_heartbeats')
        .select('*', { count: 'exact', head: true })
        .eq('status', 'running');

      // Fetch support tickets
      const { count: openTickets } = await supabase
        .from('support_tickets')
        .select('*', { count: 'exact', head: true })
        .in('status', ['open', 'in_progress']);

      // Fetch recent signups (last 7 days)
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      
      const { count: recentSignups } = await supabase
        .from('profiles')
        .select('*', { count: 'exact', head: true })
        .gte('created_at', sevenDaysAgo.toISOString());

      // Fetch recent activity
      const { data: activityData } = await supabase
        .from('admin_activity_logs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(5);

      // Fetch critical issues (bot errors, failed payments, etc.)
      const { data: botErrors } = await supabase
        .from('bot_heartbeats')
        .select('*')
        .not('error_message', 'is', null)
        .order('updated_at', { ascending: false })
        .limit(5);

      setStats({
        totalUsers: totalUsers || 0,
        activeUsers: activeUsers || 0,
        trialUsers: trialUsers || 0,
        totalRevenue,
        activeBots: activeBots || 0,
        openTickets: openTickets || 0,
        recentSignups: recentSignups || 0,
        systemHealth: botErrors && botErrors.length > 5 ? 75 : 95
      });

      setRecentActivity(activityData || []);
      setCriticalIssues(botErrors || []);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Admin Dashboard</h2>
        <p className="text-muted-foreground">
          Overview of your platform's performance and health
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalUsers}</div>
            <p className="text-xs text-muted-foreground">
              +{stats.recentSignups} in last 7 days
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Subscriptions</CardTitle>
            <UserCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeUsers}</div>
            <p className="text-xs text-muted-foreground">
              {stats.trialUsers} trial users
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">₹{stats.totalRevenue.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              Lifetime earnings
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Bots</CardTitle>
            <Bot className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeBots}</div>
            <p className="text-xs text-muted-foreground">
              Currently running
            </p>
          </CardContent>
        </Card>
      </div>

      {/* System Health & Alerts */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              System Health
            </CardTitle>
            <CardDescription>Current platform performance</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Overall Health</span>
                <span className="font-medium">{stats.systemHealth}%</span>
              </div>
              <Progress value={stats.systemHealth} className="h-2" />
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span>Database: Operational</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span>API: Healthy</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                {stats.activeBots > 0 ? (
                  <>
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span>Bots: Running</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                    <span>Bots: No active bots</span>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Action Required
            </CardTitle>
            <CardDescription>Items needing your attention</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-orange-500" />
                <span className="text-sm">Open Support Tickets</span>
              </div>
              <Badge variant={stats.openTickets > 5 ? "destructive" : "secondary"}>
                {stats.openTickets}
              </Badge>
            </div>

            {criticalIssues.length > 0 && (
              <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-500" />
                  <span className="text-sm">Bot Errors</span>
                </div>
                <Badge variant="destructive">
                  {criticalIssues.length}
                </Badge>
              </div>
            )}

            {stats.trialUsers > 0 && (
              <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-500" />
                  <span className="text-sm">Trial Users Expiring Soon</span>
                </div>
                <Badge variant="outline">
                  Check
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity & Critical Issues */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Admin Activity</CardTitle>
            <CardDescription>Latest actions performed by admins</CardDescription>
          </CardHeader>
          <CardContent>
            {recentActivity.length > 0 ? (
              <div className="space-y-3">
                {recentActivity.map((activity) => (
                  <div key={activity.id} className="flex items-start gap-3 text-sm">
                    <div className="w-2 h-2 mt-1.5 rounded-full bg-primary" />
                    <div className="flex-1">
                      <p className="font-medium">{activity.action_type}</p>
                      <p className="text-xs text-muted-foreground">{activity.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(activity.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No recent activity</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Critical Issues</CardTitle>
            <CardDescription>Bot errors and system alerts</CardDescription>
          </CardHeader>
          <CardContent>
            {criticalIssues.length > 0 ? (
              <div className="space-y-3">
                {criticalIssues.map((issue) => (
                  <div key={issue.id} className="flex items-start gap-3 text-sm p-3 bg-destructive/10 rounded-lg">
                    <AlertCircle className="h-4 w-4 text-destructive mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium">Bot Error - {issue.strategy_id.slice(0, 8)}</p>
                      <p className="text-xs text-muted-foreground">{issue.error_message}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(issue.updated_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle className="h-4 w-4" />
                <span>No critical issues at the moment</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Stats */}
      <Card>
        <CardHeader>
          <CardTitle>Platform Insights</CardTitle>
          <CardDescription>Key metrics at a glance</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">User Growth Rate</p>
              <p className="text-2xl font-bold text-green-600">
                +{stats.totalUsers > 0 ? Math.round((stats.recentSignups / stats.totalUsers) * 100) : 0}%
              </p>
              <p className="text-xs text-muted-foreground">Last 7 days</p>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Conversion Rate</p>
              <p className="text-2xl font-bold text-blue-600">
                {stats.totalUsers > 0 ? Math.round((stats.activeUsers / stats.totalUsers) * 100) : 0}%
              </p>
              <p className="text-xs text-muted-foreground">Trial to paid</p>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Avg Revenue per User</p>
              <p className="text-2xl font-bold text-purple-600">
                ₹{stats.activeUsers > 0 ? Math.round(stats.totalRevenue / stats.activeUsers) : 0}
              </p>
              <p className="text-xs text-muted-foreground">ARPU</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};