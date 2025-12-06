import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { DashboardLayout } from "@/components/dashboard/DashboardLayout";
import { StrategyBuilder } from "@/components/strategy-builder/StrategyBuilder";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Crown, Lock } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const StrategyBuilderPage = () => {
  const [loading, setLoading] = useState(true);
  const [hasAccess, setHasAccess] = useState(false);
  const [planType, setPlanType] = useState<string | null>(null);
  const navigate = useNavigate();
  const { toast } = useToast();

  useEffect(() => {
    checkAccess();
  }, []);

  const checkAccess = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        navigate("/login");
        return;
      }

      // Check subscription plan
      const { data: subscription } = await supabase
        .from("user_subscriptions")
        .select("*, plans(*)")
        .eq("user_id", user.id)
        .single();

      const userPlanType = (subscription?.plans as any)?.plan_type;
      setPlanType(userPlanType);

      // Enterprise users only
      if (userPlanType === "enterprise") {
        setHasAccess(true);
      }
    } catch (error: any) {
      toast({
        title: "Error checking access",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[600px]">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </DashboardLayout>
    );
  }

  if (!hasAccess) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-[600px]">
          <Card className="max-w-md">
            <CardHeader className="text-center">
              <div className="mx-auto h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <Crown className="h-8 w-8 text-primary" />
              </div>
              <CardTitle>Enterprise Feature</CardTitle>
              <CardDescription>
                Custom Strategy Development is available exclusively for Enterprise plan subscribers
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-center gap-2">
                <Badge variant="secondary">{planType || "Free"} Plan</Badge>
                <Lock className="h-4 w-4 text-muted-foreground" />
              </div>
              <div className="space-y-2 text-sm text-muted-foreground">
                <p>With Enterprise, you get:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Visual drag-drop strategy builder</li>
                  <li>Custom indicator combinations</li>
                  <li>Personal strategy approval</li>
                  <li>Unlimited strategy templates</li>
                </ul>
              </div>
              <Button 
                className="w-full" 
                onClick={() => navigate("/pricing")}
              >
                Upgrade to Enterprise
              </Button>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-6rem)]">
        <StrategyBuilder />
      </div>
    </DashboardLayout>
  );
};

export default StrategyBuilderPage;