import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const Terms = () => {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="container mx-auto px-4 py-24">
        <Card className="max-w-4xl mx-auto">
          <CardHeader>
            <CardTitle className="text-4xl font-bold">Terms of Service</CardTitle>
            <p className="text-muted-foreground">Last Updated: {new Date().toLocaleDateString()}</p>
          </CardHeader>
          <CardContent className="prose prose-invert max-w-none space-y-6">
            <section>
              <h2 className="text-2xl font-semibold mb-4">1. Acceptance of Terms</h2>
              <p className="text-muted-foreground">
                By accessing and using TradeBotX ("the Service"), you accept and agree to be bound by the terms 
                and provision of this agreement. If you do not agree to these terms, please do not use the Service.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">2. Service Description</h2>
              <p className="text-muted-foreground">
                TradeBotX provides automated trading software and algorithms for forex and cryptocurrency markets. 
                The Service includes access to trading strategies, market analysis tools, and automated execution capabilities.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">3. User Responsibilities</h2>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li>You are responsible for maintaining the confidentiality of your account credentials</li>
                <li>You must provide accurate and complete information when creating an account</li>
                <li>You agree to use the Service in compliance with all applicable laws and regulations</li>
                <li>You are solely responsible for all trading decisions and outcomes</li>
                <li>You must ensure your trading account has sufficient funds</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">4. Trading Risks</h2>
              <p className="text-muted-foreground">
                Trading financial instruments involves substantial risk and may not be suitable for all investors. 
                You acknowledge that automated trading systems can result in significant losses. Past performance 
                does not guarantee future results. You agree that TradeBotX is not responsible for any trading losses.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">5. Subscription and Payment</h2>
              <ul className="list-disc pl-6 text-muted-foreground space-y-2">
                <li>Subscription fees are billed according to your selected plan</li>
                <li>Payments are processed securely through our payment provider</li>
                <li>Refunds are subject to our refund policy</li>
                <li>We reserve the right to modify pricing with 30 days notice</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">6. Intellectual Property</h2>
              <p className="text-muted-foreground">
                All content, features, and functionality of the Service are owned by TradeBotX and are protected 
                by international copyright, trademark, and other intellectual property laws.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">7. Limitation of Liability</h2>
              <p className="text-muted-foreground">
                TradeBotX shall not be liable for any direct, indirect, incidental, special, consequential, or 
                exemplary damages resulting from your use of the Service, including but not limited to trading losses, 
                loss of profits, or data loss.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">8. Termination</h2>
              <p className="text-muted-foreground">
                We reserve the right to terminate or suspend your account at any time for violation of these terms. 
                You may cancel your subscription at any time through your account settings.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">9. Changes to Terms</h2>
              <p className="text-muted-foreground">
                We reserve the right to modify these terms at any time. Continued use of the Service after changes 
                constitutes acceptance of the modified terms.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-4">10. Contact Information</h2>
              <p className="text-muted-foreground">
                For questions about these Terms of Service, please contact us at legal@tradebotx.com
              </p>
            </section>
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
};

export default Terms;
