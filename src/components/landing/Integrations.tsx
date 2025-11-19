import { Building2, Link as LinkIcon, CheckCircle2, ArrowRight } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const brokers = [
  {
    name: "MetaTrader 5",
    type: "Forex & Crypto",
    status: "Fully Supported",
    features: ["Real-time data feed", "Trade execution", "Position management", "Order types: Market, Limit, Stop"]
  },
  {
    name: "XM",
    type: "Forex Broker",
    status: "Recommended",
    features: ["Low spreads", "Fast execution", "MT5 compatible", "Multiple account types"]
  },
  {
    name: "Pepperstone",
    type: "Forex Broker",
    status: "Recommended",
    features: ["Fast execution", "MT5 integration", "Multiple asset classes", "Competitive spreads"]
  },
  {
    name: "Vantage",
    type: "Forex Broker",
    status: "Compatible",
    features: ["MT5 support", "Crypto trading", "Fast execution", "Competitive spreads"]
  }
];

const connectionSteps = [
  "Get your MT5 account from any supported broker",
  "Generate API credentials (login, password, server)",
  "Enter credentials in TradeBotX setup wizard",
  "Our bot securely connects via encrypted WebSocket",
  "Start trading with one click - no code required"
];

export const Integrations = () => {
  return (
    <section id="integrations" className="py-16 sm:py-24 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-mesh opacity-20"></div>
      
      <div className="container mx-auto px-4 sm:px-6 relative z-10">
        <div className="text-center mb-12 sm:mb-16">
          <div className="inline-block px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 mb-6">
            <span className="text-sm font-medium text-primary">BROKER COMPATIBILITY</span>
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
              Works with Your
            </span>{" "}
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Favorite Brokers
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Our bot works exclusively with MetaTrader 5. All forex brokers that support MT5 are automatically compatible - no special requirements or complicated setup needed.
          </p>
        </div>

        {/* Broker Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          {brokers.map((broker, index) => (
            <Card key={index} className="p-6 bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/50 transition-all">
              <div className="flex items-start justify-between mb-4">
                <Building2 className="w-8 h-8 text-primary" />
                <span className="text-xs px-2 py-1 rounded-full bg-success/10 text-success border border-success/20">
                  {broker.status}
                </span>
              </div>
              <h3 className="font-semibold text-lg mb-1">{broker.name}</h3>
              <p className="text-sm text-muted-foreground mb-4">{broker.type}</p>
              <ul className="space-y-2">
                {broker.features.map((feature, i) => (
                  <li key={i} className="text-xs text-muted-foreground flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-primary flex-shrink-0 mt-0.5" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>

        {/* Connection Process */}
        <div className="max-w-4xl mx-auto">
          <Card className="p-8 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm border-border/50">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 rounded-lg bg-primary/10">
                <LinkIcon className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-2xl font-bold">How to Connect Your Broker</h3>
            </div>
            
            <div className="space-y-4 mb-8">
              {connectionSteps.map((step, index) => (
                <div key={index} className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                    <span className="text-sm font-bold text-primary">{index + 1}</span>
                  </div>
                  <p className="text-muted-foreground pt-1">{step}</p>
                </div>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
              <Button asChild className="flex-1">
                <a href="/docs#setup-guide">
                  View Setup Guide <ArrowRight className="w-4 h-4 ml-2" />
                </a>
              </Button>
              <Button asChild variant="outline" className="flex-1">
                <a href="https://t.me/tradebotxsupport" target="_blank" rel="noopener noreferrer">
                  Get Setup Help
                </a>
              </Button>
            </div>
          </Card>
        </div>

        {/* Security Note */}
        <div className="mt-12 p-4 bg-muted/50 border border-border/50 rounded-lg max-w-4xl mx-auto">
          <p className="text-sm text-muted-foreground text-center">
            <span className="font-semibold text-foreground">Security First:</span> Your MT5 credentials are encrypted with AES-256-GCM and stored securely. 
            We never have access to withdraw your funds - we only place trades on your behalf.
          </p>
        </div>
      </div>
    </section>
  );
};
