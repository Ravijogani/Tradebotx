import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, Activity, AlertCircle, CheckCircle, XCircle, Power } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export const BotMonitoringDashboard = () => {
  const [runningBots, setRunningBots] = useState<any[]>([]);
  const [botLogs, setBotLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBot, setSelectedBot] = useState<any>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadData();
    setupRealtime();
  }, []);

  useEffect(() => {
    if (selectedBot) {
      loadLogs(selectedBot.user_id, selectedBot.strategy_id);
    }
  }, [selectedBot]);

  const setupRealtime = () => {
    const channel = supabase
      .channel('bot-monitoring')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'user_strategies' },
        () => loadData()
      )
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'bot_logs' },
        (payload) => {
          if (selectedBot && 
              payload.new.user_id === selectedBot.user_id && 
              payload.new.strategy_id === selectedBot.strategy_id) {
            setBotLogs(prev => [payload.new, ...prev]);
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  };

  const loadData = async () => {
    try {
      const { data: strategies, error } = await supabase
        .from("user_strategies")
        .select("*")
        .eq("is_running", true)
        .order("started_at", { ascending: false });

      if (error) throw error;

      // Load strategy details
      const strategyIds = [...new Set(strategies?.map(s => s.strategy_id) || [])];
      const { data: strategyDetails } = await supabase
        .from("strategies")
        .select("id, name, description")
        .in("id", strategyIds);

      // Load user profiles
      const userIds = [...new Set(strategies?.map(s => s.user_id) || [])];
      const { data: userProfiles } = await supabase
        .from("profiles")
        .select("id, full_name, email")
        .in("id", userIds);

      const strategyMap = new Map(strategyDetails?.map(s => [s.id, s]));
      const profileMap = new Map(userProfiles?.map(p => [p.id, p]));

      const botsWithDetails = strategies?.map(bot => ({
        ...bot,
        strategies: strategyMap.get(bot.strategy_id),
        profiles: profileMap.get(bot.user_id),
      }));

      setRunningBots(botsWithDetails || []);
    } catch (error: any) {
      toast({
        title: "Error loading bots",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async (userId: string, strategyId: string) => {
    try {
      // Use bot_audit_logs instead of non-existent bot_logs table
      const { data, error } = await supabase
        .from("bot_audit_logs")
        .select("*")
        .eq("user_id", userId)
        .eq("strategy_id", strategyId)
        .order("created_at", { ascending: false })
        .limit(100);

      if (error) throw error;
      
      // Transform audit logs to match expected format
      const formattedLogs = (data || []).map(log => {
        const metadata = typeof log.metadata === 'object' && log.metadata !== null 
          ? log.metadata as Record<string, any>
          : {};
        return {
          id: log.id,
          message: `${log.action}: ${metadata.strategy_name || 'Strategy'}`,
          log_level: log.action === 'start' ? 'info' : log.action === 'stop' ? 'warning' : 'info',
          created_at: log.created_at,
          metadata: log.metadata
        };
      });
      
      setBotLogs(formattedLogs);
    } catch (error: any) {
      toast({
        title: "Error loading logs",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleEmergencyStop = async (botId: string) => {
    try {
      const { error } = await supabase
        .from("user_strategies")
        .update({
          is_running: false,
          stopped_at: new Date().toISOString(),
        })
        .eq("id", botId);

      if (error) throw error;

      toast({
        title: "Bot Stopped",
        description: "Trading bot has been stopped successfully",
      });

      loadData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleEmergencyStopAll = async () => {
    try {
      const { error } = await supabase
        .from("user_strategies")
        .update({
          is_running: false,
          stopped_at: new Date().toISOString(),
        })
        .eq("is_running", true);

      if (error) throw error;

      toast({
        title: "All Bots Stopped",
        description: "All trading bots have been stopped",
      });

      loadData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const getLogIcon = (level: string) => {
    switch (level) {
      case "error": return <XCircle className="w-4 h-4 text-red-500" />;
      case "warning": return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case "info": return <CheckCircle className="w-4 h-4 text-blue-500" />;
      default: return <Activity className="w-4 h-4" />;
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
      {/* Emergency Controls */}
      {runningBots.length > 0 && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>
              <strong>{runningBots.length}</strong> bot{runningBots.length > 1 ? 's' : ''} currently running
            </span>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleEmergencyStopAll}
            >
              <Power className="w-4 h-4 mr-2" />
              Emergency Stop All
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Running Bots */}
        <Card>
          <CardHeader>
            <CardTitle>Active Bots</CardTitle>
            <CardDescription>Currently running trading bots</CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px]">
              {runningBots.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  No bots running
                </p>
              ) : (
                <div className="space-y-3">
                  {runningBots.map((bot) => (
                    <div
                      key={bot.id}
                      onClick={() => setSelectedBot(bot)}
                      className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                        selectedBot?.id === bot.id
                          ? "border-primary bg-primary/5"
                          : "hover:bg-muted/50"
                      }`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="font-medium">{bot.strategies?.name}</h4>
                          <p className="text-sm text-muted-foreground">
                            {bot.profiles?.full_name}
                          </p>
                        </div>
                        <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
                          <Activity className="w-3 h-3 mr-1" />
                          Running
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Started: {new Date(bot.started_at).toLocaleString()}
                      </div>
                      <Button
                        size="sm"
                        variant="destructive"
                        className="mt-2 w-full"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEmergencyStop(bot.id);
                        }}
                      >
                        <Power className="w-3 h-3 mr-1" />
                        Stop Bot
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Bot Logs */}
        <Card>
          <CardHeader>
            <CardTitle>Bot Logs</CardTitle>
            <CardDescription>
              {selectedBot
                ? `Logs for ${selectedBot.strategies?.name} - ${selectedBot.profiles?.full_name}`
                : "Select a bot to view logs"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[500px]">
              {!selectedBot ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-muted-foreground">Select a bot to view logs</p>
                </div>
              ) : botLogs.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  No logs available
                </p>
              ) : (
                <div className="space-y-2">
                  {botLogs.map((log) => (
                    <div
                      key={log.id}
                      className="p-3 border rounded-lg"
                    >
                      <div className="flex items-start gap-2">
                        {getLogIcon(log.log_level)}
                        <div className="flex-1">
                          <p className="text-sm">{log.message}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(log.created_at).toLocaleString()}
                          </p>
                          {log.metadata && Object.keys(log.metadata).length > 0 && (
                            <pre className="text-xs mt-2 p-2 bg-muted rounded">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};