import { Badge } from "@/components/ui/badge";
import { 
  GitBranch, GitMerge, ToggleLeft, 
  ArrowRightLeft, Timer, Repeat
} from "lucide-react";

// Logic gate block types for visual strategy builder
export const logicGateBlocks = [
  {
    id: "logic-and",
    block_type: "logic",
    name: "AND Gate",
    description: "All conditions must be true",
    category: "logic",
    config_schema: {
      properties: {
        inputs: { type: "number", minimum: 2, maximum: 5 }
      }
    },
    default_config: { inputs: 2 },
    icon: "GitMerge",
    is_premium: false
  },
  {
    id: "logic-or",
    block_type: "logic",
    name: "OR Gate",
    description: "Any condition can be true",
    category: "logic",
    config_schema: {
      properties: {
        inputs: { type: "number", minimum: 2, maximum: 5 }
      }
    },
    default_config: { inputs: 2 },
    icon: "GitBranch",
    is_premium: false
  },
  {
    id: "logic-not",
    block_type: "logic",
    name: "NOT Gate",
    description: "Inverts the condition",
    category: "logic",
    config_schema: { properties: {} },
    default_config: {},
    icon: "ToggleLeft",
    is_premium: false
  },
  {
    id: "logic-xor",
    block_type: "logic",
    name: "XOR Gate",
    description: "Only one condition must be true",
    category: "logic",
    config_schema: {
      properties: {
        inputs: { type: "number", minimum: 2, maximum: 5 }
      }
    },
    default_config: { inputs: 2 },
    icon: "ArrowRightLeft",
    is_premium: true
  },
  {
    id: "logic-delay",
    block_type: "logic",
    name: "Delay",
    description: "Wait before executing next block",
    category: "logic",
    config_schema: {
      properties: {
        seconds: { type: "number", minimum: 1, maximum: 300 },
        bars: { type: "number", minimum: 1, maximum: 50 },
        delayType: { type: "string", enum: ["seconds", "bars"] }
      }
    },
    default_config: { seconds: 5, bars: 1, delayType: "seconds" },
    icon: "Timer",
    is_premium: false
  },
  {
    id: "logic-loop",
    block_type: "logic",
    name: "Loop",
    description: "Repeat actions multiple times",
    category: "logic",
    config_schema: {
      properties: {
        iterations: { type: "number", minimum: 1, maximum: 10 },
        loopType: { type: "string", enum: ["count", "until_condition"] }
      }
    },
    default_config: { iterations: 3, loopType: "count" },
    icon: "Repeat",
    is_premium: true
  }
];

// AI-Powered block definitions
export const aiPoweredBlocks = [
  {
    id: "ai-pattern-recognition",
    block_type: "ai",
    name: "AI Pattern Recognition",
    description: "Detect chart patterns using ML",
    category: "ai",
    config_schema: {
      properties: {
        patterns: { 
          type: "array", 
          items: { type: "string" },
          enum: ["head_shoulders", "double_top", "double_bottom", "triangle", "wedge", "channel"]
        },
        confidence: { type: "number", minimum: 0.5, maximum: 1.0 }
      }
    },
    default_config: { patterns: ["head_shoulders"], confidence: 0.75 },
    icon: "Brain",
    is_premium: true
  },
  {
    id: "ai-sentiment",
    block_type: "ai",
    name: "Market Sentiment",
    description: "Analyze news sentiment for symbols",
    category: "ai",
    config_schema: {
      properties: {
        sources: { 
          type: "array",
          enum: ["news", "social", "economic_calendar"]
        },
        sentimentThreshold: { type: "number", minimum: -1, maximum: 1 }
      }
    },
    default_config: { sources: ["news"], sentimentThreshold: 0.3 },
    icon: "Newspaper",
    is_premium: true
  },
  {
    id: "ai-trend-prediction",
    block_type: "ai",
    name: "Trend Prediction",
    description: "AI-powered trend forecasting",
    category: "ai",
    config_schema: {
      properties: {
        lookback: { type: "number", minimum: 10, maximum: 200 },
        horizon: { type: "number", minimum: 1, maximum: 20 },
        model: { type: "string", enum: ["lstm", "transformer", "ensemble"] }
      }
    },
    default_config: { lookback: 50, horizon: 5, model: "ensemble" },
    icon: "TrendingUp",
    is_premium: true
  },
  {
    id: "ai-volatility-forecast",
    block_type: "ai",
    name: "Volatility Forecast",
    description: "Predict upcoming volatility",
    category: "ai",
    config_schema: {
      properties: {
        model: { type: "string", enum: ["garch", "ml", "hybrid"] },
        threshold: { type: "number", minimum: 0, maximum: 100 }
      }
    },
    default_config: { model: "hybrid", threshold: 20 },
    icon: "Activity",
    is_premium: true
  }
];

// Multi-symbol and portfolio blocks
export const portfolioBlocks = [
  {
    id: "portfolio-correlation",
    block_type: "portfolio",
    name: "Correlation Filter",
    description: "Check correlation between symbols",
    category: "portfolio",
    config_schema: {
      properties: {
        maxCorrelation: { type: "number", minimum: 0, maximum: 1 },
        period: { type: "number", minimum: 5, maximum: 100 }
      }
    },
    default_config: { maxCorrelation: 0.7, period: 20 },
    icon: "Link",
    is_premium: true
  },
  {
    id: "portfolio-exposure",
    block_type: "portfolio",
    name: "Exposure Limit",
    description: "Limit total portfolio exposure",
    category: "portfolio",
    config_schema: {
      properties: {
        maxExposure: { type: "number", minimum: 1, maximum: 100 },
        perSymbol: { type: "number", minimum: 1, maximum: 50 }
      }
    },
    default_config: { maxExposure: 20, perSymbol: 5 },
    icon: "PieChart",
    is_premium: true
  },
  {
    id: "portfolio-multi-symbol",
    block_type: "portfolio",
    name: "Multi-Symbol",
    description: "Trade multiple symbols simultaneously",
    category: "portfolio",
    config_schema: {
      properties: {
        symbols: { 
          type: "array",
          items: { type: "string" }
        },
        mode: { type: "string", enum: ["parallel", "sequential", "weighted"] }
      }
    },
    default_config: { symbols: ["EURUSD", "GBPUSD"], mode: "parallel" },
    icon: "Layers",
    is_premium: true
  },
  {
    id: "portfolio-hedge",
    block_type: "portfolio",
    name: "Hedge Position",
    description: "Automatically hedge open positions",
    category: "portfolio",
    config_schema: {
      properties: {
        hedgeRatio: { type: "number", minimum: 0.1, maximum: 1 },
        hedgeSymbol: { type: "string" },
        triggerDrawdown: { type: "number", minimum: 1, maximum: 50 }
      }
    },
    default_config: { hedgeRatio: 0.5, hedgeSymbol: "", triggerDrawdown: 5 },
    icon: "Shield",
    is_premium: true
  }
];

export const allAdvancedBlocks = [
  ...logicGateBlocks,
  ...aiPoweredBlocks,
  ...portfolioBlocks
];
