import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Skeleton } from "@/components/ui/skeleton";
import { Trophy, TrendingUp, Wallet, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface Milestone {
  id: string;
  milestone_type: string;
  trigger_equity: number;
  initial_equity: number;
  safe_withdrawal_amount: number;
  achieved_at: string;
  notified: boolean;
}

export default function WithdrawalMilestones() {
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentEquity, setCurrentEquity] = useState(0);
  const [initialEquity, setInitialEquity] = useState(0);

  useEffect(() => {
    loadMilestones();
    
    // Set up real-time subscription for new milestones
    const channel = supabase
      .channel('withdrawal-milestones')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'withdrawal_milestones'
        },
        () => loadMilestones()
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadMilestones = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get milestones
      const { data: milestonesData, error: milestonesError } = await supabase
        .from('withdrawal_milestones')
        .select('*')
        .eq('user_id', user.id)
        .order('achieved_at', { ascending: false });

      if (milestonesError) throw milestonesError;

      // Get current equity
      const { data: heartbeat } = await supabase
        .from('bot_heartbeats')
        .select('equity')
        .eq('user_id', user.id)
        .order('last_heartbeat', { ascending: false })
        .limit(1)
        .single();

      // Get initial equity
      const { data: setup } = await supabase
        .from('user_setup')
        .select('account_size')
        .eq('user_id', user.id)
        .single();

      setMilestones(milestonesData || []);
      setCurrentEquity(heartbeat?.equity || 0);
      setInitialEquity(setup?.account_size || 10000);
    } catch (error) {
      console.error('Error loading milestones:', error);
    } finally {
      setLoading(false);
    }
  };

  const markAsNotified = async (milestoneId: string) => {
    try {
      const { error } = await supabase
        .from('withdrawal_milestones')
        .update({ notified: true })
        .eq('id', milestoneId);

      if (error) throw error;

      toast.success('Milestone acknowledged');
      loadMilestones();
    } catch (error) {
      console.error('Error updating milestone:', error);
      toast.error('Failed to update milestone');
    }
  };

  if (loading) {
    return (
      <Card className="p-4 sm:p-6">
        <Skeleton className="h-6 sm:h-8 w-36 sm:w-48 mb-4" />
        <Skeleton className="h-24 sm:h-32 w-full" />
      </Card>
    );
  }

  const nextMilestone = milestones.length === 0 
    ? initialEquity * 2 
    : milestones[0].trigger_equity * 1.5;
  const progressToNext = ((currentEquity / nextMilestone) * 100).toFixed(1);

  return (
    <Card className="p-4 sm:p-6">
      <div className="flex items-center gap-2 mb-4 sm:mb-6">
        <Trophy className="h-4 w-4 sm:h-5 sm:w-5 text-primary flex-shrink-0" />
        <h3 className="text-base sm:text-lg font-semibold">Withdrawal Milestones</h3>
      </div>

      {/* Current Progress */}
      <Card className="p-3 sm:p-4 mb-4 sm:mb-6 bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs sm:text-sm font-medium">Progress to Next Milestone</span>
          <span className="text-xs sm:text-sm font-bold">{progressToNext}%</span>
        </div>
        <div className="w-full bg-muted rounded-full h-2 sm:h-3 mb-2 sm:mb-3">
          <div 
            className="bg-gradient-to-r from-primary to-primary/80 h-2 sm:h-3 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(parseFloat(progressToNext), 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Current: ${currentEquity.toFixed(2)}</span>
          <span>Target: ${nextMilestone.toFixed(2)}</span>
        </div>
      </Card>

      {/* Milestones List */}
      {milestones.length === 0 ? (
        <div className="text-center py-6 sm:py-8">
          <TrendingUp className="h-10 w-10 sm:h-12 sm:w-12 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No milestones achieved yet.</p>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            Reach ${(initialEquity * 2).toFixed(2)} to unlock your first milestone!
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {milestones.map((milestone) => (
            <Card 
              key={milestone.id} 
              className={`p-3 sm:p-4 ${!milestone.notified ? 'border-primary bg-primary/5' : 'bg-muted/30'}`}
            >
              <div className="flex flex-col sm:flex-row items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  {milestone.milestone_type === '2x' ? (
                    <Trophy className="h-4 w-4 sm:h-5 sm:w-5 text-primary mt-1 flex-shrink-0" />
                  ) : (
                    <Wallet className="h-4 w-4 sm:h-5 sm:w-5 text-primary mt-1 flex-shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <h4 className="font-semibold mb-1 text-sm sm:text-base">
                      {milestone.milestone_type === '2x' ? '2x Initial Capital!' : '50% Growth Milestone'}
                    </h4>
                    <p className="text-xs sm:text-sm text-muted-foreground mb-2">
                      Achieved on {new Date(milestone.achieved_at).toLocaleDateString()}
                    </p>
                    <div className="space-y-1 text-xs sm:text-sm">
                      <p>Equity at milestone: <span className="font-semibold">${milestone.trigger_equity.toFixed(2)}</span></p>
                      <p className="text-success">
                        <Wallet className="h-3 w-3 inline mr-1" />
                        Safe to withdraw: <span className="font-bold">${milestone.safe_withdrawal_amount.toFixed(2)}</span>
                      </p>
                    </div>
                  </div>
                </div>
                {!milestone.notified && (
                  <Button 
                    size="sm" 
                    variant="outline"
                    onClick={() => markAsNotified(milestone.id)}
                    className="w-full sm:w-auto touch-target"
                  >
                    <CheckCircle className="h-4 w-4 mr-1" />
                    Acknowledge
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <div className="mt-4 sm:mt-6 p-3 sm:p-4 bg-muted/20 rounded-lg">
        <h4 className="font-medium mb-2 text-xs sm:text-sm">About Safe Withdrawals</h4>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Safe withdrawal amounts are calculated to protect your initial capital while allowing you to realize profits. 
          For the first 2x milestone, we suggest withdrawing 70% of profit. For subsequent 50% growth milestones, 
          we suggest 50% of total profit to maintain compound growth potential.
        </p>
      </div>
    </Card>
  );
}