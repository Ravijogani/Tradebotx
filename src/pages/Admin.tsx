import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Plus, TrendingUp, LogOut, Pencil, Trash } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const Admin = () => {
  const [loading, setLoading] = useState(true);
  const [strategies, setStrategies] = useState<any[]>([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    planType: "free" as "free" | "pro" | "enterprise",
    pythonScriptPath: "",
  });
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkAdminAccess();
  }, []);

  const checkAdminAccess = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      
      if (!user) {
        navigate("/auth/login");
        return;
      }

      // Check if user is admin
      const { data: roles } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", user.id)
        .eq("role", "admin")
        .single();

      if (!roles) {
        toast({
          title: "Access Denied",
          description: "You don't have admin permissions",
          variant: "destructive",
        });
        navigate("/dashboard");
        return;
      }

      loadStrategies();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
      navigate("/dashboard");
    }
  };

  const loadStrategies = async () => {
    const { data } = await supabase
      .from("strategies")
      .select("*")
      .order("created_at", { ascending: false });

    setStrategies(data || []);
    setLoading(false);
  };

  const handleCreateStrategy = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const { error } = await supabase.from("strategies").insert({
        name: formData.name,
        description: formData.description,
        plan_type: formData.planType,
        python_script_path: formData.pythonScriptPath,
        is_active: true,
      });

      if (error) throw error;

      toast({
        title: "Strategy created",
        description: "New trading strategy has been added successfully",
      });

      setShowCreateDialog(false);
      setFormData({
        name: "",
        description: "",
        planType: "free",
        pythonScriptPath: "",
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

  const handleDeleteStrategy = async (id: string) => {
    if (!confirm("Are you sure you want to delete this strategy?")) return;

    try {
      const { error } = await supabase
        .from("strategies")
        .delete()
        .eq("id", id);

      if (error) throw error;

      toast({
        title: "Strategy deleted",
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

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-lg sticky top-0 z-40">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-lg bg-gradient-hero flex items-center justify-center shadow-glow">
                <TrendingUp className="w-6 h-6 text-primary-foreground" />
              </div>
              <span className="text-xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                TradeBotX Admin
              </span>
            </div>

            <div className="flex items-center gap-4">
              <Button variant="ghost" onClick={() => navigate("/dashboard")}>
                User Dashboard
              </Button>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Strategy Management</h1>
            <p className="text-muted-foreground">Create and manage trading strategies</p>
          </div>

          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button className="bg-gradient-hero shadow-glow">
                <Plus className="w-4 h-4 mr-2" />
                Add Strategy
              </Button>
            </DialogTrigger>

            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Strategy</DialogTitle>
                <DialogDescription>Add a new trading strategy for users</DialogDescription>
              </DialogHeader>

              <form onSubmit={handleCreateStrategy} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Strategy Name</Label>
                  <Input
                    id="name"
                    placeholder="Scalping Pro"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="High-frequency scalping strategy..."
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="planType">Plan Type</Label>
                  <Select
                    value={formData.planType}
                    onValueChange={(value: any) => setFormData({ ...formData, planType: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="free">Free</SelectItem>
                      <SelectItem value="pro">Pro</SelectItem>
                      <SelectItem value="enterprise">Enterprise</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="pythonScript">Python Script Path</Label>
                  <Input
                    id="pythonScript"
                    placeholder="strategies/scalping_pro.py"
                    value={formData.pythonScriptPath}
                    onChange={(e) => setFormData({ ...formData, pythonScriptPath: e.target.value })}
                    required
                  />
                </div>

                <Button type="submit" className="w-full">Create Strategy</Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {/* Strategies Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {strategies.map((strategy) => (
            <Card key={strategy.id} className="p-6 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-xl font-semibold mb-1">{strategy.name}</h3>
                  <Badge variant="outline" className="text-xs">
                    {strategy.plan_type}
                  </Badge>
                </div>
              </div>

              <p className="text-sm text-muted-foreground">{strategy.description}</p>

              <div className="text-xs text-muted-foreground">
                Script: <code className="bg-muted px-2 py-1 rounded">{strategy.python_script_path}</code>
              </div>

              <div className="flex gap-2 pt-2">
                <Button
                  variant="destructive"
                  size="sm"
                  className="w-full"
                  onClick={() => handleDeleteStrategy(strategy.id)}
                >
                  <Trash className="w-4 h-4 mr-2" />
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Admin;
