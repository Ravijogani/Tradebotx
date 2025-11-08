import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Loader2, TrendingUp, Shield } from "lucide-react";

const Admin = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Sign in with email and password
      const { data: authData, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (authError) throw authError;

      if (!authData.user) {
        throw new Error("Authentication failed");
      }

      // Check if user has admin role
      const { data: roleData, error: roleError } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", authData.user.id)
        .eq("role", "admin")
        .maybeSingle();

      if (roleError) {
        console.error("Role check error:", roleError);
        throw new Error("Failed to verify admin access");
      }

      if (!roleData) {
        // User is not an admin, redirect to user dashboard
        toast({
          title: "Access Denied",
          description: "You don't have admin permissions. Redirecting to user dashboard...",
          variant: "destructive",
        });
        setTimeout(() => navigate("/dashboard"), 1500);
        return;
      }

      // User is an admin, redirect to admin dashboard
      toast({
        title: "Welcome Admin",
        description: "Login successful",
      });
      navigate("/admin/dashboard");
    } catch (error: any) {
      toast({
        title: "Login Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
      
      <Card className="w-full max-w-md p-8 space-y-6 relative z-10 border-border/50 bg-card/80 backdrop-blur-xl shadow-2xl">
        <div className="text-center space-y-2">
          <div className="w-16 h-16 rounded-lg bg-gradient-hero flex items-center justify-center shadow-glow mx-auto">
            <Shield className="w-10 h-10 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
            Admin Login
          </h1>
          <p className="text-muted-foreground">
            Enter your credentials to access the admin panel
          </p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="admin@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading}
              className="bg-background/50"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              className="bg-background/50"
            />
          </div>

          <Button
            type="submit"
            className="w-full bg-gradient-hero shadow-glow"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Verifying...
              </>
            ) : (
              "Login as Admin"
            )}
          </Button>
        </form>

        <div className="text-center">
          <Button
            variant="link"
            onClick={() => navigate("/auth/login")}
            className="text-muted-foreground"
          >
            Back to User Login
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default Admin;
