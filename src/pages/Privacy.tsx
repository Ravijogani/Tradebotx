import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

const Privacy = () => {
  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="pt-32 pb-24">
        <div className="container mx-auto px-4 max-w-4xl">
          <h1 className="font-display text-5xl font-bold mb-8 bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            Privacy Policy
          </h1>
          <div className="prose prose-invert max-w-none space-y-6 text-muted-foreground">
            <p className="text-lg">Last updated: {new Date().toLocaleDateString()}</p>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">1. Information We Collect</h2>
              <p>We collect information to provide better services to our users:</p>
              
              <h3 className="text-xl font-semibold text-foreground">Account Information</h3>
              <ul className="list-disc pl-6 space-y-2">
                <li>Email address</li>
                <li>Full name</li>
                <li>Password (encrypted)</li>
                <li>Subscription plan details</li>
              </ul>

              <h3 className="text-xl font-semibold text-foreground">Trading Configuration</h3>
              <ul className="list-disc pl-6 space-y-2">
                <li>MT5 account credentials (encrypted)</li>
                <li>Risk management preferences</li>
                <li>Trading strategy selections</li>
                <li>Position size limits</li>
              </ul>

              <h3 className="text-xl font-semibold text-foreground">Usage Data</h3>
              <ul className="list-disc pl-6 space-y-2">
                <li>Trade history and performance metrics</li>
                <li>Login times and session duration</li>
                <li>Feature usage patterns</li>
                <li>Device and browser information</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">2. How We Use Your Information</h2>
              <ul className="list-disc pl-6 space-y-2">
                <li>Provide and maintain trading services</li>
                <li>Execute trades on your behalf</li>
                <li>Send important notifications (trade alerts, trial expiration)</li>
                <li>Improve our algorithms and strategies</li>
                <li>Provide customer support</li>
                <li>Detect and prevent fraud</li>
                <li>Comply with legal obligations</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">3. Data Security</h2>
              <p>We take security seriously and implement multiple layers of protection:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Encryption:</strong> All data is encrypted in transit (SSL/TLS) and at rest (AES-256)</li>
                <li><strong>Access Control:</strong> Strict role-based access with multi-factor authentication</li>
                <li><strong>Secure Storage:</strong> MT5 credentials stored with additional encryption</li>
                <li><strong>Regular Audits:</strong> Security assessments and penetration testing</li>
                <li><strong>Monitoring:</strong> 24/7 system monitoring for suspicious activity</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">4. Data Sharing</h2>
              <p>We do not sell your personal information. We may share data with:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Service Providers:</strong> Payment processors (Razorpay), email services, cloud hosting</li>
                <li><strong>MT5 Brokers:</strong> Only credentials necessary for trade execution</li>
                <li><strong>Legal Requirements:</strong> When required by law or to protect rights and safety</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">5. Cookies and Tracking</h2>
              <p>We use cookies and similar technologies to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li>Maintain your login session</li>
                <li>Remember your preferences</li>
                <li>Analyze site usage and performance</li>
                <li>Provide personalized experience</li>
              </ul>
              <p>You can control cookies through your browser settings.</p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">6. Your Rights</h2>
              <p>You have the right to:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Access:</strong> Request a copy of your personal data</li>
                <li><strong>Correction:</strong> Update inaccurate information</li>
                <li><strong>Deletion:</strong> Request account and data deletion</li>
                <li><strong>Export:</strong> Download your trading data</li>
                <li><strong>Opt-out:</strong> Unsubscribe from marketing emails</li>
                <li><strong>Portability:</strong> Transfer data to another service</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">7. Data Retention</h2>
              <p>We retain your data:</p>
              <ul className="list-disc pl-6 space-y-2">
                <li><strong>Active accounts:</strong> For the duration of your subscription</li>
                <li><strong>Trading history:</strong> 7 years for compliance purposes</li>
                <li><strong>After deletion:</strong> Backups retained for 90 days</li>
              </ul>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">8. Children's Privacy</h2>
              <p>
                Our Service is not intended for users under 18 years of age. We do not knowingly collect information from children.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">9. International Transfers</h2>
              <p>
                Your data may be transferred to and processed in countries outside your residence. We ensure appropriate safeguards are in place.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">10. Changes to Privacy Policy</h2>
              <p>
                We may update this Privacy Policy periodically. We will notify you of significant changes via email or platform notification.
              </p>
            </section>

            <section className="space-y-4">
              <h2 className="text-2xl font-bold text-foreground">11. Contact Us</h2>
              <p>
                For privacy concerns or to exercise your rights, contact us at:
              </p>
              <p>
                Email: <a href="mailto:privacy@algotradex.com" className="text-primary hover:underline">privacy@algotradex.com</a>
              </p>
            </section>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Privacy;
