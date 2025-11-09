import { Navbar } from "@/components/landing/Navbar";
import { Hero } from "@/components/landing/Hero";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Stats } from "@/components/landing/Stats";
import { PricingSection } from "@/components/landing/PricingSection";
import { FAQ } from "@/components/landing/FAQ";
import { Footer } from "@/components/landing/Footer";
import { SEOHead } from "@/components/SEOHead";

const Landing = () => {
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
      <SEOHead
        title="TradeBotX - AI-Powered Algorithmic Trading Platform for Forex & Crypto"
        description="Automate your trading with TradeBotX's advanced AI algorithms. Execute winning trades 24/7 on Forex and Crypto markets with proper risk management and real-time analytics."
        keywords="algorithmic trading, forex bot, crypto trading bot, automated trading, AI trading platform, MetaTrader 5, MT5 bot, forex automation, crypto automation, trading algorithms"
        structuredData={structuredData}
      />
      <Navbar />
      <Hero />
      <Stats />
      <Features />
      <HowItWorks />
      <PricingSection />
      <FAQ />
      <Footer />
    </div>
  );
};

export default Landing;
