import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { Bot, Sparkles } from "lucide-react";

export const Navbar = () => {
  return (
    <nav className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-2xl border-b border-border/30">
      <div className="container mx-auto px-4 h-20 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-primary to-accent rounded-lg blur-lg opacity-50 group-hover:opacity-75 transition-opacity"></div>
            <div className="relative w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center">
              <Bot className="w-6 h-6 text-white" />
            </div>
          </div>
          <span className="font-display text-2xl font-bold bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            TradeBotX
          </span>
          <Sparkles className="w-4 h-4 text-accent" />
        </Link>
        
        <div className="hidden md:flex items-center gap-8">
          <Link 
            to="/#features" 
            className="text-foreground/80 hover:text-foreground transition-colors font-medium relative group"
          >
            Features
            <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-primary to-accent group-hover:w-full transition-all duration-300"></span>
          </Link>
          <Link 
            to="/#how-it-works" 
            className="text-foreground/80 hover:text-foreground transition-colors font-medium relative group"
          >
            How It Works
            <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-primary to-accent group-hover:w-full transition-all duration-300"></span>
          </Link>
          <Link 
            to="/pricing" 
            className="text-foreground/80 hover:text-foreground transition-colors font-medium relative group"
          >
            Pricing
            <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-primary to-accent group-hover:w-full transition-all duration-300"></span>
          </Link>
          <Link 
            to="/#faq" 
            className="text-foreground/80 hover:text-foreground transition-colors font-medium relative group"
          >
            FAQ
            <span className="absolute -bottom-1 left-0 w-0 h-0.5 bg-gradient-to-r from-primary to-accent group-hover:w-full transition-all duration-300"></span>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          <Button asChild variant="ghost" className="hover:bg-primary/10">
            <Link to="/auth/login">Sign In</Link>
          </Button>
          <Button asChild className="bg-gradient-to-r from-primary to-accent hover:shadow-glow transition-all duration-300">
            <Link to="/pricing">Get Started</Link>
          </Button>
        </div>
      </div>
    </nav>
  );
};
