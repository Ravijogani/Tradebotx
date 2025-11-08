import { useState, useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Crown, Zap, TrendingUp, Check, ArrowRight } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

export const SubscriptionManager = () => {
  const [loading, setLoading] = useState(true);
  const [currentPlan, setCurrentPlan] = useState<any>(null);
  const [allPlans, setAllPlans] = useState<any[]>([]);
  const { toast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Load current subscription
      const { data: subscription, error: subError } = await supabase
        .from("user_subscriptions")
        .select("*, plans(*)")
        .eq("user_id", user.id)
        .single();

      if (subError) throw subError;
      setCurrentPlan(subscription);

      // Load all available plans
      const { data: plans, error: plansError } = await supabase
        .from("plans")
        .select("*")
        .eq("is_active", true)
        .order("price", { ascending: true });

      if (plansError) throw plansError;
      setAllPlans(plans || []);
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

  const handleUpgrade = (planId: string) => {
    navigate(`/pricing?plan=${planId}`);
  };

  const getPlanIcon = (planType: string) => {
    switch (planType) {
      case "free":
        return <Zap className="w-5 h-5" />;
      case "pro":
        return <TrendingUp className="w-5 h-5" />;
      case "enterprise":
        return <Crown className="w-5 h-5" />;
      default:
        return <Zap className="w-5 h-5" />;
    }
  };

  const getPlanColor = (planType: string) => {
    switch (planType) {
      case "free":
        return "default";
      case "pro":
        return "secondary";
      case "enterprise":
        return "default";
      default:
        return "default";
    }
  };

  const isCurrentPlan = (planId: string) => {
    return currentPlan?.plan_id === planId;
  };

  const canUpgrade = (planPrice: number) => {
    return planPrice > (currentPlan?.plans?.price || 0);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Current Plan Overview */}
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {getPlanIcon(currentPlan?.plans?.plan_type)}
            Your Current Plan
          </CardTitle>
          <CardDescription>
            {currentPlan?.plans?.name || "No active plan"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Status</p>
              <Badge variant={currentPlan?.status === "active" ? "default" : "secondary"}>
                {currentPlan?.status || "N/A"}
              </Badge>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Price</p>
              <p className="text-lg font-bold">
                ${currentPlan?.plans?.price || 0}
                <span className="text-sm font-normal text-muted-foreground">/month</span>
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Max Strategies</p>
              <p className="text-lg font-bold">{currentPlan?.plans?.max_strategies || 0}</p>
            </div>
          </div>

          {currentPlan?.trial_ends_at && (
            <Alert className="mt-4">
              <AlertDescription>
                Trial ends on {new Date(currentPlan.trial_ends_at).toLocaleDateString()}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Available Plans */}
      <div>
        <h2 className="text-2xl font-bold mb-4">Upgrade Your Plan</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {allPlans.map((plan) => (
            <Card
              key={plan.id}
              className={`relative ${
                isCurrentPlan(plan.id)
                  ? "border-primary shadow-glow"
                  : "hover:border-primary/50 transition-all"
              }`}
            >
              {isCurrentPlan(plan.id) && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge>Current Plan</Badge>
                </div>
              )}
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  {getPlanIcon(plan.plan_type)}
                  <CardTitle>{plan.name}</CardTitle>
                </div>
                <CardDescription>
                  <span className="text-3xl font-bold text-foreground">
                    ${plan.price}
                  </span>
                  <span className="text-muted-foreground">/month</span>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Check className="w-4 h-4 text-green-500" />
                    <span className="text-sm">
                      Up to {plan.max_strategies} strategies
                    </span>
                  </div>
                  {plan.features && Array.isArray(plan.features) && plan.features.map((feature: string, idx: number) => (
                    <div key={idx} className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      <span className="text-sm">{feature}</span>
                    </div>
                  ))}
                </div>

                {isCurrentPlan(plan.id) ? (
                  <Button disabled className="w-full">
                    Current Plan
                  </Button>
                ) : canUpgrade(plan.price) ? (
                  <Button
                    onClick={() => handleUpgrade(plan.id)}
                    className="w-full gap-2"
                  >
                    Upgrade Now
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                ) : (
                  <Button disabled variant="outline" className="w-full">
                    Not Available
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};