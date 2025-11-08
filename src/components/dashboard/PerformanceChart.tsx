import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabase } from "@/integrations/supabase/client";
import { Line, LineChart, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from "recharts";
import { Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";

type TimeRange = "7d" | "30d" | "90d" | "1y";

export const PerformanceChart = () => {
  const [data, setData] = useState<any[]>([]);
  const [timeRange, setTimeRange] = useState<TimeRange>("30d");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPerformanceData();
  }, [timeRange]);

  const loadPerformanceData = async () => {
    setLoading(true);
    const daysMap = { "7d": 7, "30d": 30, "90d": 90, "1y": 365 };
    const days = daysMap[timeRange];
    
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    const { data: trades } = await supabase
      .from("trades")
      .select("*")
      .gte("opened_at", startDate.toISOString())
      .order("opened_at", { ascending: true });

    if (trades) {
      // Group trades by date and calculate cumulative P&L
      const dailyData = new Map<string, number>();
      let cumulativePL = 0;

      trades.forEach((trade) => {
        const date = new Date(trade.opened_at).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        });
        const pl = parseFloat(String(trade.profit_loss || 0));
        cumulativePL += pl;
        dailyData.set(date, cumulativePL);
      });

      const chartData = Array.from(dailyData.entries()).map(([date, pl]) => ({
        date,
        value: pl,
      }));

      setData(chartData);
    }
    setLoading(false);
  };

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="w-5 h-5 text-primary" />
              Performance Tracker
            </CardTitle>
            <CardDescription className="mt-1">
              Cumulative profit/loss over time
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {(["7d", "30d", "90d", "1y"] as TimeRange[]).map((range) => (
              <Button
                key={range}
                variant={timeRange === range ? "default" : "outline"}
                size="sm"
                onClick={() => setTimeRange(range)}
              >
                {range}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-[300px] flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">Loading chart...</div>
          </div>
        ) : data.length === 0 ? (
          <div className="h-[300px] flex items-center justify-center">
            <p className="text-muted-foreground">No trading data available for this period</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis 
                dataKey="date" 
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
              />
              <YAxis 
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
                tickFormatter={(value) => `$${value.toFixed(0)}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  padding: "8px 12px",
                }}
                labelStyle={{ color: "hsl(var(--foreground))" }}
                formatter={(value: any) => [`$${value.toFixed(2)}`, "P&L"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                fill="url(#colorValue)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
};
