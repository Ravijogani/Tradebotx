import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { 
  Plus, Trash2, Save, Play, Pause, GripVertical, 
  Loader2, Wand2, TrendingUp, Activity, Target, 
  Clock, Shield, ShoppingCart, XCircle, Filter,
  ChevronRight, Settings, Zap, Info
} from "lucide-react";
import { StrategyCanvas } from "./StrategyCanvas";
import { BlockPalette } from "./BlockPalette";
import { BlockConfigPanel } from "./BlockConfigPanel";
import { StrategyValidator } from "./StrategyValidator";
import { BacktestPanel } from "./BacktestPanel";
import { AIStrategyAssistant } from "./AIStrategyAssistant";
import { StrategyTemplates } from "./StrategyTemplates";
import { StrategyMarketplace } from "./StrategyMarketplace";

export interface StrategyBlock {
  id: string;
  block_type: string;
  name: string;
  description: string;
  category: string;
  config_schema: any;
  default_config: any;
  icon: string;
  is_premium: boolean;
}

export interface PlacedBlock {
  id: string;
  blockId: string;
  block: StrategyBlock;
  config: any;
  position: { x: number; y: number };
  connections: string[];
}

export interface CustomStrategy {
  id?: string;
  name: string;
  description: string;
  blocks: PlacedBlock[];
  is_active: boolean;
  is_approved: boolean;
}

