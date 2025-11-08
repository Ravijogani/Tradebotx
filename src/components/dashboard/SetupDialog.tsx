import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Loader2 } from "lucide-react";

interface SetupDialogProps {
  open: boolean;
  onComplete: () => void;
}

export const SetupDialog = ({ open, onComplete }: SetupDialogProps) => {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    mt5Account: "",
    mt5Password: "",
    mt5Server: "",
    riskPerTrade: "1.0",
    maxPositions: "3",
  });
  const { toast } = useToast();

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
        is_completed: true,
      });

      if (error) throw error;

      toast({
        title: "Setup completed!",
        description: "Your trading account is now configured.",
      });

      onComplete();
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
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="max-w-2xl" onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>Complete Your Account Setup</DialogTitle>
          <DialogDescription>
            Configure your MT5 trading account to start using AlgoTradeX
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="mt5Account">MT5 Account Number</Label>
              <Input
                id="mt5Account"
                placeholder="12345678"
                value={formData.mt5Account}
                onChange={(e) => setFormData({ ...formData, mt5Account: e.target.value })}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="mt5Server">MT5 Server</Label>
              <Input
                id="mt5Server"
                placeholder="Broker-Live"
                value={formData.mt5Server}
                onChange={(e) => setFormData({ ...formData, mt5Server: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="mt5Password">MT5 Password</Label>
            <Input
              id="mt5Password"
              type="password"
              placeholder="••••••••"
              value={formData.mt5Password}
              onChange={(e) => setFormData({ ...formData, mt5Password: e.target.value })}
              required
            />
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="riskPerTrade">Risk Per Trade (%)</Label>
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
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxPositions">Max Concurrent Positions</Label>
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
          </div>

          <Button type="submit" className="w-full bg-gradient-hero shadow-glow" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Complete Setup"
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
};
