import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Calculator } from "lucide-react";

interface RiskCalculatorProps {
  accountSize: number;
  onLotSizeChange?: (lotSize: number) => void;
}

export function RiskCalculator({ accountSize, onLotSizeChange }: RiskCalculatorProps) {
  const [riskPercent, setRiskPercent] = useState<string>("1");
  const [stopLossPips, setStopLossPips] = useState<string>("20");
  const [pipValue, setPipValue] = useState<string>("10");
  const [lotSize, setLotSize] = useState<number>(0);

  useEffect(() => {
    calculateLotSize();
  }, [riskPercent, stopLossPips, pipValue, accountSize]);

  const calculateLotSize = () => {
    const risk = parseFloat(riskPercent) || 0;
    const stopLoss = parseFloat(stopLossPips) || 1;
    const pv = parseFloat(pipValue) || 10;

    if (accountSize && risk && stopLoss && pv) {
      const riskAmount = (accountSize * risk) / 100;
      const calculatedLotSize = riskAmount / (stopLoss * pv);
      const roundedLotSize = Math.round(calculatedLotSize * 100) / 100;
      
      setLotSize(roundedLotSize);
      if (onLotSizeChange) {
        onLotSizeChange(roundedLotSize);
      }
    } else {
      setLotSize(0);
    }
  };

  const riskAmount = (accountSize * (parseFloat(riskPercent) || 0)) / 100;
  const potentialLoss = lotSize * (parseFloat(stopLossPips) || 0) * (parseFloat(pipValue) || 10);

  const formatNumber = (value: number): string => {
    return isNaN(value) || !isFinite(value) ? "0.00" : value.toFixed(2);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calculator className="h-5 w-5" />
          Risk Calculator
        </CardTitle>
        <CardDescription>
          Calculate optimal lot size based on your risk parameters
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="accountSize">Account Size ($)</Label>
            <Input
              id="accountSize"
              type="number"
              value={accountSize}
              disabled
              className="bg-muted"
              data-testid="input-account-size"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="riskPercent">Risk per Trade (%)</Label>
            <Input
              id="riskPercent"
              type="number"
              step="0.1"
              min="0"
              max="10"
              value={riskPercent}
              onChange={(e) => setRiskPercent(e.target.value)}
              aria-label="Risk percentage per trade"
              data-testid="input-risk-percent"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="stopLossPips">Stop Loss (Pips)</Label>
            <Input
              id="stopLossPips"
              type="number"
              step="1"
              min="1"
              value={stopLossPips}
              onChange={(e) => setStopLossPips(e.target.value)}
              aria-label="Stop loss in pips"
              data-testid="input-stop-loss-pips"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pipValue">Pip Value ($)</Label>
            <Input
              id="pipValue"
              type="number"
              step="0.1"
              min="0.1"
              value={pipValue}
              onChange={(e) => setPipValue(e.target.value)}
              aria-label="Value per pip in dollars"
              data-testid="input-pip-value"
            />
          </div>
        </div>

        <div className="border-t pt-4 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-muted-foreground">Risk Amount:</span>
            <span className="text-lg font-bold" data-testid="text-risk-amount">${formatNumber(riskAmount)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-muted-foreground">Recommended Lot Size:</span>
            <span className="text-2xl font-bold text-primary" data-testid="text-lot-size">{formatNumber(lotSize)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm font-medium text-muted-foreground">Potential Loss:</span>
            <span className="text-lg font-bold text-destructive" data-testid="text-potential-loss">${formatNumber(potentialLoss)}</span>
          </div>
        </div>

        <div className="bg-muted p-3 rounded-md text-sm text-muted-foreground">
          <p className="font-medium mb-1">Risk Management Tips:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>Never risk more than 1-2% per trade</li>
            <li>Use appropriate stop loss levels</li>
            <li>Consider market volatility when sizing positions</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
