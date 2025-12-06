import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { 
  TrendingUp, Activity, BarChart, Target, Clock, 
  Shield, ShoppingCart, XCircle, Filter, Crosshair,
  ArrowUpDown, AlignVerticalJustifyCenter, CandlestickChart
} from "lucide-react";
import type { StrategyBlock } from "./StrategyBuilder";

interface BlockPaletteProps {
  blocks: StrategyBlock[];
  onDragStart: (block: StrategyBlock) => void;
}

const iconMap: Record<string, any> = {
  TrendingUp,
  Activity,
  BarChart,
  Target,
  Clock,
  Shield,
  ShoppingCart,
  XCircle,
  Filter,
  Crosshair,
  ArrowUpDown,
  AlignVerticalJustifyCenter,
  CandlestickChart
};

const categoryLabels: Record<string, string> = {
  indicator: "Indicators",
  condition: "Conditions",
  action: "Actions",
  filter: "Filters"
};

const categoryColors: Record<string, string> = {
  indicator: "bg-blue-500",
  condition: "bg-yellow-500",
  action: "bg-green-500",
  filter: "bg-purple-500"
};

export const BlockPalette = ({ blocks, onDragStart }: BlockPaletteProps) => {
  const groupedBlocks = blocks.reduce((acc, block) => {
    const type = block.block_type;
    if (!acc[type]) acc[type] = [];
    acc[type].push(block);
    return acc;
  }, {} as Record<string, StrategyBlock[]>);

  const handleDragStart = (e: React.DragEvent, block: StrategyBlock) => {
    e.dataTransfer.setData("application/json", JSON.stringify(block));
    e.dataTransfer.effectAllowed = "copy";
    onDragStart(block);
  };

  return (
    <ScrollArea className="flex-1">
      <div className="p-3 space-y-4">
        {Object.entries(groupedBlocks).map(([type, typeBlocks]) => (
          <div key={type}>
            <div className="flex items-center gap-2 mb-2">
              <div className={`w-2 h-2 rounded-full ${categoryColors[type]}`} />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {categoryLabels[type] || type}
              </span>
            </div>
            <div className="space-y-1">
              {typeBlocks.map((block) => {
                const Icon = iconMap[block.icon] || Activity;
                return (
                  <div
                    key={block.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, block)}
                    className="flex items-center gap-2 p-2 rounded-lg border border-border bg-card hover:bg-muted/50 cursor-grab active:cursor-grabbing transition-colors"
                  >
                    <div className={`p-1.5 rounded ${categoryColors[type]}/10`}>
                      <Icon className={`h-3.5 w-3.5 ${categoryColors[type].replace('bg-', 'text-')}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-medium truncate">{block.name}</span>
                        {block.is_premium && (
                          <Badge variant="outline" className="text-[10px] px-1 py-0">
                            Pro
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  );
};