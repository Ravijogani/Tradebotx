import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Check } from "lucide-react";
import { Link } from "react-router-dom";

const plans = [
  {
    name: "Free Plan",
    price: 0,
    period: "forever",
    description: "Perfect for beginners to explore algo trading",
    features: [
      "1 Trading Strategy",
      "Partner Brokers Only (XM, Vantage, PepperStone)",
      "MT5 Integration with Encrypted Credentials",
      "Email & Telegram Notifications",
      "AI-Powered Onboarding Assistant",
      "Basic Performance Analytics",
      "Trade Journal & P&L Reports",
      "Real-time Trade Tracking",
      "Community Support",
    ],
    cta: "Get Started Free",
    popular: false,
  },
  {
    name: "Pro Plan",
    price: 99,
    period: "month",
    description: "For serious traders scaling their portfolio",
    features: [
      "5 Trading Strategies (Multiple Concurrent Bots)",
      "Any MT5 Broker Supported",
      "Advanced Risk Management Tools",
      "AI-Generated Trading Insights",
      "Priority Email & Telegram Alerts",
      "Advanced Analytics Dashboard",
      "Detailed Trade History & Reports",
      "Export Data (CSV/PDF)",
      "Referral Program Access",
      "Priority Support Tickets",
      "Real-time Position Monitoring",
    ],
    cta: "Start 7-Day Free Trial",
    popular: true,
  },
  {
    name: "Enterprise",
    price: 299,
    period: "month",
    description: "Maximum power for professional traders",
    features: [
      "Unlimited Trading Strategies",
      "Multi-Account Management",
      "Custom Strategy Development",
      "Dedicated Admin Dashboard Access",
      "Advanced Bot Monitoring & Control",
      "Custom Email Templates",
      "Invoice Generation & Payment Tracking",
      "User Role Management",
      "Platform Settings Control",
      "24/7 Dedicated Support",
      "Dedicated Account Manager",
      "Advanced Audit Logging",
      "System Health Monitoring",
    ],
    cta: "Start 7-Day Free Trial",
    popular: false,
  },
];

export const PricingSection = () => {
  return (
    <section className="py-16 sm:py-20 md:py-24 bg-muted/30">
      <div className="container mx-auto px-4 sm:px-6">
        <div className="text-center max-w-3xl mx-auto mb-12 sm:mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-3 sm:mb-4 px-4">
            Choose Your Trading Plan
          </h2>
          <p className="text-base sm:text-lg md:text-xl text-muted-foreground px-4">
            Start free forever or try premium features with our risk-free trials. No credit card required.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8 max-w-7xl mx-auto">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              className={`relative p-8 ${
                plan.popular
                  ? "border-accent shadow-glow scale-105"
                  : "border-border"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-accent text-accent-foreground px-4 py-1 rounded-full text-sm font-semibold">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="space-y-6">
                <div>
                  <h3 className="text-2xl font-bold mb-2">{plan.name}</h3>
                  <p className="text-muted-foreground text-sm">{plan.description}</p>
                </div>

                <div className="flex items-baseline gap-1">
                  <span className="text-5xl font-bold">${plan.price}</span>
                  <span className="text-muted-foreground">/{plan.period}</span>
                </div>

                <Link to={`/pricing?plan=${plan.name.toLowerCase().replace(' ', '-')}`}>
                  <Button
                    className={`w-full ${
                      plan.popular
                        ? "bg-gradient-hero shadow-glow hover:shadow-premium"
                        : ""
                    }`}
                    variant={plan.popular ? "default" : "outline"}
                    size="lg"
                  >
                    {plan.cta}
                  </Button>
                </Link>

                <div className="space-y-3 pt-6">
                  {plan.features.map((feature) => (
                    <div key={feature} className="flex items-start gap-3">
                      <Check className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
                      <span className="text-sm">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};
