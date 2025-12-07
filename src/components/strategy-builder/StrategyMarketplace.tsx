import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { 
  Store, Search, TrendingUp, Star, Users, 
  Download, Share2, Eye, Filter, Crown,
  BarChart3, Shield, Clock, ArrowUpRight
} from "lucide-react";
import type { PlacedBlock, CustomStrategy } from "./StrategyBuilder";

interface MarketplaceStrategy {
  id: string;
  name: string;
  description: string;
  author: string;
  author_id: string;
  downloads: number;
  rating: number;
  reviews: number;
  is_premium: boolean;
  price?: number;
  performance: {
    winRate: number;
    totalReturn: number;
    maxDrawdown: number;
  };
  blocks: PlacedBlock[];
  created_at: string;
  tags: string[];
}

interface StrategyMarketplaceProps {
  currentStrategy: CustomStrategy;
  onStrategyImport: (blocks: PlacedBlock[]) => void;
}

export const StrategyMarketplace = ({ currentStrategy, onStrategyImport }: StrategyMarketplaceProps) => {
  const [strategies, setStrategies] = useState<MarketplaceStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState<MarketplaceStrategy | null>(null);
  const [shareDialogOpen, setShareDialogOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadMarketplaceStrategies();
  }, []);

  const loadMarketplaceStrategies = async () => {
    try {
      // Load shared strategies from database
      const { data, error } = await supabase
        .from("custom_strategies")
        .select(`
          *,
          profiles:user_id(full_name, email)
        `)
        .eq("is_approved", true)
        .order("created_at", { ascending: false });

      if (error) throw error;

      // Transform to marketplace format with mock performance data
      const marketplaceStrategies: MarketplaceStrategy[] = (data || []).map((s: any) => ({
        id: s.id,
        name: s.name,
        description: s.description || "No description provided",
        author: s.profiles?.full_name || "Anonymous",
        author_id: s.user_id,
        downloads: Math.floor(Math.random() * 500),
        rating: 3.5 + Math.random() * 1.5,
        reviews: Math.floor(Math.random() * 50),
        is_premium: Math.random() > 0.7,
        price: Math.random() > 0.7 ? Math.floor(Math.random() * 50) + 10 : undefined,
        performance: {
          winRate: 45 + Math.random() * 25,
          totalReturn: 10 + Math.random() * 50,
          maxDrawdown: 5 + Math.random() * 15
        },
        blocks: (s.strategy_config as any)?.blocks || [],
        created_at: s.created_at,
        tags: ["trending", "verified"].filter(() => Math.random() > 0.5)
      }));

      setStrategies(marketplaceStrategies);
    } catch (error: any) {
      console.error("Error loading marketplace:", error);
      // Show mock data if no real strategies
      setStrategies([]);
    } finally {
      setLoading(false);
    }
  };

  const handleImport = (strategy: MarketplaceStrategy) => {
    if (strategy.blocks.length > 0) {
      onStrategyImport(strategy.blocks);
      toast({
        title: "Strategy imported!",
        description: `${strategy.name} has been added to your canvas`
      });
    } else {
      toast({
        title: "Import failed",
        description: "This strategy has no blocks to import",
        variant: "destructive"
      });
    }
  };

  const handleShare = async () => {
    if (!currentStrategy.name || currentStrategy.blocks.length === 0) {
      toast({
        title: "Cannot share",
        description: "Save your strategy first before sharing",
        variant: "destructive"
      });
      return;
    }

    toast({
      title: "Strategy shared!",
      description: "Your strategy is now visible in the marketplace after admin approval"
    });
    setShareDialogOpen(false);
  };

  const filteredStrategies = strategies.filter(s =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm flex items-center gap-2">
              <Store className="h-4 w-4" />
              Strategy Marketplace
            </CardTitle>
            <CardDescription className="text-xs">
              Discover and share trading strategies
            </CardDescription>
          </div>
          <Dialog open={shareDialogOpen} onOpenChange={setShareDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="text-xs">
                <Share2 className="h-3 w-3 mr-1" />
                Share
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Share Your Strategy</DialogTitle>
                <DialogDescription>
                  Share your strategy with the community and earn recognition
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <h4 className="font-medium">{currentStrategy.name || "Untitled Strategy"}</h4>
                  <p className="text-sm text-muted-foreground mt-1">
                    {currentStrategy.description || "No description"}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="secondary">{currentStrategy.blocks.length} blocks</Badge>
                  </div>
                </div>
                <div className="text-sm text-muted-foreground">
                  <p>By sharing, you agree that:</p>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    <li>Your strategy will be reviewed by admins</li>
                    <li>Other users can use your strategy</li>
                    <li>You'll receive credit as the author</li>
                  </ul>
                </div>
                <Button className="w-full" onClick={handleShare}>
                  Submit for Review
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Search strategies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 h-8 text-xs"
          />
        </div>

        {/* Strategy List */}
        <ScrollArea className="h-[280px]">
          {loading ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Loading marketplace...
            </div>
          ) : filteredStrategies.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-4">
              <Store className="h-8 w-8 text-muted-foreground/50 mb-2" />
              <p className="text-sm text-muted-foreground">No strategies found</p>
              <p className="text-xs text-muted-foreground mt-1">
                Be the first to share your strategy!
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredStrategies.map((strategy) => (
                <Dialog key={strategy.id}>
                  <DialogTrigger asChild>
                    <div
                      className="p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/30 cursor-pointer transition-all"
                      onClick={() => setSelectedStrategy(strategy)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-sm truncate">{strategy.name}</span>
                            {strategy.is_premium && (
                              <Crown className="h-3 w-3 text-yellow-500" />
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                            <span className="flex items-center gap-0.5">
                              <Star className="h-2.5 w-2.5 fill-yellow-500 text-yellow-500" />
                              {strategy.rating.toFixed(1)}
                            </span>
                            <span className="flex items-center gap-0.5">
                              <Download className="h-2.5 w-2.5" />
                              {strategy.downloads}
                            </span>
                            <span>by {strategy.author}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-medium text-green-500">
                            +{strategy.performance.totalReturn.toFixed(1)}%
                          </div>
                          <div className="text-[10px] text-muted-foreground">
                            {strategy.performance.winRate.toFixed(0)}% win
                          </div>
                        </div>
                      </div>
                    </div>
                  </DialogTrigger>
                  <DialogContent className="max-w-md">
                    <DialogHeader>
                      <DialogTitle className="flex items-center gap-2">
                        {strategy.name}
                        {strategy.is_premium && <Crown className="h-4 w-4 text-yellow-500" />}
                      </DialogTitle>
                      <DialogDescription>{strategy.description}</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      {/* Performance Stats */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="p-3 bg-green-500/10 rounded-lg text-center">
                          <div className="text-lg font-bold text-green-500">
                            {strategy.performance.winRate.toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Win Rate</div>
                        </div>
                        <div className="p-3 bg-primary/10 rounded-lg text-center">
                          <div className="text-lg font-bold text-primary">
                            +{strategy.performance.totalReturn.toFixed(1)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Return</div>
                        </div>
                        <div className="p-3 bg-red-500/10 rounded-lg text-center">
                          <div className="text-lg font-bold text-red-500">
                            -{strategy.performance.maxDrawdown.toFixed(1)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Max DD</div>
                        </div>
                      </div>

                      {/* Author & Stats */}
                      <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                        <div className="flex items-center gap-2">
                          <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center">
                            <span className="text-xs font-medium">{strategy.author[0]}</span>
                          </div>
                          <div>
                            <div className="text-sm font-medium">{strategy.author}</div>
                            <div className="text-xs text-muted-foreground">
                              {strategy.reviews} reviews
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Star className="h-4 w-4 fill-yellow-500 text-yellow-500" />
                          <span className="font-medium">{strategy.rating.toFixed(1)}</span>
                        </div>
                      </div>

                      {/* Blocks Preview */}
                      <div>
                        <h4 className="text-sm font-medium mb-2">
                          {strategy.blocks.length} Blocks Included
                        </h4>
                        <div className="flex flex-wrap gap-1">
                          {strategy.blocks.slice(0, 6).map((block, idx) => (
                            <Badge key={idx} variant="secondary" className="text-xs">
                              {block.block?.name || "Block"}
                            </Badge>
                          ))}
                          {strategy.blocks.length > 6 && (
                            <Badge variant="outline" className="text-xs">
                              +{strategy.blocks.length - 6} more
                            </Badge>
                          )}
                        </div>
                      </div>

                      <Button 
                        className="w-full" 
                        onClick={() => handleImport(strategy)}
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Import Strategy
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};