import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { toast } from "sonner";
import { ExternalLink, Info, CheckCircle2, AlertCircle, Loader2, TrendingUp } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { z } from "zod";
import { OnboardingAssistant } from "./OnboardingAssistant";
import type { Tables } from "@/integrations/supabase/types";

interface SetupDialogProps {
  open: boolean;
  onComplete: () => void;
}

// Payload sent to the encrypt-password edge function, which stashes the
// password separately and writes the rest straight into user_setup.
type SetupPayload = Pick<
  Tables<"user_setup">,
  "mt5_account" | "mt5_server" | "account_size" | "risk_per_trade" | "max_positions" | "telegram_chat_id" | "admin_approved"
> & Partial<Pick<Tables<"user_setup">, "broker_name" | "broker_account_id" | "broker_referral_code">>;

interface BrokerOption {
  name: string;
  referralLink: string;
  referralCode: string;
  description: string;
}

const BROKERS: BrokerOption[] = [
  {
    name: "XM",
    referralLink: "https://affs.click/yjD1p",
    referralCode: "94BT2",
    description: "Regulated global broker with tight spreads"
  },
  {
    name: "Vantage",
    referralLink: "https://vigco.co/la-com/vVdfb27A",
    referralCode: "vVdfb27A",
    description: "Low latency execution with deep liquidity"
  },
  {
    name: "PepperStone",
    referralLink: "https://trk.pepperstonepartners.com/aff_c?offer_id=367&aff_id=40761",
    referralCode: "",
    description: "Award-winning platform with excellent support"
  }
];

