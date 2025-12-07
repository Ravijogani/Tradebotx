import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { 
  TrendingUp, Activity, BarChart, Target, Clock, 
  Shield, ShoppingCart, XCircle, Filter, Crosshair,
  ArrowUpDown, AlignVerticalJustifyCenter, CandlestickChart,
  GitMerge, GitBranch, RotateCcw, Shuffle, RefreshCw,
  Eye, MessageCircle, Layers, Link, Search, Percent
} from "lucide-react";
import type { StrategyBlock } from "./StrategyBuilder";

interface BlockPaletteProps {
  blocks: StrategyBlock[];
  onDragStart: (block: StrategyBlock) => void;
}

const iconMap: Record<string, any> = {
  TrendingUp, Activity, BarChart, Target, Clock, Shield,
  ShoppingCart, XCircle, Filter, Crosshair, ArrowUpDown,
  AlignVerticalJustifyCenter, CandlestickChart, GitMerge,
  GitBranch, RotateCcw, Shuffle, RefreshCw, Eye,
  MessageCircle, Layers, Link, Percent
};

const categoryLabels: Record<string, string> = {
  indicator: "Indicators",
  condition: "Conditions",
  action: "Actions",
  filter: "Filters",
  logic: "Logic Gates",
  ai: "AI-Powered",
  portfolio: "Portfolio"
};

const categoryColors: Record<string, string> = {
  indicator: "bg-blue-500",
  condition: "bg-yellow-500",
  action: "bg-green-500",
  filter: "bg-purple-500",
  logic: "bg-orange-500",
  ai: "bg-pink-500",
  portfolio: "bg-cyan-500"
};

export const BlockPalette = ({ blocks, onDragStart }: BlockPaletteProps) => {
  const [searchQuery, setSearchQuery] = useState("");
  
  const filteredBlocks = blocks.filter(block =>
    block.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    block.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const groupedBlocks = filteredBlocks.reduce((acc, block) => {
    const type = block.category || block.block_type;
    if (!acc[type]) acc[type] = [];
    acc[type].push(block);
    return acc;
  }, {} as Record<string, StrategyBlock[]>);

  const handleDragStart = (e: React.DragEvent, block: StrategyBlock) => {
    e.dataTransfer.setData("application/json", JSON.stringify(block));
    e.dataTransfer.effectAllowed = "copy";
    onDragStart(block);
  };

  const categoryOrder = ['indicator', 'condition', 'filter', 'action', 'logic', 'ai', 'portfolio'];
  const sortedCategories = Object.keys(groupedBlocks).sort((a, b) => {
    const aIdx = categoryOrder.indexOf(a);
    const bIdx = categoryOrder.indexOf(b);
    return (aIdx === -1 ? 999 : aIdx) - (bIdx === -1 ? 999 : bIdx);
  });

  return (
    <div className="flex-1 flex flex-col">
      <div className="p-2 border-b border-border">
        <div className="relative">
          <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search blocks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-7 h-8 text-xs"
          />
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-4">
          {sortedCategories.map((type) => (
            <div key={type}>
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-2 h-2 rounded-full ${categoryColors[type] || 'bg-gray-500'}`} />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {categoryLabels[type] || type}
                </span>
                <Badge variant="secondary" className="text-[10px] px-1">
                  {groupedBlocks[type].length}
                </Badge>
              </div>
              <div className="space-y-1">
                {groupedBlocks[type].map((block) => {
                  const Icon = iconMap[block.icon] || Activity;
                  const colorClass = categoryColors[type] || 'bg-gray-500';
                  return (
                    <div
                      key={block.id}
                      draggable
                      onDragStart={(e) => handleDragStart(e, block)}
                      className="flex items-center gap-2 p-2 rounded-lg border border-border bg-card hover:bg-muted/50 cursor-grab active:cursor-grabbing transition-colors"
                    >
                      <div className={`p-1.5 rounded ${colorClass}/10`}>
                        <Icon className={`h-3.5 w-3.5 ${colorClass.replace('bg-', 'text-')}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="text-xs font-medium truncate">{block.name}</span>
                          {block.is_premium && (
                            <Badge variant="outline" className="text-[10px] px-1 py-0 border-yellow-500 text-yellow-500">
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
    </div>
  );
};