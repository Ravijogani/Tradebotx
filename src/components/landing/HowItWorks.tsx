import { UserPlus, Settings, Play, TrendingUp } from "lucide-react";

const steps = [
  {
    icon: UserPlus,
    title: "Sign Up & Choose Plan",
    description: "Create your account and select a plan that fits your trading goals. Start with our free plan or try Pro/Enterprise with a trial period.",
  },
  {
    icon: Settings,
    title: "Configure MT5 Account",
    description: "Connect your MetaTrader 5 account securely. Set your risk parameters, position limits, and trading preferences.",
  },
  {
    icon: Play,
    title: "Select & Start Strategy",
    description: "Choose from our tested strategies based on your plan. Click start and let the AI bot begin trading on your behalf.",
  },
  {
    icon: TrendingUp,
    title: "Monitor & Profit",
    description: "Watch your trades in real-time on the dashboard. Track performance, profits, and let the bot optimize your trading.",
  },
];

export const HowItWorks = () => {
  return (
    <section id="how-it-works" className="py-16 sm:py-20 md:py-24 bg-muted/30">
      <div className="container mx-auto px-4 sm:px-6">
        <div className="text-center mb-12 sm:mb-16">
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold mb-3 sm:mb-4 px-4">
            How TradeBotX Works
          </h2>
          <p className="text-base sm:text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto px-4">
            Get started in minutes with our simple 4-step process
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
          {steps.map((step, index) => (
            <div key={index} className="relative">
              <div className="text-center">
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center mx-auto mb-3 sm:mb-4 shadow-lg shadow-primary/20">
                  <step.icon className="w-8 h-8 sm:w-10 sm:h-10 text-primary-foreground" />
                </div>
                <div className="absolute top-8 sm:top-10 left-1/2 w-full h-0.5 bg-gradient-to-r from-primary/50 to-accent/50 -z-10 hidden lg:block last:hidden" />
                <div className="bg-background/80 backdrop-blur-sm rounded-lg p-4 sm:p-6 border border-border/50">
                  <div className="text-xs sm:text-sm font-bold text-primary mb-2">STEP {index + 1}</div>
                  <h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3">{step.title}</h3>
                  <p className="text-sm sm:text-base text-muted-foreground">{step.description}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
