import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, Clock, Activity } from "lucide-react";

const Status = () => {
  const services = [
    {
      name: "Trading Platform",
      status: "operational",
      uptime: "99.9%",
      lastUpdate: "2 minutes ago",
    },
    {
      name: "Strategy Execution Engine",
      status: "operational",
      uptime: "99.8%",
      lastUpdate: "5 minutes ago",
    },
    {
      name: "Market Data Feed",
      status: "operational",
      uptime: "99.95%",
      lastUpdate: "1 minute ago",
    },
    {
      name: "API Services",
      status: "operational",
      uptime: "99.7%",
      lastUpdate: "3 minutes ago",
    },
    {
      name: "Payment Processing",
      status: "operational",
      uptime: "100%",
      lastUpdate: "Just now",
    },
    {
      name: "Email Notifications",
      status: "operational",
      uptime: "99.9%",
      lastUpdate: "4 minutes ago",
    },
  ];

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "operational":
        return <Badge className="bg-success"><CheckCircle className="w-3 h-3 mr-1" /> Operational</Badge>;
      case "degraded":
        return <Badge className="bg-warning"><Activity className="w-3 h-3 mr-1" /> Degraded</Badge>;
      case "outage":
        return <Badge variant="destructive"><Clock className="w-3 h-3 mr-1" /> Outage</Badge>;
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="container mx-auto px-4 py-24">
        <div className="max-w-4xl mx-auto space-y-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-4xl font-bold flex items-center gap-3">
                <Activity className="w-10 h-10 text-success" />
                System Status
              </CardTitle>
              <CardDescription>
                Real-time status of all TradeBotX services
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-success/10 border border-success/30 rounded-lg p-6 mb-8">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-8 h-8 text-success" />
                  <div>
                    <h3 className="text-xl font-semibold text-success">All Systems Operational</h3>
                    <p className="text-muted-foreground text-sm">
                      All services are running smoothly with no reported issues
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-2xl font-semibold mb-4">Service Status</h3>
                {services.map((service, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-4 rounded-lg border border-border hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-1">
                      <h4 className="font-semibold mb-1">{service.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        Uptime: {service.uptime} • Updated {service.lastUpdate}
                      </p>
                    </div>
                    {getStatusBadge(service.status)}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-2xl font-bold">Platform Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="text-center p-6 rounded-lg bg-card border border-border">
                  <div className="text-3xl font-bold text-primary mb-2">98.7%</div>
                  <div className="text-sm text-muted-foreground">Overall Uptime (30 days)</div>
                </div>
                <div className="text-center p-6 rounded-lg bg-card border border-border">
                  <div className="text-3xl font-bold text-success mb-2">&lt;50ms</div>
                  <div className="text-sm text-muted-foreground">Average Response Time</div>
                </div>
                <div className="text-center p-6 rounded-lg bg-card border border-border">
                  <div className="text-3xl font-bold text-accent mb-2">0</div>
                  <div className="text-sm text-muted-foreground">Active Incidents</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-2xl font-bold">Recent Incidents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12">
                <CheckCircle className="w-16 h-16 text-success mx-auto mb-4" />
                <p className="text-lg font-medium">No Recent Incidents</p>
                <p className="text-sm text-muted-foreground mt-2">
                  All systems have been running smoothly for the past 30 days
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-2xl font-bold">Scheduled Maintenance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-12">
                <Clock className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
                <p className="text-lg font-medium">No Scheduled Maintenance</p>
                <p className="text-sm text-muted-foreground mt-2">
                  We'll notify you in advance of any planned maintenance
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="text-center text-sm text-muted-foreground">
            <p>For real-time updates and support, contact us at status@tradebotx.com</p>
            <p className="mt-2">Page last updated: {new Date().toLocaleString()}</p>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Status;
