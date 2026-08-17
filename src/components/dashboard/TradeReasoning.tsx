import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

// Shows WHY a trade was taken, from the reasoning the bot recorded at entry.
//
// The gap this fills: the trades table carried no explanation of any kind, so
// a user could see that a trade happened and what it made or lost, never what
// the bot actually saw. For a platform positioned on SMC/institutional
// methodology that is the wrong thing to hide -- the reasoning is the product.
// It existed only in the bot's log file on the VPS (and was in fact being
// dropped before reaching the database at all; see log_trade()'s metadata
// merge fix in hybrid_trading_bot_multiuser.py).
//
// Renders nothing when a trade has no recorded reasoning -- trades placed
// before this shipped, or by a strategy that doesn't compute a given field.
// Deliberately no invented defaults: an absent reason is shown as absent.

export interface TradeWhy {
  setup?: string | null;
  strategy_type?: string | null;
  regime?: string | null;
  liquidity_confluence?: string | null;
  liquidity_confluent?: boolean | null;
  premium_discount?: string | null;
  in_ote_zone?: boolean | null;
  htf_sweep?: string | null;
}

const LABELS: Record<string, string> = {
  TREND_UP: "Uptrend confirmed",
  TREND_DOWN: "Downtrend confirmed",
  BALANCE: "Ranging",
  CHOPPY: "Unclear",
  PREMIUM: "Premium (expensive half of range)",
  DISCOUNT: "Discount (cheap half of range)",
  EQUILIBRIUM: "At equilibrium",
  BULLISH_SWEEP: "Bullish liquidity sweep",
  BEARISH_SWEEP: "Bearish liquidity sweep",
};

const pretty = (v: string) => LABELS[v] ?? v.replace(/_/g, " ").toLowerCase();

function Chip({ label, hint }: { label: string; hint: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant="outline" className="text-[10px] font-normal py-0 px-1.5 cursor-help">
            {label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[260px] text-xs">
          {hint}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export const TradeReasoning = ({ why }: { why?: TradeWhy | null }) => {
  if (!why) return null;

  const chips: Array<{ label: string; hint: string }> = [];

  if (why.setup) {
    chips.push({
      label: pretty(why.setup),
      hint: `Entry setup: ${why.setup}. This is the strategy pattern that triggered the trade.`,
    });
  }
  if (why.htf_sweep) {
    chips.push({
      label: pretty(why.htf_sweep),
      hint: `A higher-timeframe candle swept liquidity beyond a prior high/low and closed back inside it — the manipulation signature this setup trades.`,
    });
  }
  if (why.regime) {
    chips.push({
      label: pretty(why.regime),
      hint: `Market regime at entry, from the M5 auction state and M30 structure. The bot stands aside entirely in ranging or unclear conditions.`,
    });
  }
  if (why.premium_discount) {
    chips.push({
      label: pretty(why.premium_discount),
      hint: `Where price sat in its current dealing range. Buys are preferred at a discount, sells at a premium.`,
    });
  }
  if (why.liquidity_confluent && why.liquidity_confluence) {
    chips.push({
      label: `At ${why.liquidity_confluence}`,
      hint: `Entry lined up with a real reference level (${why.liquidity_confluence}) rather than sitting in open air.`,
    });
  }
  if (why.in_ote_zone) {
    chips.push({
      label: "OTE zone",
      hint: `Entry fell inside the 61.8%–79% retracement of the most recent impulse leg — the optimal trade entry window.`,
    });
  }

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1 mt-1">
      {chips.map((c) => (
        <Chip key={c.label} label={c.label} hint={c.hint} />
      ))}
    </div>
  );
};
