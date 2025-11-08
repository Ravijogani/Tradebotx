import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, Activity, User, Shield, Settings, Trash, CheckCircle, XCircle } from "lucide-react";
import { format } from "date-fns";

interface ActivityLog {
  id: string;
  admin_user_id: string;
  action_type: string;
  target_user_id: string | null;
  description: string;
  metadata: any;
  created_at: string;
  admin_email?: string;
  target_email?: string;
}

export const AdminActivityLogs = () => {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActivityLogs();
  }, []);

  const loadActivityLogs = async () => {
    try {
      const { data, error } = await supabase
        .from("admin_activity_logs")
        .select(`
          *,
          admin:admin_user_id(email),
          target:target_user_id(email)
        `)
        .order("created_at", { ascending: false })
        .limit(100);

      if (error) throw error;

      const formattedLogs = data?.map((log: any) => ({
        ...log,
        admin_email: log.admin?.email,
        target_email: log.target?.email,
      })) || [];

      setLogs(formattedLogs);
    } catch (error) {
      console.error("Error loading activity logs:", error);
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case "user_approved":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "user_rejected":
        return <XCircle className="w-4 h-4 text-red-500" />;
      case "role_assigned":
        return <Shield className="w-4 h-4 text-blue-500" />;
      case "role_revoked":
        return <Shield className="w-4 h-4 text-orange-500" />;
      case "user_deleted":
        return <Trash className="w-4 h-4 text-red-500" />;
      case "settings_changed":
        return <Settings className="w-4 h-4 text-purple-500" />;
      default:
        return <Activity className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const getActionColor = (actionType: string) => {
    switch (actionType) {
      case "user_approved":
        return "bg-green-500/10 text-green-500 border-green-500/20";
      case "user_rejected":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      case "role_assigned":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "role_revoked":
        return "bg-orange-500/10 text-orange-500 border-orange-500/20";
      case "user_deleted":
        return "bg-red-500/10 text-red-500 border-red-500/20";
      case "settings_changed":
        return "bg-purple-500/10 text-purple-500 border-purple-500/20";
      default:
        return "bg-muted text-muted-foreground";
    }
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

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          Activity Logs
        </CardTitle>
        <CardDescription>
          Track all administrative actions performed in the system
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[600px] pr-4">
          <div className="space-y-3">
            {logs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No activity logs found
              </div>
            ) : (
              logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-start gap-3 p-4 rounded-lg border border-border/50 bg-card/50 hover:bg-card transition-colors"
                >
                  <div className="mt-1">{getActionIcon(log.action_type)}</div>
                  
                  <div className="flex-1 space-y-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <p className="text-sm font-medium">{log.description}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                          <User className="w-3 h-3" />
                          <span>Admin: {log.admin_email}</span>
                          {log.target_email && (
                            <>
                              <span>→</span>
                              <span>Target: {log.target_email}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <Badge variant="outline" className={getActionColor(log.action_type)}>
                        {log.action_type.replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {format(new Date(log.created_at), "PPpp")}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};
