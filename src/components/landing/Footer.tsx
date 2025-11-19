import { Link } from "react-router-dom";
import { Bot } from "lucide-react";
import { ScrollLink } from "@/components/ScrollLink";

export const Footer = () => {
  return (
    <footer className="bg-muted/30 border-t border-border/50 py-8 sm:py-12">
      <div className="container mx-auto px-4 sm:px-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8 mb-6 sm:mb-8">
          <div className="sm:col-span-2 lg:col-span-1">
            <Link to="/" className="flex items-center gap-2 mb-3 sm:mb-4">
              <Bot className="w-7 h-7 sm:w-8 sm:h-8 text-primary" />
              <span className="text-lg sm:text-xl font-bold">TradeBotX</span>
            </Link>
            <p className="text-muted-foreground text-sm">
              Advanced AI-powered trading automation platform for forex and crypto traders.
            </p>
          </div>

          <div>
            <h3 className="font-semibold mb-3 sm:mb-4 text-sm sm:text-base">Product</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/pricing" className="hover:text-primary transition-colors">Pricing</Link></li>
              <li><ScrollLink to="/#features" className="hover:text-primary transition-colors">Features</ScrollLink></li>
              <li><ScrollLink to="/#how-it-works" className="hover:text-primary transition-colors">How It Works</ScrollLink></li>
              <li><Link to="/dashboard" className="hover:text-primary transition-colors">Dashboard</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-3 sm:mb-4 text-sm sm:text-base">Support</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><a href="https://t.me/tradebotxsupport" target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors">Telegram Support (24/7)</a></li>
              <li><a href="mailto:tradebotxsuppo@gmail.com" className="hover:text-primary transition-colors">Email Support</a></li>
              <li><Link to="/docs" className="hover:text-primary transition-colors">Documentation</Link></li>
              <li><ScrollLink to="/#faq" className="hover:text-primary transition-colors">FAQ</ScrollLink></li>
              <li><Link to="/status" className="hover:text-primary transition-colors">System Status</Link></li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold mb-3 sm:mb-4 text-sm sm:text-base">Legal</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link to="/terms" className="hover:text-primary transition-colors">Terms of Service</Link></li>
              <li><Link to="/privacy" className="hover:text-primary transition-colors">Privacy Policy</Link></li>
              <li><Link to="/disclaimer" className="hover:text-primary transition-colors">Risk Disclaimer</Link></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-border/50 pt-6 sm:pt-8 text-center text-xs sm:text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} TradeBotX. All rights reserved.</p>
          <p className="mt-2">Trading involves risk. Past performance does not guarantee future results.</p>
        </div>
      </div>
    </footer>
  );
};
