import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TrendingUp, ExternalLink, BarChart3, Activity } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { ValueType } from "recharts/types/component/DefaultTooltipContent";

// VERIFIED BACKTEST RESULTS -- real numbers from a real run, nothing else.
//
// What was here before: two fabricated "Download Verified Backtesting Reports"
// cards claiming a 2020-2024 scalping backtest at +287.4% return / 2.34 Sharpe
// / 67.2% win rate and a 2019-2024 swing backtest at +412.6% / 2.87 / 58.9%,
// each with a "Download Full Report (PDF)" button pointing at "#", under the
// line "Reports audited by third-party quantitative analysts."
//
// None of those backtests were ever run. No multi-year run exists, no PDF
// exists, and no third party has audited anything. Alongside them a
// `liveMetrics` array hardcoded "Current Week P&L +8.7%" and "Today's Win
// Rate 71.4%" as if they were live, and the equity chart fell back to a
// Math.random() curve -- all under a banner reading "VERIFIED PERFORMANCE".
// That is fabricated financial performance shown to prospective clients.
//
// Replaced with the only results that have actually been produced and
// checked: python_scripts/backtest/ against real exported MT5 history, with
// real per-bar spread, verified trade sidedness, and the scope stated plainly
// rather than implied away. Update these ONLY from a real run.
const verifiedBacktest = {
  symbol: "XAUUSD",
  period: "May-Aug 2026 (~90 days)",
  strategies: [
    { name: "Shaakuni SSM", trades: 132, winRate: "17.4%", expectancy: "+0.759R", profitFactor: "1.77" },
    { name: "Balance Fade", trades: 32, winRate: "37.5%", expectancy: "+0.620R", profitFactor: "1.96" },
    { name: "Swappy 3C", trades: 18, winRate: "33.3%", expectancy: "+0.223R", profitFactor: "1.33" },
    { name: "EMA Scalp Cross", trades: 5, winRate: "60.0%", expectancy: "+0.790R", profitFactor: "2.95" },
    { name: "Structural Swing", trades: 3, winRate: "66.7%", expectancy: "+1.654R", profitFactor: "5.93" },
  ],
};

interface LiveMetric {
  label: string;
  value: string;
}

interface EquityPoint {
  time: string;
  equity: number;
  balance: number;
}

