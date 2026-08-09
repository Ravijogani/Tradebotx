import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.80.0";

import { corsHeaders } from "../_shared/cors.ts";

interface StrategyBlock {
  id: string;
  blockId: string;
  block: {
    id: string;
    name: string;
    block_type: string;
    description: string;
    // Genuinely block-type-specific JSON blobs — same convention as
    // PlacedBlock in src/components/strategy-builder/StrategyBuilder.tsx.
    config_schema: Record<string, unknown>;
    default_config: Record<string, unknown>;
  };
  config: Record<string, unknown>;
  position: { x: number; y: number };
  connections: string[];
}

interface StrategyConfig {
  name: string;
  description: string;
  blocks: StrategyBlock[];
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const lovableApiKey = Deno.env.get('LOVABLE_API_KEY');

    // Auth check
    const authHeader = req.headers.get('Authorization');
    if (!authHeader) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const supabase = createClient(supabaseUrl, supabaseServiceKey);
    const userClient = createClient(supabaseUrl, supabaseServiceKey, {
      global: { headers: { Authorization: authHeader } }
    });

    const { data: { user }, error: authError } = await userClient.auth.getUser();
    if (authError || !user) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    // Check if user is admin
    const { data: roleData } = await supabase
      .from('user_roles')
      .select('role')
      .eq('user_id', user.id)
      .eq('role', 'admin')
      .single();

