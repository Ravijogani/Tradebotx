import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";
import { z } from "zod";
import { OTPVerification } from "./OTPVerification";

const signupSchema = z.object({
  fullName: z.string().min(2, "Name must be at least 2 characters").max(100),
  email: z.string().email("Invalid email address"),
  phone: z.string().regex(/^\+?[1-9]\d{9,14}$/, "Invalid phone number"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string(),
  referralCode: z.string().optional(),
  // Risk acceptance was previously asserted only as passive prose ("by using
  // TradeBotX you confirm..."). For a platform that trades real client
  // capital, consent needs to be an affirmative act that fails validation
  // when absent -- not a sentence nobody has to read.
  acceptedRisk: z.literal(true, {
    message: "You must accept the Risk Disclaimer and Terms to continue",
  }),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

interface SignupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  planName?: string;
}

export const SignupDialog = ({ open, onOpenChange, planName }: SignupDialogProps) => {
  const [loading, setLoading] = useState(false);
  const [showOTPVerification, setShowOTPVerification] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
    referralCode: "",
    acceptedRisk: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setLoading(true);

    try {
      // Validate form
      const validated = signupSchema.parse(formData);

      // Check if user already exists
      const { data: existingUser } = await supabase
        .from("profiles")
        .select("email")
        .eq("email", validated.email)
        .single();

      if (existingUser) {
        toast({
          title: "Email already registered",
          description: "Please use a different email or try logging in",
          variant: "destructive",
        });
        setLoading(false);
        return;
      }

      // Determine plan type from planName prop
      let selectedPlanType = 'free';
      if (planName) {
        const planLower = planName.toLowerCase();
        if (planLower.includes('pro')) {
          selectedPlanType = 'pro';
        } else if (planLower.includes('enterprise')) {
          selectedPlanType = 'enterprise';
        }
      }

      // Create user account (without auto-confirm)
      const { data: authData, error: authError } = await supabase.auth.signUp({
        email: validated.email,
        password: validated.password,
        options: {
          data: {
            full_name: validated.fullName,
            phone: validated.phone,
            referral_code: validated.referralCode || null,
            // Recorded so there is an actual audit trail of who accepted
            // the risk disclosure and when, rather than an assumption.
            accepted_risk_disclaimer_at: new Date().toISOString(),
            selected_plan: selectedPlanType, // Pass selected plan to trigger
          },
          emailRedirectTo: `${window.location.origin}/auth/login`,
        },
      });

      if (authError) throw authError;

      // Send OTP
      const { error: otpError } = await supabase.functions.invoke('send-otp', {
        body: {
          email: validated.email,
          otpType: 'signup'
        }
      });

      if (otpError) {
        console.error('OTP sending error:', otpError);
        throw new Error('Failed to send verification code');
      }

      // Store email for OTP verification - welcome email will be sent AFTER verification
      setUserEmail(validated.email);
      setShowOTPVerification(true);

      toast({
        title: "Verification code sent!",
        description: "Please check your email for the OTP",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (error instanceof z.ZodError) {
        const fieldErrors: Record<string, string> = {};
        error.issues.forEach((err) => {
          if (err.path && err.path.length > 0) {
            fieldErrors[String(err.path[0])] = err.message;
          }
        });
        setErrors(fieldErrors);
        toast({
          title: "Validation Error",
          description: "Please check all fields",
          variant: "destructive",
        });
      } else {
        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  if (showOTPVerification) {
    return (
      <OTPVerification
        open={open}
        onOpenChange={onOpenChange}
        email={userEmail}
        otpType="signup"
        onVerified={async () => {
          // Send welcome email ONLY after successful OTP verification
          try {
            await supabase.functions.invoke('send-welcome-email', {
              body: {
                to: userEmail,
                userName: formData.fullName
              }
            });
          } catch (error) {
            console.error('Failed to send welcome email:', error);
          }
          
          onOpenChange(false);
          toast({
            title: "Email verified!",
            description: "Please login to continue",
          });
          window.location.href = "/auth/login";
        }}
      />
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Your Account</DialogTitle>
          <DialogDescription>
            {planName ? `Sign up for ${planName} plan` : "Sign up to start trading with TradeBotX"}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="fullName">Full Name *</Label>
            <Input
              id="fullName"
              placeholder="John Doe"
              value={formData.fullName}
              onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
              className={errors.fullName ? "border-destructive" : ""}
            />
            {errors.fullName && <p className="text-sm text-destructive">{errors.fullName}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email *</Label>
            <Input
              id="email"
              type="email"
              placeholder="john@example.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className={errors.email ? "border-destructive" : ""}
            />
            {errors.email && <p className="text-sm text-destructive">{errors.email}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="phone">Phone Number (with country code) *</Label>
            <Input
              id="phone"
              type="tel"
              placeholder="+1234567890"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              className={errors.phone ? "border-destructive" : ""}
              aria-describedby="phone-hint"
            />
            <p id="phone-hint" className="text-xs text-muted-foreground">
              Include country code (e.g., +1 for US, +91 for India)
            </p>
            {errors.phone && <p className="text-sm text-destructive">{errors.phone}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="referralCode">Referral Code (Optional)</Label>
            <Input
              id="referralCode"
              placeholder="Enter referral code"
              value={formData.referralCode}
              onChange={(e) => setFormData({ ...formData, referralCode: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password *</Label>
            <Input
              id="password"
              type="password"
              placeholder="••••••••"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className={errors.password ? "border-destructive" : ""}
            />
            {errors.password && <p className="text-sm text-destructive">{errors.password}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password *</Label>
            <Input
              id="confirmPassword"
              type="password"
              placeholder="••••••••"
              value={formData.confirmPassword}
              onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
              className={errors.confirmPassword ? "border-destructive" : ""}
            />
            {errors.confirmPassword && <p className="text-sm text-destructive">{errors.confirmPassword}</p>}
          </div>

          <div className="space-y-2 rounded-lg border border-border/60 bg-muted/30 p-3">
            <div className="flex items-start gap-3">
              <Checkbox
                id="acceptedRisk"
                checked={formData.acceptedRisk}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, acceptedRisk: checked === true })
                }
                className="mt-0.5"
                aria-describedby="acceptedRisk-desc"
              />
              <Label htmlFor="acceptedRisk" id="acceptedRisk-desc" className="text-sm font-normal leading-snug cursor-pointer">
                I understand that automated trading carries a real risk of financial
                loss, that past performance does not guarantee future results, and
                that I may lose money. I accept the{" "}
                <a href="/disclaimer" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                  Risk Disclaimer
                </a>{" "}
                and{" "}
                <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                  Terms of Service
                </a>.
              </Label>
            </div>
            {errors.acceptedRisk && <p className="text-sm text-destructive">{errors.acceptedRisk}</p>}
          </div>

          <Button type="submit" className="w-full bg-gradient-hero shadow-glow" disabled={loading || !formData.acceptedRisk}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating Account...
              </>
            ) : (
              "Create Account"
            )}
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <a href="/auth/login" className="text-primary hover:underline">
              Sign in
            </a>
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
};
