import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { 
  Sparkles, Loader2, Wand2, Lightbulb, 
  TrendingUp, Shield, Zap, Send
} from "lucide-react";
import type { StrategyBlock, PlacedBlock } from "./StrategyBuilder";

interface AIStrategyAssistantProps {
  availableBlocks: StrategyBlock[];
  onStrategyGenerated: (blocks: PlacedBlock[]) => void;
}

// Shape of a single block entry in the ai-strategy-assistant edge
// function's response — matched against availableBlocks by id or name.
interface AIBlockSuggestion {
  blockId?: string;
  name?: string;
  config?: Record<string, unknown>;
  connections?: string[];
}

const quickPrompts = [
  { icon: TrendingUp, label: "Scalping Strategy", prompt: "Create a scalping strategy for EURUSD using RSI and MACD with tight stop losses" },
  { icon: Shield, label: "Conservative", prompt: "Create a conservative swing trading strategy with low risk using moving averages" },
  { icon: Zap, label: "Momentum", prompt: "Create a momentum breakout strategy using Bollinger Bands and volume confirmation" },
];

export const AIStrategyAssistant = ({ availableBlocks, onStrategyGenerated }: AIStrategyAssistantProps) => {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const { toast } = useToast();

  const generateStrategy = async (inputPrompt: string) => {
    if (!inputPrompt.trim()) {
      toast({
        title: "Please describe your strategy",
        description: "Enter what kind of trading strategy you want to create",
        variant: "destructive"
      });
      return;
    }

    setLoading(true);
    try {
      const { data, error } = await supabase.functions.invoke('ai-strategy-assistant', {
        body: { 
          prompt: inputPrompt,
          availableBlocks: availableBlocks.map(b => ({
            id: b.id,
            name: b.name,
            block_type: b.block_type,
            category: b.category,
            description: b.description,
            default_config: b.default_config
          }))
        }
      });

      if (error) throw error;

      if (data.blocks && data.blocks.length > 0) {
        // Convert AI response to PlacedBlocks
        const placedBlocks: PlacedBlock[] = data.blocks.map((blockData: AIBlockSuggestion, index: number) => {
          const sourceBlock = availableBlocks.find(b => b.id === blockData.blockId || b.name === blockData.name);
          if (!sourceBlock) return null;
          
          return {
            id: `ai-block-${Date.now()}-${index}`,
            blockId: sourceBlock.id,
            block: sourceBlock,
            config: blockData.config || sourceBlock.default_config,
            position: { 
              x: 50 + (index % 3) * 200, 
              y: 50 + Math.floor(index / 3) * 120 
            },
            connections: blockData.connections || []
          };
        }).filter(Boolean);

        onStrategyGenerated(placedBlocks);
        setSuggestions(data.suggestions || []);
        
        toast({
          title: "Strategy generated!",
          description: `Created ${placedBlocks.length} blocks based on your description`
        });
      } else {
        toast({
          title: "Could not generate strategy",
          description: data.message || "Try being more specific about your trading approach",
          variant: "destructive"
        });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("AI Strategy error:", error);
      toast({
        title: "Failed to generate strategy",
        description: message || "Please try again",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-background">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          AI Strategy Assistant
        </CardTitle>
        <CardDescription className="text-xs">
          Describe your trading idea in plain English
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Quick Prompts */}
        <div className="flex flex-wrap gap-2">
          {quickPrompts.map((qp, idx) => (
            <Button
              key={idx}
              variant="outline"
              size="sm"
              className="text-xs h-7"
              onClick={() => {
                setPrompt(qp.prompt);
                generateStrategy(qp.prompt);
              }}
              disabled={loading}
            >
              <qp.icon className="h-3 w-3 mr-1" />
              {qp.label}
            </Button>
          ))}
        </div>

        {/* Custom Prompt Input */}
        <div className="space-y-2">
          <Textarea
            placeholder="E.g., Create a strategy that buys when RSI is oversold and price is above the 200 EMA, with a 2% stop loss..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="min-h-[80px] text-sm resize-none"
            disabled={loading}
          />
          <Button
            className="w-full"
            size="sm"
            onClick={() => generateStrategy(prompt)}
            disabled={loading || !prompt.trim()}
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4 mr-2" />
                Generate Strategy
              </>
            )}
          </Button>
        </div>

        {/* AI Suggestions */}
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Lightbulb className="h-3 w-3" />
              <span>AI Suggestions</span>
            </div>
            <div className="space-y-1">
              {suggestions.map((suggestion, idx) => (
                <div key={idx} className="text-xs p-2 bg-muted/50 rounded-md">
                  {suggestion}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};