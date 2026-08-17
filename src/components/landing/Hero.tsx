import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { TrendingUp, Zap, Shield, ArrowRight } from "lucide-react";
import heroImage from "@/assets/hero-trading.jpg";
import { supabase } from "@/integrations/supabase/client";

export const Hero = () => {
  const [stats, setStats] = useState({
    userCount: 0,
    tradingVolume: 0,
    tradesExecuted: 0,
  });

  useEffect(() => {
    const loadStats = async () => {
      try {
        // Get user count
        const { count: userCount } = await supabase
          .from("profiles")
          .select("*", { count: "exact", head: true });

        // Get trades count and volume
        const { data: trades } = await supabase
          .from("trades")
          .select("quantity, entry_price");

        const tradesExecuted = trades?.length || 0;
        const tradingVolume = trades?.reduce((sum, t) => 
          sum + (parseFloat(String(t.quantity)) * parseFloat(String(t.entry_price))), 0) || 0;

        setStats({
          userCount: userCount || 0,
          tradingVolume,
          tradesExecuted,
        });
      } catch (error) {
        console.error("Error loading stats:", error);
      }
    };

    loadStats();
  }, []);

  const formatNumber = (num: number): string => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M+`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K+`;
    return num.toString();
  };

  const formatCurrency = (num: number): string => {
    if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M+`;
    if (num >= 1000) return `$${(num / 1000).toFixed(0)}K+`;
    return `$${num.toFixed(0)}`;
  };

  return (
    <section className="relative min-h-[100dvh] flex items-center justify-center overflow-hidden py-safe">
      {/* Animated background gradient mesh */}
      <div className="absolute inset-0 bg-gradient-mesh opacity-50 animate-float"></div>
      
      {/* Background Image with overlay */}
      <div 
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `url(${heroImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-background/95 via-background/85 to-background"></div>
      </div>

      {/* Floating particles effect */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-64 h-64 sm:w-96 sm:h-96 bg-primary/20 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 sm:w-96 sm:h-96 bg-accent/20 rounded-full blur-3xl animate-float" style={{ animationDelay: '1.5s' }}></div>
      </div>

      {/* Content */}
      <div className="container mx-auto container-padding py-8 sm:py-12 md:py-16 lg:py-20 relative z-10">
        <div className="max-w-5xl mx-auto text-center space-y-4 sm:space-y-6">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 animate-fade-in touch-target">
            <Zap className="w-4 h-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              Next-Gen AI Trading Platform
            </span>
          </div>

          {/* Main heading */}
          <h1 className="font-display text-responsive-xl font-bold leading-[1.1] sm:leading-tight animate-fade-in-up">
            <span className="bg-gradient-to-r from-foreground via-foreground to-foreground/80 bg-clip-text text-transparent block">
              Trade Smarter with
            </span>
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent animate-glow-pulse block mt-1 sm:mt-2">
              AI Precision
            </span>
          </h1>

          {/* Subheading */}
          <p className="text-responsive-base text-muted-foreground/90 max-w-3xl mx-auto leading-relaxed animate-fade-in" style={{ animationDelay: '0.2s' }}>
            Harness the power of advanced algorithms and machine learning to automate your forex and crypto trading. 
            <span className="text-foreground font-semibold"> Maximize profits while minimizing risk.</span>
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap justify-center gap-2 sm:gap-3 animate-fade-in" style={{ animationDelay: '0.3s' }}>
            <div className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-card/50 backdrop-blur-sm border border-border touch-target">
              <TrendingUp className="w-4 h-4 text-success flex-shrink-0" />
              <span className="text-xs sm:text-sm whitespace-nowrap">98.7% Uptime</span>
            </div>
            <div className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-card/50 backdrop-blur-sm border border-border touch-target">
              <Shield className="w-4 h-4 text-primary flex-shrink-0" />
              <span className="text-xs sm:text-sm whitespace-nowrap">Bank-Grade Security</span>
            </div>
            <div className="flex items-center gap-2 px-3 sm:px-4 py-2 rounded-full bg-card/50 backdrop-blur-sm border border-border touch-target">
              <Zap className="w-4 h-4 text-accent flex-shrink-0" />
              <span className="text-xs sm:text-sm whitespace-nowrap">Real-Time Execution</span>
            </div>
          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center animate-fade-in pt-2" style={{ animationDelay: '0.4s' }}>
            <Button asChild size="lg" className="text-base sm:text-lg group relative overflow-hidden bg-gradient-to-r from-primary to-accent hover:shadow-glow transition-all duration-300 w-full sm:w-auto touch-target">
              <Link to="/auth/login?signup=true" className="relative z-10">
                Start 7-Day Free Trial
                <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="text-base sm:text-lg border-primary/30 hover:bg-primary/10 hover:border-primary/50 backdrop-blur-sm transition-all duration-300 w-full sm:w-auto touch-target">
              <Link to="/docs#setup-guide">
                View Setup Guide
              </Link>
            </Button>
          </div>

          {/* Trust indicators -- real platform numbers, or none at all.
              These fell back to invented figures ("500+" users, "$100K+"
              volume, "1K+" trades) whenever the real query returned zero,
              so a brand-new deployment advertised traction it did not have.
              A quieter section is better than a fabricated one. */}
          {(stats.userCount > 0 || stats.tradingVolume > 0 || stats.tradesExecuted > 0) && (
            <div className="pt-8 sm:pt-12 border-t border-border/50 animate-fade-in" style={{ animationDelay: '0.5s' }}>
              <p className="text-xs sm:text-sm text-muted-foreground/80 mb-4">No credit card required</p>
              <div className="grid grid-cols-3 gap-4 sm:gap-6 md:gap-8 text-center">
                <div>
                  <div className="text-xl sm:text-2xl md:text-3xl font-bold text-foreground">
                    {formatNumber(stats.userCount)}
                  </div>
                  <div className="text-muted-foreground/80 text-[10px] sm:text-xs mt-1">Registered Users</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl md:text-3xl font-bold text-foreground">
                    {formatCurrency(stats.tradingVolume)}
                  </div>
                  <div className="text-muted-foreground/80 text-[10px] sm:text-xs mt-1">Trading Volume</div>
                </div>
                <div>
                  <div className="text-xl sm:text-2xl md:text-3xl font-bold text-foreground">
                    {formatNumber(stats.tradesExecuted)}
                  </div>
                  <div className="text-muted-foreground/80 text-[10px] sm:text-xs mt-1">Trades Executed</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