export const LivePerformance = () => {
  const [equityData, setEquityData] = useState<EquityPoint[]>([]);
  const [liveMetrics, setLiveMetrics] = useState<LiveMetric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEquityData();
    loadLiveMetrics();

    const channel = supabase
      .channel('equity-updates')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'bot_heartbeats' },
        () => { loadEquityData(); loadLiveMetrics(); }
      )
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, []);

  // Real platform aggregates, or nothing. This replaces a hardcoded array
  // that presented invented figures ("Current Week P&L +8.7%", "Today's Win
  // Rate 71.4%") as live readings.
  const loadLiveMetrics = async () => {
    try {
      const { data: closed } = await supabase
        .from('trades')
        .select('profit_loss')
        .not('profit_loss', 'is', null)
        .limit(1000);

      const { count: openCount } = await supabase
        .from('trades')
        .select('id', { count: 'exact', head: true })
        .eq('status', 'open');

      const metrics: LiveMetric[] = [];
      if (closed && closed.length > 0) {
        const wins = closed.filter((t) => Number(t.profit_loss) > 0).length;
        metrics.push({ label: 'Closed Trades', value: String(closed.length) });
        metrics.push({ label: 'Win Rate', value: `${((wins / closed.length) * 100).toFixed(1)}%` });
      }
      if (typeof openCount === 'number') {
        metrics.push({ label: 'Open Positions', value: String(openCount) });
      }
      setLiveMetrics(metrics);
    } catch {
      setLiveMetrics([]);
    }
  };

  const loadEquityData = async () => {
    try {
      const { data, error } = await supabase
        .from('bot_heartbeats')
        .select('equity, balance, last_heartbeat')
        .not('equity', 'is', null)
        .order('last_heartbeat', { ascending: true })
        .limit(50);

      if (error) throw error;

      // Real data only. The previous version generated a synthetic
      // upward-drifting equity curve with Math.random() whenever fewer than
      // six real points existed, and rendered it under a "VERIFIED
      // PERFORMANCE" heading. An empty state is the honest answer.
      if (data && data.length > 5) {
        setEquityData(data.map((item) => ({
          time: new Date(item.last_heartbeat).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
          }),
          equity: Number(item.equity) || 0,
          balance: Number(item.balance) || 0,
        })));
      } else {
        setEquityData([]);
      }
    } catch (error) {
      console.error('Error loading equity data:', error);
      setEquityData([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section id="performance" className="py-16 sm:py-24 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-background via-primary/5 to-background"></div>
      
      <div className="container mx-auto px-4 sm:px-6 relative z-10">
        <div className="text-center mb-12 sm:mb-16">
          <div className="inline-block px-4 py-2 rounded-full bg-gradient-surface backdrop-blur-xl border border-primary/20 mb-6">
            <span className="text-sm font-medium text-primary">BACKTEST RESULTS</span>
          </div>
          <h2 className="font-display text-3xl sm:text-4xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
              Real Numbers,
            </span>{" "}
            <span className="bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Honestly Scoped
            </span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Every figure below comes from a real backtest run against real exported market
            history, with real per-bar spread applied. We show the scope of that testing plainly,
            including where it is still narrow. Past results never guarantee future performance.
          </p>
        </div>

        {/* Live Equity Curve Section */}
        <div className="mb-12">
          <Card className="p-6 bg-card/50 backdrop-blur-sm border-border/50">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xl font-bold mb-1">Live Account Performance</h3>
                <p className="text-sm text-muted-foreground">
                  {equityData.length > 0 ? 'Live • aggregated across connected accounts' : 'No live accounts are trading yet'}
                </p>
              </div>
            </div>
            
            {/* Live Metrics Grid */}
            {liveMetrics.length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                {liveMetrics.map((metric, index) => (
                  <div key={index} className="p-4 rounded-lg bg-background/50 border border-border/50">
                    <div className="text-sm text-muted-foreground mb-1">{metric.label}</div>
                    <span className="text-2xl font-bold">{metric.value}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Live Equity Curve */}
            <div className="w-full bg-gradient-to-br from-primary/5 to-accent/5 rounded-lg border border-border/50 p-4">
              {loading ? (
                <div className="aspect-video flex items-center justify-center">
                  <div className="text-center">
                    <Activity className="w-12 h-12 text-muted-foreground mx-auto mb-4 animate-pulse" />
                    <p className="text-muted-foreground">Loading live data...</p>
                  </div>
                </div>
              ) : equityData.length > 0 ? (
                <div className="h-[400px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart 
                      data={equityData}
                      margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" opacity={0.3} />
                      <XAxis 
                        dataKey="time" 
                        className="text-xs"
                        stroke="hsl(var(--muted-foreground))"
                        tick={{ fill: 'hsl(var(--muted-foreground))' }}
                        tickMargin={10}
                      />
                      <YAxis 
                        className="text-xs"
                        stroke="hsl(var(--muted-foreground))"
                        tick={{ fill: 'hsl(var(--muted-foreground))' }}
                        tickMargin={10}
                        domain={[(dataMin: number) => {
                          const padding = Math.max((dataMin * 0.001), 0.5);
                          return (dataMin - padding).toFixed(2);
                        }, (dataMax: number) => {
                          const padding = Math.max((dataMax * 0.001), 0.5);
                          return (dataMax + padding).toFixed(2);
                        }]}
                        tickFormatter={(value) => value.toFixed(2)}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          backgroundColor: 'hsl(var(--background))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                        }}
                        labelStyle={{ color: 'hsl(var(--foreground))' }}
                        formatter={(value: ValueType) => [`$${Number(value).toFixed(2)}`, '']}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="equity" 
                        stroke="hsl(var(--primary))" 
                        strokeWidth={3}
                        dot={{ fill: 'hsl(var(--primary))', r: 4 }}
                        activeDot={{ r: 6, fill: 'hsl(var(--primary))' }}
                        name="Equity (with floating P&L)"
                        connectNulls
                      />
                      <Line 
                        type="monotone" 
                        dataKey="balance" 
                        stroke="hsl(var(--accent))" 
                        strokeWidth={3}
                        dot={{ fill: 'hsl(var(--accent))', r: 4 }}
                        activeDot={{ r: 6, fill: 'hsl(var(--accent))' }}
                        name="Balance (realized P&L)"
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="flex gap-6 justify-center mt-4 text-sm">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-primary" />
                      <span className="text-muted-foreground">Equity (with floating P&L)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full bg-accent" />
                      <span className="text-muted-foreground">Balance (realized P&L)</span>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </Card>
        </div>

        {/* Telegram Community Section */}
        <div className="mb-12">
          <Card className="p-8 bg-gradient-to-br from-primary/10 via-accent/5 to-primary/10 backdrop-blur-sm border-primary/20 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
            <div className="relative z-10">
              <div className="flex flex-col md:flex-row items-center gap-6 md:gap-8">
                <div className="flex-shrink-0">
                  <div className="w-20 h-20 rounded-full bg-gradient-hero flex items-center justify-center shadow-glow">
                    <TrendingUp className="w-10 h-10 text-primary-foreground" />
                  </div>
                </div>
                <div className="flex-1 text-center md:text-left">
                  <h3 className="text-2xl sm:text-3xl font-bold mb-3">
                    Join Our Trading Community
                  </h3>
                  <p className="text-muted-foreground text-base sm:text-lg mb-4">
                    Connect with 1000+ traders, get real-time trade alerts, share strategies, and get instant support from our team and experienced community members.
                  </p>
                  <div className="flex flex-wrap gap-3 justify-center md:justify-start text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Activity className="w-4 h-4 text-primary" /> Live Trade Signals
                    </span>
                    <span className="flex items-center gap-1">
                      <BarChart3 className="w-4 h-4 text-primary" /> Strategy Discussions
                    </span>
                    <span className="flex items-center gap-1">
                      <ExternalLink className="w-4 h-4 text-primary" /> Market Updates
                    </span>
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <Button 
                    size="lg"
                    className="bg-gradient-hero shadow-glow hover:scale-105 transition-all group"
                    onClick={() => window.open("https://t.me/TradeBotXAlgo", "_blank")}
                  >
                    <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                    </svg>
                    Join Telegram
                    <ExternalLink className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Strategy Explanation */}
        <div className="mb-12">
          <Card className="p-6 sm:p-8 bg-card/50 backdrop-blur-sm border-border/50">
            <h3 className="text-2xl font-bold mb-6">How Our Strategies Work</h3>
            <div className="space-y-6">
              <div>
                <h4 className="text-lg font-semibold mb-3 text-primary">1. Multi-Timeframe Analysis</h4>
                <p className="text-muted-foreground">
                  Our AI analyzes price action across 5 different timeframes (M1, M5, M15, H1, H4) to identify high-probability setups. 
                  We use a proprietary confluence scoring system that requires 3+ timeframes to align before entry.
                </p>
              </div>
              
              <div>
                <h4 className="text-lg font-semibold mb-3 text-primary">2. Machine Learning Pattern Recognition</h4>
                <p className="text-muted-foreground">
                  Trained on 10+ years of historical data, our ML models identify 47 unique price patterns including 
                  support/resistance zones, trend continuations, and reversal signals. Each pattern is weighted by historical win rate.
                </p>
              </div>
              
              <div>
                <h4 className="text-lg font-semibold mb-3 text-primary">3. Adaptive Risk Management</h4>
                <p className="text-muted-foreground">
                  Position sizing automatically adjusts based on account equity, market volatility (ATR), and current drawdown. 
                  Maximum risk per trade: 1-2% of account. Daily loss limit: 5%. Weekly loss limit: 10%.
                </p>
              </div>
              
              <div>
                <h4 className="text-lg font-semibold mb-3 text-primary">4. Smart Exit Logic</h4>
                <p className="text-muted-foreground">
                  Combines trailing stops with profit targets. When trade reaches 1:1 R:R, stop moves to breakeven. 
                  Partial profit taking at 1:1.5 and 1:2.5 levels. Final position closed at 1:3 or trailing stop hit.
                </p>
              </div>
            </div>
          </Card>
        </div>

        {/* Verified backtest results -- real run, stated scope */}
        <div>
          <h3 className="text-2xl font-bold mb-2 text-center">Verified Backtest Results</h3>
          <p className="text-sm text-muted-foreground text-center mb-6 max-w-2xl mx-auto">
            {verifiedBacktest.symbol} · {verifiedBacktest.period} · real exported market history with
            per-bar spread applied and every trade's stop/target geometry checked.
          </p>

          <Card className="p-4 sm:p-6 bg-card/50 backdrop-blur-sm border-border/50">
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[560px]">
                <thead>
                  <tr className="text-muted-foreground border-b border-border/50">
                    <th className="text-left font-medium py-2 pr-4">Strategy</th>
                    <th className="text-right font-medium py-2 px-4">Trades</th>
                    <th className="text-right font-medium py-2 px-4">Win Rate</th>
                    <th className="text-right font-medium py-2 px-4">Expectancy</th>
                    <th className="text-right font-medium py-2 pl-4">Profit Factor</th>
                  </tr>
                </thead>
                <tbody>
                  {verifiedBacktest.strategies.map((row) => (
                    <tr key={row.name} className="border-b border-border/30 last:border-0">
                      <td className="py-3 pr-4 font-medium">{row.name}</td>
                      <td className="py-3 px-4 text-right tabular-nums">{row.trades}</td>
                      <td className="py-3 px-4 text-right tabular-nums">{row.winRate}</td>
                      <td className="py-3 px-4 text-right tabular-nums text-success">{row.expectancy}</td>
                      <td className="py-3 pl-4 text-right tabular-nums font-semibold text-primary">{row.profitFactor}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* The limitations, stated up front rather than buried. */}
          <div className="mt-6 p-4 sm:p-5 rounded-lg border border-border/50 bg-background/40 max-w-3xl mx-auto">
            <h4 className="text-sm font-semibold mb-2">What these numbers do and don't show</h4>
            <ul className="text-sm text-muted-foreground space-y-1.5 list-disc pl-5">
              <li>
                One instrument ({verifiedBacktest.symbol}) over roughly 90 days. They are not
                multi-year, multi-market, or walk-forward validated yet.
              </li>
              <li>
                The smaller samples (5 and 3 trades) are far too small to draw conclusions from.
                We show them rather than quietly omitting them.
              </li>
              <li>
                Backtest results, not a live track record. Live execution adds slippage, spread
                widening and latency that no backtest fully reproduces.
              </li>
              <li>Past performance never guarantees future results. Trading carries real risk of loss.</li>
            </ul>
          </div>
        </div>

      </div>
    </section>
  );
};
