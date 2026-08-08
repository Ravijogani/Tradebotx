import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { 
  Loader2, CheckCircle, XCircle, Code, Eye, 
  Wand2, RefreshCw, Download, User, Calendar
} from "lucide-react";
import { format } from "date-fns";

interface CustomStrategy {
  id: string;
  user_id: string;
  name: string;
  description: string;
  strategy_config: any;
  is_active: boolean;
  is_approved: boolean;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

interface Profile {
  id: string;
  email: string;
  full_name: string | null;
}

export const CustomStrategyApproval = () => {
  const [strategies, setStrategies] = useState<CustomStrategy[]>([]);
  const [profiles, setProfiles] = useState<Record<string, Profile>>({});
  const [loading, setLoading] = useState(true);
  const [selectedStrategy, setSelectedStrategy] = useState<CustomStrategy | null>(null);
  const [generatedCode, setGeneratedCode] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [showCodeDialog, setShowCodeDialog] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const { data, error } = await supabase
        .from("custom_strategies")
        .select("*")
        .order("created_at", { ascending: false });

      if (error) throw error;

      setStrategies(data || []);

      // Load user profiles
      const userIds = [...new Set((data || []).map(s => s.user_id))];
      if (userIds.length > 0) {
        const { data: profileData } = await supabase
          .from("profiles")
          .select("id, email, full_name")
          .in("id", userIds);

        const profileMap: Record<string, Profile> = {};
        profileData?.forEach(p => {
          profileMap[p.id] = p;
        });
        setProfiles(profileMap);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error loading strategies",
        description: message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const generateCode = async (strategy: CustomStrategy) => {
    setGenerating(true);
    setSelectedStrategy(strategy);
    setShowCodeDialog(true);

    try {
      const { data, error } = await supabase.functions.invoke("generate-strategy-code", {
        body: { strategyId: strategy.id, action: "generate" }
      });

      if (error) throw error;

      setGeneratedCode(data.code);
      toast({ title: "Code generated successfully" });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error generating code",
        description: message,
        variant: "destructive"
      });
    } finally {
      setGenerating(false);
    }
  };

  const approveStrategy = async (strategy: CustomStrategy) => {
    setApproving(true);
    try {
      const { error } = await supabase.functions.invoke("generate-strategy-code", {
        body: { strategyId: strategy.id, action: "approve" }
      });

      if (error) throw error;

      toast({ title: "Strategy approved successfully" });
      loadStrategies();
      setShowCodeDialog(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error approving strategy",
        description: message,
        variant: "destructive"
      });
    } finally {
      setApproving(false);
    }
  };

  const rejectStrategy = async (strategy: CustomStrategy) => {
    try {
      const { error } = await supabase
        .from("custom_strategies")
        .update({ is_approved: false, is_active: false })
        .eq("id", strategy.id);

      if (error) throw error;

      toast({ title: "Strategy rejected" });
      loadStrategies();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error rejecting strategy",
        description: message,
        variant: "destructive"
      });
    }
  };

  const downloadCode = () => {
    if (!generatedCode || !selectedStrategy) return;

    const blob = new Blob([generatedCode], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedStrategy.name.replace(/\s+/g, "_").toLowerCase()}_strategy.py`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const pendingStrategies = strategies.filter(s => !s.is_approved);
  const approvedStrategies = strategies.filter(s => s.is_approved);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pending Approval */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Wand2 className="h-5 w-5" />
                Pending Strategy Approval
              </CardTitle>
              <CardDescription>
                Review and approve custom strategies created by Enterprise users
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={loadStrategies}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {pendingStrategies.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">
              No strategies pending approval
            </p>
          ) : (
            <div className="space-y-4">
              {pendingStrategies.map(strategy => {
                const user = profiles[strategy.user_id];
                const blocks = strategy.strategy_config?.blocks || [];

                return (
                  <div
                    key={strategy.id}
                    className="border border-border rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold">{strategy.name}</h3>
                          <Badge variant="secondary">{blocks.length} blocks</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {strategy.description || "No description"}
                        </p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {user?.full_name || user?.email || "Unknown"}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {format(new Date(strategy.created_at), "MMM d, yyyy")}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedStrategy(strategy);
                            setGeneratedCode("");
                            setShowCodeDialog(true);
                          }}
                        >
                          <Eye className="h-4 w-4 mr-2" />
                          View
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => generateCode(strategy)}
                        >
                          <Code className="h-4 w-4 mr-2" />
                          Generate
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => rejectStrategy(strategy)}
                        >
                          <XCircle className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Approved Strategies */}
      <Card>
        <CardHeader>
          <CardTitle>Approved Strategies</CardTitle>
          <CardDescription>
            Strategies that have been approved and are ready for live trading
          </CardDescription>
        </CardHeader>
        <CardContent>
          {approvedStrategies.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">
              No approved strategies yet
            </p>
          ) : (
            <div className="space-y-3">
              {approvedStrategies.map(strategy => {
                const user = profiles[strategy.user_id];

                return (
                  <div
                    key={strategy.id}
                    className="flex items-center justify-between p-3 border border-border rounded-lg"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{strategy.name}</span>
                        <Badge variant="default" className="bg-green-600">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          Approved
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {user?.full_name || user?.email} • 
                        Approved {strategy.approved_at 
                          ? format(new Date(strategy.approved_at), "MMM d, yyyy") 
                          : "N/A"}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => generateCode(strategy)}
                    >
                      <Code className="h-4 w-4 mr-2" />
                      View Code
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Code Dialog */}
      <Dialog open={showCodeDialog} onOpenChange={setShowCodeDialog}>
        <DialogContent className="max-w-4xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle>{selectedStrategy?.name}</DialogTitle>
            <DialogDescription>
              {selectedStrategy?.description || "Strategy configuration and generated code"}
              {" — approving publishes it to the strategy marketplace for other users to import into their own builder. It does not start a live bot; the generated code below is reference/export only."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Block Summary */}
            <div className="p-3 bg-muted/50 rounded-lg">
              <h4 className="font-medium text-sm mb-2">Strategy Blocks</h4>
              <div className="flex flex-wrap gap-2">
                {(selectedStrategy?.strategy_config?.blocks || []).map((block: any) => (
                  <Badge key={block.id} variant="outline">
                    {block.block?.name || "Unknown"}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Generated Code */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-sm">Generated Python Code</h4>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => selectedStrategy && generateCode(selectedStrategy)}
                    disabled={generating}
                  >
                    {generating ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4 mr-2" />
                    )}
                    Regenerate
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={downloadCode}
                    disabled={!generatedCode}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                </div>
              </div>
              <ScrollArea className="h-[400px] border border-border rounded-lg">
                {generating ? (
                  <div className="flex items-center justify-center h-full">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                ) : generatedCode ? (
                  <pre className="p-4 text-xs font-mono whitespace-pre-wrap">
                    {generatedCode}
                  </pre>
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground">
                    Click "Regenerate" to generate Python code
                  </div>
                )}
              </ScrollArea>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 pt-4 border-t border-border">
              <Button variant="outline" onClick={() => setShowCodeDialog(false)}>
                Close
              </Button>
              {!selectedStrategy?.is_approved && (
                <Button
                  onClick={() => selectedStrategy && approveStrategy(selectedStrategy)}
                  disabled={approving || !generatedCode}
                >
                  {approving ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <CheckCircle className="h-4 w-4 mr-2" />
                  )}
                  Approve for Marketplace
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
