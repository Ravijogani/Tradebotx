import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { BookOpen, Code, Zap, Settings } from "lucide-react";
import { Link } from "react-router-dom";

const Docs = () => {
  const sections = [
    {
      icon: BookOpen,
      title: "Getting Started",
      description: "Learn the basics of AlgoTradeX and set up your first trading strategy",
      items: [
        "Create an account and choose your plan",
        "Connect your MT5 trading account",
        "Configure risk management settings",
        "Select and activate your first strategy",
      ],
    },
    {
      icon: Settings,
      title: "Configuration",
      description: "Detailed guide on configuring your trading parameters",
      items: [
        "MT5 account setup and connection",
        "Risk per trade and position sizing",
        "Maximum concurrent positions",
        "Stop-loss and take-profit settings",
      ],
    },
    {
      icon: Zap,
      title: "Trading Strategies",
      description: "Understand available strategies and how to use them effectively",
      items: [
        "Strategy selection based on your plan",
        "Understanding strategy performance metrics",
        "Starting and stopping strategies",
        "Monitoring real-time trade execution",
      ],
    },
    {
      icon: Code,
      title: "Advanced Features",
      description: "Explore advanced platform capabilities",
      items: [
        "Custom strategy parameters",
        "Performance analytics and reporting",
        "API integration (coming soon)",
        "Webhook notifications",
      ],
    },
  ];

  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="pt-32 pb-24">
        <div className="container mx-auto px-4 max-w-6xl">
          <div className="text-center mb-16">
            <h1 className="font-display text-5xl font-bold mb-4 bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
              Documentation
            </h1>
            <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
              Everything you need to know to start automated trading with AlgoTradeX
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6 mb-16">
            {sections.map((section, index) => (
              <div
                key={index}
                className="p-6 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50 hover:border-primary/50 transition-all duration-300 hover:shadow-glow"
              >
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-primary to-accent p-0.5 mb-4">
                  <div className="w-full h-full rounded-xl bg-card flex items-center justify-center">
                    <section.icon className="w-7 h-7 text-foreground" />
                  </div>
                </div>
                <h3 className="text-2xl font-bold text-foreground mb-2">{section.title}</h3>
                <p className="text-muted-foreground mb-4">{section.description}</p>
                <ul className="space-y-2">
                  {section.items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary mt-2 flex-shrink-0"></div>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Quick Start Guide */}
          <div className="p-8 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50 mb-8">
            <h2 className="text-3xl font-bold text-foreground mb-6">Quick Start Guide</h2>
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold text-foreground mb-3 flex items-center gap-2">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">1</span>
                  Sign Up and Select Plan
                </h3>
                <p className="text-muted-foreground ml-10">
                  Visit our <Link to="/pricing" className="text-primary hover:underline">pricing page</Link> and select a plan that fits your trading needs. 
                  Free and trial options available.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold text-foreground mb-3 flex items-center gap-2">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">2</span>
                  Complete Account Setup
                </h3>
                <p className="text-muted-foreground ml-10">
                  After logging in, you'll be prompted to complete your setup:
                </p>
                <ul className="list-disc ml-16 mt-2 space-y-1 text-muted-foreground">
                  <li>Enter your MT5 account credentials (account number, password, server)</li>
                  <li>Set risk parameters (risk per trade: 1-5%)</li>
                  <li>Configure maximum concurrent positions (1-10)</li>
                </ul>
              </div>

              <div>
                <h3 className="text-xl font-semibold text-foreground mb-3 flex items-center gap-2">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">3</span>
                  Select and Start Strategy
                </h3>
                <p className="text-muted-foreground ml-10">
                  Choose from available strategies based on your plan. Click "Start" to begin automated trading. 
                  The bot will connect to your MT5 account and start executing trades according to the selected strategy.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold text-foreground mb-3 flex items-center gap-2">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">4</span>
                  Monitor Performance
                </h3>
                <p className="text-muted-foreground ml-10">
                  View real-time trades, profit/loss, win rate, and performance metrics on your dashboard. 
                  You can stop the strategy at any time.
                </p>
              </div>
            </div>
          </div>

          {/* FAQ */}
          <div className="p-8 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50">
            <h2 className="text-3xl font-bold text-foreground mb-6">Frequently Asked Questions</h2>
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-foreground mb-2">Is my MT5 account safe?</h4>
                <p className="text-muted-foreground">
                  Yes. We use bank-grade encryption to store your credentials. We only have trading permissions, never withdrawal access.
                </p>
              </div>
              <div>
                <h4 className="font-semibold text-foreground mb-2">Can I stop trading anytime?</h4>
                <p className="text-muted-foreground">
                  Absolutely. You have full control and can start/stop strategies from your dashboard at any time.
                </p>
              </div>
              <div>
                <h4 className="font-semibold text-foreground mb-2">What happens if I lose internet connection?</h4>
                <p className="text-muted-foreground">
                  Our bots run on our cloud servers, not your computer. Your strategies continue running even if you're offline.
                </p>
              </div>
              <div>
                <h4 className="font-semibold text-foreground mb-2">How do I change my risk settings?</h4>
                <p className="text-muted-foreground">
                  Stop all strategies first, then access the setup dialog from your dashboard settings to modify parameters.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-12 text-center">
            <p className="text-muted-foreground mb-4">Need more help?</p>
            <a href="mailto:support@algotradex.com" className="text-primary hover:underline font-medium">
              Contact our support team
            </a>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Docs;
