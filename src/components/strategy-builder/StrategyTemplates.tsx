import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { 
  BookOpen, TrendingUp, Shield, Zap, BarChart3, 
  Target, ArrowRight, Star, Clock, Activity
} from "lucide-react";
import type { StrategyBlock, PlacedBlock } from "./StrategyBuilder";
import type { LucideIcon } from "lucide-react";

interface StrategyTemplatesProps {
  availableBlocks: StrategyBlock[];
  onTemplateSelect: (blocks: PlacedBlock[]) => void;
}

interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  category: "beginner" | "intermediate" | "advanced";
  icon: LucideIcon;
  popularity: number;
  blocks: {
    blockType: string;
    blockName: string;
    // Block-type-specific (RSI period, order type, percent thresholds, ...) —
    // matches the same Record<string, unknown> pattern used for
    // PlacedBlock["config"] in StrategyBuilder.tsx.
    config: Record<string, unknown>;
    position: { x: number; y: number };
  }[];
  expectedReturn: string;
  riskLevel: "low" | "medium" | "high";
}

const templates: StrategyTemplate[] = [
  {
    id: "rsi-oversold",
    name: "RSI Oversold Bounce",
    description: "Buy when RSI drops below 30 and price starts recovering. Great for mean reversion trading.",
    category: "beginner",
    icon: TrendingUp,
    popularity: 4.5,
    expectedReturn: "15-25%",
    riskLevel: "low",
    blocks: [
      { blockType: "indicator", blockName: "RSI", config: { period: 14, overbought: 70, oversold: 30 }, position: { x: 50, y: 50 } },
      { blockType: "condition", blockName: "Price Condition", config: { condition: "less_than", value: 30 }, position: { x: 250, y: 50 } },
      { blockType: "action", blockName: "Buy", config: { order_type: "market", position_size: "1%" }, position: { x: 450, y: 50 } },
      { blockType: "action", blockName: "Stop Loss", config: { type: "percent", value: 2 }, position: { x: 450, y: 170 } },
      { blockType: "action", blockName: "Take Profit", config: { type: "percent", value: 4 }, position: { x: 450, y: 290 } },
    ]
  },
  {
    id: "macd-crossover",
    name: "MACD Crossover",
    description: "Classic momentum strategy that enters when MACD line crosses above signal line.",
    category: "beginner",
    icon: Activity,
    popularity: 4.2,
    expectedReturn: "20-35%",
    riskLevel: "medium",
    blocks: [
      { blockType: "indicator", blockName: "MACD", config: { fast: 12, slow: 26, signal: 9 }, position: { x: 50, y: 50 } },
      { blockType: "condition", blockName: "Crossover", config: { type: "bullish_crossover" }, position: { x: 250, y: 50 } },
      { blockType: "filter", blockName: "Trend Filter", config: { trend: "bullish" }, position: { x: 250, y: 170 } },
      { blockType: "action", blockName: "Buy", config: { order_type: "market", position_size: "2%" }, position: { x: 450, y: 110 } },
    ]
  },
  {
    id: "bollinger-squeeze",
    name: "Bollinger Squeeze Breakout",
    description: "Captures explosive moves when Bollinger Bands contract and then expand with price breakout.",
    category: "intermediate",
    icon: Zap,
    popularity: 4.7,
    expectedReturn: "30-50%",
    riskLevel: "high",
    blocks: [
      { blockType: "indicator", blockName: "Bollinger Bands", config: { period: 20, deviation: 2 }, position: { x: 50, y: 50 } },
      { blockType: "condition", blockName: "Squeeze Condition", config: { bandwidth_threshold: 0.1 }, position: { x: 250, y: 50 } },
      { blockType: "condition", blockName: "Breakout", config: { direction: "above_upper_band" }, position: { x: 250, y: 170 } },
      { blockType: "action", blockName: "Buy", config: { order_type: "market", position_size: "1.5%" }, position: { x: 450, y: 110 } },
    ]
  },
  {
    id: "multi-timeframe",
    name: "Multi-Timeframe Trend Following",
    description: "Aligns multiple timeframes to ensure trading in the direction of the major trend.",
    category: "advanced",
    icon: BarChart3,
    popularity: 4.8,
    expectedReturn: "25-40%",
    riskLevel: "medium",
    blocks: [
      { blockType: "indicator", blockName: "EMA", config: { period: 200, timeframe: "D1" }, position: { x: 50, y: 50 } },
      { blockType: "indicator", blockName: "EMA", config: { period: 50, timeframe: "H4" }, position: { x: 50, y: 170 } },
      { blockType: "indicator", blockName: "RSI", config: { period: 14, timeframe: "H1" }, position: { x: 50, y: 290 } },
      { blockType: "condition", blockName: "All Bullish", config: { operator: "AND" }, position: { x: 250, y: 170 } },
      { blockType: "action", blockName: "Buy", config: { order_type: "limit", position_size: "2%" }, position: { x: 450, y: 170 } },
    ]
  },
  {
    id: "ai-sentiment",
    name: "AI Sentiment Strategy",
    description: "Uses AI-powered sentiment analysis to enter trades based on market mood.",
    category: "advanced",
    icon: Target,
    popularity: 4.3,
    expectedReturn: "35-55%",
    riskLevel: "high",
    blocks: [
      { blockType: "ai", blockName: "Sentiment Analyzer", config: { sources: ["news", "twitter"], threshold: 0.6 }, position: { x: 50, y: 50 } },
      { blockType: "ai", blockName: "Trend Predictor", config: { timeframe: "1h", lookback: 50 }, position: { x: 50, y: 170 } },
      { blockType: "logic", blockName: "AND Gate", config: { inputs: 2 }, position: { x: 250, y: 110 } },
      { blockType: "action", blockName: "Buy", config: { order_type: "market", position_size: "1%" }, position: { x: 450, y: 110 } },
    ]
  },
];

