import { Navbar } from "@/components/landing/Navbar";
import { PricingSection } from "@/components/landing/PricingSection";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { SignupDialog } from "@/components/auth/SignupDialog";

const Pricing = () => {
  const [searchParams] = useSearchParams();
  const [showSignup, setShowSignup] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string>("");

  useEffect(() => {
    const plan = searchParams.get("plan");
    if (plan) {
      setSelectedPlan(plan);
      setShowSignup(true);
    }
  }, [searchParams]);

  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="pt-24">
        <PricingSection />
      </div>

      <SignupDialog 
        open={showSignup} 
        onOpenChange={setShowSignup}
        planName={selectedPlan}
      />
    </div>
  );
};

export default Pricing;
