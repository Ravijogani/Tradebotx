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
    answer: "Once you connect your MT5 account and select a strategy, our Python-based trading bot continuously monitors the market, identifies opportunities based on technical indicators and AI analysis, and executes trades automatically with proper risk management.",
  },
  {
    question: "Is my trading account safe?",
    answer: "Yes. We never hold your funds. The bot connects to your MT5 account using read-only API credentials for market data and trading permissions. Your funds remain in your broker account at all times. We use bank-level encryption for all data transmission.",
  },
  {
    question: "What markets can I trade?",
    answer: "TradeBotX supports both forex and cryptocurrency trading through MetaTrader 5 integration. You can trade major forex pairs, crypto pairs, and other instruments supported by your MT5 broker.",
  },
  {
    question: "Can I customize risk parameters?",
    answer: "Absolutely! You have full control over risk management settings including risk per trade, maximum positions, stop-loss levels, and take-profit targets. Our system enforces these limits to protect your capital.",
  },
  {
    question: "What happens after my trial ends?",
    answer: "You'll receive email notifications before your trial expires. After expiration, you'll need to upgrade to a paid plan to continue using the trading bots. You can easily upgrade through our secure payment gateway.",
  },
  {
    question: "Do I need trading experience?",
    answer: "No prior trading experience is required. Our strategies are pre-configured and tested. However, we recommend understanding basic trading concepts and starting with the free plan to familiarize yourself with the platform.",
  },
  {
    question: "Can I stop the bot anytime?",
    answer: "Yes, you have complete control. You can start, stop, or switch strategies at any time from your dashboard. The bot will immediately halt all trading activity when stopped.",
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
