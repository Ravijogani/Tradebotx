import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";
import { OTPVerification } from "@/components/auth/OTPVerification";
import logo from "@/assets/tradebotx-logo.png";
import logoWhite from "@/assets/tradebotx-logo-white.png";
import { useTheme } from "@/components/theme-provider";

const Login = () => {
  const [loading, setLoading] = useState(false);
  const [showOTPVerification, setShowOTPVerification] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const navigate = useNavigate();
  const { toast } = useToast();
  const { theme } = useTheme();

  // Determine which logo to use based on theme
  const getEffectiveTheme = () => {
    if (theme === "light") return "light";
    if (theme === "dark") return "dark";
    if (theme === "system") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return "dark";
  };

  const currentLogo = getEffectiveTheme() === "light" ? logo : logoWhite;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      // First verify credentials
      const { data, error } = await supabase.auth.signInWithPassword({
        email: formData.email,
        password: formData.password,
      });

      if (error) throw error;

      if (data.user) {
        // Send OTP for additional verification
        const { error: otpError } = await supabase.functions.invoke('send-otp', {
          body: {
            email: formData.email,
            otpType: 'login'
          }
        });

        if (otpError) {
          console.error('OTP sending error:', otpError);
          throw new Error('Failed to send verification code');
        }

        // Sign out temporarily until OTP is verified
        await supabase.auth.signOut();

        setUserEmail(formData.email);
        setShowOTPVerification(true);

        toast({
          title: "Verification code sent!",
          description: "Please check your email for the OTP",
        });
      }
    } catch (error: any) {
      toast({
        title: "Login failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleOTPVerified = async () => {
    // Sign in again after OTP verification
    const { data, error } = await supabase.auth.signInWithPassword({
      email: formData.email,
      password: formData.password,
    });

    if (error) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
      return;
    }

    if (data.user) {
      toast({
        title: "Welcome back!",
        description: "Successfully logged in to your account.",
      });
      navigate("/dashboard");
    }
  };

  if (showOTPVerification) {
    return (
      <OTPVerification
        open={true}
        onOpenChange={(open) => {
          if (!open) {
            setShowOTPVerification(false);
            setUserEmail("");
          }
        }}
        email={userEmail}
        otpType="login"
        onVerified={handleOTPVerified}
      />
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/10 via-background to-accent/10 p-4">
      <Card className="w-full max-w-md shadow-premium">
        <CardHeader className="space-y-4 text-center">
          <Link to="/" className="flex items-center gap-2 justify-center">
            <img 
              src={currentLogo} 
              alt="TradeBotX" 
              className="h-16 w-auto object-contain"
            />
          </Link>
          <CardTitle className="text-2xl">Welcome Back</CardTitle>
          <CardDescription>Sign in to your TradeBotX account</CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="john@example.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required
              />
            </div>

            <Button type="submit" className="w-full bg-gradient-hero shadow-glow" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </Button>

            <div className="text-center text-sm text-muted-foreground">
              Don't have an account?{" "}
              <Link to="/pricing" className="text-accent hover:underline font-medium">
                Sign up
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default Login;