const categoryColors = {
  beginner: "bg-green-500/10 text-green-600 border-green-500/30",
  intermediate: "bg-yellow-500/10 text-yellow-600 border-yellow-500/30",
  advanced: "bg-red-500/10 text-red-600 border-red-500/30"
};

const riskColors = {
  low: "text-green-500",
  medium: "text-yellow-500",
  high: "text-red-500"
};

export const StrategyTemplates = ({ availableBlocks, onTemplateSelect }: StrategyTemplatesProps) => {
  const [selectedTemplate, setSelectedTemplate] = useState<StrategyTemplate | null>(null);
  const { toast } = useToast();

  const applyTemplate = (template: StrategyTemplate) => {
    const placedBlocks: PlacedBlock[] = template.blocks.map((blockDef, index) => {
      // Try to find matching block from available blocks
      const matchingBlock = availableBlocks.find(b => 
        b.name.toLowerCase().includes(blockDef.blockName.toLowerCase()) ||
        b.block_type === blockDef.blockType
      );

      if (!matchingBlock) {
        // Create a placeholder block if not found
        return {
          id: `template-${template.id}-${index}`,
          blockId: `placeholder-${index}`,
          block: {
            id: `placeholder-${index}`,
            block_type: blockDef.blockType,
            name: blockDef.blockName,
            description: "",
            category: blockDef.blockType,
            config_schema: {},
            default_config: blockDef.config,
            icon: "Activity",
            is_premium: false
          },
          config: blockDef.config,
          position: blockDef.position,
          connections: []
        };
      }

      return {
        id: `template-${template.id}-${index}`,
        blockId: matchingBlock.id,
        block: matchingBlock,
        config: { ...matchingBlock.default_config, ...blockDef.config },
        position: blockDef.position,
        connections: []
      };
    });

    onTemplateSelect(placedBlocks);
    setSelectedTemplate(null);
    
    toast({
      title: `Template applied: ${template.name}`,
      description: `${placedBlocks.length} blocks added to your canvas`
    });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          Strategy Templates
        </CardTitle>
        <CardDescription className="text-xs">
          Start with proven strategies and customize them
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[300px]">
          <div className="space-y-2">
            {templates.map((template) => (
              <Dialog key={template.id}>
                <DialogTrigger asChild>
                  <div
                    className="p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 cursor-pointer transition-all group"
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <div className="p-1.5 rounded-md bg-primary/10">
                          <template.icon className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <div className="font-medium text-sm">{template.name}</div>
                          <div className="flex items-center gap-1 mt-0.5">
                            <Badge variant="outline" className={`text-[10px] ${categoryColors[template.category]}`}>
                              {template.category}
                            </Badge>
                            <div className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                              <Star className="h-2.5 w-2.5 fill-yellow-500 text-yellow-500" />
                              {template.popularity}
                            </div>
                          </div>
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                      {template.description}
                    </p>
                  </div>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <template.icon className="h-5 w-5 text-primary" />
                      {template.name}
                    </DialogTitle>
                    <DialogDescription>
                      {template.description}
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-3 bg-muted/50 rounded-lg text-center">
                        <div className="text-lg font-bold text-primary">{template.expectedReturn}</div>
                        <div className="text-xs text-muted-foreground">Expected Return</div>
                      </div>
                      <div className="p-3 bg-muted/50 rounded-lg text-center">
                        <div className={`text-lg font-bold capitalize ${riskColors[template.riskLevel]}`}>
                          {template.riskLevel}
                        </div>
                        <div className="text-xs text-muted-foreground">Risk Level</div>
                      </div>
                      <div className="p-3 bg-muted/50 rounded-lg text-center">
                        <div className="text-lg font-bold">{template.blocks.length}</div>
                        <div className="text-xs text-muted-foreground">Blocks</div>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium mb-2">Blocks Included:</h4>
                      <div className="flex flex-wrap gap-1">
                        {template.blocks.map((block, idx) => (
                          <Badge key={idx} variant="secondary" className="text-xs">
                            {block.blockName}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <Button 
                      className="w-full" 
                      onClick={() => applyTemplate(template)}
                    >
                      Apply Template
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};