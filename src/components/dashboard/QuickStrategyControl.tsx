import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, Square, Zap, Clock, AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface UserStrategyWithDetails {
  id: string;
  strategy_id: string;
  is_running: boolean;
  started_at: string | null;
  strategy: {
    name: string;
    description: string;
  };
}

export const QuickStrategyControl = () => {
  const [strategies, setStrategies] = useState<UserStrategyWithDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [setupApproved, setSetupApproved] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadStrategies();

    // Realtime subscription
    const channel = supabase
      .channel('quick-strategy-control')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'user_strategies' },
        () => loadStrategies()
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const loadStrategies = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Check if setup is approved
      const { data: setup } = await supabase
        .from("user_setup")
        .select("admin_approved")
        .eq("user_id", user.id)
        .single();

      setSetupApproved(setup?.admin_approved || false);

      // Load user strategies with strategy details
      const { data, error } = await supabase
        .from("user_strategies")
        .select(`
          id,
          strategy_id,
          is_running,
          started_at,
          strategies:strategy_id (
            name,
            description
          )
        `)
        .eq("user_id", user.id)
        .order("created_at", { ascending: false });

      if (error) throw error;

      // Transform the data to match our interface
      const transformedData = (data || []).map(item => ({
        id: item.id,
        strategy_id: item.strategy_id,
        is_running: item.is_running,
        started_at: item.started_at,
        strategy: Array.isArray(item.strategies) ? item.strategies[0] : item.strategies
      })).filter(item => item.strategy); // Filter out any without strategy details

      setStrategies(transformedData);
    } catch (error: any) {
      console.error("Error loading strategies:", error);
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStartStop = async (userStrategyId: string, isRunning: boolean) => {
    setActionLoading(userStrategyId);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      if (isRunning) {
        // Stop the bot
        const { error } = await supabase.functions.invoke("stop-trading-bot", {
          body: { userStrategyId },
        });

        if (error) throw error;

        toast({
          title: "Bot Stopped",
          description: "Trading bot has been stopped successfully",
        });
      } else {
        // Start the bot
        const { error } = await supabase.functions.invoke("start-trading-bot", {
          body: { userStrategyId },
        });

        if (error) throw error;

        toast({
          title: "Bot Started",
          description: "Trading bot is now running",
        });
      }

      await loadStrategies();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setActionLoading(null);
    }
  };

  const formatRunningTime = (startedAt: string | null) => {
    if (!startedAt) return "Not started";
    
    const start = new Date(startedAt);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    
    if (diffHours > 24) {
      const days = Math.floor(diffHours / 24);
      return `${days}d ${diffHours % 24}h`;
    } else if (diffHours > 0) {
      return `${diffHours}h ${diffMins}m`;
    } else {
      return `${diffMins}m`;
    }
  };

  if (!setupApproved) {
    return (
      <Alert className="border-warning/50 bg-warning/5">
        <AlertCircle className="h-4 w-4 text-warning" />
        <AlertDescription>
          Your account setup is pending admin approval. You'll be able to start trading once approved.
        </AlertDescription>
      </Alert>
    );
  }

  if (loading) {
    return (
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardContent className="p-6 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  }

  if (strategies.length === 0) {
    return (
      <Alert className="border-muted bg-muted/20">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          No strategies selected yet. Go to the Strategies tab to select a trading strategy.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <Zap className="w-5 h-5 text-primary" />
          Quick Controls
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {strategies.map((userStrategy) => (
          <div
            key={userStrategy.id}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 sm:p-4 rounded-lg border border-border/50 bg-background/50 hover:bg-background/80 transition-colors"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-semibold text-sm sm:text-base truncate">
                  {userStrategy.strategy.name}
                </h4>
                {userStrategy.is_running && (
                  <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20 text-xs">
                    <span className="relative flex h-2 w-2 mr-1">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                    Live
                  </Badge>
                )}
              </div>
              {userStrategy.is_running && userStrategy.started_at && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3" />
                  Running for {formatRunningTime(userStrategy.started_at)}
                </div>
              )}
            </div>

            <Button
              onClick={() => handleStartStop(userStrategy.id, userStrategy.is_running)}
              disabled={actionLoading === userStrategy.id}
              variant={userStrategy.is_running ? "destructive" : "default"}
              size="sm"
              className={`min-w-[100px] ${!userStrategy.is_running ? 'bg-gradient-hero shadow-glow' : ''}`}
            >
              {actionLoading === userStrategy.id ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {userStrategy.is_running ? "Stopping..." : "Starting..."}
                </>
              ) : (
                <>
                  {userStrategy.is_running ? (
                    <>
                      <Square className="w-4 h-4 mr-2" />
                      Stop
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Start
                    </>
                  )}
                </>
              )}
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};
