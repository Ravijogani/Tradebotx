import { Helmet } from "react-helmet-async";

interface SEOHeadProps {
  title?: string;
  description?: string;
  keywords?: string;
  image?: string;
  url?: string;
  type?: string;
  author?: string;
  publishedTime?: string;
  structuredData?: object;
}

export const SEOHead = ({
  title = "TradeBotX - AI-Powered Algorithmic Trading Platform",
  description = "Automate your Forex and Crypto trading with TradeBotX. Advanced AI-powered algorithmic trading platform with 24/7 execution, proper risk management, and real-time analytics.",
  keywords = "algorithmic trading, forex, crypto, automated trading, trading bot, AI trading, MetaTrader 5, MT5, forex bot, crypto bot, trading automation",
  image = "https://lovable.dev/opengraph-image-p98pqg.png",
  url = "https://tradebotx.com",
  type = "website",
  author = "TradeBotX",
  publishedTime,
  structuredData,
}: SEOHeadProps) => {
  const fullTitle = title.includes("TradeBotX") ? title : `${title} | TradeBotX`;
  const canonicalUrl = url || typeof window !== "undefined" ? window.location.href : "";

  // Default structured data
  const defaultStructuredData = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    "name": "TradeBotX",
    "applicationCategory": "FinanceApplication",
    "operatingSystem": "Web",
    "description": description,
    "offers": {
      "@type": "AggregateOffer",
      "priceCurrency": "INR",
      "lowPrice": "0",
      "highPrice": "49999",
    },
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": "4.8",
      "reviewCount": "127"
    }
  };

  return (
    <Helmet>
      {/* Primary Meta Tags */}
      <title>{fullTitle}</title>
      <meta name="title" content={fullTitle} />
      <meta name="description" content={description} />
      <meta name="keywords" content={keywords} />
      <meta name="author" content={author} />
      <link rel="canonical" href={canonicalUrl} />

      {/* Open Graph / Facebook */}
      <meta property="og:type" content={type} />
      <meta property="og:url" content={canonicalUrl} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={image} />
      <meta property="og:site_name" content="TradeBotX" />
      {publishedTime && <meta property="article:published_time" content={publishedTime} />}

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@TradeBotX" />
      <meta name="twitter:url" content={canonicalUrl} />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={image} />

      {/* Additional SEO tags */}
      <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
      <meta name="googlebot" content="index, follow" />
      <meta name="language" content="English" />
      <meta name="revisit-after" content="7 days" />

      {/* Structured Data */}
      <script type="application/ld+json">
        {JSON.stringify(structuredData || defaultStructuredData)}
      </script>
    </Helmet>
  );
};
