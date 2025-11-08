import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

const Terms = () => {
  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="pt-32 pb-24">
        <div className="container mx-auto px-4 max-w-4xl">
          <h1 className="font-display text-5xl font-bold mb-8 bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            Terms of Service
          </h1>
          <div className="prose prose-invert max-w-none space-y-6 text-muted-foreground">
            <p className="text-lg">Last updated: {new Date().toLocaleDateString()}</p>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">1. Acceptance of Terms</h2>
              <p>
                By accessing and using AlgoTradeX ("the Service"), you accept and agree to be bound by the terms and provision of this agreement. 
                If you do not agree to abide by the above, please do not use this service.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">2. Service Description</h2>
              <p>
                AlgoTradeX provides automated algorithmic trading software for forex and cryptocurrency markets. The Service includes:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Access to AI-powered trading strategies</li>
                <li>Real-time trade execution through MetaTrader 5 (MT5) integration</li>
                <li>Performance analytics and reporting</li>
                <li>Risk management tools</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">3. User Accounts</h2>
              <p>
                To use the Service, you must create an account. You are responsible for:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Maintaining the confidentiality of your account credentials</li>
                <li>All activities that occur under your account</li>
                <li>Providing accurate and complete information</li>
                <li>Updating your information to keep it accurate</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">4. Trading Risks</h2>
              <p className="font-semibold text-warning">
                IMPORTANT: Trading forex and cryptocurrencies carries a high level of risk and may not be suitable for all investors.
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>You may lose some or all of your invested capital</li>
                <li>Past performance does not guarantee future results</li>
                <li>Automated trading systems cannot guarantee profits</li>
                <li>You trade at your own risk and are responsible for all trading decisions</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">5. Subscription and Payments</h2>
              <ul className="list-disc pl-6 space-y-2">
                <li>Subscription fees are charged according to your selected plan</li>
                <li>Payments are processed securely through Razorpay</li>
                <li>Trial periods are available for certain plans</li>
                <li>Cancellation must be done before the next billing cycle</li>
                <li>No refunds for partial months of service</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">6. MT5 Integration</h2>
              <p>
                You must provide valid MT5 account credentials to use our trading features. You acknowledge that:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>We securely store your credentials using encryption</li>
                <li>You maintain your own broker relationship</li>
                <li>We are not responsible for broker-related issues</li>
                <li>Your broker's terms and fees apply separately</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">7. Prohibited Activities</h2>
              <p>You may not:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Reverse engineer or attempt to extract source code</li>
                <li>Use the Service for illegal activities</li>
                <li>Share your account with others</li>
                <li>Interfere with the Service's operation</li>
                <li>Attempt to gain unauthorized access to systems</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">8. Limitation of Liability</h2>
              <p>
                AlgoTradeX is provided "as is" without warranties of any kind. We are not liable for:
              </p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Trading losses or financial damages</li>
                <li>System downtime or technical issues</li>
                <li>Third-party service failures (brokers, internet providers)</li>
                <li>Market conditions or execution delays</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">9. Termination</h2>
              <p>
                We reserve the right to terminate or suspend your account at our discretion, without notice, for conduct that violates these Terms or is harmful to other users or the Service.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">10. Changes to Terms</h2>
              <p>
                We may modify these Terms at any time. Continued use of the Service after changes constitutes acceptance of the new Terms.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">11. Contact</h2>
              <p>
                For questions about these Terms, contact us at <a href="mailto:legal@algotradex.com" className="text-primary hover:underline">legal@algotradex.com</a>
              </p>
            </section>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Terms;
