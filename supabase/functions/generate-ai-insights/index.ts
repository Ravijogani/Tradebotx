import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { handleError } from "../_shared/error-handler.ts";

import { corsHeaders } from "../_shared/cors.ts";

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      {
        global: {
          headers: { Authorization: req.headers.get('Authorization')! },
        },
      }
    );

    const { data: { user } } = await supabaseClient.auth.getUser();
    if (!user) {
      throw new Error('Unauthorized');
    }

    const { analysisType, contextData } = await req.json();
    const startTime = Date.now();

    // Get user's trading history for context
    const { data: trades } = await supabaseClient
      .from('trades')
      .select('*')
      .eq('user_id', user.id)
      .order('opened_at', { ascending: false })
      .limit(50);

    const { data: strategies } = await supabaseClient
      .from('user_strategies')
      .select('*, strategies(name, description)')
      .eq('user_id', user.id);

    // Check if user has enough data for analysis
    if (!trades || trades.length === 0) {
      return new Response(
        JSON.stringify({
          success: false,
          error: 'Insufficient data',
          message: 'You need at least one trade to generate AI insights. Start trading to unlock AI-powered analysis.'
        }),
        {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        }
      );
    }

    // Calculate performance metrics
    const closedTrades = trades.filter(t => t.status === 'closed');
    const totalPnL = closedTrades.reduce((sum, t) => sum + (t.profit_loss || 0), 0);
    const winningTrades = closedTrades.filter(t => (t.profit_loss || 0) > 0);
    const winRate = closedTrades.length > 0 ? (winningTrades.length / closedTrades.length * 100).toFixed(1) : 0;

    // Prepare context for AI
    const context = {
      trades: trades || [],
      strategies: strategies || [],
      metrics: {
        totalTrades: closedTrades.length,
        totalPnL: totalPnL.toFixed(2),
        winRate,
        winningTrades: winningTrades.length,
        losingTrades: closedTrades.length - winningTrades.length
      },
      ...contextData
    };

    let systemPrompt = '';
    let tools: any[] = [];
    let toolChoice: any = undefined;

    switch (analysisType) {
      case 'trade_recommendation':
        systemPrompt = `You are an expert forex/crypto trading advisor. Analyze the user's trading history and provide actionable trade recommendations. Focus on risk management and realistic profit targets based on their past performance.`;
        tools = [{
          type: "function",
          function: {
            name: "provide_trade_recommendations",
            description: "Provide specific trade recommendations with entry, stop loss, and take profit levels",
            parameters: {
              type: "object",
              properties: {
                recommendations: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      symbol: { type: "string", description: "Trading pair like EURUSD, GBPUSD" },
                      direction: { type: "string", enum: ["BUY", "SELL"] },
                      entry: { type: "number", description: "Entry price" },
                      stopLoss: { type: "number", description: "Stop loss price" },
                      takeProfit: { type: "number", description: "Take profit price" },
                      reasoning: { type: "string", description: "Why this trade is recommended" },
                      confidence: { type: "number", description: "Confidence score 0-1" }
                    },
                    required: ["symbol", "direction", "entry", "stopLoss", "takeProfit", "reasoning", "confidence"]
                  },
                  minItems: 2,
                  maxItems: 5
                }
              },
              required: ["recommendations"]
            }
          }
        }];
        toolChoice = { type: "function", function: { name: "provide_trade_recommendations" } };
        break;

      case 'sentiment_analysis':
        systemPrompt = `You are a market sentiment analyst. Analyze trading patterns to determine overall market sentiment and trader psychology.`;
        tools = [{
          type: "function",
          function: {
            name: "analyze_sentiment",
            description: "Analyze market sentiment based on trading patterns",
            parameters: {
              type: "object",
              properties: {
                sentiment: { type: "string", enum: ["bullish", "bearish", "neutral"], description: "Overall market sentiment" },
                riskAppetite: { type: "string", enum: ["high", "moderate", "low"], description: "Risk appetite level" },
                confidence: { type: "number", description: "Confidence score 0-1" },
                factors: { type: "array", items: { type: "string" }, description: "Key psychological factors" },
                recommendation: { type: "string", description: "What the trader should do based on sentiment" }
              },
              required: ["sentiment", "riskAppetite", "confidence", "factors", "recommendation"]
            }
          }
        }];
        toolChoice = { type: "function", function: { name: "analyze_sentiment" } };
        break;

      case 'predictive_analytics':
        systemPrompt = `You are a quantitative analyst specializing in predictive trading analytics. Use historical data to forecast potential outcomes.`;
        tools = [{
          type: "function",
          function: {
            name: "predict_performance",
            description: "Predict future trading performance based on historical data",
            parameters: {
              type: "object",
              properties: {
                predictions: {
                  type: "object",
                  properties: {
                    expectedWinRate: { type: "number", description: "Expected win rate percentage for next month" },
                    optimalPositionSize: { type: "number", description: "Optimal position size as % of account" },
                    bestTradingTimes: { type: "array", items: { type: "string" }, description: "Best times to trade" },
                    drawdownRisk: { type: "string", enum: ["low", "moderate", "high"], description: "Risk of drawdown" }
                  },
                  required: ["expectedWinRate", "optimalPositionSize", "bestTradingTimes", "drawdownRisk"]
                },
                confidence: { type: "number", description: "Confidence score 0-1" },
                reasoning: { type: "string", description: "Reasoning behind predictions" }
              },
              required: ["predictions", "confidence", "reasoning"]
            }
          }
        }];
        toolChoice = { type: "function", function: { name: "predict_performance" } };
        break;

      case 'strategy_optimization':
        systemPrompt = `You are a trading strategy optimization expert. Analyze strategy performance and suggest specific improvements.`;
        tools = [{
          type: "function",
          function: {
            name: "optimize_strategies",
            description: "Provide specific parameter optimizations for trading strategies",
            parameters: {
              type: "object",
              properties: {
                optimizations: {
                  type: "array",
                  items: {
                    type: "object",
                    properties: {
                      strategyName: { type: "string", description: "Name of the strategy" },
                      currentPerformance: { type: "string", description: "Current performance summary" },
                      suggestedChanges: { type: "array", items: { type: "string" }, description: "Specific changes to make" },
                      expectedImprovement: { type: "string", description: "Expected improvement percentage" },
                      reasoning: { type: "string", description: "Why these changes will help" }
                    },
                    required: ["strategyName", "currentPerformance", "suggestedChanges", "expectedImprovement", "reasoning"]
                  }
                }
              },
              required: ["optimizations"]
            }
          }
        }];
        toolChoice = { type: "function", function: { name: "optimize_strategies" } };
        break;

      default:
        throw new Error('Invalid analysis type');
    }

    // Call Lovable AI
    const LOVABLE_API_KEY = Deno.env.get('LOVABLE_API_KEY');
    if (!LOVABLE_API_KEY) {
      throw new Error('LOVABLE_API_KEY not configured');
    }

    console.log(`Generating ${analysisType} for user ${user.id} with ${trades.length} trades`);

    const aiResponse = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LOVABLE_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'google/gemini-2.5-flash',
        messages: [
          { 
            role: 'system', 
            content: systemPrompt 
          },
          { 
            role: 'user', 
            content: `Analyze this trading data and provide insights:\n\nMetrics: ${JSON.stringify(context.metrics, null, 2)}\n\nRecent Trades (${context.trades.length}): ${JSON.stringify(context.trades.slice(0, 20), null, 2)}\n\nStrategies: ${JSON.stringify(context.strategies, null, 2)}`
          }
        ],
        tools,
        tool_choice: toolChoice
      }),
    });

    if (!aiResponse.ok) {
      const errorText = await aiResponse.text();
      console.error('AI API Error:', aiResponse.status, errorText);
      
      if (aiResponse.status === 429) {
        throw new Error('AI rate limit exceeded. Please try again in a few moments.');
      }
      if (aiResponse.status === 402) {
        throw new Error('AI credits exhausted. Please add credits to continue.');
      }
      throw new Error('AI analysis failed');
    }

    const aiData = await aiResponse.json();
    console.log('AI response received:', JSON.stringify(aiData, null, 2));
    
    // Parse AI response from tool call
    let parsedData;
    const choice = aiData.choices[0];
    
    if (choice.message.tool_calls && choice.message.tool_calls.length > 0) {
      // Extract structured data from tool call
      const toolCall = choice.message.tool_calls[0];
      try {
        parsedData = JSON.parse(toolCall.function.arguments);
        console.log('Parsed tool call data:', JSON.stringify(parsedData, null, 2));
      } catch (e) {
        console.error('Failed to parse tool call arguments:', toolCall.function.arguments);
        throw new Error('Failed to parse AI response');
      }
    } else {
      // Fallback to content parsing
      const aiContent = choice.message.content;
      try {
        const jsonMatch = aiContent.match(/```json\s*([\s\S]*?)\s*```/) || 
                         aiContent.match(/\{[\s\S]*\}/);
        const jsonStr = jsonMatch ? (jsonMatch[1] || jsonMatch[0]) : aiContent;
        parsedData = JSON.parse(jsonStr);
      } catch (e) {
        console.error('Failed to parse AI response:', aiContent);
        throw new Error('AI did not return structured data. Please try again.');
      }
    }

    const processingTime = Date.now() - startTime;

    // Store analysis history
    await supabaseClient
      .from('ai_analysis_history')
      .insert({
        user_id: user.id,
        analysis_type: analysisType,
        input_data: context,
        output_data: parsedData,
        processing_time_ms: processingTime
      });

    // Create insights based on analysis type
    const insights = await createInsights(supabaseClient, user.id, analysisType, parsedData);

    return new Response(
      JSON.stringify({
        success: true,
        analysisType,
        data: parsedData,
        insights,
        processingTime
      }),
      {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error) {
    return handleError(error, corsHeaders);
  }
});

