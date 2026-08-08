import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Clock } from "lucide-react";

interface OTPVerificationProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  email: string;
  otpType: 'signup' | 'login' | 'admin_login';
  onVerified: () => void;
  onResend?: () => Promise<void>;
}

export const OTPVerification = ({ open = true, onOpenChange, email, otpType, onVerified, onResend }: OTPVerificationProps) => {
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [timeLeft, setTimeLeft] = useState(120); // 2 minutes
  const { toast } = useToast();

  useEffect(() => {
    if (open && timeLeft > 0) {
      const timer = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [open, timeLeft]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (otp.length !== 6) {
        throw new Error('Please enter a 6-digit OTP');
      }

      // Verify OTP
      const { data, error } = await supabase.rpc('verify_otp', {
        p_email: email,
        p_otp_code: otp,
        p_otp_type: otpType
      });

      if (error) throw error;

      if (!data) {
        throw new Error('Invalid or expired OTP');
      }

      toast({
        title: "Verification successful!",
        description: "Your account has been verified",
      });

      onVerified();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Verification failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setResending(true);

    try {
      if (onResend) {
        await onResend();
      } else {
        const { error } = await supabase.functions.invoke('send-otp', {
          body: {
            email,
            otpType
          }
        });

        if (error) throw error;
      }

      setTimeLeft(120); // Reset timer
      setOtp(""); // Clear OTP input

      toast({
        title: "OTP resent!",
        description: "Please check your email",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
    } finally {
      setResending(false);
    }
  };

  // For admin_login, render without Dialog wrapper
  if (otpType === 'admin_login') {
    return (
      <div className="w-full max-w-md p-8 space-y-6 relative z-10 border border-border/50 bg-card/80 backdrop-blur-xl shadow-2xl rounded-lg">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold">Verify Your Identity</h2>
          <p className="text-muted-foreground">
            Enter the 6-digit code sent to {email}
          </p>
        </div>

        <form onSubmit={handleVerify} className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Verification Code</label>
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                <Clock className="w-4 h-4" />
                {formatTime(timeLeft)}
              </div>
            </div>
            <Input
              type="text"
              placeholder="000000"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="text-center text-2xl tracking-widest"
              maxLength={6}
              autoFocus
            />
          </div>

          <Button type="submit" className="w-full bg-gradient-hero shadow-glow" disabled={loading || timeLeft === 0}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Verifying...
              </>
            ) : (
              "Verify OTP"
            )}
          </Button>

          <div className="text-center">
            <p className="text-sm text-muted-foreground mb-2">
              Didn't receive the code?
            </p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResend}
              disabled={resending || timeLeft > 0}
            >
              {resending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resending...
                </>
              ) : (
                "Resend OTP"
              )}
            </Button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Verify Your Email</DialogTitle>
          <DialogDescription>
            Enter the 6-digit code sent to {email}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleVerify} className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">Verification Code</label>
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                <Clock className="w-4 h-4" />
                {formatTime(timeLeft)}
              </div>
            </div>
            <Input
              type="text"
              placeholder="000000"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="text-center text-2xl tracking-widest"
              maxLength={6}
              autoFocus
            />
          </div>

          <Button type="submit" className="w-full bg-gradient-hero shadow-glow" disabled={loading || timeLeft === 0}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Verifying...
              </>
            ) : (
              "Verify OTP"
            )}
          </Button>

          <div className="text-center">
            <p className="text-sm text-muted-foreground mb-2">
              Didn't receive the code?
            </p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResend}
              disabled={resending || timeLeft > 0}
            >
              {resending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resending...
                </>
              ) : (
                "Resend OTP"
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
