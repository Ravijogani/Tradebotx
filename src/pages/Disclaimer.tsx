import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { AlertTriangle } from "lucide-react";

const Disclaimer = () => {
  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="pt-32 pb-24">
        <div className="container mx-auto px-4 max-w-4xl">
          <div className="flex items-center gap-4 mb-8">
            <div className="w-16 h-16 rounded-2xl bg-warning/10 flex items-center justify-center">
              <AlertTriangle className="w-8 h-8 text-warning" />
            </div>
            <h1 className="font-display text-5xl font-bold bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
              Risk Disclaimer
            </h1>
          </div>
          
          <div className="prose prose-invert max-w-none space-y-6 text-muted-foreground">
            <div className="bg-warning/10 border border-warning/30 rounded-xl p-6 mb-8">
              <p className="text-warning font-semibold text-lg mb-2">
                ⚠️ HIGH RISK WARNING
              </p>
              <p className="text-foreground">
                Trading forex and cryptocurrencies on margin carries a high level of risk and may not be suitable for all investors. 
                The high degree of leverage can work against you as well as for you.
              </p>
            </div>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">1. General Risk Disclosure</h2>
              <p>
                Before deciding to trade forex or cryptocurrencies, you should carefully consider your investment objectives, level of experience, and risk appetite. 
                <strong className="text-foreground"> You could sustain a loss of some or all of your initial investment.</strong>
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Never invest money you cannot afford to lose</li>
                <li>Past performance is not indicative of future results</li>
                <li>Automated trading does not guarantee profits</li>
                <li>Market conditions can change rapidly and unpredictably</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">2. No Financial Advice</h2>
              <p>
                AlgoTradeX is a software platform that provides tools for automated trading. 
                <strong className="text-foreground"> We do not provide investment advice, financial advice, or recommendations.</strong>
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>All trading decisions are made by you</li>
                <li>We are not registered investment advisors</li>
                <li>Consult with a licensed financial advisor before trading</li>
                <li>You are solely responsible for your trading outcomes</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">3. Automated Trading Risks</h2>
              <p>Automated trading systems carry specific risks:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Technical Failures:</strong> Internet outages, server downtime, or system errors can result in missed trades or losses</li>
                <li><strong>Algorithm Limitations:</strong> No algorithm can predict all market conditions or guarantee profits</li>
                <li><strong>Slippage:</strong> Actual execution prices may differ from intended prices during volatile markets</li>
                <li><strong>Over-Optimization:</strong> Strategies tested on historical data may not perform well in live markets</li>
                <li><strong>Black Swan Events:</strong> Unexpected market events can cause severe losses</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">4. Leverage and Margin</h2>
              <p className="text-warning font-semibold">
                Trading on margin increases both potential profits and potential losses.
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Small market movements can result in large losses</li>
                <li>You may lose more than your initial investment</li>
                <li>Margin calls can force position closures at unfavorable prices</li>
                <li>Understand your broker's margin requirements and policies</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">5. Market Volatility</h2>
              <p>Financial markets are inherently volatile:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Cryptocurrency markets are particularly volatile and can experience extreme price swings</li>
                <li>Forex markets can be affected by global events, economic data, and central bank policies</li>
                <li>Liquidity can dry up during extreme market conditions</li>
                <li>Gap openings can result in orders filled at unexpected prices</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">6. Performance Claims</h2>
              <p>
                Any performance results displayed on our platform:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Are based on historical backtesting or simulated results</li>
                <li>Do not guarantee future performance</li>
                <li>May not reflect all costs and fees</li>
                <li>Are provided for informational purposes only</li>
                <li>Individual results may vary significantly</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">7. Third-Party Services</h2>
              <p>
                We integrate with third-party services (brokers, MT5 platforms):
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>We are not responsible for third-party service failures</li>
                <li>Your broker's terms and conditions apply separately</li>
                <li>Broker fees, spreads, and commissions may affect profitability</li>
                <li>Verify your broker is properly regulated</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">8. Regulatory Considerations</h2>
              <p>
                Trading regulations vary by jurisdiction:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Ensure you comply with local laws and regulations</li>
                <li>Some jurisdictions restrict or prohibit forex/crypto trading</li>
                <li>Tax obligations on trading profits may apply</li>
                <li>Regulatory protection may be limited or unavailable</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">9. No Guarantee of Uptime</h2>
              <p>
                While we strive for maximum uptime:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>System maintenance may temporarily interrupt service</li>
                <li>Unexpected technical issues can occur</li>
                <li>We are not liable for losses due to downtime</li>
                <li>Always monitor your trades and have backup plans</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">10. Educational Responsibility</h2>
              <p>
                Before using automated trading:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Educate yourself about forex and cryptocurrency markets</li>
                <li>Understand technical and fundamental analysis</li>
                <li>Learn about risk management techniques</li>
                <li>Start with small amounts and increase gradually</li>
                <li>Consider paper trading before risking real capital</li>
              </ul>
            </section>

            <div className="bg-destructive/10 border border-destructive/30 rounded-xl p-6 mt-8">
              <p className="text-destructive font-semibold text-lg mb-2">
                📌 IMPORTANT ACKNOWLEDGMENT
              </p>
              <p className="text-foreground">
                By using AlgoTradeX, you acknowledge that you have read, understood, and accepted all the risks outlined in this disclaimer. 
                You agree that you are solely responsible for your trading decisions and outcomes.
              </p>
            </div>

            <section className="space-y-4 mt-8">
              <h2 className="text-2xl font-bold text-foreground">Contact</h2>
              <p>
                For questions about this Risk Disclaimer, contact us at:
              </p>
              <p>
                Email: <a href="mailto:compliance@algotradex.com" className="text-primary hover:underline">compliance@algotradex.com</a>
              </p>
            </section>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Disclaimer;
