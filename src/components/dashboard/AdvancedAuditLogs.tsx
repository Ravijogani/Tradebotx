import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { 
  Shield, Clock, User, Bot, Settings, CreditCard, 
  LogIn, LogOut, Download, Search, Filter, Loader2,
  Activity, AlertTriangle, CheckCircle, Info
} from "lucide-react";
import { format } from "date-fns";
import type { LucideIcon } from "lucide-react";
import type { Tables } from "@/integrations/supabase/types";

type AuditLog = Tables<"advanced_audit_logs">;

const categoryIcons: Record<string, LucideIcon> = {
  auth: LogIn,
  trading: Activity,
  settings: Settings,
  bot: Bot,
  account: User,
  payment: CreditCard
};

const categoryColors: Record<string, string> = {
  auth: "bg-blue-500/10 text-blue-500",
  trading: "bg-green-500/10 text-green-500",
  settings: "bg-purple-500/10 text-purple-500",
  bot: "bg-orange-500/10 text-orange-500",
  account: "bg-cyan-500/10 text-cyan-500",
  payment: "bg-yellow-500/10 text-yellow-500"
};

export const AdvancedAuditLogs = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const { toast } = useToast();

  useEffect(() => {
    loadLogs();
  }, [categoryFilter]);

  const loadLogs = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      let query = supabase
        .from("advanced_audit_logs")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false })
        .limit(100);

      if (categoryFilter !== "all") {
        query = query.eq("action_category", categoryFilter);
      }

      const { data, error } = await query;

      if (error) throw error;
      setLogs(data || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error loading audit logs",
        description: message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter(log => 
    log.action_description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    log.action_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const exportLogs = () => {
    const csvContent = [
      ["Timestamp", "Category", "Action", "Description", "IP Address"].join(","),
      ...filteredLogs.map(log => [
        format(new Date(log.created_at), "yyyy-MM-dd HH:mm:ss"),
        log.action_category,
        log.action_type,
        `"${log.action_description}"`,
        log.ip_address || "N/A"
      ].join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-logs-${format(new Date(), "yyyy-MM-dd")}.csv`;
    a.click();
    URL.revokeObjectURL(url);

    toast({ title: "Audit logs exported" });
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Advanced Audit Logs
            </CardTitle>
            <CardDescription>
              Complete history of all actions on your account
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={exportLogs}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Filter by category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              <SelectItem value="auth">Authentication</SelectItem>
              <SelectItem value="trading">Trading</SelectItem>
              <SelectItem value="bot">Bot Actions</SelectItem>
              <SelectItem value="settings">Settings</SelectItem>
              <SelectItem value="account">Account</SelectItem>
              <SelectItem value="payment">Payment</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Logs List */}
        <ScrollArea className="h-[500px]">
          {filteredLogs.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No audit logs found</p>
              <p className="text-sm">Actions on your account will appear here</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredLogs.map((log) => {
                const Icon = categoryIcons[log.action_category] || Info;
                const colorClass = categoryColors[log.action_category] || "bg-muted text-muted-foreground";

                return (
                  <div
                    key={log.id}
                    className="flex items-start gap-4 p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
                  >
                    <div className={`p-2 rounded-lg ${colorClass}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium">{log.action_type}</span>
                        <Badge variant="outline" className="text-xs">
                          {log.action_category}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1">
                        {log.action_description}
                      </p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {format(new Date(log.created_at), "MMM d, yyyy 'at' h:mm a")}
                        </span>
                        {log.ip_address && (
                          <span>IP: {log.ip_address}</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};