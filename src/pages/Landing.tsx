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
    "name": "TradeBotX",
    "applicationCategory": "FinanceApplication",
    "operatingSystem": "Web",
    "description": "Advanced AI-powered algorithmic trading platform with 24/7 automated execution for Forex and Crypto markets",
    "offers": [
      {
        "@type": "Offer",
        "name": "Free Plan",
        "price": "0",
        "priceCurrency": "INR"
      },
      {
        "@type": "Offer",
        "name": "Pro Plan",
        "price": "9999",
        "priceCurrency": "INR"
      },
      {
        "@type": "Offer",
        "name": "Enterprise Plan",
        "price": "49999",
        "priceCurrency": "INR"
      }
    ],
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "4.8",
      "reviewCount": "127",
      "bestRating": "5",
      "worstRating": "1"
    }
  };

  return (
    <div className="min-h-screen">
      <ScrollProgress />
      <SEOHead
        title="TradeBotX - AI-Powered Algorithmic Trading Platform for Forex & Crypto"
        description="Automate your trading with TradeBotX's advanced AI algorithms. Execute winning trades 24/7 on Forex and Crypto markets with proper risk management and real-time analytics."
        keywords="algorithmic trading, forex bot, crypto trading bot, automated trading, AI trading platform, MetaTrader 5, MT5 bot, forex automation, crypto automation, trading algorithms"
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
