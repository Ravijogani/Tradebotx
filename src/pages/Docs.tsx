import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Book, Rocket, Settings, BarChart, Shield, HelpCircle } from "lucide-react";
import { Link } from "react-router-dom";

const Docs = () => {
  const sections = [
    {
      icon: Rocket,
      title: "Getting Started",
      description: "Quick start guide to set up your account and activate your first trading strategy",
      items: [
        "Create your account",
        "Connect your MT5 trading account",
        "Configure risk parameters",
        "Activate your first strategy",
      ],
    },
    {
      icon: Settings,
      title: "Account Setup",
      description: "Configure your trading account and risk management settings",
      items: [
        "MT5 Account Connection",
        "Risk per trade settings",
        "Maximum positions limit",
        "Stop loss configuration",
      ],
    },
    {
      icon: BarChart,
      title: "Trading Strategies",
      description: "Understanding and selecting the right trading strategies for your goals",
      items: [
        "Strategy overview",
        "Performance metrics",
        "Starting and stopping strategies",
        "Strategy combination tips",
      ],
    },
    {
      icon: Shield,
      title: "Security & Risk",
      description: "Best practices for secure trading and risk management",
      items: [
        "Account security",
        "Two-factor authentication",
        "Risk management principles",
        "Position sizing guidelines",
      ],
    },
  ];

  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="container mx-auto px-4 py-24">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
              Documentation
            </h1>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Everything you need to know to get started with TradeBotX automated trading
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6 mb-12">
            {sections.map((section, index) => (
              <Card key={index} className="hover:shadow-glow transition-all duration-300">
                <CardHeader>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
                      <section.icon className="w-6 h-6 text-white" />
                    </div>
                    <CardTitle className="text-2xl">{section.title}</CardTitle>
                  </div>
                  <p className="text-muted-foreground">{section.description}</p>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {section.items.map((item, itemIndex) => (
                      <li key={itemIndex} className="flex items-center gap-2 text-muted-foreground">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="text-3xl font-bold flex items-center gap-3">
                <Book className="w-8 h-8 text-primary" />
                Quick Start Guide
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="text-xl font-semibold mb-3">Step 1: Create Your Account</h3>
                <p className="text-muted-foreground">
                  Sign up for TradeBotX by choosing a pricing plan that fits your needs. Start with our free trial 
                  to explore the platform risk-free.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3">Step 2: Connect MT5 Account</h3>
                <p className="text-muted-foreground">
                  Connect your MetaTrader 5 trading account by providing your account credentials. Our platform 
                  securely stores and encrypts this information.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3">Step 3: Configure Risk Settings</h3>
                <p className="text-muted-foreground">
                  Set your risk parameters including risk per trade (recommended 1-2%), maximum open positions, 
                  and other safety limits to protect your capital.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3">Step 4: Select Trading Strategy</h3>
                <p className="text-muted-foreground">
                  Browse available trading strategies based on your subscription plan. Review performance metrics 
                  and select strategies that align with your trading goals.
                </p>
              </div>

              <div>
                <h3 className="text-xl font-semibold mb-3">Step 5: Activate & Monitor</h3>
                <p className="text-muted-foreground">
                  Activate your chosen strategies and monitor their performance through your dashboard. You can 
                  start or stop strategies at any time.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="text-3xl font-bold">FAQ</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h4 className="font-semibold mb-2">What is TradeBotX?</h4>
                <p className="text-muted-foreground">
                  TradeBotX is an automated trading platform that uses AI and machine learning algorithms to execute
                  trades on your behalf in forex and cryptocurrency markets.
                </p>
              </div>

              <div>
                <h4 className="font-semibold mb-2">Do I need trading experience?</h4>
                <p className="text-muted-foreground">
                  While trading experience is helpful, TradeBotX is designed to be user-friendly for traders of all 
                  levels. However, we recommend understanding basic trading concepts and risks.
                </p>
              </div>

              <div>
                <h4 className="font-semibold mb-2">How much capital do I need?</h4>
                <p className="text-muted-foreground">
                  The minimum capital depends on your broker's requirements, but we recommend starting with at least 
                  $500-$1000 to properly manage risk with our strategies.
                </p>
              </div>

              <div>
                <h4 className="font-semibold mb-2">Can I stop a strategy anytime?</h4>
                <p className="text-muted-foreground">
                  Yes, you have full control to start or stop any strategy at any time through your dashboard.
                </p>
              </div>

              <div>
                <h4 className="font-semibold mb-2">What if I need help?</h4>
                <p className="text-muted-foreground">
                  Our support team is available 24/7 via Telegram at <a href="https://t.me/tradebotxsupport" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">@tradebotxsupport</a>. We also have extensive 
                  documentation and video tutorials available.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-r from-primary/10 to-accent/10 border-primary/20">
            <CardContent className="py-8 text-center">
              <HelpCircle className="w-16 h-16 mx-auto mb-4 text-primary" />
              <h3 className="text-2xl font-bold mb-3">Need More Help?</h3>
              <p className="text-muted-foreground mb-6">
                Can't find what you're looking for? Our support team is here to help!
              </p>
              <div className="flex justify-center gap-4">
                <a
                  href="https://t.me/tradebotxsupport"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-6 py-3 bg-gradient-to-r from-primary to-accent text-white rounded-lg font-semibold hover:shadow-glow transition-all"
                >
                  Contact Support
                </a>
                <Link
                  to="/#faq"
                  className="px-6 py-3 bg-background border border-border rounded-lg font-semibold hover:bg-muted transition-all"
                >
                  View FAQ
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Docs;
