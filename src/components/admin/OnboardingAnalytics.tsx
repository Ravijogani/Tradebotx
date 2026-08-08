import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { 
  Mail, 
  Users, 
  CheckCircle2, 
  Clock, 
  TrendingUp, 
  Send,
  RefreshCw,
  AlertCircle,
  ArrowRight
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { format, formatDistanceToNow } from "date-fns";

interface OnboardingStats {
  totalIncomplete: number;
  totalCompleted: number;
  emailsSentBySequence: Record<number, number>;
  pendingUsers: Array<{
    user_id: string;
    email: string;
    full_name: string | null;
    created_at: string;
    current_sequence: number;
    last_email_sent: string | null;
  }>;
  conversionRate: number;
}

const EMAIL_SEQUENCE_LABELS: Record<number, { label: string; type: string }> = {
  1: { label: "Setup Reminder", type: "reminder" },
  2: { label: "Value Proposition", type: "value_prop" },
  3: { label: "Support Offer", type: "support" },
  4: { label: "Urgency", type: "urgency" },
  5: { label: "Final Reminder", type: "final" },
};

export function OnboardingAnalytics() {
  const [stats, setStats] = useState<OnboardingStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggeringNurture, setTriggeringNurture] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);

      // Get incomplete setups
      const { data: incompleteSetups, error: incompleteError } = await supabase
        .from('user_setup')
        .select('user_id, created_at')
        .eq('is_completed', false);

      if (incompleteError) throw incompleteError;

      // Get completed setups
      const { data: completedSetups, error: completedError } = await supabase
        .from('user_setup')
        .select('user_id')
        .eq('is_completed', true);

      if (completedError) throw completedError;

      // Get emails sent by sequence
      const { data: emailsSent, error: emailsError } = await supabase
        .from('onboarding_emails')
        .select('email_sequence, user_id, sent_at');

      if (emailsError) throw emailsError;

      // Count emails per sequence
      const emailsSentBySequence: Record<number, number> = {};
      for (let i = 1; i <= 5; i++) {
        emailsSentBySequence[i] = emailsSent?.filter(e => e.email_sequence === i).length || 0;
      }

      // Get pending users with their profiles and email status
      const pendingUsers: OnboardingStats['pendingUsers'] = [];
      
      for (const setup of incompleteSetups || []) {
        const { data: profile } = await supabase
          .from('profiles')
          .select('email, full_name')
          .eq('id', setup.user_id)
          .single();

        const userEmails = emailsSent?.filter(e => e.user_id === setup.user_id) || [];
        const maxSequence = userEmails.length > 0 
          ? Math.max(...userEmails.map(e => e.email_sequence))
          : 0;
        const lastEmail = userEmails.sort((a, b) => 
          new Date(b.sent_at).getTime() - new Date(a.sent_at).getTime()
        )[0];

        pendingUsers.push({
          user_id: setup.user_id,
          email: profile?.email || 'Unknown',
          full_name: profile?.full_name || null,
          created_at: setup.created_at,
          current_sequence: maxSequence,
          last_email_sent: lastEmail?.sent_at || null,
        });
      }

      // Sort by signup date (oldest first)
      pendingUsers.sort((a, b) => 
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );

      // Calculate conversion rate
      const totalUsers = (incompleteSetups?.length || 0) + (completedSetups?.length || 0);
      const conversionRate = totalUsers > 0 
        ? ((completedSetups?.length || 0) / totalUsers) * 100 
        : 0;

      setStats({
        totalIncomplete: incompleteSetups?.length || 0,
        totalCompleted: completedSetups?.length || 0,
        emailsSentBySequence,
        pendingUsers,
        conversionRate,
      });

    } catch (error) {
      console.error('Error loading onboarding stats:', error);
      toast({
        title: "Error",
        description: "Failed to load onboarding analytics",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const triggerNurtureNow = async () => {
    try {
      setTriggeringNurture(true);
      
      const { data, error } = await supabase.functions.invoke('send-onboarding-nurture', {
        body: {},
      });

      if (error) throw error;

      toast({
        title: "Nurture Emails Triggered",
        description: `Sent ${data?.emailsSent || 0} emails`,
      });

      // Reload stats
      await loadStats();

    } catch (error) {
      console.error('Error triggering nurture:', error);
      toast({
        title: "Error",
        description: "Failed to trigger nurture emails",
        variant: "destructive",
      });
    } finally {
      setTriggeringNurture(false);
    }
  };

  const getSequenceBadgeColor = (sequence: number) => {
    const colors: Record<number, string> = {
      0: "bg-muted text-muted-foreground",
      1: "bg-blue-500/20 text-blue-400 border-blue-500/30",
      2: "bg-purple-500/20 text-purple-400 border-purple-500/30",
      3: "bg-green-500/20 text-green-400 border-green-500/30",
      4: "bg-orange-500/20 text-orange-400 border-orange-500/30",
      5: "bg-red-500/20 text-red-400 border-red-500/30",
    };
    return colors[sequence] || colors[0];
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!stats) return null;

  const totalEmailsSent = Object.values(stats.emailsSentBySequence).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold">Onboarding Analytics</h2>
          <p className="text-muted-foreground">Track email nurture sequence and user conversions</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadStats} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button 
            size="sm" 
            onClick={triggerNurtureNow} 
            disabled={triggeringNurture}
            className="bg-gradient-to-r from-primary to-accent"
          >
            <Send className={`w-4 h-4 mr-2 ${triggeringNurture ? 'animate-pulse' : ''}`} />
            {triggeringNurture ? 'Sending...' : 'Send Now'}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-orange-500/10 to-transparent border-orange-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Clock className="w-4 h-4 text-orange-400" />
              Incomplete Setups
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-orange-400">{stats.totalIncomplete}</div>
            <p className="text-xs text-muted-foreground mt-1">Users awaiting setup</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-500/10 to-transparent border-green-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              Completed Setups
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-400">{stats.totalCompleted}</div>
            <p className="text-xs text-muted-foreground mt-1">Users active</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-blue-500/10 to-transparent border-blue-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Mail className="w-4 h-4 text-blue-400" />
              Emails Sent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-blue-400">{totalEmailsSent}</div>
            <p className="text-xs text-muted-foreground mt-1">Total nurture emails</p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-primary/10 to-transparent border-primary/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary" />
              Conversion Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-primary">{stats.conversionRate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground mt-1">Signup to setup</p>
          </CardContent>
        </Card>
      </div>

      {/* Email Sequence Funnel */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="w-5 h-5" />
            Email Sequence Funnel
          </CardTitle>
          <CardDescription>Emails sent at each stage of the nurture sequence</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((sequence) => {
              const count = stats.emailsSentBySequence[sequence] || 0;
              const maxCount = Math.max(...Object.values(stats.emailsSentBySequence), 1);
              const percentage = (count / maxCount) * 100;
              const config = EMAIL_SEQUENCE_LABELS[sequence];

              return (
                <div key={sequence} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className={getSequenceBadgeColor(sequence)}>
                        Email {sequence}
                      </Badge>
                      <span className="text-sm font-medium">{config.label}</span>
                    </div>
                    <span className="text-sm font-bold">{count} sent</span>
                  </div>
                  <Progress value={percentage} className="h-2" />
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Pending Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Pending Users ({stats.pendingUsers.length})
          </CardTitle>
          <CardDescription>Users who haven't completed setup, ordered by signup date</CardDescription>
        </CardHeader>
        <CardContent>
          {stats.pendingUsers.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-green-400" />
              <p>All users have completed their setup!</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-2 text-xs font-medium text-muted-foreground uppercase">User</th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-muted-foreground uppercase">Signed Up</th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-muted-foreground uppercase">Current Stage</th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-muted-foreground uppercase">Last Email</th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-muted-foreground uppercase">Next Action</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.pendingUsers.map((user) => {
                    const nextSequence = user.current_sequence + 1;
                    const nextEmail = nextSequence <= 5 ? EMAIL_SEQUENCE_LABELS[nextSequence] : null;

                    return (
                      <tr key={user.user_id} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-3 px-2">
                          <div>
                            <p className="font-medium text-sm">{user.full_name || 'No name'}</p>
                            <p className="text-xs text-muted-foreground">{user.email}</p>
                          </div>
                        </td>
                        <td className="py-3 px-2">
                          <div>
                            <p className="text-sm">{format(new Date(user.created_at), 'MMM d, yyyy')}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatDistanceToNow(new Date(user.created_at), { addSuffix: true })}
                            </p>
                          </div>
                        </td>
                        <td className="py-3 px-2">
                          {user.current_sequence === 0 ? (
                            <Badge variant="outline" className="bg-muted">
                              No emails sent
                            </Badge>
                          ) : (
                            <Badge variant="outline" className={getSequenceBadgeColor(user.current_sequence)}>
                              Email {user.current_sequence}: {EMAIL_SEQUENCE_LABELS[user.current_sequence]?.label}
                            </Badge>
                          )}
                        </td>
                        <td className="py-3 px-2 text-sm text-muted-foreground">
                          {user.last_email_sent 
                            ? formatDistanceToNow(new Date(user.last_email_sent), { addSuffix: true })
                            : '-'
                          }
                        </td>
                        <td className="py-3 px-2">
                          {nextEmail ? (
                            <div className="flex items-center gap-2 text-sm">
                              <ArrowRight className="w-4 h-4 text-primary" />
                              <span>Email {nextSequence}</span>
                            </div>
                          ) : (
                            <Badge variant="outline" className="bg-red-500/10 text-red-400 border-red-500/30">
                              <AlertCircle className="w-3 h-3 mr-1" />
                              Sequence Complete
                            </Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}