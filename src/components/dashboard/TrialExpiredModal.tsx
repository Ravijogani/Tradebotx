import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertTriangle, Lock } from "lucide-react";
import { RazorpayDialog } from "@/components/payment/RazorpayDialog";
import { supabase } from "@/integrations/supabase/client";

export function TrialExpiredModal() {
  const [showPayment, setShowPayment] = useState(false);
  const [isTrialExpired, setIsTrialExpired] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    checkTrialStatus();
  }, []);

  const checkTrialStatus = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    
    setUserId(user.id);

    const { data: subscription } = await supabase
      .from("user_subscriptions")
      .select("status, trial_ends_at")
      .eq("user_id", user.id)
      .maybeSingle();

    const trialExpired = subscription?.status === 'expired';
    setIsTrialExpired(trialExpired);
  };

  if (!isTrialExpired) {
    return null;
  }

  if (showPayment && userId) {
    return (
      <RazorpayDialog
        open={true}
        onOpenChange={(open) => {
          // Don't allow closing the payment modal when trial expired
          if (!open && isTrialExpired) {
            return;
          }
          setShowPayment(open);
        }}
        planId="pro_plan"
        planName="Pro"
        amount={99}
        userId={userId}
      />
    );
  }

  return (
    <Dialog open={true} modal>
      <DialogContent 
        className="max-w-md" 
        data-testid="dialog-trial-expired"
        // Prevent closing
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <div className="flex items-center gap-2 text-destructive mb-2">
            <AlertTriangle className="h-6 w-6" />
            <DialogTitle data-testid="text-trial-expired-title">
              Free Trial Expired
            </DialogTitle>
          </div>
          <DialogDescription data-testid="text-trial-expired-description">
            Your 7-day free trial of TradeBotX has ended. Upgrade to continue using 
            our AI-powered trading platform.
          </DialogDescription>
        </DialogHeader>

        <Card className="p-6 bg-muted/50 border-destructive/20" data-testid="card-trial-info">
          <div className="flex items-start gap-3">
            <Lock className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="space-y-2">
              <p className="text-sm font-medium">
                What happens now?
              </p>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                <li>All trading bots have been stopped</li>
                <li>Dashboard access is limited</li>
                <li>New trades cannot be executed</li>
                <li>Your data and settings are safe</li>
              </ul>
            </div>
          </div>
        </Card>

        <div className="space-y-3">
          <Button
            className="w-full"
            onClick={() => setShowPayment(true)}
            data-testid="button-upgrade-now"
          >
            Upgrade to Pro - $99/month
          </Button>

          <Button
            variant="outline"
            className="w-full"
            onClick={async () => {
              await fetch('/api/custom-auth/logout', { method: 'POST' });
              window.location.href = '/';
            }}
            data-testid="button-logout-trial-expired"
          >
            Logout
          </Button>
        </div>

        <p className="text-xs text-center text-muted-foreground">
          Questions? Contact us on Telegram: <a href="https://t.me/tradebotxsupport" className="text-primary hover:underline">@tradebotxsupport</a>
        </p>
      </DialogContent>
    </Dialog>
  );
}
