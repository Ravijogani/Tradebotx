import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Zap, Play, Square, CheckCircle, AlertCircle, TrendingUp, Clock } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Strategy {
  id: string;
  name: string;
  description: string;
  plan_type: string;
  is_active: boolean;
}

interface UserStrategy {
  id: string;
  strategy_id: string;
  is_running: boolean;
  started_at: string | null;
  stopped_at: string | null;
}

export const StrategySelection = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [userStrategies, setUserStrategies] = useState<UserStrategy[]>([]);
  const [userPlan, setUserPlan] = useState<string>("");
  const [setupApproved, setSetupApproved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadData();
    
    // Set up realtime subscription for user_strategies changes
    const channel = supabase
      .channel('user-strategies-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'user_strategies'
        },
        (payload) => {
          console.log('User strategy change:', payload);
          // Reload data when any user_strategy changes
          loadData();
          
          // Show toast for bot status changes
          if (payload.eventType === 'UPDATE') {
            const isRunning = payload.new.is_running;
            const wasRunning = payload.old?.is_running;
            
            if (wasRunning && !isRunning) {
              toast({
                title: "Bot Stopped",
                description: "Trading bot has been stopped",
                variant: "default"
              });
            }
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadData = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Check if setup is approved
      const { data: setup, error: setupError } = await supabase
        .from("user_setup")
        .select("admin_approved")
        .eq("user_id", user.id)
        .maybeSingle();

      console.log("StrategySelection - Setup query result:", { setup, setupError, userId: user.id });

      if (setupError) {
        console.error("Error loading setup:", setupError);
      }

      if (setup?.admin_approved !== true) {
        console.log("StrategySelection - Not approved, hiding strategies");
        setSetupApproved(false);
        setLoading(false);
        return;
      }
      setSetupApproved(true);

      // Get user's plan
      const { data: subscription } = await supabase
        .from("user_subscriptions")
        .select("plans(plan_type)")
        .eq("user_id", user.id)
        .single();

      const planType = subscription?.plans?.plan_type || "free";
      setUserPlan(planType);

      // Get available strategies for user's plan
      const { data: strategiesData, error: strategiesError } = await supabase
        .from("strategies")
        .select("*")
        .eq("is_active", true)
        .or(`plan_type.eq.${planType},plan_type.eq.free`);

      if (strategiesError) throw strategiesError;
      setStrategies(strategiesData || []);

      // Get user's active strategies
      const { data: userStrategiesData, error: userStrategiesError } = await supabase
        .from("user_strategies")
        .select("*")
        .eq("user_id", user.id);

      if (userStrategiesError) throw userStrategiesError;
      setUserStrategies(userStrategiesData || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error loading strategies",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStartStrategy = async (strategyId: string, strategyName: string) => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      return;
    }

    // Check if strategy is already running
    const existingStrategy = userStrategies.find(
      us => us.strategy_id === strategyId && us.is_running
    );

    if (existingStrategy) {
      toast({
        title: "Already Running",
        description: "This strategy is already active",
      });
      return;
    }

    setActionLoading(strategyId);

    // Set a timeout to prevent infinite loading
    const timeoutId = setTimeout(() => {
      setActionLoading(null);
      toast({
        title: "Request Timeout",
        description: "The operation is taking longer than expected. Please refresh to check bot status.",
        variant: "destructive",
      });
    }, 15000);

    try {
      console.log("Starting strategy:", { strategyId, strategyName });
      
      const { data, error } = await supabase.functions.invoke('start-trading-bot', {
        body: { strategyId, strategyName }
      });

      console.log("Start strategy response:", { data, error });

      if (error) {
        // Check if it's an "already running" error
        if (error.message?.includes("already running") || error.message?.includes("already started")) {
          toast({
            title: "Bot Already Running",
            description: "The bot is already active",
          });
          await loadData();
          return;
        }
        throw error;
      }

      toast({
        title: "Bot Starting",
        description: `${strategyName} is starting up`,
      });

      // Reload to get actual state
      await loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("Start strategy error:", error);
      toast({
        title: "Error",
        description: message || "Failed to start strategy",
        variant: "destructive",
      });
      await loadData();
    } finally {
      clearTimeout(timeoutId);
      setActionLoading(null);
    }
  };

  const handleStopStrategy = async (userStrategyId: string, strategyName: string) => {
    setActionLoading(userStrategyId);

    // Set a timeout to prevent infinite loading
    const timeoutId = setTimeout(() => {
      setActionLoading(null);
      toast({
        title: "Request Timeout",
        description: "The operation is taking longer than expected. Please refresh to check bot status.",
        variant: "destructive",
      });
    }, 15000);

    try {
      console.log("Stopping strategy:", { userStrategyId, strategyName });
      
      const { data, error } = await supabase.functions.invoke('stop-trading-bot', {
        body: { userStrategyId }
      });

      console.log("Stop strategy response:", { data, error });

      if (error) {
        // Check if it's an "already stopped" error
        if (error.message?.includes("already stopped") || error.message?.includes("not running")) {
          toast({
            title: "Bot Already Stopped",
            description: "The bot is not currently running",
          });
          await loadData();
          return;
        }
        throw error;
      }

      toast({
        title: "Bot Stopped",
        description: `${strategyName} has been stopped`,
      });

      // Reload to get actual state
      await loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("Stop strategy error:", error);
      toast({
        title: "Error",
        description: message || "Failed to stop strategy",
        variant: "destructive",
      });
      await loadData();
    } finally {
      clearTimeout(timeoutId);
      setActionLoading(null);
    }
  };

  const isStrategyRunning = (strategyId: string) => {
    return userStrategies.some(us => us.strategy_id === strategyId && us.is_running);
  };

  const getRunningUserStrategy = (strategyId: string) => {
    return userStrategies.find(us => us.strategy_id === strategyId && us.is_running);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }

  if (!setupApproved) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-orange-500" />
            Setup Approval Pending
          </CardTitle>
          <CardDescription>
            Your account setup is awaiting admin approval
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Alert>
            <Clock className="h-4 w-4" />
            <AlertDescription>
              An administrator needs to review and approve your setup before you can select and run trading strategies.
              You will be notified once your account is approved.
            </AlertDescription>
          </Alert>
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
              <Zap className="w-5 h-5" />
              Trading Strategies
            </CardTitle>
            <CardDescription>
              Select and manage your active trading strategies
            </CardDescription>
          </div>
          <Badge variant="outline" className="capitalize">
            {userPlan} Plan
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[500px] pr-4">
          <div className="space-y-4">
            {strategies.length === 0 ? (
              <Alert>
                <TrendingUp className="h-4 w-4" />
                <AlertDescription>
                  No strategies available for your plan. Contact support or upgrade your plan to access more strategies.
                </AlertDescription>
              </Alert>
            ) : (
              strategies.map((strategy) => {
                const running = isStrategyRunning(strategy.id);
                const userStrategy = getRunningUserStrategy(strategy.id);
                const isLoading = actionLoading === strategy.id || actionLoading === userStrategy?.id;

                return (
                  <Card key={strategy.id} className={running ? "border-green-500/50 bg-green-500/5" : ""}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <CardTitle className="text-lg">{strategy.name}</CardTitle>
                            {running && (
                              <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
                                <CheckCircle className="w-3 h-3 mr-1" />
                                Running
                              </Badge>
                            )}
                          </div>
                          <CardDescription className="mt-2">{strategy.description}</CardDescription>
                          {running && userStrategy?.started_at && (
                            <p className="text-xs text-muted-foreground mt-2">
                              Started: {new Date(userStrategy.started_at).toLocaleString()}
                            </p>
                          )}
                        </div>
                        <Badge variant="outline" className="capitalize ml-4">
                          {strategy.plan_type}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex gap-2">
                        {!running ? (
                          <Button
                            onClick={() => handleStartStrategy(strategy.id, strategy.name)}
                            disabled={isLoading}
                            className="gap-2"
                          >
                            {isLoading ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Starting...
                              </>
                            ) : (
                              <>
                                <Play className="w-4 h-4" />
                                Start Strategy
                              </>
                            )}
                          </Button>
                        ) : (
                          <Button
                            onClick={() => handleStopStrategy(userStrategy!.id, strategy.name)}
                            disabled={isLoading}
                            variant="destructive"
                            className="gap-2"
                          >
                            {isLoading ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Stopping...
                              </>
                            ) : (
                              <>
                                <Square className="w-4 h-4" />
                                Stop Strategy
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        </ScrollArea>

        <div className="mt-4 p-4 bg-muted rounded-lg">
          <p className="text-sm text-muted-foreground">
            <strong>Note:</strong> Strategies will connect to your MT5 account and execute trades based on the configured parameters.
            Make sure your MT5 account has sufficient funds and proper risk management settings.
          </p>
        </div>
      </CardContent>
    </Card>
  );
};
