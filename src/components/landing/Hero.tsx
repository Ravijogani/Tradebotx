import { Button } from "@/components/ui/button";
import { ArrowRight, BarChart3, Shield, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import heroImage from "@/assets/hero-trading.jpg";

export const Hero = () => {
  return (
    <section className="relative min-h-screen flex items-center pt-16">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-background to-accent/10" />
      
      <div className="container mx-auto px-4 relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div className="space-y-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent/10 border border-accent/20">
              <Zap className="w-4 h-4 text-accent" />
              <span className="text-sm font-medium">AI-Powered Trading</span>
            </div>

            <h1 className="text-5xl md:text-6xl font-bold leading-tight">
              Automate Your{" "}
              <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                Trading Success
              </span>
            </h1>

            <p className="text-xl text-muted-foreground max-w-xl">
              Advanced algorithmic trading platform for Forex & Crypto. Execute winning strategies 24/7 with proper risk management and real-time analytics.
            </p>

            <div className="flex flex-wrap gap-4">
              <Link to="/pricing">
                <Button size="lg" className="bg-gradient-hero shadow-glow hover:shadow-premium transition-all group">
                  Start Trading Free
                  <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link to="/auth/login">
                <Button size="lg" variant="outline">
                  Sign In
                </Button>
              </Link>
            </div>

            <div className="grid grid-cols-3 gap-6 pt-8">
              {[
                { icon: Shield, label: "Bank-Grade Security", value: "256-bit" },
                { icon: BarChart3, label: "Win Rate", value: "87%" },
                { icon: Zap, label: "Execution Speed", value: "<100ms" },
              ].map((stat, idx) => (
                <div key={idx} className="space-y-2">
                  <stat.icon className="w-8 h-8 text-accent" />
                  <p className="text-2xl font-bold">{stat.value}</p>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="absolute inset-0 bg-gradient-hero rounded-3xl blur-3xl opacity-20" />
            <img
              src={heroImage}
              alt="AlgoTradeX Trading Platform"
              className="relative rounded-3xl shadow-premium border border-border"
            />
          </div>
        </div>
      </div>
    </section>
  );
};
