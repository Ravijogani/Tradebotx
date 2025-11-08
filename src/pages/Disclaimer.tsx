import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertTriangle } from "lucide-react";

const Disclaimer = () => {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="container mx-auto px-4 py-24">
        <Card className="max-w-4xl mx-auto">
          <CardHeader>
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="w-10 h-10 text-warning" />
              <CardTitle className="text-4xl font-bold">Risk Disclaimer</CardTitle>
            </div>
            <p className="text-muted-foreground">Last Updated: {new Date().toLocaleDateString()}</p>
          </CardHeader>
          <CardContent className="prose prose-invert max-w-none space-y-6">
            <section className="bg-warning/10 border border-warning/30 rounded-lg p-6">
              <h3 className="text-xl font-semibold text-warning mb-3">⚠️ Important Risk Warning</h3>
              <p className="text-muted-foreground">
                Trading forex, cryptocurrencies, and other financial instruments involves substantial risk of loss 
                and is not suitable for all investors. The high degree of leverage can work against you as well as 
                for you. Before deciding to trade, you should carefully consider your investment objectives, level 
                of experience, and risk appetite.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">1. General Trading Risks</h2>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li><strong>Market Volatility:</strong> Financial markets can be highly volatile and unpredictable</li>
                <li><strong>Leverage Risk:</strong> Using leverage can magnify both gains and losses</li>
                <li><strong>Capital Loss:</strong> You may lose some or all of your invested capital</li>
                <li><strong>Past Performance:</strong> Historical results do not guarantee future returns</li>
                <li><strong>Technical Failures:</strong> System outages or connectivity issues may prevent order execution</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">2. Automated Trading Risks</h2>
              <p className="text-muted-foreground mb-4">
                Using automated trading systems like AlgoTradeX introduces additional risks:
              </p>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li><strong>Algorithm Performance:</strong> Algorithms may not perform as expected in all market conditions</li>
                <li><strong>Technology Dependence:</strong> System failures or bugs may result in unexpected behavior</li>
                <li><strong>Over-Optimization:</strong> Strategies may be over-fitted to historical data</li>
                <li><strong>Market Changes:</strong> Algorithms may not adapt quickly to sudden market shifts</li>
                <li><strong>Execution Delays:</strong> Network or broker delays may affect trade execution</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">3. No Guaranteed Returns</h2>
              <p className="text-muted-foreground">
                AlgoTradeX does not guarantee any specific returns or profits. All trading results are dependent on 
                market conditions, your trading setup, and the strategies you choose to deploy. Performance metrics 
                shown on our platform are historical and for informational purposes only.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">4. Not Financial Advice</h2>
              <p className="text-muted-foreground">
                The information provided by AlgoTradeX is for educational and informational purposes only. It should 
                not be considered financial advice or a recommendation to buy or sell any financial instrument. You 
                should consult with a qualified financial advisor before making any investment decisions.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">5. Regulatory Compliance</h2>
              <p className="text-muted-foreground">
                You are responsible for ensuring that your use of AlgoTradeX complies with all applicable laws and 
                regulations in your jurisdiction. Some countries may restrict or prohibit the use of automated 
                trading systems.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">6. Broker Relationship</h2>
              <p className="text-muted-foreground">
                AlgoTradeX is not a broker or financial institution. You must maintain your own trading account with 
                a licensed broker. We are not responsible for any issues with your broker, including execution quality, 
                spreads, or account management.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">7. User Responsibility</h2>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li>You are solely responsible for monitoring your trading account</li>
                <li>You should regularly review your trading performance and risk exposure</li>
                <li>You must ensure sufficient funds are available in your account</li>
                <li>You should understand how each strategy works before activating it</li>
                <li>You must set appropriate risk parameters for your situation</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">8. Third-Party Services</h2>
              <p className="text-muted-foreground">
                AlgoTradeX integrates with third-party services (brokers, data providers, etc.). We are not 
                responsible for the availability, accuracy, or reliability of these third-party services.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">9. Limitation of Liability</h2>
              <p className="text-muted-foreground">
                By using AlgoTradeX, you acknowledge and accept all risks associated with trading. We shall not be 
                liable for any losses, damages, or claims arising from your use of our service, including but not 
                limited to trading losses, system failures, or data inaccuracies.
              </p>
            </section>

            <section className="bg-destructive/10 border border-destructive/30 rounded-lg p-6">
              <h3 className="text-xl font-semibold text-destructive mb-3">⚠️ Risk Acknowledgment</h3>
              <p className="text-muted-foreground">
                By using AlgoTradeX, you confirm that you understand and accept these risks. You acknowledge that 
                you could lose all of your invested capital and that you are financially able to bear such losses. 
                You should only trade with money you can afford to lose.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">10. Questions?</h2>
              <p className="text-muted-foreground">
                If you have questions about the risks involved in using AlgoTradeX, please contact us at 
                risk@algotradex.com or consult with a qualified financial advisor.
              </p>
            </section>
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
};

export default Disclaimer;
