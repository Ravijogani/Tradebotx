import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CheckCircle2, AlertTriangle, XCircle, Info } from "lucide-react";
import type { PlacedBlock } from "./StrategyBuilder";

interface ValidationResult {
  type: "error" | "warning" | "info" | "success";
  message: string;
  blockId?: string;
}

interface StrategyValidatorProps {
  blocks: PlacedBlock[];
  onBlockSelect?: (blockId: string) => void;
}

export const validateStrategy = (blocks: PlacedBlock[]): ValidationResult[] => {
  const results: ValidationResult[] = [];

  // Check if strategy has any blocks
  if (blocks.length === 0) {
    results.push({
      type: "error",
      message: "Strategy has no blocks. Add at least one indicator and one action."
    });
    return results;
  }

  // Group blocks by type
  const blocksByType = blocks.reduce((acc, block) => {
    const type = block.block.block_type;
    if (!acc[type]) acc[type] = [];
    acc[type].push(block);
    return acc;
  }, {} as Record<string, PlacedBlock[]>);

  // Must have at least one indicator
  if (!blocksByType.indicator?.length) {
    results.push({
      type: "error",
      message: "Strategy must have at least one indicator (RSI, MACD, etc.)"
    });
  }

  // Must have at least one action
  if (!blocksByType.action?.length) {
    results.push({
      type: "error",
      message: "Strategy must have at least one action (Market Order, Stop Loss, etc.)"
    });
  }

  // Should have at least one condition
  if (!blocksByType.condition?.length) {
    results.push({
      type: "warning",
      message: "Consider adding conditions to define entry/exit rules"
    });
  }

  // Check for orphaned blocks (no connections)
  const connectedBlocks = new Set<string>();
  blocks.forEach(block => {
    block.connections.forEach(id => connectedBlocks.add(id));
  });

  const hasConnectionsFrom = new Set<string>();
  blocks.forEach(block => {
    if (block.connections.length > 0) {
      hasConnectionsFrom.add(block.id);
    }
  });

  // Check for blocks with no incoming or outgoing connections
  const orphanedBlocks = blocks.filter(block => 
    !connectedBlocks.has(block.id) && !hasConnectionsFrom.has(block.id)
  );

  if (orphanedBlocks.length > 1) {
    results.push({
      type: "warning",
      message: `${orphanedBlocks.length} blocks are not connected. Connect them to define strategy flow.`
    });
  }

  // Check for risk management
  const hasStopLoss = blocks.some(b => b.block.name.toLowerCase().includes("stop loss"));
  const hasTakeProfit = blocks.some(b => b.block.name.toLowerCase().includes("take profit"));

  if (!hasStopLoss) {
    results.push({
      type: "warning",
      message: "No Stop Loss block found. Consider adding risk management."
    });
  }

  if (!hasTakeProfit) {
    results.push({
      type: "info",
      message: "No Take Profit block found. You may want to define exit targets."
    });
  }

  // Check for duplicate indicators with same config
  const indicatorConfigs = new Map<string, PlacedBlock>();
  blocksByType.indicator?.forEach(block => {
    const key = `${block.block.name}-${JSON.stringify(block.config)}`;
    if (indicatorConfigs.has(key)) {
      results.push({
        type: "warning",
        message: `Duplicate ${block.block.name} with same configuration found`,
        blockId: block.id
      });
    } else {
      indicatorConfigs.set(key, block);
    }
  });

  // If no errors, add success message
  if (!results.some(r => r.type === "error")) {
    results.push({
      type: "success",
      message: "Strategy structure is valid and ready for review"
    });
  }

  return results;
};

export const StrategyValidator = ({ blocks, onBlockSelect }: StrategyValidatorProps) => {
  const results = validateStrategy(blocks);

  const getIcon = (type: ValidationResult["type"]) => {
    switch (type) {
      case "error": return <XCircle className="h-4 w-4 text-destructive" />;
      case "warning": return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case "info": return <Info className="h-4 w-4 text-blue-500" />;
      case "success": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    }
  };

  const getBadgeVariant = (type: ValidationResult["type"]) => {
    switch (type) {
      case "error": return "destructive";
      case "warning": return "outline";
      case "info": return "secondary";
      case "success": return "default";
    }
  };

  const errorCount = results.filter(r => r.type === "error").length;
  const warningCount = results.filter(r => r.type === "warning").length;

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-lg">
        <span className="text-sm font-medium">Validation</span>
        {errorCount > 0 && (
          <Badge variant="destructive" className="text-xs">
            {errorCount} error{errorCount > 1 ? "s" : ""}
          </Badge>
        )}
        {warningCount > 0 && (
          <Badge variant="outline" className="text-xs text-yellow-600">
            {warningCount} warning{warningCount > 1 ? "s" : ""}
          </Badge>
        )}
        {errorCount === 0 && warningCount === 0 && (
          <Badge variant="default" className="text-xs bg-green-600">Valid</Badge>
        )}
      </div>

      {/* Results List */}
      <ScrollArea className="h-[200px]">
        <div className="space-y-2 px-1">
          {results.map((result, index) => (
            <div
              key={index}
              className={`flex items-start gap-2 p-2 rounded-lg text-sm ${
                result.blockId ? "cursor-pointer hover:bg-muted/50" : ""
              }`}
              onClick={() => result.blockId && onBlockSelect?.(result.blockId)}
            >
              {getIcon(result.type)}
              <span className="flex-1">{result.message}</span>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
};
