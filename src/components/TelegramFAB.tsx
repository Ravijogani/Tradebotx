import { MessageCircle, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export const TelegramFAB = () => {
  const handleTelegramClick = () => {
    window.open("https://t.me/TradeBotXAlgo", "_blank");
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            onClick={handleTelegramClick}
            size="lg"
            className="fixed bottom-6 right-6 z-50 h-14 w-14 rounded-full shadow-glow bg-gradient-hero hover:scale-110 transition-all duration-300"
            aria-label="Join Telegram Community"
          >
            <Users className="h-6 w-6" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>Join Telegram Community</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
