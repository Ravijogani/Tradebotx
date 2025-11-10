import { Navbar } from "@/components/landing/Navbar";
import { Hero } from "@/components/landing/Hero";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Stats } from "@/components/landing/Stats";
import { PricingSection } from "@/components/landing/PricingSection";
import { FAQ } from "@/components/landing/FAQ";
import { Footer } from "@/components/landing/Footer";
import { SEOHead } from "@/components/SEOHead";
import { useScrollAnimation } from "@/hooks/useScrollAnimation";
import { ScrollProgress } from "@/components/ui/scroll-progress";

const Landing = () => {
  const featuresAnimation = useScrollAnimation({ threshold: 0.2 });
  const howItWorksAnimation = useScrollAnimation({ threshold: 0.2 });
  const statsAnimation = useScrollAnimation({ threshold: 0.3 });
  const pricingAnimation = useScrollAnimation({ threshold: 0.2 });
  const faqAnimation = useScrollAnimation({ threshold: 0.2 });
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "TradeBotX - Best AI Algorithmic Trading Bot",
    "applicationCategory": "FinanceApplication",
    "operatingSystem": "Web, Windows, Mac, Linux",
    "description": "TradeBotX is the #1 AI-powered algorithmic trading platform for Forex and Crypto. Trusted by 10,000+ traders with 98.7% uptime, proven strategies, 24/7 automated execution, and advanced risk management.",
    "url": "https://tradebotx.com",
    "screenshot": "https://tradebotx.com/dashboard-preview.jpg",
    "keywords": "best algorithmic trading bot, automated forex trading, crypto trading bot, AI trading platform, MetaTrader 5 bot, best trading bot, algo trading software",
    "offers": [
      {
        "@type": "Offer",
        "name": "Free Trial Plan",
        "description": "Get started with basic algorithmic trading features",
        "price": "0",
        "priceCurrency": "INR",
        "availability": "https://schema.org/InStock"
      },
      {
        "@type": "Offer",
        "name": "Pro Plan",
        "description": "Professional trading with unlimited strategies and advanced AI",
        "price": "9999",
        "priceCurrency": "INR",
        "availability": "https://schema.org/InStock"
      },
      {
        "@type": "Offer",
        "name": "Enterprise Plan",
        "description": "Premium features with dedicated support and custom strategies",
        "price": "49999",
        "priceCurrency": "INR",
        "availability": "https://schema.org/InStock"
      }
    ],
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "4.8",
      "reviewCount": "127",
      "ratingCount": "127",
      "bestRating": "5",
      "worstRating": "1"
    },
    "featureList": [
      "AI-Powered Trading Algorithms",
      "24/7 Automated Execution",
      "Real-Time Market Analysis",
      "Advanced Risk Management",
      "Multi-Strategy Support",
      "MetaTrader 5 Integration",
      "Forex & Crypto Trading",
      "Professional Analytics Dashboard",
      "Telegram Notifications",
      "Bank-Grade Security"
    ]
  };

  return (
    <div className="min-h-screen">
      <ScrollProgress />
      <SEOHead
        title="TradeBotX - Best AI Algorithmic Trading Bot for Forex & Crypto | #1 Automated Trading Platform"
        description="TradeBotX is the #1 AI-powered algorithmic trading bot with 98.7% uptime. Automate Forex & Crypto trading with proven strategies, 24/7 execution, real-time analytics, and MetaTrader 5 integration. Trusted by 10,000+ traders worldwide. Start free trial today!"
        keywords="best trading bot, algorithmic trading bot, automated forex trading, crypto trading bot, AI trading platform, MetaTrader 5 bot, forex robot, crypto automation, trading algorithm, algo trading software, best algo trading platform, automated trading system, forex EA, expert advisor, trading bot software, best forex bot, best crypto bot, cryptocurrency trading bot, automated crypto trading, trading automation platform"
        structuredData={structuredData}
      />
      <Navbar />
      <Hero />
      <section ref={statsAnimation.ref as any} className={`scroll-animate ${statsAnimation.isVisible ? 'visible' : ''}`}>
        <Stats />
      </section>
      <section ref={featuresAnimation.ref as any} className={`scroll-animate ${featuresAnimation.isVisible ? 'visible' : ''}`}>
        <Features />
      </section>
      <section ref={howItWorksAnimation.ref as any} className={`scroll-animate ${howItWorksAnimation.isVisible ? 'visible' : ''}`}>
        <HowItWorks />
      </section>
      <section ref={pricingAnimation.ref as any} className={`scroll-animate ${pricingAnimation.isVisible ? 'visible' : ''}`}>
        <PricingSection />
      </section>
      <section ref={faqAnimation.ref as any} className={`scroll-animate ${faqAnimation.isVisible ? 'visible' : ''}`}>
        <FAQ />
      </section>
      <Footer />
    </div>
  );
};

export default Landing;
