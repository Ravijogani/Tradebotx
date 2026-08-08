import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, Square, TrendingUp } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import type { Tables } from "@/integrations/supabase/types";

export const StrategySelector = () => {
  const [strategies, setStrategies] = useState<Tables<"strategies">[]>([]);
  const [userStrategies, setUserStrategies] = useState<Tables<"user_strategies">[]>([]);
  const [loading, setLoading] = useState(true);
  const [adminApproved, setAdminApproved] = useState(false);
  const [planType, setPlanType] = useState<string>('');
  const { toast } = useToast();

  useEffect(() => {
    loadStrategies();
    checkApprovalStatus();
  }, []);

  const checkApprovalStatus = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data: subscription } = await supabase
        .from('user_subscriptions')
        .select('plans(plan_type)')
        .eq('user_id', user.id)
        .single();

      const { data: setup, error: setupError } = await supabase
        .from('user_setup')
        .select('admin_approved')
        .eq('user_id', user.id)
        .maybeSingle();

      console.log("StrategySelector - Setup query result:", { setup, setupError, userId: user.id });

      if (setupError) {
        console.error("Error loading setup:", setupError);
      }

      const type = (subscription?.plans as Pick<Tables<"plans">, "plan_type"> | null)?.plan_type || '';
      setPlanType(type);
      const isApproved = setup?.admin_approved === true;
      console.log("StrategySelector - Admin approved:", isApproved);
      setAdminApproved(isApproved);
    } catch (error) {
      console.error('Error checking approval:', error);
    }
  };

  const loadStrategies = async () => {
    try {
      const { data: strategiesData } = await supabase
        .from("strategies")
        .select("*")
        .eq("is_active", true);

      const { data: userStratData } = await supabase
        .from("user_strategies")
        .select("*");

      setStrategies(strategiesData || []);
      setUserStrategies(userStratData || []);
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

  const handleStrategyToggle = async (strategyId: string, isRunning: boolean) => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      if (isRunning) {
        // Stop strategy
        await supabase
          .from("user_strategies")
          .update({ 
            is_running: false,
            stopped_at: new Date().toISOString()
          })
          .eq("user_id", user.id)
          .eq("strategy_id", strategyId);
      } else {
        // Start strategy
        const existing = userStrategies.find(us => us.strategy_id === strategyId);
        
        if (existing) {
          await supabase
            .from("user_strategies")
            .update({ 
              is_running: true,
              started_at: new Date().toISOString()
            })
            .eq("id", existing.id);
        } else {
          await supabase
            .from("user_strategies")
            .insert({
              user_id: user.id,
              strategy_id: strategyId,
              is_running: true,
              started_at: new Date().toISOString()
            });
        }
      }

      toast({
        title: isRunning ? "Strategy stopped" : "Strategy started",
        description: `Trading strategy ${isRunning ? "stopped" : "activated"} successfully`,
      });

      loadStrategies();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    }
  };

  const isStrategyRunning = (strategyId: string) => {
    return userStrategies.some(us => us.strategy_id === strategyId && us.is_running);
  };

  // Show waiting card for users who haven't been approved
  if (!adminApproved) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-3xl font-bold mb-2">Trading Strategies</h2>
          <p className="text-muted-foreground">
            Select and activate strategies based on your subscription plan
          </p>
        </div>

        <Card className="p-6 bg-orange-500/5 border-orange-500/20">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-orange-500/10 flex items-center justify-center flex-shrink-0">
              <TrendingUp className="w-6 h-6 text-orange-500" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">Waiting for Admin Approval</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Your account setup has been submitted. Our admin team will review and approve your account details shortly. You'll be able to start trading bots once approved.
              </p>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  if (loading) {
    return <div>Loading strategies...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold mb-2">Trading Strategies</h2>
        <p className="text-muted-foreground">
          Select and activate strategies based on your subscription plan
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {strategies.map((strategy) => {
          const running = isStrategyRunning(strategy.id);
          
          return (
            <Card key={strategy.id} className="p-6 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-xl font-semibold mb-1">{strategy.name}</h3>
                  <Badge variant="outline" className="text-xs">
                    {strategy.plan_type}
                  </Badge>
                </div>
                <TrendingUp className="w-8 h-8 text-accent" />
              </div>

              <p className="text-sm text-muted-foreground">
                {strategy.description}
              </p>

              <Button
                className={`w-full ${
                  running
                    ? "bg-destructive hover:bg-destructive/90"
                    : "bg-gradient-hero shadow-glow"
                }`}
                onClick={() => handleStrategyToggle(strategy.id, running)}
                disabled={loading || running || !adminApproved}
              >
                {running ? (
                  <>
                    <Square className="w-4 h-4 mr-2" />
                    Stop Strategy
                  </>
                ) : !adminApproved ? (
                  "Pending Approval"
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    Start Strategy
                  </>
                )}
              </Button>
            </Card>
          );
        })}
      </div>
    </div>
  );
};
