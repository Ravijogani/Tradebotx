import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { CheckCircle, XCircle, Loader2, Activity, Server, Database, Mail } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

export const SystemHealthCheck = () => {
  const [checking, setChecking] = useState(false);
  const [results, setResults] = useState<any>(null);
  const { toast } = useToast();

  const runHealthCheck = async () => {
    setChecking(true);
    const healthResults: any = {
      timestamp: new Date().toISOString(),
      checks: {}
    };

    try {
      // Check 1: Bot Manager Connection
      try {
        const { data: botManager, error } = await supabase.functions.invoke('verify-bot-manager');
        healthResults.checks.botManager = {
          name: 'Bot Manager',
          status: botManager?.healthy ? 'healthy' : 'unhealthy',
          configured: botManager?.configured,
          details: botManager?.error || 'Connected successfully',
          url: botManager?.url,
        };
      } catch (error: any) {
        healthResults.checks.botManager = {
          name: 'Bot Manager',
          status: 'error',
          details: error.message,
        };
      }

      // Check 2: Database Connection
      try {
        const { error } = await supabase.from('strategies').select('count').limit(1);
        healthResults.checks.database = {
          name: 'Database',
          status: error ? 'unhealthy' : 'healthy',
          details: error ? error.message : 'Connected successfully',
        };
      } catch (error: any) {
        healthResults.checks.database = {
          name: 'Database',
          status: 'error',
          details: error.message,
        };
      }

      // Check 3: Strategies Available
      try {
        const { data, error } = await supabase
          .from('strategies')
          .select('count')
          .eq('is_active', true);
        
        healthResults.checks.strategies = {
          name: 'Active Strategies',
          status: data && data.length > 0 ? 'healthy' : 'warning',
          details: data ? `${data.length} strategies available` : 'No strategies configured',
        };
      } catch (error: any) {
        healthResults.checks.strategies = {
          name: 'Active Strategies',
          status: 'error',
          details: error.message,
        };
      }

      // Check 4: Running Bots
      try {
        const { data, error } = await supabase
          .from('user_strategies')
          .select('count')
          .eq('is_running', true);
        
        healthResults.checks.runningBots = {
          name: 'Running Bots',
          status: 'info',
          details: data ? `${data.length} bots currently running` : 'No bots running',
          count: data?.length || 0,
        };
      } catch (error: any) {
        healthResults.checks.runningBots = {
          name: 'Running Bots',
          status: 'error',
          details: error.message,
        };
      }

      setResults(healthResults);

      toast({
        title: "Health Check Complete",
        description: "System health status updated",
      });

    } catch (error: any) {
      toast({
        title: "Health Check Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setChecking(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'unhealthy': return <XCircle className="w-5 h-5 text-red-500" />;
      case 'warning': return <Activity className="w-5 h-5 text-yellow-500" />;
      case 'info': return <Activity className="w-5 h-5 text-blue-500" />;
      default: return <XCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Badge className="bg-green-500/10 text-green-500 border-green-500/20">Healthy</Badge>;
      case 'unhealthy':
        return <Badge className="bg-red-500/10 text-red-500 border-red-500/20">Unhealthy</Badge>;
      case 'warning':
        return <Badge className="bg-yellow-500/10 text-yellow-500 border-yellow-500/20">Warning</Badge>;
      case 'info':
        return <Badge className="bg-blue-500/10 text-blue-500 border-blue-500/20">Info</Badge>;
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Activity className="w-5 h-5" />
              System Health Check
            </CardTitle>
            <CardDescription>Verify all system components are functioning correctly</CardDescription>
          </div>
          <Button onClick={runHealthCheck} disabled={checking}>
            {checking ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Checking...
              </>
            ) : (
              'Run Health Check'
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!results ? (
          <Alert>
            <Server className="h-4 w-4" />
            <AlertDescription>
              Click "Run Health Check" to verify all system components
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Last checked: {new Date(results.timestamp).toLocaleString()}
            </div>

            <div className="space-y-3">
              {Object.values(results.checks).map((check: any, idx: number) => (
                <div key={idx} className="flex items-start gap-3 p-4 border rounded-lg">
                  {getStatusIcon(check.status)}
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <h4 className="font-medium">{check.name}</h4>
                      {getStatusBadge(check.status)}
                    </div>
                    <p className="text-sm text-muted-foreground">{check.details}</p>
                    {check.url && (
                      <p className="text-xs text-muted-foreground mt-1">URL: {check.url}</p>
                    )}
                    {check.count !== undefined && (
                      <p className="text-xs text-muted-foreground mt-1">Count: {check.count}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Summary */}
            <div className="pt-4 border-t">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green-500">
                    {Object.values(results.checks).filter((c: any) => c.status === 'healthy').length}
                  </div>
                  <div className="text-xs text-muted-foreground">Healthy</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-yellow-500">
                    {Object.values(results.checks).filter((c: any) => c.status === 'warning').length}
                  </div>
                  <div className="text-xs text-muted-foreground">Warnings</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-500">
                    {Object.values(results.checks).filter((c: any) => c.status === 'unhealthy' || c.status === 'error').length}
                  </div>
                  <div className="text-xs text-muted-foreground">Issues</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};