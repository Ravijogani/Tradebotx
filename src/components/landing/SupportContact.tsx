import { MessageCircle, Mail, Book, Clock, Users, Headphones } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

const supportChannels = [
  {
    icon: MessageCircle,
    title: "Telegram Support",
    description: "Join our community for instant help",
    action: "Join Now",
    link: "https://t.me/tradebotxsupport",
    availability: "24/7 Community",
    color: "from-blue-500 to-cyan-500"
  },
  {
    icon: Mail,
    title: "Email Support",
    description: "Detailed assistance for complex issues",
    action: "Email Us",
    link: "mailto:support@tradebotx.com",
    availability: "Response in 24-48h",
    color: "from-purple-500 to-pink-500"
  },
  {
    icon: Book,
    title: "Documentation",
    description: "Comprehensive guides and tutorials",
    action: "Read Docs",
    link: "/docs",
    availability: "Always Available",
    color: "from-emerald-500 to-green-500"
  },
  {
    icon: Headphones,
    title: "Priority Support",
    description: "Dedicated support for Pro & Enterprise",
    action: "Upgrade",
    link: "/pricing",
    availability: "Within 4 hours",
    color: "from-orange-500 to-red-500"
  }
];

const resources = [
  { title: "Getting Started Guide", link: "/docs#getting-started" },
  { title: "MT5 Setup Tutorial", link: "/docs#mt5-setup" },
  { title: "Trading Strategies Explained", link: "/docs#strategies" },
  { title: "Risk Management Best Practices", link: "/docs#risk-management" },
  { title: "API Documentation", link: "/docs#api" },
  { title: "Troubleshooting Common Issues", link: "/docs#troubleshooting" }
];

export const SupportContact = () => {
  return (
    <section id="support" className="py-16 sm:py-24 md:py-32 bg-muted/30 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-mesh opacity-20"></div>
      
      <div className="container mx-auto px-4 sm:px-6 relative z-10">
        <div className="text-center mb-12 sm:mb-16">
          <div className="inline-block px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 mb-6">
            <span className="text-sm font-medium text-primary">HELP & SUPPORT</span>
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
              We're Here to
            </span>{" "}
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Help You Succeed
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Get help from our team of trading experts and join a community of successful traders
          </p>
        </div>

        {/* Support Channels */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-16">
          {supportChannels.map((channel, index) => (
            <Card 
              key={index} 
              className="p-6 bg-card/50 backdrop-blur-sm border-border/50 hover:border-primary/50 transition-all hover:shadow-lg hover:shadow-primary/10 group"
            >
              <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${channel.color} p-0.5 mb-4`}>
                <div className="w-full h-full bg-card rounded-lg flex items-center justify-center">
                  <channel.icon className="w-6 h-6 text-primary" />
                </div>
              </div>
              <h3 className="font-semibold text-lg mb-2">{channel.title}</h3>
              <p className="text-sm text-muted-foreground mb-4">{channel.description}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground mb-4">
                <Clock className="w-3.5 h-3.5" />
                <span>{channel.availability}</span>
              </div>
              <Button asChild variant="outline" className="w-full group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                <a href={channel.link} target={channel.link.startsWith('http') ? '_blank' : undefined} rel={channel.link.startsWith('http') ? 'noopener noreferrer' : undefined}>
                  {channel.action}
                </a>
              </Button>
            </Card>
          ))}
        </div>

        {/* Quick Resources */}
        <div className="max-w-4xl mx-auto">
          <Card className="p-8 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm border-border/50">
            <div className="flex items-center gap-3 mb-6">
              <Users className="w-6 h-6 text-primary" />
              <h3 className="text-2xl font-bold">Popular Resources</h3>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
              {resources.map((resource, index) => (
                <a 
                  key={index}
                  href={resource.link}
                  className="flex items-center gap-3 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors group"
                >
                  <Book className="w-5 h-5 text-primary flex-shrink-0" />
                  <span className="text-sm group-hover:text-primary transition-colors">{resource.title}</span>
                </a>
              ))}
            </div>

            <div className="text-center">
              <Button asChild size="lg">
                <a href="/docs">
                  Browse All Documentation
                </a>
              </Button>
            </div>
          </Card>
        </div>

        {/* Emergency Contact */}
        <div className="mt-12 p-6 bg-destructive/10 border border-destructive/20 rounded-lg max-w-4xl mx-auto">
          <div className="text-center">
            <p className="font-semibold text-destructive mb-2">Need Urgent Help?</p>
            <p className="text-sm text-muted-foreground mb-4">
              For critical trading issues or bot malfunctions, contact us immediately via Telegram or use the emergency stop button in your dashboard.
            </p>
            <Button asChild variant="destructive" size="sm">
              <a href="https://t.me/tradebotxsupport" target="_blank" rel="noopener noreferrer">
                Emergency Support
              </a>
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};
