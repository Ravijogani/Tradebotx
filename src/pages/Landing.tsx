import { Navbar } from "@/components/landing/Navbar";
import { Hero } from "@/components/landing/Hero";
import { Features } from "@/components/landing/Features";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Stats } from "@/components/landing/Stats";
import { PricingSection } from "@/components/landing/PricingSection";
import { FAQ } from "@/components/landing/FAQ";
import { Footer } from "@/components/landing/Footer";

const Landing = () => {
  return (
    <div className="min-h-screen">
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
