import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabase } from "@/integrations/supabase/client";
import { Activity, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

interface BotHealth {
  status: string;
  last_heartbeat: string;
  mt5_connected: boolean;
  error_message?: string;
}

export const BotHealthIndicator = () => {
  const [health, setHealth] = useState<BotHealth | null>(null);
  const [isStale, setIsStale] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadBotHealth();
    
    // Check for stale heartbeat every 30 seconds
    const staleInterval = setInterval(() => {
      checkHeartbeatFreshness();
    }, 30000);
    
    // Set up realtime subscription
    const channel = supabase
      .channel('bot-heartbeat-changes')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'bot_heartbeats'
        },
        (payload) => {
          console.log('Heartbeat change:', payload);
          loadBotHealth();
          
          if (payload.eventType === 'UPDATE' && payload.new.status === 'crashed') {
            toast({
              title: "⚠️ Bot Crashed",
              description: payload.new.error_message || "Bot has stopped unexpectedly",
              variant: "destructive"
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
      clearInterval(staleInterval);
    };
  }, []);

  const loadBotHealth = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data } = await supabase
      .from("bot_heartbeats")
      .select("*")
      .eq("user_id", user.id)
      .order("last_heartbeat", { ascending: false })
      .limit(1)
      .maybeSingle();

    setHealth(data);
    checkHeartbeatFreshness(data);
  };

  const checkHeartbeatFreshness = (healthData?: BotHealth | null) => {
    const data = healthData || health;
    if (!data) {
      setIsStale(false);
      return;
    }

    const lastBeat = new Date(data.last_heartbeat).getTime();
    const now = Date.now();
    const diffSeconds = (now - lastBeat) / 1000;
    
    // Consider stale if no heartbeat for over 60 seconds
    setIsStale(diffSeconds > 60);
  };

  if (!health) {
    return null;
  }

  const getStatusInfo = () => {
    if (isStale) {
      return {
        icon: AlertTriangle,
        color: 'text-yellow-500',
        bgColor: 'bg-yellow-500/10',
        label: 'Connection Lost',
        variant: 'secondary' as const
      };
    }

    switch (health.status) {
      case 'running':
        return {
          icon: CheckCircle,
          color: 'text-success',
          bgColor: 'bg-success/10',
          label: 'Running',
          variant: 'default' as const
        };
      case 'reconnecting':
        return {
          icon: Activity,
          color: 'text-yellow-500',
          bgColor: 'bg-yellow-500/10',
          label: 'Reconnecting',
          variant: 'secondary' as const
        };
      case 'crashed':
      case 'stopped':
        return {
          icon: XCircle,
          color: 'text-destructive',
          bgColor: 'bg-destructive/10',
          label: health.status === 'crashed' ? 'Crashed' : 'Stopped',
          variant: 'destructive' as const
        };
      default:
        return {
          icon: Activity,
          color: 'text-muted-foreground',
          bgColor: 'bg-muted/50',
          label: 'Unknown',
          variant: 'secondary' as const
        };
    }
  };

  const statusInfo = getStatusInfo();
  const Icon = statusInfo.icon;

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm w-full min-w-0">
      <CardHeader className="pb-3 p-3 sm:p-4 md:p-6">
        <CardTitle className="text-sm sm:text-base flex items-center gap-2">
          Bot Status
        </CardTitle>
      </CardHeader>
      <CardContent className="p-3 sm:p-4 md:p-6 pt-0">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-lg ${statusInfo.bgColor} flex items-center justify-center flex-shrink-0`}>
              <Icon className={`w-4 h-4 sm:w-5 sm:h-5 ${statusInfo.color}`} />
            </div>
            <div className="min-w-0">
              <Badge variant={statusInfo.variant} className="mb-1 text-xs">
                {statusInfo.label}
              </Badge>
              <div className="text-xs text-muted-foreground truncate">
                {isStale ? 'No heartbeat' : `MT5: ${health.mt5_connected ? 'Connected' : 'Disconnected'}`}
              </div>
            </div>
          </div>
          
          <div className="text-left sm:text-right border-t sm:border-t-0 sm:border-l border-border/30 pt-2 sm:pt-0 sm:pl-3">
            <div className="text-xs text-muted-foreground">Last update</div>
            <div className="text-xs sm:text-sm font-medium">
              {new Date(health.last_heartbeat).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </div>
          </div>
        </div>
        
        {health.error_message && (
          <div className="mt-3 p-2 rounded bg-destructive/10 border border-destructive/20">
            <p className="text-xs text-destructive break-words">{health.error_message}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};