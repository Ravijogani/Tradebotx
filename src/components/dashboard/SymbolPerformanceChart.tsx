import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp, TrendingDown } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

interface SymbolPerformance {
  symbol: string;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_pnl: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
}

export default function SymbolPerformanceChart() {
  const [data, setData] = useState<SymbolPerformance[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSymbolPerformance();
  }, []);

  const loadSymbolPerformance = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data: symbolData, error } = await supabase
        .from('symbol_performance')
        .select('*')
        .eq('user_id', user.id)
        .order('total_pnl', { ascending: false });

      if (error) throw error;
      setData(symbolData || []);
    } catch (error) {
      console.error('Error loading symbol performance:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-4 sm:p-6">
        <Skeleton className="h-6 sm:h-8 w-48 sm:w-64 mb-4" />
        <Skeleton className="h-48 sm:h-64 w-full" />
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-4">Symbol Performance</h3>
        <p className="text-sm text-muted-foreground">No symbol data available yet.</p>
      </Card>
    );
  }

  return (
    <Card className="p-4 sm:p-6">
      <h3 className="text-base sm:text-lg font-semibold mb-4 sm:mb-6">Symbol Performance Analysis</h3>
      
      <div className="mb-4 sm:mb-6 w-full overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
        <div className="min-w-[400px]">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="symbol" className="text-xs" tick={{ fontSize: 12 }} />
              <YAxis className="text-xs" tick={{ fontSize: 12 }} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '6px',
                  fontSize: '12px'
                }}
                formatter={(value: number) => `$${value.toFixed(2)}`}
              />
              <Bar dataKey="total_pnl" radius={[4, 4, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.total_pnl >= 0 ? 'hsl(var(--success))' : 'hsl(var(--destructive))'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <ScrollArea className="h-[400px]">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 pr-4">
          {data.map((symbol) => (
            <Card key={symbol.symbol} className="p-3 sm:p-4 bg-muted/30">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-sm sm:text-base">{symbol.symbol}</h4>
                {symbol.total_pnl >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-success flex-shrink-0" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-destructive flex-shrink-0" />
                )}
              </div>
              <div className="space-y-1 text-xs sm:text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total P&L:</span>
                  <span className={symbol.total_pnl >= 0 ? "text-success font-medium" : "text-destructive font-medium"}>
                    ${symbol.total_pnl.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Win Rate:</span>
                  <span>{symbol.win_rate.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Trades:</span>
                  <span className="truncate ml-2">{symbol.total_trades} ({symbol.winning_trades}W/{symbol.losing_trades}L)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Win:</span>
                  <span className="text-success">${symbol.avg_win.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Loss:</span>
                  <span className="text-destructive">${symbol.avg_loss.toFixed(2)}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </ScrollArea>
    </Card>
  );
}