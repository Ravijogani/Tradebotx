import { Link } from "react-router-dom";
import { Bot } from "lucide-react";

export const Footer = () => {
  return (
    <footer className="bg-muted/30 border-t border-border/50 py-12">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div>
            <Link to="/" className="flex items-center gap-2 mb-4">
              <Bot className="w-8 h-8 text-primary" />
              <span className="text-xl font-bold">TradeBotX</span>
            </Link>
            <p className="text-muted-foreground text-sm">
              Advanced AI-powered trading automation platform for forex and crypto traders.
            </p>
          </div>

          <div>
            <h3 className="font-semibold mb-4">Product</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/pricing" className="hover:text-primary transition-colors">Pricing</Link></li>
              <li><Link to="/#features" className="hover:text-primary transition-colors">Features</Link></li>
              <li><Link to="/#how-it-works" className="hover:text-primary transition-colors">How It Works</Link></li>
              <li><Link to="/dashboard" className="hover:text-primary transition-colors">Dashboard</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-4">Support</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/#faq" className="hover:text-primary transition-colors">FAQ</Link></li>
              <li><a href="mailto:support@tradebotx.com" className="hover:text-primary transition-colors">Contact Us</a></li>
              <li><Link to="/docs" className="hover:text-primary transition-colors">Documentation</Link></li>
              <li><Link to="/status" className="hover:text-primary transition-colors">System Status</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-4">Legal</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/terms" className="hover:text-primary transition-colors">Terms of Service</Link></li>
              <li><Link to="/privacy" className="hover:text-primary transition-colors">Privacy Policy</Link></li>
              <li><Link to="/disclaimer" className="hover:text-primary transition-colors">Risk Disclaimer</Link></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-border/50 pt-8 text-center text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} TradeBotX. All rights reserved.</p>
          <p className="mt-2">Trading involves risk. Past performance does not guarantee future results.</p>
        </div>
      </div>
    </footer>
  );
};
