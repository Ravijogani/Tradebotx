import { Bot, TrendingUp, Shield, Zap, LineChart, Clock, Brain, Lock } from "lucide-react";

const features = [
  {
    icon: Bot,
    title: "AI-Powered Trading",
    description: "Advanced machine learning algorithms analyze market patterns in real-time, adapting to market conditions for optimal trade execution.",
    gradient: "from-blue-500 to-cyan-500",
  },
  {
    icon: Brain,
    title: "Smart Strategies",
    description: "Choose from battle-tested trading strategies optimized by AI, each designed for specific market conditions and risk profiles.",
    gradient: "from-purple-500 to-pink-500",
  },
  {
    icon: Shield,
    title: "Advanced Risk Management",
    description: "Multi-layer protection with dynamic stop-loss, trailing stops, position sizing, and maximum drawdown limits.",
    gradient: "from-emerald-500 to-green-500",
  },
  {
    icon: Zap,
    title: "Lightning Execution",
    description: "Sub-millisecond trade execution through optimized MT5 integration. Never miss a profitable opportunity again.",
    gradient: "from-yellow-500 to-orange-500",
  },
  {
    icon: LineChart,
    title: "Advanced Analytics",
    description: "Real-time performance metrics, AI-powered insights, and predictive analytics to optimize your trading strategy.",
    gradient: "from-indigo-500 to-purple-500",
  },
  {
    icon: Clock,
    title: "24/7 Autonomous Trading",
    description: "Fully automated trading system that never sleeps. Monitor multiple markets simultaneously across all time zones.",
    gradient: "from-rose-500 to-red-500",
  },
  {
    icon: Lock,
    title: "Enterprise Security",
    description: "Bank-grade encryption, secure API integration, and SOC 2 compliance to protect your trading data and credentials.",
    gradient: "from-teal-500 to-cyan-500",
  },
  {
    icon: TrendingUp,
    title: "Performance Optimization",
    description: "Continuous AI learning from market data and trade results to improve strategy performance over time.",
    gradient: "from-violet-500 to-purple-500",
  },
];

export const Features = () => {
  return (
    <section id="features" className="py-32 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-gradient-mesh opacity-30"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/10 rounded-full blur-3xl"></div>
      
      <div className="container mx-auto px-4 relative z-10">
        <div className="text-center mb-20 animate-fade-in-up">
          <div className="inline-block px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 mb-6">
            <span className="text-sm font-medium text-primary">POWERFUL FEATURES</span>
          </div>
          <h2 className="font-display text-5xl md:text-6xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
              Built for
            </span>{" "}
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Professional Traders
            </span>
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Enterprise-grade tools and AI technology designed to give you an unfair advantage in the markets
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <div
              key={index}
              className="group relative animate-fade-in"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              {/* Glassmorphism card */}
              <div className="relative h-full p-6 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50 hover:border-primary/50 transition-all duration-500 hover:shadow-glow group-hover:-translate-y-2">
                {/* Gradient icon container */}
                <div className={`relative w-14 h-14 rounded-xl bg-gradient-to-br ${feature.gradient} p-0.5 mb-5 group-hover:scale-110 transition-transform duration-300`}>
                  <div className="w-full h-full rounded-xl bg-card flex items-center justify-center">
                    <feature.icon className="w-7 h-7 text-foreground" />
                  </div>
                </div>

                {/* Content */}
                <h3 className="font-display text-xl font-semibold mb-3 group-hover:text-primary transition-colors">
                  {feature.title}
                </h3>
                <p className="text-muted-foreground leading-relaxed text-sm">
                  {feature.description}
                </p>

                {/* Hover glow effect */}
                <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-10 transition-opacity duration-500 blur-xl -z-10`}></div>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom CTA */}
        <div className="text-center mt-16 animate-fade-in" style={{ animationDelay: '0.8s' }}>
          <p className="text-muted-foreground mb-4">And many more features to supercharge your trading</p>
          <div className="flex justify-center gap-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="w-2 h-2 rounded-full bg-primary/30"></div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
