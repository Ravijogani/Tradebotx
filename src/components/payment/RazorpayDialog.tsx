import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { Loader2 } from "lucide-react";

interface RazorpayDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  planId: string;
  planName: string;
  amount: number;
  userId: string;
}

declare global {
  interface Window {
    Razorpay: any;
  }
}

export const RazorpayDialog = ({ open, onOpenChange, planId, planName, amount, userId }: RazorpayDialogProps) => {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handlePayment = async () => {
    setLoading(true);
    try {
      // Razorpay configuration will be set by user
      const razorpayKeyId = import.meta.env.VITE_RAZORPAY_KEY_ID;
      
      if (!razorpayKeyId) {
        throw new Error('Razorpay is not configured. Please contact support.');
      }

      // Create order on backend
      const { data: orderData, error: orderError } = await supabase.functions.invoke('create-razorpay-order', {
        body: { amount: amount * 100, planId, userId }, // Amount in paise
      });

      if (orderError) throw orderError;

      const options = {
        key: razorpayKeyId,
        amount: orderData.amount,
        currency: 'INR',
        name: 'AlgoTradeX',
        description: `${planName} Plan Subscription`,
        order_id: orderData.id,
        handler: async function (response: any) {
          try {
            // Verify payment on backend
            const { error: verifyError } = await supabase.functions.invoke('verify-razorpay-payment', {
              body: {
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                userId,
                planId,
              },
            });

            if (verifyError) throw verifyError;

            toast({
              title: "Payment Successful!",
              description: "Your subscription has been activated.",
            });

            onOpenChange(false);
            window.location.reload();
          } catch (error: any) {
            toast({
              title: "Payment Verification Failed",
              description: error.message,
              variant: "destructive",
            });
          }
        },
        prefill: {
          email: (await supabase.auth.getUser()).data.user?.email,
        },
        theme: {
          color: '#1e40af',
        },
      };

      const razorpay = new window.Razorpay(options);
      razorpay.open();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upgrade to {planName}</DialogTitle>
          <DialogDescription>
            Complete your payment to activate the {planName} plan and continue trading.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="bg-muted p-6 rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <span className="text-muted-foreground">Plan:</span>
              <span className="font-semibold">{planName}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">Amount:</span>
              <span className="text-2xl font-bold">₹{amount}</span>
            </div>
          </div>

          <Button onClick={handlePayment} className="w-full" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              `Pay ₹${amount}`
            )}
          </Button>

          <p className="text-xs text-center text-muted-foreground">
            Secure payment powered by Razorpay
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