// Zod validation schema for secure input validation
const setupSchema = z.object({
  mt5Account: z.string()
    .regex(/^\d{5,20}$/, 'MT5 account must be 5-20 digits'),
  mt5Password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .max(100, 'Password too long'),
  mt5Server: z.string()
    .regex(/^[a-zA-Z0-9.-]+$/, 'Invalid server format (alphanumeric, dots, and hyphens only)')
    .min(3, 'Server name too short')
    .max(100, 'Server name too long'),
  brokerAccountId: z.string()
    .regex(/^[a-zA-Z0-9-]+$/, 'Invalid account ID format (alphanumeric and hyphens only)')
    .min(3, 'Account ID too short')
    .max(50, 'Account ID too long')
    .optional(),
  accountSize: z.number()
    .min(100, 'Account size must be at least $100')
    .max(10000000, 'Account size too large'),
  riskPerTrade: z.number()
    .min(0.1, 'Risk must be at least 0.1%')
    .max(10, 'Risk cannot exceed 10%'),
  maxPositions: z.number()
    .int('Must be a whole number')
    .min(1, 'At least 1 position required')
    .max(20, 'Maximum 20 positions allowed'),
  telegramChatId: z.string().optional()
});

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
        // 'starter' was checked here too, but the plan_type enum only ever
        // has free/pro/enterprise — that branch was dead.
        const type = (subscription.plans as Pick<Tables<"plans">, "plan_type">).plan_type;
        setPlanType(type === 'free' ? 'free' : 'paid');
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
    // For free plan: step 1 (broker) -> step 2 (MT5) -> step 3 (prefs)
    // For paid plan: step 1 (MT5) -> step 2 (prefs)
    setStep(planType === 'free' ? 3 : 2);
  };

  const handleSubmit = async () => {
    if (!formData.accountSize || !formData.riskPerTrade) {
      toast.error("Please fill in all required fields");
      return;
    }

    // Validate all inputs using zod schema
    try {
      const validationData = {
        mt5Account: formData.mt5Account.trim(),
        mt5Password: formData.mt5Password,
        mt5Server: formData.mt5Server.trim(),
        brokerAccountId: planType === 'free' ? formData.brokerAccountId.trim() : undefined,
        accountSize: parseFloat(formData.accountSize),
        riskPerTrade: parseFloat(formData.riskPerTrade),
        maxPositions: parseInt(formData.maxPositions),
        telegramChatId: formData.telegramChatId.trim() || undefined
      };

      setupSchema.parse(validationData);
    } catch (error) {
      if (error instanceof z.ZodError) {
        const firstError = error.issues[0];
        toast.error(firstError.message);
        return;
      }
      toast.error("Invalid input. Please check your data.");
      return;
    }

    setLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      // Prepare setup data (without password)
      const setupData: SetupPayload = {
        mt5_account: formData.mt5Account.trim(),
        mt5_server: formData.mt5Server.trim(),
        account_size: parseFloat(formData.accountSize),
        risk_per_trade: parseFloat(formData.riskPerTrade),
        max_positions: parseInt(formData.maxPositions),
        telegram_chat_id: formData.telegramChatId.trim() || null,
        admin_approved: false
      };

      if (planType === 'free' && selectedBroker) {
        setupData.broker_name = selectedBroker.name;
        setupData.broker_account_id = formData.brokerAccountId.trim();
        setupData.broker_referral_code = selectedBroker.referralCode;
      }
      
      // Call edge function to encrypt password and save setup
      const { data, error } = await supabase.functions.invoke('encrypt-password', {
        body: {
          password: formData.mt5Password,
          setupData
        }
      });

      if (error) throw error;

      toast.success("Setup submitted! Waiting for admin approval to activate your account.");
      
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
    <>
      <OnboardingAssistant 
        context={{
          currentStep: `Step ${step} of ${totalSteps}`,
          fieldName: step === 1 ? 'Broker Selection' : step === 2 ? 'MT5 Configuration' : 'Trading Preferences'
        }}
      />
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
                        {broker.referralCode && (
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            Code: {broker.referralCode}
                          </code>
                        )}
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
                      <strong>Important:</strong> After creating your account with {selectedBroker.name}{selectedBroker.referralCode && ` using partner code ${selectedBroker.referralCode}`}, copy your account ID/number and paste it below.
                    </AlertDescription>
                  </Alert>
                  
                  <div>
                    <Label htmlFor="brokerAccountId">
                      {selectedBroker.name} Account ID / Account Number *
                    </Label>
                    <Input
                      id="brokerAccountId"
                      value={formData.brokerAccountId}
                      onChange={(e) => setFormData({ ...formData, brokerAccountId: e.target.value })}
                      placeholder="e.g., 12345678"
                      className="mt-1.5"
                    />
                    <p className="text-xs text-muted-foreground mt-1.5">
                      Enter the account ID/number from your newly created {selectedBroker.name} account. This will be verified by our admin.
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
                <div className="mt-2 p-3 bg-muted/50 rounded-lg border border-border">
                  <p className="text-xs font-medium mb-1 flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    How to find your MT5 Account Number:
                  </p>
                  <ol className="text-xs text-muted-foreground space-y-1 ml-4 list-decimal">
                    <li>Open your MetaTrader 5 platform</li>
                    <li>Click on <strong>Tools</strong> in the top menu</li>
                    <li>Select <strong>Options</strong></li>
                    <li>Look for your account number (usually 5-20 digits)</li>
                  </ol>
                </div>
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
                <div className="mt-2 p-3 bg-muted/50 rounded-lg border border-border">
                  <p className="text-xs font-medium mb-1 flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    Security Recommendation:
                  </p>
                  <p className="text-xs text-muted-foreground mb-2">
                    <strong>Use an Investor Password (Read-Only)</strong> instead of your main password for maximum security.
                  </p>
                  <ol className="text-xs text-muted-foreground space-y-1 ml-4 list-decimal">
                    <li>In MT5, go to <strong>Tools → Options → Server</strong></li>
                    <li>Click on <strong>Change</strong> next to "Investor Password"</li>
                    <li>Set a new investor password (read-only access)</li>
                    <li>Use that password here instead of your main password</li>
                  </ol>
                  <p className="text-xs text-muted-foreground mt-2">
                    ℹ️ Investor passwords allow the bot to view and place trades but cannot withdraw funds.
                  </p>
                </div>
              </div>

              <div>
                <Label htmlFor="mt5Server">MT5 Server *</Label>
                <Input
                  id="mt5Server"
                  value={formData.mt5Server}
                  onChange={(e) => setFormData({ ...formData, mt5Server: e.target.value })}
                  placeholder="e.g., XM-Demo, XM-Real, Vantage-Live"
                  className="mt-1.5"
                />
                <div className="mt-2 p-3 bg-muted/50 rounded-lg border border-border">
                  <p className="text-xs font-medium mb-1 flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    How to find your MT5 Server:
                  </p>
                  <ol className="text-xs text-muted-foreground space-y-1 ml-4 list-decimal">
                    <li>Open MetaTrader 5</li>
                    <li>Go to <strong>Tools → Options</strong></li>
                    <li>Click on the <strong>Server</strong> tab</li>
                    <li>Copy the server name exactly as shown (e.g., "XM-Demo" or "Vantage-Live")</li>
                  </ol>
                </div>
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
                  Enter your current trading account balance in US Dollars. This helps calculate position sizes. Minimum: $100
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
                <div className="mt-2 p-3 bg-muted/50 rounded-lg border border-border">
                  <p className="text-xs text-muted-foreground">
                    <strong>Risk per trade</strong> determines how much of your account you're willing to risk on each trade.
                  </p>
                  <div className="text-xs text-muted-foreground mt-2 space-y-1">
                    <div>• <strong>1-2%:</strong> Conservative (Recommended for beginners)</div>
                    <div>• <strong>3-5%:</strong> Moderate risk</div>
                    <div>• <strong>Above 5%:</strong> Aggressive (Not recommended)</div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    💡 Lower risk = slower growth but better account protection
                  </p>
                </div>
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
                  Maximum number of trades that can run at the same time. Recommended: 3-5 positions. Range: 1-20
                </p>
              </div>

              <div>
                <Label htmlFor="telegramChatId">Telegram Chat ID (Optional)</Label>
                <Input
                  id="telegramChatId"
                  value={formData.telegramChatId}
                  onChange={(e) => setFormData({ ...formData, telegramChatId: e.target.value })}
                  placeholder="e.g., 123456789"
                  className="mt-1.5"
                />
                <div className="mt-2 p-3 bg-muted/50 rounded-lg border border-border">
                  <p className="text-xs font-medium mb-1 flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    How to get your Telegram Chat ID:
                  </p>
                  <ol className="text-xs text-muted-foreground space-y-1.5 ml-4 list-decimal">
                    <li>Open Telegram app</li>
                    <li>Search for <strong>@userinfobot</strong></li>
                    <li>Start a chat and type <strong>/start</strong></li>
                    <li>The bot will reply with your Chat ID</li>
                    <li>Copy the ID and paste it here</li>
                  </ol>
                  <p className="text-xs text-muted-foreground mt-2">
                    📱 You'll receive instant notifications when trades open or close. Leave empty to skip.
                  </p>
                </div>
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
    </>
  );
};