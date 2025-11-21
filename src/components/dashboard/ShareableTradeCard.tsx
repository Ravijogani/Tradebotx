import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Share2, Download, Copy, Rocket } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import html2canvas from "html2canvas";

interface Trade {
  id: string;
  symbol: string;
  trade_type: string;
  entry_price: number;
  exit_price?: number;
  profit_loss?: number;
  quantity: number;
  metadata?: any;
}

interface ShareableTradeCardProps {
  trade: Trade;
}

export const ShareableTradeCard = ({ trade }: ShareableTradeCardProps) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [referralCode, setReferralCode] = useState<string | null>(null);
  const { toast } = useToast();

  const profitPercent = trade.exit_price 
    ? ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100 * (trade.trade_type.toLowerCase() === 'sell' ? -1 : 1)
    : 0;

  const isProfit = (trade.profit_loss || 0) > 0;

  // Only show share button for profitable closed trades
  if (!trade.exit_price || !isProfit) {
    return null;
  }

  const loadReferralCode = async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data: profile } = await supabase
      .from("profiles")
      .select("referral_code")
      .eq("id", user.id)
      .maybeSingle();

    if (profile?.referral_code) {
      setReferralCode(profile.referral_code);
    }
  };

  const generateShareImage = async () => {
    setIsGenerating(true);
    await loadReferralCode();

    try {
      const cardElement = document.getElementById('shareable-trade-card');
      if (!cardElement) return;

      const canvas = await html2canvas(cardElement, {
        backgroundColor: '#0F172A',
        scale: 2,
        logging: false,
      });

      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `tradebotx-${trade.symbol}-${profitPercent.toFixed(2)}%.png`;
          link.click();
          URL.revokeObjectURL(url);
          
          toast({
            title: "Image Downloaded",
            description: "Share your success with others!",
          });
        }
      });
    } catch (error) {
      console.error('Error generating image:', error);
      toast({
        title: "Error",
        description: "Failed to generate share image",
        variant: "destructive",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const copyReferralLink = () => {
    if (referralCode) {
      const link = `${window.location.origin}/?ref=${referralCode}`;
      navigator.clipboard.writeText(link);
      toast({
        title: "Link Copied!",
        description: "Share this link to earn rewards",
      });
    }
  };

  const metadata = typeof trade.metadata === 'object' && trade.metadata !== null ? trade.metadata as any : {};
  const leverage = metadata.leverage || '50x';

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 bg-success/10 hover:bg-success/20 border-success/30"
          onClick={loadReferralCode}
        >
          <Share2 className="w-4 h-4" />
          Share Win
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Share Your Success</DialogTitle>
        </DialogHeader>

        {/* Hidden card for screenshot */}
        <div id="shareable-trade-card" className="w-[500px] h-[650px] bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 rounded-3xl p-8 relative overflow-hidden mx-auto">
          {/* Background stars decoration */}
          <div className="absolute inset-0 opacity-20">
            <div className="absolute top-10 left-10 w-1 h-1 bg-white rounded-full" />
            <div className="absolute top-20 right-20 w-1 h-1 bg-white rounded-full" />
            <div className="absolute bottom-40 left-20 w-1 h-1 bg-white rounded-full" />
            <div className="absolute bottom-20 right-32 w-1 h-1 bg-white rounded-full" />
            <div className="absolute top-32 right-10 w-1 h-1 bg-white rounded-full" />
          </div>

          {/* Content */}
          <div className="relative z-10 flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <div className="text-white font-bold text-2xl">
                Trade<span className="text-orange-500">Bot</span>X
              </div>
              {referralCode && (
                <div className="text-blue-300 text-sm font-semibold px-3 py-1 bg-blue-500/20 rounded-full">
                  #{referralCode}
                </div>
              )}
            </div>

            {/* Symbol */}
            <div className="text-center mb-6">
              <div className="text-white text-4xl font-bold mb-3">
                {trade.symbol}
              </div>
              <div className="flex items-center justify-center gap-3">
                <span className={`px-4 py-1.5 rounded-lg text-sm font-semibold ${
                  trade.trade_type.toLowerCase() === 'buy' 
                    ? 'bg-green-500/20 text-green-400' 
                    : 'bg-red-500/20 text-red-400'
                }`}>
                  {trade.trade_type.toUpperCase()}
                </span>
                <span className="px-4 py-1.5 rounded-lg text-sm font-semibold bg-white/10 text-white">
                  {leverage}
                </span>
              </div>
            </div>

            {/* Rocket illustration area */}
            <div className="flex-1 flex items-center justify-center mb-8">
              <div className="relative">
                <div className="w-32 h-32 bg-gradient-to-b from-blue-400 to-purple-600 rounded-full opacity-30 blur-3xl absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                <Rocket className="w-24 h-24 text-blue-400 relative z-10" />
              </div>
            </div>

            {/* Profit percentage */}
            <div className="text-center mb-8">
              <div className="text-sm text-blue-300 mb-2 font-medium">Profit %</div>
              <div className="text-6xl font-bold text-green-400">
                +{profitPercent.toFixed(2)}%
              </div>
            </div>

            {/* Entry and Exit prices */}
            <div className="grid grid-cols-2 gap-6">
              <div className="text-center">
                <div className="text-sm text-blue-200 mb-2">Entry Price</div>
                <div className="text-2xl font-bold text-white">
                  {trade.entry_price.toFixed(2)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-sm text-blue-200 mb-2">Exit Price</div>
                <div className="text-2xl font-bold text-white">
                  {trade.exit_price?.toFixed(2)}
                </div>
              </div>
            </div>

            {/* Footer */}
            {referralCode && (
              <div className="mt-8 pt-6 border-t border-white/10">
                <div className="text-center text-sm text-blue-200">
                  Join TradeBotX with code: <span className="font-bold text-white">{referralCode}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Preview and actions */}
        <div className="space-y-4 mt-4">
          <p className="text-sm text-muted-foreground text-center">
            Download and share this image to inspire others!
          </p>
          
          <div className="flex gap-2">
            <Button
              onClick={generateShareImage}
              disabled={isGenerating}
              className="flex-1 gap-2"
            >
              <Download className="w-4 h-4" />
              {isGenerating ? "Generating..." : "Download Image"}
            </Button>
            
            {referralCode && (
              <Button
                onClick={copyReferralLink}
                variant="outline"
                className="gap-2"
              >
                <Copy className="w-4 h-4" />
                Copy Link
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
