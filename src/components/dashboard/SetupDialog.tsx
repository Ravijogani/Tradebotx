import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { ExternalLink, Info, CheckCircle2, AlertCircle, Loader2, TrendingUp } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface SetupDialogProps {
  open: boolean;
  onComplete: () => void;
}

interface BrokerOption {
  name: string;
  referralLink: string;
  referralCode: string;
  description: string;
}

const BROKERS: BrokerOption[] = [
  {
    name: "XM",
    referralLink: "https://www.xm.com/register?ib=YOUR_XM_IB_CODE",
    referralCode: "XM-IB-12345",
    description: "Regulated global broker with tight spreads"
  },
  {
    name: "Vantage",
    referralLink: "https://www.vantagemarkets.com/register?ib=YOUR_VANTAGE_IB_CODE",
    referralCode: "VNTG-IB-67890",
    description: "Low latency execution with deep liquidity"
  },
  {
    name: "PepperStone",
    referralLink: "https://www.pepperstone.com/register?ib=YOUR_PEPPER_IB_CODE",
    referralCode: "PPST-IB-24680",
    description: "Award-winning platform with excellent support"
  }
];

export const SetupDialog = ({ open, onComplete }: SetupDialogProps) => {
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(1);
  const [planType, setPlanType] = useState<'free' | 'paid'>('free');
  const [selectedBroker, setSelectedBroker] = useState<BrokerOption | null>(null);
  const [formData, setFormData] = useState({
    brokerAccountId: "",
    mt5Account: "",
    mt5Password: "",
    mt5Server: "",
    accountSize: "10000",
    riskPerTrade: "1",
    maxPositions: "3",
    telegramChatId: ""
  });

  useEffect(() => {
    const checkPlanType = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data: subscription } = await supabase
        .from('user_subscriptions')
        .select('plan_id, plans(plan_type)')
        .eq('user_id', user.id)
        .single();

      if (subscription?.plans) {
        const type = (subscription.plans as any).plan_type;
        setPlanType(type === 'free' || type === 'starter' ? 'free' : 'paid');
      }
    };

    if (open) {
      checkPlanType();
    }
  }, [open]);

  const totalSteps = planType === 'free' ? 3 : 2;

  const handleBrokerSelect = (broker: BrokerOption) => {
    setSelectedBroker(broker);
  };

  const handleBrokerStep = () => {
    if (!selectedBroker) {
      toast.error("Please select a broker");
      return;
    }
    if (!formData.brokerAccountId.trim()) {
      toast.error("Please enter your broker account ID");
      return;
    }
    setStep(2);
  };

  const handleMT5Step = () => {
    if (!formData.mt5Account.trim() || !formData.mt5Password.trim() || !formData.mt5Server.trim()) {
      toast.error("Please fill in all MT5 details");
      return;
    }
    setStep(planType === 'free' ? 3 : 2);
  };

  const handleSubmit = async () => {
    if (!formData.accountSize || !formData.riskPerTrade) {
      toast.error("Please fill in all required fields");
      return;
    }

    setLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const updateData: any = {
        mt5_account: formData.mt5Account,
        mt5_password: formData.mt5Password,
        mt5_server: formData.mt5Server,
        account_size: parseFloat(formData.accountSize),
        risk_per_trade: parseFloat(formData.riskPerTrade),
        max_positions: parseInt(formData.maxPositions),
        telegram_chat_id: formData.telegramChatId || null,
        is_completed: true,
        submitted_for_approval_at: new Date().toISOString()
      };

      if (planType === 'free' && selectedBroker) {
        updateData.broker_name = selectedBroker.name;
        updateData.broker_account_id = formData.brokerAccountId;
        updateData.broker_referral_code = selectedBroker.referralCode;
        updateData.admin_approved = false;
      } else {
        updateData.admin_approved = true; // Auto-approve paid users
      }

      const { error } = await supabase
        .from('user_setup')
        .update(updateData)
        .eq('user_id', user.id);

      if (error) throw error;

      toast.success(
        planType === 'free' 
          ? "Setup submitted! Waiting for admin approval to activate your account."
          : "Setup completed successfully!"
      );
      
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (error) {
      console.error("Setup error:", error);
      toast.error("Failed to complete setup");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-lg bg-gradient-hero flex items-center justify-center shadow-glow">
              <TrendingUp className="w-6 h-6 text-primary-foreground" />
            </div>
            <DialogTitle className="text-2xl">Account Setup</DialogTitle>
          </div>
          <DialogDescription>
            Complete your account setup to start automated trading
          </DialogDescription>
          <div className="flex items-center gap-2 mt-4">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <div
                key={i}
                className={`h-2 flex-1 rounded-full transition-colors ${
                  i + 1 <= step ? 'bg-primary' : 'bg-muted'
                }`}
              />
            ))}
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Step {step} of {totalSteps}
          </p>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Step 1: Broker Account (Free/Starter users only) */}
          {planType === 'free' && step === 1 && (
            <div className="space-y-4">
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  To use TradeBotX with a free plan, you need to open a trading account with one of our partner brokers using our referral link.
                </AlertDescription>
              </Alert>

              <div>
                <Label className="text-base font-semibold mb-3 block">Select Your Broker</Label>
                <div className="grid gap-3">
                  {BROKERS.map((broker) => (
                    <div
                      key={broker.name}
                      className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
                        selectedBroker?.name === broker.name
                          ? 'border-primary bg-primary/5'
                          : 'border-border hover:border-primary/50'
                      }`}
                      onClick={() => handleBrokerSelect(broker)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="font-semibold text-lg">{broker.name}</h3>
                          <p className="text-sm text-muted-foreground">{broker.description}</p>
                        </div>
                        {selectedBroker?.name === broker.name && (
                          <CheckCircle2 className="h-5 w-5 text-primary flex-shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-3">
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {broker.referralCode}
                        </code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            window.open(broker.referralLink, '_blank');
                          }}
                        >
                          Open Account <ExternalLink className="ml-1 h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {selectedBroker && (
                <div className="space-y-3 p-4 bg-muted/50 rounded-lg">
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      <strong>Important:</strong> After creating your account with {selectedBroker.name}, copy your account ID and paste it below.
                    </AlertDescription>
                  </Alert>
                  
                  <div>
                    <Label htmlFor="brokerAccountId">
                      {selectedBroker.name} Account ID *
                    </Label>
                    <Input
                      id="brokerAccountId"
                      value={formData.brokerAccountId}
                      onChange={(e) => setFormData({ ...formData, brokerAccountId: e.target.value })}
                      placeholder="Enter your broker account ID"
                      className="mt-1.5"
                    />
                    <p className="text-xs text-muted-foreground mt-1.5">
                      This will be verified by our admin before activation
                    </p>
                  </div>
                </div>
              )}

              <Button 
                onClick={handleBrokerStep} 
                className="w-full bg-gradient-hero shadow-glow"
                disabled={!selectedBroker || !formData.brokerAccountId.trim()}
              >
                Continue to MT5 Setup
              </Button>
            </div>
          )}

          {/* Step 2: MT5 Configuration */}
          {((planType === 'free' && step === 2) || (planType === 'paid' && step === 1)) && (
            <div className="space-y-4">
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Connect your MetaTrader 5 account. Your credentials are encrypted and stored securely.
                </AlertDescription>
              </Alert>

              <div>
                <Label htmlFor="mt5Account">MT5 Account Number *</Label>
                <Input
                  id="mt5Account"
                  value={formData.mt5Account}
                  onChange={(e) => setFormData({ ...formData, mt5Account: e.target.value })}
                  placeholder="e.g., 12345678"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Find this in your MT5 platform under Tools → Options
                </p>
              </div>

              <div>
                <Label htmlFor="mt5Password">MT5 Password *</Label>
                <Input
                  id="mt5Password"
                  type="password"
                  value={formData.mt5Password}
                  onChange={(e) => setFormData({ ...formData, mt5Password: e.target.value })}
                  placeholder="Your MT5 password"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  We recommend using a read-only investor password for security
                </p>
              </div>

              <div>
                <Label htmlFor="mt5Server">MT5 Server *</Label>
                <Input
                  id="mt5Server"
                  value={formData.mt5Server}
                  onChange={(e) => setFormData({ ...formData, mt5Server: e.target.value })}
                  placeholder="e.g., BrokerName-Demo or BrokerName-Live"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Server address shown in MT5 under Tools → Options → Server
                </p>
              </div>

              <div className="flex gap-3">
                {planType === 'free' && (
                  <Button variant="outline" onClick={() => setStep(1)} className="flex-1">
                    Back
                  </Button>
                )}
                <Button onClick={handleMT5Step} className="flex-1 bg-gradient-hero shadow-glow">
                  Continue to Preferences
                </Button>
              </div>
            </div>
          )}

          {/* Step 3: Trading Preferences */}
          {((planType === 'free' && step === 3) || (planType === 'paid' && step === 2)) && (
            <div className="space-y-4">
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Configure your trading parameters. These can be adjusted later from settings.
                </AlertDescription>
              </Alert>

              <div>
                <Label htmlFor="accountSize">Account Size (USD) *</Label>
                <Input
                  id="accountSize"
                  type="number"
                  value={formData.accountSize}
                  onChange={(e) => setFormData({ ...formData, accountSize: e.target.value })}
                  placeholder="10000"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Your trading account balance in USD
                </p>
              </div>

              <div>
                <Label htmlFor="riskPerTrade">Risk Per Trade (%) *</Label>
                <Input
                  id="riskPerTrade"
                  type="number"
                  step="0.1"
                  value={formData.riskPerTrade}
                  onChange={(e) => setFormData({ ...formData, riskPerTrade: e.target.value })}
                  placeholder="1.0"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Recommended: 1-2% per trade. Lower risk = safer trading
                </p>
              </div>

              <div>
                <Label htmlFor="maxPositions">Maximum Simultaneous Positions *</Label>
                <Input
                  id="maxPositions"
                  type="number"
                  value={formData.maxPositions}
                  onChange={(e) => setFormData({ ...formData, maxPositions: e.target.value })}
                  placeholder="3"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  How many trades can run at the same time
                </p>
              </div>

              <div>
                <Label htmlFor="telegramChatId">Telegram Chat ID (Optional)</Label>
                <Input
                  id="telegramChatId"
                  value={formData.telegramChatId}
                  onChange={(e) => setFormData({ ...formData, telegramChatId: e.target.value })}
                  placeholder="Get notifications on Telegram"
                  className="mt-1.5"
                />
                <p className="text-xs text-muted-foreground mt-1.5">
                  Receive trade alerts on Telegram. Leave empty to skip.
                </p>
              </div>

              <div className="flex gap-3">
                <Button 
                  variant="outline" 
                  onClick={() => setStep(planType === 'free' ? 2 : 1)} 
                  className="flex-1"
                >
                  Back
                </Button>
                <Button 
                  onClick={handleSubmit} 
                  disabled={loading} 
                  className="flex-1 bg-gradient-hero shadow-glow"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    "Complete Setup"
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};