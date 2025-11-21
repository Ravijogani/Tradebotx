import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Share2, Download, Copy, TrendingUp, Trophy } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import html2canvas from "html2canvas";

interface ShareableAchievementCardProps {
  achievementType: 'equity_growth' | 'milestone' | 'streak';
  title: string;
  subtitle?: string;
  mainValue: string;
  secondaryValue?: string;
  initialEquity?: number;
  currentEquity?: number;
  growthPercent?: number;
}

export const ShareableAchievementCard = ({ 
  achievementType,
  title,
  subtitle,
  mainValue,
  secondaryValue,
  initialEquity,
  currentEquity,
  growthPercent
}: ShareableAchievementCardProps) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [referralCode, setReferralCode] = useState<string | null>(null);
  const { toast } = useToast();

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
      const cardElement = document.getElementById('shareable-achievement-card');
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
          link.download = `tradebotx-achievement-${Date.now()}.png`;
          link.click();
          URL.revokeObjectURL(url);
          
          toast({
            title: "Achievement Downloaded",
            description: "Share your success with the world!",
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

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 bg-primary/10 hover:bg-primary/20 border-primary/30"
          onClick={loadReferralCode}
        >
          <Share2 className="w-4 h-4" />
          Share Achievement
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Share Your Achievement</DialogTitle>
        </DialogHeader>

        {/* Hidden card for screenshot */}
        <div id="shareable-achievement-card" className="w-[500px] h-[650px] bg-gradient-to-br from-slate-900 via-purple-950 to-slate-900 rounded-3xl p-8 relative overflow-hidden mx-auto">
          {/* Background decoration */}
          <div className="absolute inset-0 opacity-10">
            <div className="absolute top-10 left-10 w-2 h-2 bg-white rounded-full animate-pulse" />
            <div className="absolute top-20 right-20 w-2 h-2 bg-white rounded-full animate-pulse" style={{ animationDelay: '0.5s' }} />
            <div className="absolute bottom-40 left-20 w-2 h-2 bg-white rounded-full animate-pulse" style={{ animationDelay: '1s' }} />
            <div className="absolute bottom-20 right-32 w-2 h-2 bg-white rounded-full animate-pulse" style={{ animationDelay: '1.5s' }} />
            <div className="absolute top-32 right-10 w-2 h-2 bg-white rounded-full animate-pulse" style={{ animationDelay: '2s' }} />
          </div>

          {/* Gradient orbs */}
          <div className="absolute top-20 left-10 w-40 h-40 bg-gradient-to-br from-blue-500/30 to-purple-500/30 rounded-full blur-3xl" />
          <div className="absolute bottom-20 right-10 w-40 h-40 bg-gradient-to-br from-purple-500/30 to-pink-500/30 rounded-full blur-3xl" />

          {/* Content */}
          <div className="relative z-10 flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
              <div className="text-white font-bold text-2xl">
                Trade<span className="text-orange-500">Bot</span>X
              </div>
              {referralCode && (
                <div className="text-purple-300 text-sm font-semibold px-3 py-1 bg-purple-500/20 rounded-full">
                  #{referralCode}
                </div>
              )}
            </div>

            {/* Achievement Badge */}
            <div className="flex items-center justify-center mb-6">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-yellow-400/20 to-orange-500/20 flex items-center justify-center border-4 border-yellow-500/30">
                <Trophy className="w-12 h-12 text-yellow-400" />
              </div>
            </div>

            {/* Title */}
            <div className="text-center mb-8">
              <div className="text-white text-3xl font-bold mb-2">
                {title}
              </div>
              {subtitle && (
                <div className="text-purple-200 text-lg">
                  {subtitle}
                </div>
              )}
            </div>

            {/* Main Achievement Value */}
            <div className="flex-1 flex items-center justify-center mb-8">
              <div className="text-center">
                <div className="text-sm text-purple-300 mb-3 font-medium uppercase tracking-wider">
                  Achievement Unlocked
                </div>
                <div className="text-6xl font-bold bg-gradient-to-r from-green-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
                  {mainValue}
                </div>
                {secondaryValue && (
                  <div className="text-2xl text-purple-200 mt-3 font-semibold">
                    {secondaryValue}
                  </div>
                )}
              </div>
            </div>

            {/* Growth Details */}
            {initialEquity && currentEquity && growthPercent && (
              <div className="mb-8">
                <div className="grid grid-cols-2 gap-6 p-6 rounded-2xl bg-white/5 backdrop-blur-sm border border-white/10">
                  <div className="text-center">
                    <div className="text-sm text-purple-200 mb-2">Starting Equity</div>
                    <div className="text-2xl font-bold text-white">
                      ${initialEquity.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-purple-200 mb-2">Current Equity</div>
                    <div className="text-2xl font-bold text-green-400">
                      ${currentEquity.toFixed(2)}
                    </div>
                  </div>
                </div>
                <div className="mt-4 text-center">
                  <div className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-green-500/20 border border-green-500/30">
                    <TrendingUp className="w-5 h-5 text-green-400" />
                    <span className="text-2xl font-bold text-green-400">
                      +{growthPercent.toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Footer */}
            {referralCode && (
              <div className="pt-6 border-t border-white/10">
                <div className="text-center">
                  <div className="text-sm text-purple-200 mb-2">
                    Start your trading journey with
                  </div>
                  <div className="text-lg font-bold text-white">
                    Code: <span className="text-orange-400">{referralCode}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Preview and actions */}
        <div className="space-y-4 mt-4">
          <p className="text-sm text-muted-foreground text-center">
            Download and share your achievement to inspire others!
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
