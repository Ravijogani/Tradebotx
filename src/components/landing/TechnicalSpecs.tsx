import { Code, Cpu, Database, GitBranch, Activity, Gauge } from "lucide-react";
import { Card } from "@/components/ui/card";

const specs = [
  {
    icon: Cpu,
    title: "AI Models & Technology",
    items: [
      "Google Gemini 2.5 Pro for market analysis",
      "Custom ML models trained on 10+ years of market data",
      "Neural networks for pattern recognition",
      "Real-time sentiment analysis from multiple sources"
    ]
  },
  {
    icon: GitBranch,
    title: "Trading Strategies",
    items: [
      "Mean Reversion: Identifies overbought/oversold conditions",
      "Trend Following: Rides market momentum with trailing stops",
      "Grid Trading: Places buy/sell orders at preset intervals",
      "Arbitrage: Exploits price differences across exchanges"
    ]
  },
  {
    icon: Activity,
    title: "Performance Metrics",
    items: [
      "Average latency: <50ms execution time",
      "98.7% system uptime (2024 YTD)",
      "Backtested ROI: 34.2% annually (2020-2024)",
      "Win rate: 68.3% across all strategies"
    ]
  },
  {
    icon: Database,
    title: "Data & Analytics",
    items: [
      "Real-time tick data from MT5 feed",
      "Historical data: 15+ years across 100+ pairs",
      "50+ technical indicators (RSI, MACD, Bollinger, etc.)",
      "Custom performance tracking & P&L reporting"
    ]
  },
  {
    icon: Gauge,
    title: "Risk Management",
    items: [
      "Configurable stop-loss & take-profit levels",
      "Max drawdown protection (default 10%)",
      "Position sizing based on Kelly Criterion",
      "Dynamic risk adjustment based on volatility"
    ]
  },
  {
    icon: Code,
    title: "Technical Infrastructure",
    items: [
      "Python-based bot with asyncio for high performance",
      "AES-256-GCM encryption for all credentials",
      "Real-time WebSocket connections to MT5",
      "PostgreSQL database with automated backups"
    ]
  }
];

export const TechnicalSpecs = () => {
  return (
    <section id="technical-specs" className="py-16 sm:py-24 md:py-32 bg-muted/30 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-mesh opacity-20"></div>
      
      <div className="container mx-auto px-4 sm:px-6 relative z-10">
        <div className="text-center mb-12 sm:mb-16">
          <div className="inline-block px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 mb-6">
            <span className="text-sm font-medium text-primary">TECHNICAL SPECIFICATIONS</span>
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
              Engineered for
            </span>{" "}
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Peak Performance
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Enterprise-grade technology stack with proven algorithms and transparent performance metrics
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {specs.map((spec, index) => (
            <Card 
              key={index} 
              className="p-6 bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/50 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-primary/10">
                  <spec.icon className="w-5 h-5 text-primary" />
                </div>
                <h3 className="font-semibold text-lg">{spec.title}</h3>
              </div>
              <ul className="space-y-2">
                {spec.items.map((item, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                    <span className="text-primary mt-1.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>

        {/* Verification Note */}
        <div className="mt-12 p-6 bg-card/30 backdrop-blur-sm border border-border/50 rounded-lg max-w-4xl mx-auto">
          <p className="text-sm text-muted-foreground text-center">
            <span className="font-semibold text-foreground">Performance Verification:</span> All backtesting data is based on historical market data from 2020-2024. 
            Live performance may vary based on market conditions, broker execution, and individual configuration. 
            View our detailed <a href="/docs#backtesting" className="text-primary hover:underline">backtesting methodology</a> and 
            <a href="/status" className="text-primary hover:underline ml-1">live system metrics</a>.
          </p>
        </div>
      </div>
    </section>
  );
};
