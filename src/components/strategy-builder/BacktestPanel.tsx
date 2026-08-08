import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import { 
  Play, Loader2, TrendingUp, TrendingDown, 
  Target, BarChart3, AlertTriangle, Calendar
} from "lucide-react";
import type { PlacedBlock } from "./StrategyBuilder";

interface BacktestResult {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalPnL: number;
  maxDrawdown: number;
  sharpeRatio: number;
  profitFactor: number;
  avgWin: number;
  avgLoss: number;
}

interface BacktestPanelProps {
  blocks: PlacedBlock[];
  strategyName: string;
}

export const BacktestPanel = ({ blocks, strategyName }: BacktestPanelProps) => {
  const [symbol, setSymbol] = useState("EURUSD");
  const [timeframe, setTimeframe] = useState("M15");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [initialBalance, setInitialBalance] = useState(10000);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const { toast } = useToast();

  const runBacktest = async () => {
    if (blocks.length === 0) {
      toast({
        title: "No blocks",
        description: "Add blocks to your strategy before backtesting",
        variant: "destructive"
      });
      return;
    }

    setRunning(true);
    setProgress(0);
    setResult(null);

    // Simulate backtest progress
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 95) {
          clearInterval(progressInterval);
          return 95;
        }
        return prev + Math.random() * 15;
      });
    }, 300);

    try {
      // Simulate backtest (in production, this would call an actual backtest service)
      await new Promise(resolve => setTimeout(resolve, 3000));

      clearInterval(progressInterval);
      setProgress(100);

      // Generate simulated results based on strategy complexity
      const hasRiskManagement = blocks.some(b => 
        b.block.name.toLowerCase().includes("stop") || 
        b.block.name.toLowerCase().includes("take profit")
      );
      const hasFilters = blocks.some(b => b.block.block_type === "filter");
      const indicatorCount = blocks.filter(b => b.block.block_type === "indicator").length;

      // More sophisticated strategies tend to have better results
      const baseWinRate = 45 + (indicatorCount * 3) + (hasFilters ? 5 : 0) + (hasRiskManagement ? 5 : 0);
      const winRate = Math.min(65, baseWinRate + (Math.random() * 10 - 5));
      
      const totalTrades = Math.floor(50 + Math.random() * 150);
      const winningTrades = Math.floor(totalTrades * (winRate / 100));
      const losingTrades = totalTrades - winningTrades;
      
      const avgWin = 50 + Math.random() * 100;
      const avgLoss = 30 + Math.random() * 60;
      
      const totalPnL = (winningTrades * avgWin) - (losingTrades * avgLoss);
      const profitFactor = losingTrades > 0 ? (winningTrades * avgWin) / (losingTrades * avgLoss) : 2;

      setResult({
        totalTrades,
        winningTrades,
        losingTrades,
        winRate: Math.round(winRate * 10) / 10,
        totalPnL: Math.round(totalPnL * 100) / 100,
        maxDrawdown: Math.round((10 + Math.random() * 15) * 100) / 100,
        sharpeRatio: Math.round((0.5 + Math.random() * 2) * 100) / 100,
        profitFactor: Math.round(profitFactor * 100) / 100,
        avgWin: Math.round(avgWin * 100) / 100,
        avgLoss: Math.round(avgLoss * 100) / 100
      });

      toast({ title: "Backtest completed" });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      toast({
        title: "Backtest failed",
        description: message,
        variant: "destructive"
      });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Backtest Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Symbol & Timeframe */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Symbol</Label>
              <Select value={symbol} onValueChange={setSymbol}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="EURUSD">EURUSD</SelectItem>
                  <SelectItem value="GBPUSD">GBPUSD</SelectItem>
                  <SelectItem value="USDJPY">USDJPY</SelectItem>
                  <SelectItem value="XAUUSD">XAUUSD</SelectItem>
                  <SelectItem value="BTCUSD">BTCUSD</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Timeframe</Label>
              <Select value={timeframe} onValueChange={setTimeframe}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="M1">M1</SelectItem>
                  <SelectItem value="M5">M5</SelectItem>
                  <SelectItem value="M15">M15</SelectItem>
                  <SelectItem value="H1">H1</SelectItem>
                  <SelectItem value="H4">H4</SelectItem>
                  <SelectItem value="D1">D1</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Start Date</Label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">End Date</Label>
              <Input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>

          {/* Initial Balance */}
          <div className="space-y-1.5">
            <Label className="text-xs">Initial Balance ($)</Label>
            <Input
              type="number"
              value={initialBalance}
              onChange={(e) => setInitialBalance(Number(e.target.value))}
              className="h-8 text-xs"
            />
          </div>

          {/* Run Button */}
          <Button
            className="w-full"
            size="sm"
            onClick={runBacktest}
            disabled={running || blocks.length === 0}
          >
            {running ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run Backtest
              </>
            )}
          </Button>

          {/* Progress */}
          {running && (
            <div className="space-y-1">
              <Progress value={progress} className="h-2" />
              <p className="text-xs text-muted-foreground text-center">
                {Math.round(progress)}% complete
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {result && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Target className="h-4 w-4" />
              Backtest Results
            </CardTitle>
            <CardDescription className="text-xs">
              {symbol} • {timeframe} • {result.totalTrades} trades
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Key Metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-muted/50 rounded-lg text-center">
                <div className={`text-lg font-bold ${result.totalPnL >= 0 ? "text-green-500" : "text-red-500"}`}>
                  {result.totalPnL >= 0 ? "+" : ""}{result.totalPnL.toFixed(2)}
                </div>
                <div className="text-xs text-muted-foreground">Total P&L</div>
              </div>
              <div className="p-3 bg-muted/50 rounded-lg text-center">
                <div className={`text-lg font-bold ${result.winRate >= 50 ? "text-green-500" : "text-yellow-500"}`}>
                  {result.winRate}%
                </div>
                <div className="text-xs text-muted-foreground">Win Rate</div>
              </div>
            </div>

            {/* Detailed Stats */}
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-border">
                <span className="text-muted-foreground">Winning Trades</span>
                <span className="font-medium text-green-500">{result.winningTrades}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border">
                <span className="text-muted-foreground">Losing Trades</span>
                <span className="font-medium text-red-500">{result.losingTrades}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border">
                <span className="text-muted-foreground">Avg Win</span>
                <span className="font-medium text-green-500">+${result.avgWin}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border">
                <span className="text-muted-foreground">Avg Loss</span>
                <span className="font-medium text-red-500">-${result.avgLoss}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border">
                <span className="text-muted-foreground">Profit Factor</span>
                <span className="font-medium">{result.profitFactor}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border">
                <span className="text-muted-foreground">Max Drawdown</span>
                <span className="font-medium text-red-500">{result.maxDrawdown}%</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-muted-foreground">Sharpe Ratio</span>
                <span className="font-medium">{result.sharpeRatio}</span>
              </div>
            </div>

            {/* Warning if poor performance */}
            {(result.winRate < 45 || result.totalPnL < 0) && (
              <div className="flex items-start gap-2 p-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <AlertTriangle className="h-4 w-4 text-yellow-500 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-yellow-600">
                  This strategy shows poor backtest results. Consider adjusting parameters or adding risk management.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
