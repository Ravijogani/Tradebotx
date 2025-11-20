import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertTriangle, TrendingUp, Activity, Target } from "lucide-react";

interface RiskMetrics {
  sharpeRatio: number;
  maxDrawdown: number;
  sortinoRatio: number;
  profitFactor: number;
  recoveryFactor: number;
  expectancy: number;
}

export default function RiskMetricsCard() {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRiskMetrics();
  }, []);

  const loadRiskMetrics = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Get all closed trades
      const { data: trades, error } = await supabase
        .from('trades')
        .select('profit_loss, closed_at')
        .eq('user_id', user.id)
        .eq('status', 'closed')
        .order('closed_at', { ascending: true });

      if (error) throw error;
      if (!trades || trades.length === 0) {
        setLoading(false);
        return;
      }

      // Calculate metrics
      const returns = trades.map(t => t.profit_loss || 0);
      const positiveReturns = returns.filter(r => r > 0);
      const negativeReturns = returns.filter(r => r < 0);
      
      // Sharpe Ratio (simplified - assuming risk-free rate = 0)
      const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
      const stdDev = Math.sqrt(
        returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
      );
      const sharpeRatio = stdDev !== 0 ? avgReturn / stdDev : 0;

      // Max Drawdown
      let peak = 0;
      let maxDrawdown = 0;
      let cumulative = 0;
      trades.forEach(trade => {
        cumulative += trade.profit_loss || 0;
        if (cumulative > peak) peak = cumulative;
        const drawdown = peak - cumulative;
        if (drawdown > maxDrawdown) maxDrawdown = drawdown;
      });

      // Sortino Ratio (only considers downside deviation)
      const downStdDev = Math.sqrt(
        negativeReturns.reduce((sum, r) => sum + Math.pow(r, 2), 0) / (negativeReturns.length || 1)
      );
      const sortinoRatio = downStdDev !== 0 ? avgReturn / downStdDev : 0;

      // Profit Factor
      const totalWins = positiveReturns.reduce((a, b) => a + b, 0);
      const totalLosses = Math.abs(negativeReturns.reduce((a, b) => a + b, 0));
      const profitFactor = totalLosses !== 0 ? totalWins / totalLosses : totalWins > 0 ? 999 : 0;

      // Recovery Factor
      const totalProfit = returns.reduce((a, b) => a + b, 0);
      const recoveryFactor = maxDrawdown !== 0 ? totalProfit / maxDrawdown : 0;

      // Expectancy
      const winRate = positiveReturns.length / returns.length;
      const avgWin = totalWins / (positiveReturns.length || 1);
      const avgLoss = totalLosses / (negativeReturns.length || 1);
      const expectancy = (winRate * avgWin) - ((1 - winRate) * avgLoss);

      setMetrics({
        sharpeRatio: Number(sharpeRatio.toFixed(2)),
        maxDrawdown: Number(maxDrawdown.toFixed(2)),
        sortinoRatio: Number(sortinoRatio.toFixed(2)),
        profitFactor: Number(profitFactor.toFixed(2)),
        recoveryFactor: Number(recoveryFactor.toFixed(2)),
        expectancy: Number(expectancy.toFixed(2))
      });
    } catch (error) {
      console.error('Error loading risk metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-4 sm:p-6">
        <Skeleton className="h-6 sm:h-8 w-36 sm:w-48 mb-4" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-20 sm:h-24" />
          ))}
        </div>
      </Card>
    );
  }

  if (!metrics) {
    return (
      <Card className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold mb-4">Risk Metrics</h3>
        <p className="text-sm text-muted-foreground">Not enough trade data to calculate risk metrics.</p>
      </Card>
    );
  }

  const getRiskColor = (value: number, metric: string) => {
    switch (metric) {
      case 'sharpe':
      case 'sortino':
        return value >= 1 ? 'text-success' : value >= 0 ? 'text-warning' : 'text-destructive';
      case 'profitFactor':
        return value >= 2 ? 'text-success' : value >= 1 ? 'text-warning' : 'text-destructive';
      case 'maxDrawdown':
        return value <= 100 ? 'text-success' : value <= 300 ? 'text-warning' : 'text-destructive';
      default:
        return value >= 0 ? 'text-success' : 'text-destructive';
    }
  };

  return (
    <Card className="p-4 sm:p-6">
      <h3 className="text-base sm:text-lg font-semibold mb-4 sm:mb-6">Advanced Risk Metrics</h3>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
        <Card className="p-3 sm:p-4 bg-muted/30">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground">Sharpe Ratio</span>
          </div>
          <p className={`text-xl sm:text-2xl font-bold ${getRiskColor(metrics.sharpeRatio, 'sharpe')}`}>
            {metrics.sharpeRatio}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {metrics.sharpeRatio >= 1 ? 'Excellent' : metrics.sharpeRatio >= 0 ? 'Good' : 'Poor'}
          </p>
        </Card>

        <Card className="p-3 sm:p-4 bg-muted/30">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground">Max Drawdown</span>
          </div>
          <p className={`text-xl sm:text-2xl font-bold ${getRiskColor(metrics.maxDrawdown, 'maxDrawdown')}`}>
            ${metrics.maxDrawdown}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {metrics.maxDrawdown <= 100 ? 'Low Risk' : metrics.maxDrawdown <= 300 ? 'Moderate' : 'High Risk'}
          </p>
        </Card>

        <Card className="p-3 sm:p-4 bg-muted/30">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground">Sortino Ratio</span>
          </div>
          <p className={`text-xl sm:text-2xl font-bold ${getRiskColor(metrics.sortinoRatio, 'sortino')}`}>
            {metrics.sortinoRatio}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Downside risk-adjusted</p>
        </Card>

        <Card className="p-3 sm:p-4 bg-muted/30">
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground">Profit Factor</span>
          </div>
          <p className={`text-xl sm:text-2xl font-bold ${getRiskColor(metrics.profitFactor, 'profitFactor')}`}>
            {metrics.profitFactor}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {metrics.profitFactor >= 2 ? 'Excellent' : metrics.profitFactor >= 1 ? 'Profitable' : 'Losing'}
          </p>
        </Card>

        <Card className="p-3 sm:p-4 bg-muted/30">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground">Recovery Factor</span>
          </div>
          <p className={`text-xl sm:text-2xl font-bold ${metrics.recoveryFactor >= 0 ? 'text-success' : 'text-destructive'}`}>
            {metrics.recoveryFactor}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Profit/Max Drawdown</p>
        </Card>

        <Card className="p-3 sm:p-4 bg-muted/30">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary flex-shrink-0" />
            <span className="text-xs sm:text-sm font-medium text-muted-foreground">Expectancy</span>
          </div>
          <p className={`text-xl sm:text-2xl font-bold ${metrics.expectancy >= 0 ? 'text-success' : 'text-destructive'}`}>
            ${metrics.expectancy}
          </p>
          <p className="text-xs text-muted-foreground mt-1">Expected per trade</p>
        </Card>
      </div>

      <div className="mt-4 sm:mt-6 p-3 sm:p-4 bg-muted/20 rounded-lg">
        <h4 className="font-medium mb-2 text-sm sm:text-base">Risk Assessment</h4>
        <div className="space-y-2 text-xs sm:text-sm">
          <p className="text-muted-foreground">
            • <strong>Sharpe Ratio:</strong> Measures risk-adjusted returns. Above 1 is good, above 2 is excellent.
          </p>
          <p className="text-muted-foreground">
            • <strong>Max Drawdown:</strong> Largest peak-to-trough decline. Lower is better for capital preservation.
          </p>
          <p className="text-muted-foreground">
            • <strong>Profit Factor:</strong> Gross profit / Gross loss. Above 1.5 indicates a profitable system.
          </p>
        </div>
      </div>
    </Card>
  );
}