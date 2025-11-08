import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Loader2, Plus, Edit, Trash2, Upload, FileCode, TrendingUp } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface Strategy {
  id: string;
  name: string;
  description: string;
  plan_type: string;
  python_script_path: string;
  is_active: boolean;
  performance_data: any;
  created_at: string;
}

const ADMIN_EMAIL = "admin@tradebotx.com";

export const AdminStrategies = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<Strategy | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const { toast } = useToast();

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    plan_type: "free" as "free" | "pro" | "enterprise",
    python_file: null as File | null,
    is_active: true,
  });

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const { data, error } = await supabase
        .from("strategies")
        .select("*")
        .order("created_at", { ascending: false });

      if (error) throw error;
      setStrategies(data || []);
    } catch (error: any) {
      toast({
        title: "Error loading strategies",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith(".py")) {
        toast({
          title: "Invalid file",
          description: "Please upload a Python (.py) file",
          variant: "destructive",
        });
        return;
      }
      setFormData({ ...formData, python_file: file });
    }
  };

  const uploadPythonScript = async (file: File): Promise<string> => {
    const fileName = `${Date.now()}-${file.name}`;
    const filePath = `strategies/${fileName}`;

    const { error: uploadError } = await supabase.storage
      .from("strategy-scripts")
      .upload(filePath, file);

    if (uploadError) throw uploadError;
    return filePath;
  };

  const handleSubmit = async () => {
    try {
      setUploadingFile(true);

      let scriptPath = editingStrategy?.python_script_path || "";

      if (formData.python_file) {
        scriptPath = await uploadPythonScript(formData.python_file);
      }

      if (!scriptPath) {
        toast({
          title: "Missing file",
          description: "Please upload a Python script",
          variant: "destructive",
        });
        return;
      }

      const strategyData = {
        name: formData.name,
        description: formData.description,
        plan_type: formData.plan_type,
        python_script_path: scriptPath,
        is_active: formData.is_active,
      };

      if (editingStrategy) {
        const { error } = await supabase
          .from("strategies")
          .update(strategyData)
          .eq("id", editingStrategy.id);

        if (error) throw error;

        // Log activity
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
          await supabase.from("admin_activity_logs").insert({
            admin_user_id: user.id,
            action_type: "strategy_updated",
            description: `Updated strategy: ${formData.name}`,
            metadata: { strategy_id: editingStrategy.id, plan_type: formData.plan_type }
          });

          // Send email notification
          try {
            await supabase.functions.invoke('send-admin-alert', {
              body: {
                adminEmail: ADMIN_EMAIL,
                actionType: 'Strategy Updated',
                performedBy: user.email || 'Unknown Admin',
                details: `Strategy "${formData.name}" has been updated for ${formData.plan_type} plan users.`
              }
            });
          } catch (emailError) {
            console.error('Failed to send admin alert:', emailError);
          }
        }

        toast({ title: "Success", description: "Strategy updated successfully" });
      } else {
        const { error } = await supabase
          .from("strategies")
          .insert([strategyData]);

        if (error) throw error;

        // Log activity
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
          await supabase.from("admin_activity_logs").insert({
            admin_user_id: user.id,
            action_type: "strategy_created",
            description: `Created strategy: ${formData.name}`,
            metadata: { plan_type: formData.plan_type }
          });

          // Send email notification
          try {
            await supabase.functions.invoke('send-admin-alert', {
              body: {
                adminEmail: ADMIN_EMAIL,
                actionType: 'Strategy Created',
                performedBy: user.email || 'Unknown Admin',
                details: `New strategy "${formData.name}" has been created for ${formData.plan_type} plan users.`
              }
            });
          } catch (emailError) {
            console.error('Failed to send admin alert:', emailError);
          }
        }

        toast({ title: "Success", description: "Strategy created successfully" });
      }

      resetForm();
      loadStrategies();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setUploadingFile(false);
    }
  };

  const handleEdit = (strategy: Strategy) => {
    setEditingStrategy(strategy);
    setFormData({
      name: strategy.name,
      description: strategy.description,
      plan_type: strategy.plan_type as any,
      python_file: null,
      is_active: strategy.is_active,
    });
    setDialogOpen(true);
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;

    try {
      const { error } = await supabase
        .from("strategies")
        .delete()
        .eq("id", id);

      if (error) throw error;

      // Log activity
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        await supabase.from("admin_activity_logs").insert({
          admin_user_id: user.id,
          action_type: "strategy_deleted",
          description: `Deleted strategy: ${name}`,
          metadata: { strategy_id: id }
        });
      }

      toast({ title: "Success", description: "Strategy deleted successfully" });
      loadStrategies();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const toggleActive = async (strategy: Strategy) => {
    try {
      const { error } = await supabase
        .from("strategies")
        .update({ is_active: !strategy.is_active })
        .eq("id", strategy.id);

      if (error) throw error;

      toast({
        title: "Success",
        description: `Strategy ${!strategy.is_active ? "activated" : "deactivated"}`,
      });
      loadStrategies();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      plan_type: "free",
      python_file: null,
      is_active: true,
    });
    setEditingStrategy(null);
    setDialogOpen(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Trading Strategies
              </CardTitle>
              <CardDescription>
                Manage trading strategies and assign them to subscription plans
              </CardDescription>
            </div>
            <Button onClick={() => setDialogOpen(true)} className="gap-2">
              <Plus className="w-4 h-4" />
              Add Strategy
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Strategy Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Script</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {strategies.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground">
                      No strategies found. Create your first strategy to get started.
                    </TableCell>
                  </TableRow>
                ) : (
                  strategies.map((strategy) => (
                    <TableRow key={strategy.id}>
                      <TableCell className="font-medium">{strategy.name}</TableCell>
                      <TableCell className="max-w-xs truncate">{strategy.description}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {strategy.plan_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <FileCode className="w-4 h-4" />
                          {strategy.python_script_path.split("/").pop()}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={strategy.is_active}
                          onCheckedChange={() => toggleActive(strategy)}
                        />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(strategy.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex gap-2 justify-end">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEdit(strategy)}
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleDelete(strategy.id, strategy.name)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="mt-4 text-sm text-muted-foreground">
            Total Strategies: {strategies.length} | Active: {strategies.filter(s => s.is_active).length}
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open) => !open && resetForm()}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingStrategy ? "Edit Strategy" : "Create New Strategy"}
            </DialogTitle>
            <DialogDescription>
              Configure the trading strategy and upload the Python script
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Strategy Name *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Scalping Strategy"
              />
            </div>

            <div>
              <Label htmlFor="description">Description *</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe the strategy, its goals, and expected performance..."
                rows={4}
              />
            </div>

            <div>
              <Label htmlFor="plan">Subscription Plan *</Label>
              <Select
                value={formData.plan_type}
                onValueChange={(value: any) => setFormData({ ...formData, plan_type: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">Free Plan</SelectItem>
                  <SelectItem value="pro">Pro Plan</SelectItem>
                  <SelectItem value="enterprise">Enterprise Plan</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="script">Python Script (.py) *</Label>
              <div className="mt-1.5">
                <Input
                  id="script"
                  type="file"
                  accept=".py"
                  onChange={handleFileChange}
                  className="cursor-pointer"
                />
                {editingStrategy && !formData.python_file && (
                  <Alert className="mt-2">
                    <FileCode className="h-4 w-4" />
                    <AlertDescription>
                      Current file: {editingStrategy.python_script_path.split("/").pop()}
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Switch
                id="active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
              />
              <Label htmlFor="active" className="cursor-pointer">
                Make strategy active immediately
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={resetForm}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={
                !formData.name ||
                !formData.description ||
                (!formData.python_file && !editingStrategy) ||
                uploadingFile
              }
            >
              {uploadingFile ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  {editingStrategy ? "Update Strategy" : "Create Strategy"}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};
