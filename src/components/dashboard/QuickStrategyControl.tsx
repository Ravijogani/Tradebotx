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
  status?: string;
  bot_pid?: number | null;
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
      const { data: setup, error: setupError } = await supabase
        .from("user_setup")
        .select("admin_approved")
        .eq("user_id", user.id)
        .maybeSingle();

      console.log("Setup query result:", { setup, setupError, userId: user.id });

      if (setupError) {
        console.error("Error loading setup:", setupError);
      }

      const isApproved = setup?.admin_approved === true;
      console.log("Admin approved status:", isApproved);
      setSetupApproved(isApproved);

      // Load user strategies with strategy details
      const { data, error } = await supabase
        .from("user_strategies")
        .select(`
          id,
          strategy_id,
          is_running,
          started_at,
          status,
          bot_pid,
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
        status: item.status,
        bot_pid: item.bot_pid,
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

  const handleStartStop = async (userStrategyId: string, strategyId: string, isRunning: boolean) => {
    // Check if already in a transitional state
    const currentStrategy = strategies.find(s => s.id === userStrategyId);
    if (currentStrategy?.status === 'starting' || currentStrategy?.status === 'stopping') {
      toast({
        title: "Please Wait",
        description: "Bot is already processing your previous command",
      });
      return;
    }

    setActionLoading(userStrategyId);
    
    // Set a timeout to prevent infinite loading
    const timeoutId = setTimeout(() => {
      setActionLoading(null);
      toast({
        title: "Request Timeout",
        description: "The operation is taking longer than expected. Please check the bot status.",
        variant: "destructive",
      });
    }, 15000); // 15 second timeout
    
    try {
      const { data: { user }, error: authError } = await supabase.auth.getUser();
      
      if (authError) {
        console.error("Auth error:", authError);
        toast({
          title: "Authentication Error",
          description: "Please refresh the page and try again",
          variant: "destructive",
        });
        clearTimeout(timeoutId);
        setActionLoading(null);
        return;
      }

      if (!user) {
        toast({
          title: "Not Authenticated",
          description: "Please log in again",
          variant: "destructive",
        });
        clearTimeout(timeoutId);
        setActionLoading(null);
        return;
      }

      console.log(`${isRunning ? 'Stopping' : 'Starting'} bot - User Strategy ID:`, userStrategyId);
      console.log(`Current strategy status:`, currentStrategy?.status);
      console.log(`Strategy ID:`, strategyId);

      if (isRunning) {
        console.log("Invoking stop-trading-bot edge function...");
        const { data, error } = await supabase.functions.invoke("stop-trading-bot", {
          body: { userStrategyId },
        });
        
        console.log("Stop response:", { data, error });
        
        if (error) {
          // Check if it's an "already stopped" error
          if (error.message?.includes("already stopped") || error.message?.includes("not running")) {
            toast({
              title: "Bot Already Stopped",
              description: "The bot is not currently running",
            });
            await loadStrategies();
            return;
          }
          throw error;
        }

        toast({
          title: "Bot Stopped",
          description: "Trading bot has been stopped successfully",
        });
      } else {
        console.log("Invoking start-trading-bot edge function...");
        const { data, error } = await supabase.functions.invoke("start-trading-bot", {
          body: { strategyId },
        });
        
        console.log("Start response:", { data, error });
        
        if (error) {
          // Check if it's an "already running" error
          if (error.message?.includes("already running") || error.message?.includes("already started")) {
            toast({
              title: "Bot Already Running",
              description: "The bot is already active",
            });
            await loadStrategies();
            return;
          }
          throw error;
        }

        toast({
          title: "Bot Starting",
          description: "Bot start command sent successfully",
        });
      }

      // Reload to get actual state from server
      await loadStrategies();
    } catch (error: any) {
      console.error("Handle start/stop error:", error);
      toast({
        title: "Error",
        description: error.message || "Failed to process request",
        variant: "destructive",
      });
      // Reload strategies to sync with actual backend state
      await loadStrategies();
    } finally {
      clearTimeout(timeoutId);
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

  const getStatusBadge = (status?: string, isRunning?: boolean) => {
    switch (status) {
      case 'running':
        return (
          <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20 text-xs">
            <span className="relative flex h-2 w-2 mr-1">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
            </span>
            Live
          </Badge>
        );
      case 'starting':
        return (
          <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 text-xs">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            Starting...
          </Badge>
        );
      case 'stopping':
        return (
          <Badge variant="outline" className="bg-orange-500/10 text-orange-500 border-orange-500/20 text-xs">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            Stopping...
          </Badge>
        );
      case 'crashed':
        return (
          <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20 text-xs">
            ⚠ Crashed
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-xs">
            ○ Stopped
          </Badge>
        );
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
                {getStatusBadge(userStrategy.status, userStrategy.is_running)}
              </div>
              {userStrategy.is_running && userStrategy.started_at && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3" />
                  Running for {formatRunningTime(userStrategy.started_at)}
                  {userStrategy.bot_pid && ` • PID: ${userStrategy.bot_pid}`}
                </div>
              )}
              {userStrategy.status === 'starting' && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="w-3 h-3" />
                  Waiting for bot process to start...
                </div>
              )}
            </div>

            <Button
              onClick={() => handleStartStop(userStrategy.id, userStrategy.strategy_id, userStrategy.is_running)}
              disabled={actionLoading === userStrategy.id || userStrategy.status === 'starting' || userStrategy.status === 'stopping'}
              variant={userStrategy.is_running ? "destructive" : "default"}
              size="sm"
              className={`min-w-[100px] ${!userStrategy.is_running && userStrategy.status !== 'starting' ? 'bg-gradient-hero shadow-glow' : ''}`}
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