export const StrategyBuilder = () => {
  const [blocks, setBlocks] = useState<StrategyBlock[]>([]);
  const [strategies, setStrategies] = useState<CustomStrategy[]>([]);
  const [currentStrategy, setCurrentStrategy] = useState<CustomStrategy>({
    name: "",
    description: "",
    blocks: [],
    is_active: false,
    is_approved: false
  });
  const [selectedBlock, setSelectedBlock] = useState<PlacedBlock | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [blocksRes, strategiesRes] = await Promise.all([
        supabase.from("strategy_blocks").select("*").eq("is_active", true),
        supabase.from("custom_strategies").select("*").order("created_at", { ascending: false })
      ]);

      if (blocksRes.error) throw blocksRes.error;
      if (strategiesRes.error) throw strategiesRes.error;

      setBlocks(blocksRes.data || []);
      
      const loadedStrategies = (strategiesRes.data || []).map(s => ({
        id: s.id,
        name: s.name,
        description: s.description || "",
        blocks: (s.strategy_config as any)?.blocks || [],
        is_active: s.is_active,
        is_approved: s.is_approved
      }));
      setStrategies(loadedStrategies);
    } catch (error: any) {
      toast({
        title: "Error loading data",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleBlockDrop = useCallback((block: StrategyBlock, position: { x: number; y: number }) => {
    const newPlacedBlock: PlacedBlock = {
      id: `block-${Date.now()}`,
      blockId: block.id,
      block,
      config: { ...block.default_config },
      position,
      connections: []
    };

    setCurrentStrategy(prev => ({
      ...prev,
      blocks: [...prev.blocks, newPlacedBlock]
    }));
  }, []);

  const handleBlockSelect = (block: PlacedBlock) => {
    setSelectedBlock(block);
  };

  const handleBlockConfigChange = (blockId: string, config: any) => {
    setCurrentStrategy(prev => ({
      ...prev,
      blocks: prev.blocks.map(b => 
        b.id === blockId ? { ...b, config } : b
      )
    }));
    if (selectedBlock?.id === blockId) {
      setSelectedBlock(prev => prev ? { ...prev, config } : null);
    }
  };

  const handleBlockDelete = (blockId: string) => {
    setCurrentStrategy(prev => ({
      ...prev,
      blocks: prev.blocks.filter(b => b.id !== blockId)
    }));
    if (selectedBlock?.id === blockId) {
      setSelectedBlock(null);
    }
  };

  const handleBlockMove = (blockId: string, position: { x: number; y: number }) => {
    setCurrentStrategy(prev => ({
      ...prev,
      blocks: prev.blocks.map(b => 
        b.id === blockId ? { ...b, position } : b
      )
    }));
  };

  const handleConnect = (fromId: string, toId: string) => {
    setCurrentStrategy(prev => ({
      ...prev,
      blocks: prev.blocks.map(b => 
        b.id === fromId 
          ? { ...b, connections: [...b.connections, toId] } 
          : b
      )
    }));
  };

  const handleSave = async () => {
    if (!currentStrategy.name.trim()) {
      toast({
        title: "Strategy name required",
        description: "Please enter a name for your strategy",
        variant: "destructive"
      });
      return;
    }

    setSaving(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const strategyConfig = JSON.parse(JSON.stringify({ blocks: currentStrategy.blocks }));

      if (currentStrategy.id) {
        const { error } = await supabase
          .from("custom_strategies")
          .update({
            name: currentStrategy.name,
            description: currentStrategy.description,
            strategy_config: strategyConfig
          })
          .eq("id", currentStrategy.id);
        if (error) throw error;
      } else {
        const { data, error } = await supabase
          .from("custom_strategies")
          .insert({
            user_id: user.id,
            name: currentStrategy.name,
            description: currentStrategy.description,
            strategy_config: strategyConfig
          })
          .select()
          .single();
        if (error) throw error;
        setCurrentStrategy(prev => ({ ...prev, id: data.id }));
      }

      toast({ title: "Strategy saved successfully" });
      setShowSaveDialog(false);
      loadData();
    } catch (error: any) {
      toast({
        title: "Error saving strategy",
        description: error.message,
        variant: "destructive"
      });
    } finally {
      setSaving(false);
    }
  };

  const loadStrategy = (strategy: CustomStrategy) => {
    setCurrentStrategy(strategy);
    setSelectedBlock(null);
  };

  const newStrategy = () => {
    setCurrentStrategy({
      name: "",
      description: "",
      blocks: [],
      is_active: false,
      is_approved: false
    });
    setSelectedBlock(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[600px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">Strategy Builder</h2>
          </div>
          {currentStrategy.name && (
            <div className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{currentStrategy.name}</span>
              {currentStrategy.is_approved && (
                <Badge variant="default" className="text-xs">Approved</Badge>
              )}
              {!currentStrategy.is_approved && currentStrategy.id && (
                <Badge variant="secondary" className="text-xs">Pending Approval</Badge>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={newStrategy}>
            <Plus className="h-4 w-4 mr-2" />
            New
          </Button>
          <Button 
            size="sm" 
            onClick={() => setShowSaveDialog(true)}
            disabled={currentStrategy.blocks.length === 0}
          >
            <Save className="h-4 w-4 mr-2" />
            Save
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Block Palette, AI & Templates */}
        <div className="w-72 border-r border-border flex flex-col">
          <Tabs defaultValue="blocks" className="flex-1 flex flex-col">
            <TabsList className="w-full grid grid-cols-3 rounded-none border-b border-border">
              <TabsTrigger value="blocks" className="text-xs">Blocks</TabsTrigger>
              <TabsTrigger value="ai" className="text-xs">AI</TabsTrigger>
              <TabsTrigger value="templates" className="text-xs">Templates</TabsTrigger>
            </TabsList>
            <TabsContent value="blocks" className="flex-1 flex flex-col m-0">
              <div className="p-3 border-b border-border">
                <h3 className="font-medium text-sm">Drag & Drop Blocks</h3>
              </div>
              <BlockPalette 
                blocks={blocks} 
                onDragStart={(block) => {}} 
              />
            </TabsContent>
            <TabsContent value="ai" className="flex-1 p-3 m-0 overflow-auto">
              <AIStrategyAssistant 
                availableBlocks={blocks}
                onStrategyGenerated={(newBlocks) => {
                  setCurrentStrategy(prev => ({
                    ...prev,
                    blocks: [...prev.blocks, ...newBlocks]
                  }));
                }}
              />
            </TabsContent>
            <TabsContent value="templates" className="flex-1 p-3 m-0 overflow-auto">
              <StrategyTemplates 
                availableBlocks={blocks}
                onTemplateSelect={(templateBlocks) => {
                  setCurrentStrategy(prev => ({
                    ...prev,
                    blocks: templateBlocks
                  }));
                }}
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Center - Canvas */}
        <div className="flex-1 flex flex-col">
          <StrategyCanvas
            blocks={currentStrategy.blocks}
            availableBlocks={blocks}
            onBlockDrop={handleBlockDrop}
            onBlockSelect={handleBlockSelect}
            onBlockDelete={handleBlockDelete}
            onBlockMove={handleBlockMove}
            onConnect={handleConnect}
            selectedBlockId={selectedBlock?.id}
          />
        </div>

        {/* Right Panel - Config, Backtest & Saved Strategies */}
        <div className="w-80 border-l border-border flex flex-col">
          <Tabs defaultValue="config" className="flex-1 flex flex-col">
            <TabsList className="w-full grid grid-cols-5 rounded-none border-b border-border">
              <TabsTrigger value="config" className="text-xs">Config</TabsTrigger>
              <TabsTrigger value="validate" className="text-xs">Validate</TabsTrigger>
              <TabsTrigger value="backtest" className="text-xs">Backtest</TabsTrigger>
              <TabsTrigger value="market" className="text-xs">Market</TabsTrigger>
              <TabsTrigger value="saved" className="text-xs">Saved</TabsTrigger>
            </TabsList>
            <TabsContent value="config" className="flex-1 p-0 m-0">
              {selectedBlock ? (
                <BlockConfigPanel
                  block={selectedBlock}
                  onChange={(config) => handleBlockConfigChange(selectedBlock.id, config)}
                  onDelete={() => handleBlockDelete(selectedBlock.id)}
                />
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm p-4 text-center">
                  <div>
                    <Settings className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>Select a block to configure</p>
                  </div>
                </div>
              )}
            </TabsContent>
            <TabsContent value="validate" className="flex-1 p-0 m-0 overflow-auto">
              <StrategyValidator blocks={currentStrategy.blocks} />
            </TabsContent>
            <TabsContent value="backtest" className="flex-1 p-0 m-0 overflow-auto">
              <BacktestPanel blocks={currentStrategy.blocks} strategyName={currentStrategy.name} />
            </TabsContent>
            <TabsContent value="market" className="flex-1 p-3 m-0 overflow-auto">
              <StrategyMarketplace 
                currentStrategy={currentStrategy}
                onStrategyImport={(importedBlocks) => {
                  setCurrentStrategy(prev => ({
                    ...prev,
                    blocks: importedBlocks
                  }));
                }}
              />
            </TabsContent>
            <TabsContent value="saved" className="flex-1 p-0 m-0">
              <ScrollArea className="h-full">
                <div className="p-3 space-y-2">
                  {strategies.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground text-sm">
                      <p>No saved strategies</p>
                    </div>
                  ) : (
                    strategies.map((strategy) => (
                      <div
                        key={strategy.id}
                        className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                          currentStrategy.id === strategy.id 
                            ? "border-primary bg-primary/5" 
                            : "border-border hover:bg-muted/50"
                        }`}
                        onClick={() => loadStrategy(strategy)}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm">{strategy.name}</span>
                          {strategy.is_approved ? (
                            <Badge variant="default" className="text-xs">Live</Badge>
                          ) : (
                            <Badge variant="secondary" className="text-xs">Draft</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {strategy.description || `${strategy.blocks.length} blocks`}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Save Dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Strategy</DialogTitle>
            <DialogDescription>
              Give your strategy a name and description
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Strategy Name</Label>
              <Input
                value={currentStrategy.name}
                onChange={(e) => setCurrentStrategy(prev => ({ ...prev, name: e.target.value }))}
                placeholder="My Custom Strategy"
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={currentStrategy.description}
                onChange={(e) => setCurrentStrategy(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Describe your strategy..."
                rows={3}
              />
            </div>
            <div className="bg-muted/50 p-3 rounded-lg">
              <div className="flex items-center gap-2 text-sm">
                <Info className="h-4 w-4 text-muted-foreground" />
                <span className="text-muted-foreground">
                  Strategies require admin approval before they can go live
                </span>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowSaveDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                Save Strategy
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};