    if (!roleData) {
      return new Response(JSON.stringify({ error: 'Admin access required' }), {
        status: 403,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const { strategyId, action } = await req.json();

    if (!strategyId) {
      return new Response(JSON.stringify({ error: 'strategyId required' }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    // Fetch strategy
    const { data: strategy, error: strategyError } = await supabase
      .from('custom_strategies')
      .select('*')
      .eq('id', strategyId)
      .single();

    if (strategyError || !strategy) {
      return new Response(JSON.stringify({ error: 'Strategy not found' }), {
        status: 404,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    const strategyConfig = strategy.strategy_config as StrategyConfig;

    if (action === 'generate') {
      // Generate Python code using AI
      const pythonCode = await generatePythonCode(strategyConfig, lovableApiKey);

      // Store generated code
      await supabase
        .from('custom_strategies')
        .update({
          strategy_config: {
            ...strategyConfig,
            generated_code: pythonCode,
            code_generated_at: new Date().toISOString(),
            code_generated_by: user.id
          }
        })
        .eq('id', strategyId);

      console.log(`Generated Python code for strategy ${strategyId}`);

      return new Response(JSON.stringify({ 
        success: true, 
        code: pythonCode,
        message: 'Python code generated successfully'
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    if (action === 'approve') {
      // Approving publishes the strategy to the marketplace (custom_strategies
      // with is_approved=true) so other users can import its blocks into their
      // own builder. It does NOT create a runnable bot — no edge function or
      // bot-manager script reads custom_strategies for that.
      await supabase
        .from('custom_strategies')
        .update({
          is_approved: true,
          approved_by: user.id,
          approved_at: new Date().toISOString()
        })
        .eq('id', strategyId);

      console.log(`Strategy ${strategyId} approved by admin ${user.id}`);

      return new Response(JSON.stringify({
        success: true,
        message: 'Strategy approved and published to the marketplace'
      }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify({ error: 'Invalid action' }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error: unknown) {
    console.error('Error in generate-strategy-code:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
});

async function generatePythonCode(strategy: StrategyConfig, apiKey?: string): Promise<string> {
  const blocks = strategy.blocks || [];
  
  // Build prompt for AI
  const blockDescriptions = blocks.map(b => {
    return `- ${b.block.name} (${b.block.block_type}): ${JSON.stringify(b.config)}`;
  }).join('\n');

  const prompt = `Generate a complete Python trading bot script for MetaTrader 5 based on this strategy configuration:

Strategy Name: ${strategy.name}
Description: ${strategy.description}

Blocks:
${blockDescriptions}

Requirements:
1. Use MetaTrader5 library for trading
2. Include proper error handling and logging
3. Implement all indicators using TA-Lib or custom calculations
4. Include risk management based on the action blocks
5. Add heartbeat reporting to Supabase
6. Follow the existing bot_wrapper.py pattern for initialization
7. Include proper position sizing based on config
8. Add comments explaining each section

Generate production-ready Python code that can be deployed immediately.`;

  if (apiKey) {
    try {
      const response = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'google/gemini-2.5-flash',
          messages: [
            {
              role: 'system',
              content: `You are an expert Python developer specializing in algorithmic trading and MetaTrader 5 integration. 
Generate clean, well-documented, production-ready Python code.
Always include proper error handling, logging, and follow best practices.
The code should integrate with Supabase for data storage and heartbeat reporting.`
            },
            { role: 'user', content: prompt }
          ],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const generatedCode = data.choices?.[0]?.message?.content || '';
        
        // Extract Python code block if wrapped in markdown
        const codeMatch = generatedCode.match(/```python\n([\s\S]*?)\n```/);
        return codeMatch ? codeMatch[1] : generatedCode;
      }
    } catch (error) {
      console.error('AI generation failed, using template:', error);
    }
  }

  // Fallback: Generate template-based code
  return generateTemplateCode(strategy);
}

function generateTemplateCode(strategy: StrategyConfig): string {
  const blocks = strategy.blocks || [];
  
  // Separate blocks by type
  const indicators = blocks.filter(b => b.block.block_type === 'indicator');
  const conditions = blocks.filter(b => b.block.block_type === 'condition');
  const actions = blocks.filter(b => b.block.block_type === 'action');
  const filters = blocks.filter(b => b.block.block_type === 'filter');

  // Generate indicator code
  const indicatorCode = indicators.map(ind => {
    const name = ind.block.name.toLowerCase().replace(/\s+/g, '_');
    const config = ind.config;
    
    switch (ind.block.name) {
      case 'RSI':
        return `    # RSI Indicator
    rsi_period = ${config.period || 14}
    rsi_values = calculate_rsi(rates, rsi_period)
    current_rsi = rsi_values[-1] if len(rsi_values) > 0 else 50`;
      
      case 'MACD':
        return `    # MACD Indicator
    macd_fast = ${config.fast || 12}
    macd_slow = ${config.slow || 26}
    macd_signal = ${config.signal || 9}
    macd, signal, histogram = calculate_macd(rates, macd_fast, macd_slow, macd_signal)`;
      
      case 'Bollinger Bands':
        return `    # Bollinger Bands
    bb_period = ${config.period || 20}
    bb_std = ${config.stdDev || 2}
    upper_band, middle_band, lower_band = calculate_bollinger(rates, bb_period, bb_std)`;
      
      case 'SMA':
        return `    # Simple Moving Average
    sma_period = ${config.period || 20}
    sma_values = calculate_sma(rates, sma_period)`;
      
      default:
        return `    # ${ind.block.name} - requires custom implementation`;
    }
  }).join('\n\n');

  // Generate condition checks
  const conditionChecks = conditions.map(cond => {
    switch (cond.block.name) {
      case 'Indicator Value':
        return `        # Check indicator value
        indicator_check = current_rsi ${cond.config.operator || '>'} ${cond.config.value || 0}`;
      
      case 'Price Crossover':
        return `        # Price crossover check
        crossover_check = check_crossover(rates, "${cond.config.indicator}", "${cond.config.direction}")`;
      
      default:
        return `        # ${cond.block.name} condition`;
    }
  }).join('\n');

  // Generate action code
  const actionCode = actions.map(act => {
    switch (act.block.name) {
      case 'Market Order':
        return `            # Execute market order
            side = "${act.config.side || 'buy'}"
            lot_size = ${act.config.lotSize || 0.01}
            execute_order(symbol, side, lot_size)`;
      
      case 'Set Stop Loss':
        return `            # Set stop loss
            sl_type = "${act.config.type || 'percentage'}"
            sl_value = ${act.config.value || 2}
            stop_loss = calculate_stop_loss(entry_price, sl_type, sl_value)`;
      
      case 'Set Take Profit':
        return `            # Set take profit
            tp_type = "${act.config.type || 'rr_ratio'}"
            tp_value = ${act.config.value || 2}
            take_profit = calculate_take_profit(entry_price, tp_type, tp_value, stop_loss)`;
      
      default:
        return `            # ${act.block.name} action`;
    }
  }).join('\n');

  return `#!/usr/bin/env python3
"""
Custom Strategy: ${strategy.name}
Description: ${strategy.description}
Generated: ${new Date().toISOString()}

This is an auto-generated trading strategy based on visual block configuration.
Review and test thoroughly before live trading.
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import time
import logging
from datetime import datetime
from supabase import create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CustomStrategy:
    def __init__(self, config):
        self.config = config
        self.symbol = config.get('symbol', 'EURUSD')
        self.timeframe = mt5.TIMEFRAME_M15
        self.supabase = create_client(
            config.get('supabase_url'),
            config.get('supabase_key')
        )
        
    def calculate_rsi(self, rates, period=14):
        """Calculate RSI indicator"""
        close = rates['close']
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = pd.Series(gain).rolling(window=period).mean()
        avg_loss = pd.Series(loss).rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.values
    
    def calculate_macd(self, rates, fast=12, slow=26, signal=9):
        """Calculate MACD indicator"""
        close = pd.Series(rates['close'])
        exp1 = close.ewm(span=fast).mean()
        exp2 = close.ewm(span=slow).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        return macd.values, signal_line.values, histogram.values
    
    def calculate_bollinger(self, rates, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        close = pd.Series(rates['close'])
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper.values, middle.values, lower.values
    
    def calculate_sma(self, rates, period=20):
        """Calculate Simple Moving Average"""
        close = pd.Series(rates['close'])
        return close.rolling(window=period).mean().values
    
    def execute_order(self, symbol, side, lot_size, sl=None, tp=None):
        """Execute a market order"""
        order_type = mt5.ORDER_TYPE_BUY if side == 'buy' else mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(symbol).ask if side == 'buy' else mt5.symbol_info_tick(symbol).bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "${strategy.name}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if sl:
            request["sl"] = sl
        if tp:
            request["tp"] = tp
            
        result = mt5.order_send(request)
        logger.info(f"Order result: {result}")
        return result
    
    def analyze(self):
        """Main analysis function"""
        # Get market data
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 200)
        if rates is None or len(rates) == 0:
            logger.warning("No rates data available")
            return None
            
        rates = pd.DataFrame(rates)
        
        # Calculate indicators
${indicatorCode}
        
        # Check conditions
        entry_signal = None
        
${conditionChecks}
        
        # Execute actions if conditions met
        if entry_signal:
${actionCode}
        
        return entry_signal
    
    def send_heartbeat(self, status='running', error=None):
        """Send heartbeat to Supabase"""
        try:
            account = mt5.account_info()
            self.supabase.table('bot_heartbeats').upsert({
                'user_id': self.config.get('user_id'),
                'strategy_id': self.config.get('strategy_id'),
                'status': status,
                'balance': account.balance if account else 0,
                'equity': account.equity if account else 0,
                'mt5_connected': mt5.terminal_info() is not None,
                'error_message': error,
                'last_heartbeat': datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
    
    def run(self):
        """Main trading loop"""
        logger.info(f"Starting strategy: ${strategy.name}")
        
        while True:
            try:
                self.send_heartbeat()
                signal = self.analyze()
                
                if signal:
                    logger.info(f"Signal generated: {signal}")
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Strategy error: {e}")
                self.send_heartbeat(status='error', error=str(e))
                time.sleep(30)

if __name__ == "__main__":
    # This will be called with config from bot_wrapper.py
    import sys
    import json
    
    if len(sys.argv) > 1:
        config = json.loads(sys.argv[1])
        strategy = CustomStrategy(config)
        strategy.run()
`;
}
