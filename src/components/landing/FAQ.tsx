import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const faqs = [
  {
    question: "What is TradeBotX?",
    answer: "TradeBotX is an advanced automated trading platform that uses AI-powered algorithms to execute trades on your behalf in forex and crypto markets. Our bots work 24/7, analyzing market conditions and executing trades based on proven strategies.",
  },
  {
    question: "How does the trading bot work?",
    answer: "Once you connect your MT5 account and select a strategy, our Python-based trading bot continuously monitors the market, identifies opportunities based on technical indicators and AI analysis, and executes trades automatically with proper risk management. We use a combination of mean reversion, trend following, grid trading, and arbitrage strategies.",
  },
  {
    question: "Is my trading account safe?",
    answer: "Yes. We never hold your funds. The bot connects to your MT5 account using read-only API credentials for market data and trading permissions. Your funds remain in your broker account at all times. We use AES-256-GCM encryption for all data transmission and are SOC 2 Type II compliant.",
  },
  {
    question: "What brokers are supported?",
    answer: "TradeBotX works with any MetaTrader 5 (MT5) compatible broker. We recommend IC Markets, Pepperstone, and FBS for best execution speeds and low spreads. You can trade forex pairs, crypto CFDs, and other instruments supported by your broker.",
  },
  {
    question: "What AI models do you use?",
    answer: "We use Google Gemini 2.5 Pro for market analysis and custom machine learning models trained on 10+ years of historical market data. Our neural networks identify patterns, perform sentiment analysis from multiple sources, and make real-time trading decisions.",
  },
  {
    question: "Can I see the backtesting results?",
    answer: "Yes. All our strategies have been backtested on historical data from 2020-2024. Average annual ROI is 34.2% with a 68.3% win rate across all strategies. View detailed performance metrics on our Status page and read our backtesting methodology in the documentation.",
  },
  {
    question: "Can I customize risk parameters?",
    answer: "Absolutely! You have full control over risk management settings including risk per trade (default 1-2%), maximum positions, stop-loss levels, and take-profit targets. Our system uses Kelly Criterion for position sizing and enforces max drawdown protection (default 10%).",
  },
  {
    question: "How do I get support?",
    answer: "We offer multiple support channels: 24/7 Telegram community support, email support (24-48h response), comprehensive documentation with setup guides, and priority support for Pro & Enterprise users (4h response time). Emergency bot issues can be reported via Telegram.",
  },
  {
    question: "What happens after my trial ends?",
    answer: "You'll receive email notifications before your 7-day trial expires. After expiration, you'll need to upgrade to a paid plan to continue using the trading bots. Your data and settings are preserved, and you can upgrade anytime through our secure payment gateway.",
  },
  {
    question: "Do I need trading experience?",
    answer: "No prior trading experience is required. Our strategies are pre-configured and tested. However, we recommend understanding basic trading concepts and starting with the free trial to familiarize yourself with the platform. We provide an AI onboarding assistant to guide you through setup.",
  },
  {
    question: "Can I stop the bot anytime?",
    answer: "Yes, you have complete control. You can start, stop, or switch strategies at any time from your dashboard. The bot will immediately halt all trading activity when stopped. For emergency situations, use the emergency stop button to close all positions immediately.",
  },
  {
    question: "How is TradeBotX different from other bots?",
    answer: "We focus on transparency and verifiable results. Our strategy code is open-source on GitHub, performance metrics are publicly available, and all backtesting uses verified historical data. We're non-custodial (never hold your funds), and provide 24/7 support with an active community.",
  },
];

export const FAQ = () => {
  return (
    <section className="py-24 bg-background">
      <div className="container mx-auto px-4 max-w-4xl">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4">
            Frequently Asked Questions
          </h2>
          <p className="text-xl text-muted-foreground">
            Everything you need to know about TradeBotX
          </p>
        </div>

        <Accordion type="single" collapsible className="space-y-4">
          {faqs.map((faq, index) => (
            <AccordionItem key={index} value={`item-${index}`} className="border border-border/50 rounded-lg px-6">
              <AccordionTrigger className="text-left hover:text-primary">
                {faq.question}
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground leading-relaxed">
                {faq.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
};
