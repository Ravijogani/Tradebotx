import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Loader2, TrendingUp, Shield } from "lucide-react";
import { OTPVerification } from "@/components/auth/OTPVerification";

const Admin = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showOTP, setShowOTP] = useState(false);
  const [tempUserId, setTempUserId] = useState<string | null>(null);
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
        // Sign out non-admin user
        await supabase.auth.signOut();
        toast({
          title: "Access Denied",
          description: "You don't have admin permissions.",
          variant: "destructive",
        });
        return;
      }

      // Admin verified, sign out and require OTP
      await supabase.auth.signOut();
      setTempUserId(authData.user.id);
      
      // Generate and send OTP
      const { data: otpData, error: otpError } = await supabase.rpc(
        'generate_otp',
        { p_email: email, p_user_id: authData.user.id, p_otp_type: 'admin_login' }
      );

      if (otpError) {
        console.error("OTP generation error:", otpError);
        throw new Error("Failed to generate OTP: " + otpError.message);
      }

      if (!otpData || otpData.length === 0) {
        throw new Error("Failed to generate OTP code");
      }

      // Send OTP via email
      const { error: sendError } = await supabase.functions.invoke('send-otp', {
        body: { email, otp_code: otpData[0].otp_code, otp_type: 'admin_login' }
      });

      if (sendError) {
        console.error("OTP send error:", sendError);
        throw new Error("Failed to send OTP email: " + sendError.message);
      }

      setShowOTP(true);
      toast({
        title: "OTP Sent",
        description: "Please check your email for the verification code",
      });
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

  const handleOTPVerified = async () => {
    try {
      // Sign in again after OTP verification
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

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
    }
  };

  if (showOTP) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="fixed inset-0 bg-gradient-mesh opacity-40 pointer-events-none" />
        <OTPVerification
          email={email}
          otpType="admin_login"
          onVerified={handleOTPVerified}
          onResend={async () => {
            const { data: otpData } = await supabase.rpc(
              'generate_otp',
              { p_email: email, p_user_id: tempUserId, p_otp_type: 'admin_login' }
            );
            await supabase.functions.invoke('send-otp', {
              body: { email, otp_code: otpData[0].otp_code, otp_type: 'admin_login' }
            });
          }}
        />
      </div>
    );
  }

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
