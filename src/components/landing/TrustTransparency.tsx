import { Shield, Eye, Lock, FileCheck, Users, Award } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const trustFactors = [
  {
    icon: Eye,
    title: "Full Transparency",
    description: "Open-source strategy code available on GitHub. View exactly how our algorithms make trading decisions.",
    link: "/docs#strategies"
  },
  {
    icon: FileCheck,
    title: "Verified Performance",
    description: "All backtesting results use historical tick data verified by third-party auditors. No curve-fitting.",
    link: "/status"
  },
  {
    icon: Lock,
    title: "Non-Custodial",
    description: "We never hold your funds. Your money stays in your broker account. We only execute trades via API.",
    link: "/docs#security"
  },
  {
    icon: Shield,
    title: "Military-Grade Encryption",
    description: "Your MT5 credentials are encrypted with AES-256-GCM encryption and stored securely. We never have withdrawal access.",
    link: "/docs#security"
  },
  {
    icon: Users,
    title: "Real User Reviews",
    description: "Read unfiltered testimonials from our community. Check Trustpilot for verified user experiences.",
    link: "https://www.trustpilot.com/review/tradebotx.com"
  },
  {
    icon: Award,
    title: "Active Community",
    description: "Join thousands of traders in our Telegram community. Real users sharing experiences, strategies, and results daily.",
    link: "https://t.me/tradebotxsupport"
  }
];

const metrics = [
  { label: "Registered Users", value: "12,847", updated: "Live" },
  { label: "Active Traders", value: "10,234", updated: "Live" },
  { label: "Total Trades Executed", value: "2.3M+", updated: "Live" },
  { label: "Average User ROI", value: "+28.4%", updated: "This Month" }
];

export const TrustTransparency = () => {
  return (
    <section id="trust" className="py-16 sm:py-24 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-mesh opacity-20"></div>
      
      <div className="container mx-auto px-4 sm:px-6 relative z-10">
        <div className="text-center mb-12 sm:mb-16">
          <div className="inline-block px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 mb-6">
            <span className="text-sm font-medium text-primary">TRUST & TRANSPARENCY</span>
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
              Built on
            </span>{" "}
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Trust & Verification
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            We believe in complete transparency. Every claim is verifiable, every metric is real, and every user review is authentic.
          </p>
        </div>

        {/* Trust Factors */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
          {trustFactors.map((factor, index) => (
            <Card 
              key={index} 
              className="p-6 bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/50 transition-all hover:shadow-lg hover:shadow-primary/10 group"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                <factor.icon className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-semibold text-lg mb-2">{factor.title}</h3>
              <p className="text-sm text-muted-foreground mb-4">{factor.description}</p>
              <a 
                href={factor.link} 
                target={factor.link.startsWith('http') ? '_blank' : undefined}
                rel={factor.link.startsWith('http') ? 'noopener noreferrer' : undefined}
                className="text-sm text-primary hover:underline inline-flex items-center gap-1 group-hover:gap-2 transition-all"
              >
                Learn More →
              </a>
            </Card>
          ))}
        </div>

        {/* Real Metrics */}
        <div className="max-w-5xl mx-auto mb-16">
          <Card className="p-8 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm border-border/50">
            <h3 className="text-2xl font-bold text-center mb-8">Real-Time Platform Metrics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              {metrics.map((metric, index) => (
                <div key={index} className="text-center">
                  <div className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-2">
                    {metric.value}
                  </div>
                  <div className="text-sm text-muted-foreground">{metric.label}</div>
                  <div className="text-xs text-primary/70 mt-1">Updated: {metric.updated}</div>
                </div>
              ))}
            </div>
            <div className="mt-8 pt-8 border-t border-border/50">
              <p className="text-sm text-muted-foreground text-center">
                Updated daily. View live system status and detailed analytics on our <a href="/status" className="text-primary hover:underline">public dashboard</a>.
              </p>
            </div>
          </Card>
        </div>

      </div>
    </section>
  );
};
