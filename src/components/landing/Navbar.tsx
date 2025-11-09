import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { Sparkles, Menu } from "lucide-react";
import logoDark from "@/assets/tradebotx-logo.png";
import logoWhite from "@/assets/tradebotx-logo-white.png";
import { useState, useEffect } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    // Check initial theme
    const checkTheme = () => {
      const isDark = document.documentElement.classList.contains('dark');
      setIsDarkMode(isDark);
    };
    
    checkTheme();
    
    // Watch for theme changes
    const observer = new MutationObserver(checkTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    });
    
    return () => observer.disconnect();
  }, []);

  return (
    <nav className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-2xl border-b border-border/30">
      <div className="container mx-auto px-4 h-20 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-primary to-accent rounded-lg blur-lg opacity-50 group-hover:opacity-75 transition-opacity"></div>
            <img 
              src={isDarkMode ? logoWhite : logoDark} 
              alt="TradeBotX" 
              className="relative h-10 sm:h-12 w-auto object-contain transition-opacity duration-300"
            />
          </div>
          <Sparkles className="w-3 h-3 sm:w-4 sm:h-4 text-accent animate-pulse" />
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

        <div className="hidden md:flex items-center gap-3">
          <Button asChild variant="ghost" className="hover:bg-primary/10">
            <Link to="/auth/login">Sign In</Link>
          </Button>
          <Button asChild className="bg-gradient-to-r from-primary to-accent hover:shadow-glow transition-all duration-300">
            <Link to="/pricing">Get Started</Link>
          </Button>
        </div>

        {/* Mobile Menu */}
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
          <SheetTrigger asChild className="md:hidden">
            <Button variant="ghost" size="icon">
              <Menu className="w-6 h-6" />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-[300px]">
            <SheetHeader>
              <SheetTitle>Menu</SheetTitle>
            </SheetHeader>
            <div className="flex flex-col gap-4 mt-8">
              <Link 
                to="/#features" 
                onClick={() => setIsOpen(false)}
                className="text-foreground/80 hover:text-foreground transition-colors font-medium py-2"
              >
                Features
              </Link>
              <Link 
                to="/#how-it-works" 
                onClick={() => setIsOpen(false)}
                className="text-foreground/80 hover:text-foreground transition-colors font-medium py-2"
              >
                How It Works
              </Link>
              <Link 
                to="/pricing" 
                onClick={() => setIsOpen(false)}
                className="text-foreground/80 hover:text-foreground transition-colors font-medium py-2"
              >
                Pricing
              </Link>
              <Link 
                to="/#faq" 
                onClick={() => setIsOpen(false)}
                className="text-foreground/80 hover:text-foreground transition-colors font-medium py-2"
              >
                FAQ
              </Link>
              <div className="pt-4 border-t border-border flex flex-col gap-3">
                <Button asChild variant="ghost" className="w-full" onClick={() => setIsOpen(false)}>
                  <Link to="/auth/login">Sign In</Link>
                </Button>
                <Button asChild className="w-full bg-gradient-to-r from-primary to-accent" onClick={() => setIsOpen(false)}>
                  <Link to="/pricing">Get Started</Link>
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </nav>
  );
};