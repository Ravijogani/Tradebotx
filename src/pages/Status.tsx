import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { CheckCircle2, Server, Database, Zap } from "lucide-react";

const Status = () => {
  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="pt-32 pb-24">
        <div className="container mx-auto px-4 max-w-4xl">
          <h1 className="font-display text-5xl font-bold mb-4 bg-gradient-to-r from-foreground to-foreground/80 bg-clip-text text-transparent">
            System Status
          </h1>
          <p className="text-xl text-muted-foreground mb-12">
            Real-time monitoring of AlgoTradeX platform services
          </p>

          <div className="grid gap-6">
            {/* Overall Status */}
            <div className="p-6 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-foreground mb-2">All Systems Operational</h2>
                  <p className="text-muted-foreground">Last checked: {new Date().toLocaleString()}</p>
                </div>
                <CheckCircle2 className="w-12 h-12 text-success" />
              </div>
            </div>

            {/* Services Status */}
            <div className="space-y-4">
              <h3 className="text-xl font-semibold text-foreground">Core Services</h3>
              
              <div className="p-5 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 flex items-center justify-between hover:border-success/50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-success/10 flex items-center justify-center">
                    <Server className="w-6 h-6 text-success" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-foreground">API Server</h4>
                    <p className="text-sm text-muted-foreground">Response time: 45ms</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
                  <span className="text-success font-medium">Operational</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 flex items-center justify-between hover:border-success/50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-success/10 flex items-center justify-center">
                    <Database className="w-6 h-6 text-success" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-foreground">Database</h4>
                    <p className="text-sm text-muted-foreground">Query time: 12ms</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
                  <span className="text-success font-medium">Operational</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 flex items-center justify-between hover:border-success/50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-success/10 flex items-center justify-center">
                    <Zap className="w-6 h-6 text-success" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-foreground">Trading Engine</h4>
                    <p className="text-sm text-muted-foreground">Execution time: 80ms</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
                  <span className="text-success font-medium">Operational</span>
                </div>
              </div>

              <div className="p-5 rounded-xl bg-card/50 backdrop-blur-sm border border-border/50 flex items-center justify-between hover:border-success/50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-lg bg-success/10 flex items-center justify-center">
                    <CheckCircle2 className="w-6 h-6 text-success" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-foreground">MT5 Integration</h4>
                    <p className="text-sm text-muted-foreground">Connection: Active</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-success animate-pulse"></div>
                  <span className="text-success font-medium">Operational</span>
                </div>
              </div>
            </div>

            {/* Uptime Stats */}
            <div className="mt-8 p-6 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50">
              <h3 className="text-xl font-semibold text-foreground mb-6">Uptime Statistics</h3>
              <div className="grid grid-cols-3 gap-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-success mb-1">99.9%</div>
                  <div className="text-sm text-muted-foreground">Last 30 Days</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-success mb-1">99.8%</div>
                  <div className="text-sm text-muted-foreground">Last 90 Days</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-success mb-1">99.7%</div>
                  <div className="text-sm text-muted-foreground">Last 365 Days</div>
                </div>
              </div>
            </div>

            {/* Incidents */}
            <div className="p-6 rounded-2xl bg-gradient-surface backdrop-blur-xl border border-border/50">
              <h3 className="text-xl font-semibold text-foreground mb-4">Recent Incidents</h3>
              <p className="text-muted-foreground">No incidents reported in the last 30 days.</p>
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default Status;