async function createInsights(supabaseClient: any, userId: string, analysisType: string, data: any) {
  const insights = [];

  try {
    switch (analysisType) {
      case 'trade_recommendation':
        if (data.recommendations) {
          for (const rec of data.recommendations) {
            const insight = await supabaseClient
              .from('ai_insights')
              .insert({
                user_id: userId,
                insight_type: 'trade_recommendation',
                title: `${rec.direction} ${rec.symbol}`,
                description: rec.reasoning || 'AI-generated trade recommendation',
                confidence_score: rec.confidence || 0.75,
                data: rec,
                expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
              })
              .select()
              .single();
            insights.push(insight.data);
          }
        }
        break;

      case 'sentiment_analysis':
        if (data.sentiment) {
          const insight = await supabaseClient
            .from('ai_insights')
            .insert({
              user_id: userId,
              insight_type: 'sentiment_analysis',
              title: `Market Sentiment: ${data.sentiment}`,
              description: `Risk appetite: ${data.riskAppetite}. Key factors: ${data.factors?.join(', ')}`,
              confidence_score: data.confidence || 0.8,
              data: data,
              expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
            })
            .select()
            .single();
          insights.push(insight.data);
        }
        break;

      case 'predictive_analytics':
        if (data.predictions) {
          const insight = await supabaseClient
            .from('ai_insights')
            .insert({
              user_id: userId,
              insight_type: 'predictive_analytics',
              title: 'Performance Predictions',
              description: `Expected win rate: ${data.predictions.winRate}%. Drawdown risk: ${data.predictions.drawdownRisk}`,
              confidence_score: data.confidence || 0.7,
              data: data,
              expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
            })
            .select()
            .single();
          insights.push(insight.data);
        }
        break;

      case 'strategy_optimization':
        if (data.optimizations) {
          for (const opt of data.optimizations) {
            const insight = await supabaseClient
              .from('ai_insights')
              .insert({
                user_id: userId,
                insight_type: 'strategy_optimization',
                title: `Optimize ${opt.strategyName}`,
                description: opt.reasoning || 'AI-suggested strategy optimization',
                confidence_score: 0.75,
                data: opt
              })
              .select()
              .single();
            insights.push(insight.data);
          }
        }
        break;
    }
  } catch (error) {
    console.error('Error creating insights:', error);
  }

  return insights;
}