import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, 
  Play, 
  Square, 
  Bot, 
  Clock, 
  AlertCircle,
  Activity,
  StopCircle,
  Cpu
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface RunningBot {
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
  heartbeat?: {
    last_heartbeat: string;
    mt5_connected: boolean;
    balance?: number;
    equity?: number;
  };
}

export const RunningBotsPanel = () => {
  const [bots, setBots] = useState<RunningBot[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [stopAllLoading, setStopAllLoading] = useState(false);
  const [showStopAllDialog, setShowStopAllDialog] = useState(false);
  const [setupApproved, setSetupApproved] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadBots();

    // Realtime subscription for both user_strategies and heartbeats
    const strategiesChannel = supabase
      .channel('running-bots-strategies')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'user_strategies' },
        () => loadBots()
      )
      .subscribe();

    const heartbeatsChannel = supabase
      .channel('running-bots-heartbeats')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'bot_heartbeats' },
        () => loadBots()
      )
      .subscribe();

    return () => {
      supabase.removeChannel(strategiesChannel);
      supabase.removeChannel(heartbeatsChannel);
    };
  }, []);

  const loadBots = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Check if setup is approved
      const { data: setup } = await supabase
        .from("user_setup")
        .select("admin_approved")
        .eq("user_id", user.id)
        .maybeSingle();

      setSetupApproved(setup?.admin_approved === true);

      // Load user strategies with strategy details
      const { data: strategiesData, error } = await supabase
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

      // Load heartbeats for each strategy
      const botsWithHeartbeats: RunningBot[] = [];
      
      for (const item of strategiesData || []) {
        const strategy = Array.isArray(item.strategies) ? item.strategies[0] : item.strategies;
        if (!strategy) continue;

        // Get heartbeat data
        const { data: heartbeat } = await supabase
          .from("bot_heartbeats")
          .select("last_heartbeat, mt5_connected, balance, equity")
          .eq("user_id", user.id)
          .eq("strategy_id", item.strategy_id)
          .maybeSingle();

        botsWithHeartbeats.push({
          id: item.id,
          strategy_id: item.strategy_id,
          is_running: item.is_running,
          started_at: item.started_at,
          status: item.status,
          bot_pid: item.bot_pid,
          strategy,
          heartbeat: heartbeat || undefined
        });
      }

      setBots(botsWithHeartbeats);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("Error loading bots:", error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStartStop = async (botId: string, strategyId: string, isRunning: boolean) => {
    const currentBot = bots.find(b => b.id === botId);
    if (currentBot?.status === 'starting' || currentBot?.status === 'stopping') {
      toast({
        title: "Please Wait",
        description: "Bot is already processing your previous command",
      });
      return;
    }

    setActionLoading(botId);
    
    const timeoutId = setTimeout(() => {
      setActionLoading(null);
      toast({
        title: "Request Timeout",
        description: "The operation is taking longer than expected.",
        variant: "destructive",
      });
    }, 15000);
    
    try {
      if (isRunning) {
        const { error } = await supabase.functions.invoke("stop-trading-bot", {
          body: { userStrategyId: botId },
        });
        
        if (error) {
          if (error.message?.includes("already stopped") || error.message?.includes("not running")) {
            toast({ title: "Bot Already Stopped", description: "The bot is not currently running" });
            await loadBots();
            return;
          }
          throw error;
        }

        toast({ title: "Bot Stopped", description: "Trading bot has been stopped successfully" });
      } else {
        const { error } = await supabase.functions.invoke("start-trading-bot", {
          body: { strategyId },
        });
        
        if (error) {
          if (error.message?.includes("already running")) {
            toast({ title: "Bot Already Running", description: "The bot is already active" });
            await loadBots();
            return;
          }
          throw error;
        }

        toast({ title: "Bot Starting", description: "Bot start command sent successfully" });
      }

      await loadBots();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("Handle start/stop error:", error);
      toast({
        title: "Error",
        description: message || "Failed to process request",
        variant: "destructive",
      });
      await loadBots();
    } finally {
      clearTimeout(timeoutId);
      setActionLoading(null);
    }
  };

  const handleStopAll = async () => {
    setShowStopAllDialog(false);
    setStopAllLoading(true);

    const runningBots = bots.filter(b => b.is_running || b.status === 'running');
    
    try {
      for (const bot of runningBots) {
        await supabase.functions.invoke("stop-trading-bot", {
          body: { userStrategyId: bot.id },
        });
      }

      toast({
        title: "All Bots Stopped",
        description: `Successfully stopped ${runningBots.length} bot(s)`,
      });

      await loadBots();
    } catch (error) {
      toast({
        title: "Error",
        description: "Some bots may not have stopped correctly",
        variant: "destructive",
      });
      await loadBots();
    } finally {
      setStopAllLoading(false);
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

  const isHeartbeatFresh = (lastHeartbeat?: string) => {
    if (!lastHeartbeat) return false;
    const diffSeconds = (Date.now() - new Date(lastHeartbeat).getTime()) / 1000;
    return diffSeconds <= 60;
  };

  const getStatusBadge = (bot: RunningBot) => {
    const { status, is_running, heartbeat } = bot;
    const freshHeartbeat = isHeartbeatFresh(heartbeat?.last_heartbeat);

    if (status === 'starting') {
      return (
        <Badge variant="outline" className="bg-blue-500/10 text-blue-500 border-blue-500/20 text-xs">
          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          Starting
        </Badge>
      );
    }

    if (status === 'stopping') {
      return (
        <Badge variant="outline" className="bg-orange-500/10 text-orange-500 border-orange-500/20 text-xs">
          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
          Stopping
        </Badge>
      );
    }

    if (status === 'crashed') {
      return (
        <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20 text-xs">
          <AlertCircle className="w-3 h-3 mr-1" />
          Crashed
        </Badge>
      );
    }

    if ((status === 'running' || is_running) && freshHeartbeat) {
      return (
        <Badge variant="outline" className="bg-green-500/10 text-green-500 border-green-500/20 text-xs">
          <span className="relative flex h-2 w-2 mr-1">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
          </span>
          Live
        </Badge>
      );
    }

    if (is_running && !freshHeartbeat) {
      return (
        <Badge variant="outline" className="bg-yellow-500/10 text-yellow-500 border-yellow-500/20 text-xs">
          <AlertCircle className="w-3 h-3 mr-1" />
          Stale
        </Badge>
      );
    }

    return (
      <Badge variant="outline" className="text-xs text-muted-foreground">
        Stopped
      </Badge>
    );
  };

  const runningBots = bots.filter(b => b.is_running || b.status === 'running' || b.status === 'starting');
  const stoppedBots = bots.filter(b => !b.is_running && b.status !== 'running' && b.status !== 'starting');

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

  if (bots.length === 0) {
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
    <>
      <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="w-5 h-5 text-primary" />
              Bot Controls
              {runningBots.length > 0 && (
                <Badge className="bg-green-500/20 text-green-500 border-green-500/30 ml-2">
                  {runningBots.length} Running
                </Badge>
              )}
            </CardTitle>
            {runningBots.length > 1 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowStopAllDialog(true)}
                disabled={stopAllLoading}
                className="gap-2"
              >
                {stopAllLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <StopCircle className="w-4 h-4" />
                )}
                Stop All
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Running Bots Section */}
          {runningBots.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Active Bots ({runningBots.length})
              </h4>
              <div className="space-y-2">
                {runningBots.map((bot) => (
                  <div
                    key={bot.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-lg border border-green-500/20 bg-green-500/5 hover:bg-green-500/10 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <h4 className="font-semibold text-sm sm:text-base truncate">
                          {bot.strategy.name}
                        </h4>
                        {getStatusBadge(bot)}
                        {bot.heartbeat?.mt5_connected && (
                          <Badge variant="outline" className="text-xs bg-blue-500/10 text-blue-500 border-blue-500/20">
                            MT5 Connected
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                        {bot.started_at && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatRunningTime(bot.started_at)}
                          </span>
                        )}
                        {bot.bot_pid && (
                          <span className="flex items-center gap-1">
                            <Cpu className="w-3 h-3" />
                            PID: {bot.bot_pid}
                          </span>
                        )}
                        {bot.heartbeat?.equity && (
                          <span className="text-green-500">
                            Equity: ${bot.heartbeat.equity.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>

                    <Button
                      onClick={() => handleStartStop(bot.id, bot.strategy_id, true)}
                      disabled={actionLoading === bot.id || bot.status === 'starting' || bot.status === 'stopping'}
                      variant="destructive"
                      size="sm"
                      className="min-w-[100px]"
                    >
                      {actionLoading === bot.id ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Stopping...
                        </>
                      ) : (
                        <>
                          <Square className="w-4 h-4 mr-2" />
                          Stop
                        </>
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stopped Bots Section */}
          {stoppedBots.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">
                Available Strategies ({stoppedBots.length})
              </h4>
              <div className="space-y-2">
                {stoppedBots.map((bot) => (
                  <div
                    key={bot.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-lg border border-border/50 bg-background/50 hover:bg-background/80 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-semibold text-sm sm:text-base truncate">
                          {bot.strategy.name}
                        </h4>
                        {getStatusBadge(bot)}
                      </div>
                      <p className="text-xs text-muted-foreground truncate">
                        {bot.strategy.description}
                      </p>
                    </div>

                    <Button
                      onClick={() => handleStartStop(bot.id, bot.strategy_id, false)}
                      disabled={actionLoading === bot.id || bot.status === 'stopping'}
                      size="sm"
                      className="min-w-[100px] bg-gradient-hero shadow-glow"
                    >
                      {actionLoading === bot.id ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Starting...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 mr-2" />
                          Start
                        </>
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stop All Confirmation Dialog */}
      <AlertDialog open={showStopAllDialog} onOpenChange={setShowStopAllDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Stop All Bots?</AlertDialogTitle>
            <AlertDialogDescription>
              This will stop all {runningBots.length} running bot(s). Any open positions will remain open but no new trades will be executed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleStopAll} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Stop All Bots
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
