import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2, CheckCircle, TrendingUp } from "lucide-react";

interface SetupDialogProps {
  open: boolean;
  onComplete: () => void;
}

export const SetupDialog = ({ open, onComplete }: SetupDialogProps) => {
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);
  const [formData, setFormData] = useState({
    mt5Account: "",
    mt5Password: "",
    mt5Server: "",
    riskPerTrade: "1.0",
    maxPositions: "3",
    accountSize: "10000",
    telegramChatId: "",
  });
  const { toast } = useToast();

  const handleStep1Continue = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.mt5Account || !formData.mt5Password || !formData.mt5Server) {
      toast({
        title: "Error",
        description: "Please fill in all MT5 account details",
        variant: "destructive",
      });
      return;
    }

    setStep(2);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const { data: { user } } = await supabase.auth.getUser();
      
      if (!user) throw new Error("Not authenticated");

      const { error } = await supabase.from("user_setup").upsert({
        user_id: user.id,
        mt5_account: formData.mt5Account,
        mt5_password: formData.mt5Password,
        mt5_server: formData.mt5Server,
        risk_per_trade: parseFloat(formData.riskPerTrade),
        max_positions: parseInt(formData.maxPositions),
        account_size: parseFloat(formData.accountSize),
        telegram_chat_id: formData.telegramChatId || null,
        is_completed: true,
      });

      if (error) throw error;

      toast({
        title: "Setup Complete!",
        description: "Your account is now ready. Reloading...",
      });

      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (error: any) {
      toast({
        title: "Setup Failed",
        description: error.message || "Failed to complete setup. Please try again.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="max-w-2xl" onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-lg bg-gradient-hero flex items-center justify-center shadow-glow">
              <TrendingUp className="w-6 h-6 text-primary-foreground" />
            </div>
            <DialogTitle>
              Complete Your Account Setup
            </DialogTitle>
          </div>
          <DialogDescription>
            {step === 1 
              ? "Configure your MT5 trading account details" 
              : "Set your trading preferences and optional integrations"}
          </DialogDescription>
        </DialogHeader>

        {/* Progress Indicator */}
        <div className="flex items-center gap-2 mb-4">
          <div className={`flex-1 h-2 rounded-full transition-colors ${step >= 1 ? 'bg-primary' : 'bg-muted'}`} />
          <div className={`flex-1 h-2 rounded-full transition-colors ${step >= 2 ? 'bg-primary' : 'bg-muted'}`} />
        </div>

        {step === 1 ? (
          <form onSubmit={handleStep1Continue} className="space-y-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-primary" />
                MT5 Account Details
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="mt5Account">MT5 Account Number *</Label>
                  <Input
                    id="mt5Account"
                    value={formData.mt5Account}
                    onChange={(e) => setFormData({ ...formData, mt5Account: e.target.value })}
                    placeholder="123456789"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mt5Password">MT5 Password *</Label>
                  <Input
                    id="mt5Password"
                    type="password"
                    value={formData.mt5Password}
                    onChange={(e) => setFormData({ ...formData, mt5Password: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="mt5Server">MT5 Server *</Label>
                  <Input
                    id="mt5Server"
                    value={formData.mt5Server}
                    onChange={(e) => setFormData({ ...formData, mt5Server: e.target.value })}
                    placeholder="e.g., ICMarkets-Demo01"
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Find this in your MT5 platform under Tools → Options → Server
                  </p>
                </div>
              </div>
            </div>

            <Button type="submit" className="w-full bg-gradient-hero shadow-glow">
              Continue to Trading Preferences
            </Button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-primary" />
                Trading Preferences
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="accountSize">Account Size ($) *</Label>
                  <Input
                    id="accountSize"
                    type="number"
                    min="100"
                    step="100"
                    value={formData.accountSize}
                    onChange={(e) => setFormData({ ...formData, accountSize: e.target.value })}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Your current trading account balance
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="riskPerTrade">Risk per Trade (%) *</Label>
                  <Input
                    id="riskPerTrade"
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="10"
                    value={formData.riskPerTrade}
                    onChange={(e) => setFormData({ ...formData, riskPerTrade: e.target.value })}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    Recommended: 1-2% for conservative trading
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="maxPositions">Max Concurrent Positions *</Label>
                  <Input
                    id="maxPositions"
                    type="number"
                    min="1"
                    max="10"
                    value={formData.maxPositions}
                    onChange={(e) => setFormData({ ...formData, maxPositions: e.target.value })}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="telegramChatId">Telegram Chat ID (Optional)</Label>
                  <Input
                    id="telegramChatId"
                    value={formData.telegramChatId}
                    onChange={(e) => setFormData({ ...formData, telegramChatId: e.target.value })}
                    placeholder="123456789"
                  />
                  <p className="text-xs text-muted-foreground">
                    Get notified about trades on Telegram
                  </p>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => setStep(1)}
                className="flex-1"
              >
                Back
              </Button>
              <Button 
                type="submit" 
                className="flex-1 bg-gradient-hero shadow-glow" 
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Complete Setup"
                )}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};
