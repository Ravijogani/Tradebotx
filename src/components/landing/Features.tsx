import { Bot, TrendingUp, Shield, Zap, LineChart, Clock, Brain, Lock } from "lucide-react";

const features = [
  {
    icon: Bot,
    title: "Automated Trading Bots",
    description: "Multiple concurrent trading bots with MT5 integration. Start/stop control, real-time monitoring, and encrypted credential storage.",
    gradient: "from-blue-500 to-cyan-500",
  },
  {
    icon: Brain,
    title: "AI-Powered Insights",
    description: "Get AI-generated trading insights, performance analysis, and an intelligent onboarding assistant to guide your setup.",
    gradient: "from-purple-500 to-pink-500",
  },
  {
    icon: Shield,
    title: "Advanced Risk Management",
    description: "Configurable risk per trade, max positions, account size management, and automated position monitoring with stop-loss protection.",
    gradient: "from-emerald-500 to-green-500",
  },
  {
    icon: Zap,
    title: "Real-time Notifications",
    description: "Instant email and Telegram alerts for trade executions, bot status changes, setup approvals, and critical events.",
    gradient: "from-yellow-500 to-orange-500",
  },
  {
    icon: LineChart,
    title: "Advanced Analytics",
    description: "Comprehensive performance tracking, P&L reports, trade journal, strategy performance metrics, and exportable data (CSV/PDF).",
    gradient: "from-indigo-500 to-purple-500",
  },
  {
    icon: Clock,
    title: "24/7 Trade Monitoring",
    description: "Continuous position tracking, automated execution, and real-time updates. Track open positions, closed trades, and performance metrics.",
    gradient: "from-rose-500 to-red-500",
  },
  {
    icon: Lock,
    title: "Enterprise Security",
    description: "AES-256-GCM encryption for MT5 credentials, secure payment processing with Razorpay, and comprehensive audit logging.",
    gradient: "from-teal-500 to-cyan-500",
  },
  {
    icon: TrendingUp,
    title: "Admin & Support Tools",
    description: "User approval workflows, support ticket system, invoice generation, referral program management, and comprehensive admin dashboard.",
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
