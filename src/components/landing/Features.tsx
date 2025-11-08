import { Bot, TrendingUp, Shield, Zap, LineChart, Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const features = [
  {
    icon: Bot,
    title: "AI-Powered Trading",
    description: "Advanced algorithms analyze market patterns and execute trades with precision, maximizing your profit potential 24/7.",
  },
  {
    icon: TrendingUp,
    title: "Multiple Strategies",
    description: "Choose from proven trading strategies tailored for different market conditions and risk appetites.",
  },
  {
    icon: Shield,
    title: "Risk Management",
    description: "Built-in risk controls with customizable stop-loss, take-profit, and position sizing to protect your capital.",
  },
  {
    icon: Zap,
    title: "Real-Time Execution",
    description: "Lightning-fast trade execution through MT5 integration ensures you never miss an opportunity.",
  },
  {
    icon: LineChart,
    title: "Performance Analytics",
    description: "Comprehensive analytics dashboard showing profit/loss, win rates, and detailed trade history.",
  },
  {
    icon: Clock,
    title: "24/7 Monitoring",
    description: "Our bots work around the clock, monitoring markets and executing trades even while you sleep.",
  },
];

export const Features = () => {
  return (
    <section className="py-24 bg-gradient-to-b from-background to-muted/20">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
            Powerful Features for Serious Traders
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Everything you need to automate your trading and achieve consistent profits
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <Card key={index} className="border-border/50 hover:border-primary/50 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10">
              <CardContent className="p-6">
                <div className="w-14 h-14 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <feature.icon className="w-7 h-7 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-3">{feature.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{feature.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
};
