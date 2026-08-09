import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Share2, Download, Copy, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import html2canvas from "html2canvas";
import tradebotxLogo from "@/assets/tradebotx-logo-white.png";

interface Trade {
  id: string;
  symbol: string;
  trade_type: string;
  entry_price: number;
  exit_price?: number;
  profit_loss?: number;
  quantity: number;
  metadata?: unknown;
  closed_at?: string;
}

// trades.metadata is JSONB — this is the shape the bot writes for leverage,
// same convention as StatsOverview's TradeMetadata.
interface TradeMetadata {
  leverage?: string;
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
  const profitAmount = trade.profit_loss || 0;

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
        backgroundColor: '#0a0a1a',
        scale: 2,
        logging: false,
        useCORS: true,
      });
      canvas.toBlob((blob) => {
        if (blob) {
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `TradeBotX-${trade.symbol}-+${profitPercent.toFixed(1)}%.png`;
          link.click();
          URL.revokeObjectURL(url);
          toast({ title: "Image Downloaded!", description: "Share it on social media to inspire others!" });
        }
      });
    } catch (error) {
      console.error('Error generating image:', error);
      toast({ title: "Error", description: "Failed to generate share image", variant: "destructive" });
    } finally {
      setIsGenerating(false);
    }
  };

  const copyReferralLink = () => {
    if (referralCode) {
      const link = `${window.location.origin}/?ref=${referralCode}`;
      navigator.clipboard.writeText(link);
      toast({ title: "Referral Link Copied!", description: "Share this link — earn rewards when they sign up!" });
    }
  };

  const metadata: TradeMetadata = typeof trade.metadata === 'object' && trade.metadata !== null ? trade.metadata as TradeMetadata : {};
  const leverage = metadata.leverage || '50x';
  const isBuy = trade.trade_type.toLowerCase() === 'buy';
  const closedDate = trade.closed_at ? new Date(trade.closed_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '';

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 bg-green-500/10 hover:bg-green-500/20 border-green-500/30 text-green-400"
          onClick={loadReferralCode}
        >
          <Share2 className="w-4 h-4" />
          Share Win
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg p-4">
        <DialogHeader>
          <DialogTitle>Share Your Winning Trade</DialogTitle>
        </DialogHeader>

        {/* The shareable card */}
        <div
          id="shareable-trade-card"
          className="w-[480px] bg-[#0a0a1a] rounded-2xl overflow-hidden mx-auto"
          style={{ fontFamily: "'Inter', 'Segoe UI', sans-serif" }}
        >
          {/* Top gradient bar */}
          <div className="h-1.5 bg-gradient-to-r from-green-500 via-emerald-400 to-green-500" />

          {/* Header */}
          <div className="flex items-center justify-between px-6 pt-5 pb-3">
            <img src={tradebotxLogo} alt="TradeBotX" className="h-8 object-contain" crossOrigin="anonymous" />
            <div className="flex items-center gap-2">
              {closedDate && (
                <span className="text-[11px] text-gray-400">{closedDate}</span>
              )}
              <span className="text-[11px] text-gray-500 bg-white/5 px-2 py-0.5 rounded">{leverage}</span>
            </div>
          </div>

          {/* Main content */}
          <div className="px-6 pt-2 pb-4">
            {/* Symbol + direction */}
            <div className="flex items-center gap-3 mb-5">
              <div className="text-white text-3xl font-bold tracking-tight">{trade.symbol}</div>
              <span className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold ${
                isBuy ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'
              }`}>
                {isBuy ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                {trade.trade_type.toUpperCase()}
              </span>
            </div>

            {/* Profit showcase */}
            <div className="bg-gradient-to-br from-green-500/10 to-emerald-500/5 border border-green-500/20 rounded-xl p-5 mb-5">
              <div className="text-xs text-green-300/70 uppercase tracking-widest mb-2 font-semibold">Profit Earned</div>
              <div className="flex items-end gap-4">
                <div className="text-5xl font-extrabold text-green-400 leading-none">
                  +₹{profitAmount.toFixed(2)}
                </div>
                <div className="text-xl font-bold text-green-300/80 pb-1">
                  (+{profitPercent.toFixed(2)}%)
                </div>
              </div>
            </div>

            {/* Entry / Exit prices */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div className="bg-white/[0.03] rounded-lg p-3.5 border border-white/5">
                <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Entry Price</div>
                <div className="text-lg font-bold text-white">{trade.entry_price.toFixed(2)}</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-3.5 border border-white/5">
                <div className="text-[11px] text-gray-500 uppercase tracking-wider mb-1">Exit Price</div>
                <div className="text-lg font-bold text-white">{trade.exit_price?.toFixed(2)}</div>
              </div>
            </div>

            {/* Quantity */}
            <div className="flex items-center justify-between bg-white/[0.03] rounded-lg px-4 py-2.5 border border-white/5 mb-5">
              <span className="text-xs text-gray-500 uppercase tracking-wider">Quantity</span>
              <span className="text-sm font-semibold text-white">{trade.quantity}</span>
            </div>
          </div>

          {/* Referral footer */}
          <div className="bg-gradient-to-r from-orange-500/10 via-orange-400/5 to-orange-500/10 border-t border-orange-500/20 px-6 py-4">
            <div className="text-center">
              <div className="text-xs text-orange-300/80 mb-1">
                Want results like this? Start automated trading with
              </div>
              <div className="text-base font-bold text-white">
                TradeBotX
                {referralCode && (
                  <span className="text-orange-400 ml-1">• Code: {referralCode}</span>
                )}
              </div>
              <div className="text-[10px] text-gray-500 mt-1">tradebotx.lovable.app</div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="space-y-3 mt-3">
          <p className="text-xs text-muted-foreground text-center">
            Download & share on WhatsApp, Instagram, or Twitter to attract new traders!
          </p>
          <div className="flex gap-2">
            <Button onClick={generateShareImage} disabled={isGenerating} className="flex-1 gap-2">
              <Download className="w-4 h-4" />
              {isGenerating ? "Generating..." : "Download Image"}
            </Button>
            {referralCode && (
              <Button onClick={copyReferralLink} variant="outline" className="gap-2">
                <Copy className="w-4 h-4" />
                Referral Link
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
