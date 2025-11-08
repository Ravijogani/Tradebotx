import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { HelpCircle } from "lucide-react";

export const FAQ = () => {
  const faqs = [
    {
      question: "How do I start trading with a bot?",
      answer: "First, complete your one-time setup by providing your MT5 credentials and broker details. Once approved by admin, you can select a strategy from the available options based on your subscription plan and click 'Start' to activate the bot."
    },
    {
      question: "Can I run multiple strategies simultaneously?",
      answer: "Yes, you can run multiple strategies depending on your subscription plan. Starter plan allows 1 strategy, Pro plan allows 3 strategies, and Enterprise plan allows unlimited strategies running simultaneously."
    },
    {
      question: "How do I stop a running bot?",
      answer: "Simply navigate to the Strategies section in your dashboard and click the 'Stop' button next to the running strategy. The bot will safely close all positions before stopping."
    },
    {
      question: "What are the risk parameters?",
      answer: "Risk parameters include account size, risk per trade (%), and maximum positions. These settings determine how much capital the bot can use and how many trades it can execute simultaneously. You can configure these during setup."
    },
    {
      question: "How do I track my performance?",
      answer: "Your dashboard displays real-time performance metrics including total P&L, win rate, and trade history. You can also view detailed analytics in the P&L Reports section and export data for further analysis."
    },
    {
      question: "What brokers are supported?",
      answer: "We support all MT5-compatible brokers. During setup, you'll need to provide your broker name, account ID, and MT5 credentials. Check with admin for a list of tested and recommended brokers."
    },
    {
      question: "How do I get support?",
      answer: "You can create a support ticket from the Support section in your dashboard. Our team will respond to your queries and you can track the conversation thread. For urgent issues, mark the priority as 'Urgent'."
    },
    {
      question: "Can I modify my trading parameters after setup?",
      answer: "Yes, you can update your risk parameters and Telegram settings from the User Settings section. However, broker credentials changes require admin approval."
    },
    {
      question: "How do referrals work?",
      answer: "Generate your unique referral code from the Referral Program section. Share it with friends - when they sign up using your code, you'll earn rewards. Track your referral earnings in the dashboard."
    },
    {
      question: "What payment methods are accepted?",
      answer: "We accept payments through Razorpay, which supports credit/debit cards, UPI, net banking, and wallets. All transactions are secure and you'll receive invoices via email."
    }
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HelpCircle className="w-5 h-5" />
          Frequently Asked Questions
        </CardTitle>
        <CardDescription>
          Common questions about trading bots and platform features
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion type="single" collapsible className="w-full">
          {faqs.map((faq, index) => (
            <AccordionItem key={index} value={`item-${index}`}>
              <AccordionTrigger className="text-left">
                {faq.question}
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground">
                {faq.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
};