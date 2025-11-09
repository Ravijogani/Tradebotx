import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.80.0";
import { handleError } from "../_shared/error-handler.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

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
      .order('created_at', { ascending: false })
      .limit(50);

    const { data: strategies } = await supabaseClient
      .from('user_strategies')
      .select('*')
      .eq('user_id', user.id);

    // Prepare context for AI
    const context = {
      trades: trades || [],
      strategies: strategies || [],
      ...contextData
    };

    let systemPrompt = '';
    let userPrompt = '';

    switch (analysisType) {
      case 'trade_recommendation':
        systemPrompt = `You are an expert forex/crypto trading advisor. Analyze the user's trading history and current market conditions to provide actionable trade recommendations. Focus on risk management and realistic profit targets.`;
        userPrompt = `Based on this trading history: ${JSON.stringify(context.trades.slice(0, 10))}, provide 3 specific trade recommendations with entry points, stop loss, and take profit levels. Format as JSON with structure: { recommendations: [{ symbol, direction, entry, stopLoss, takeProfit, reasoning, confidence }] }`;
        break;

      case 'sentiment_analysis':
        systemPrompt = `You are a market sentiment analyst. Analyze trading patterns and market data to determine overall market sentiment and trader psychology.`;
        userPrompt = `Analyze these recent trades: ${JSON.stringify(context.trades.slice(0, 20))}. Provide sentiment analysis including: overall market sentiment (bullish/bearish/neutral), risk appetite level, and key psychological factors. Format as JSON: { sentiment: string, riskAppetite: string, confidence: number, factors: string[] }`;
        break;

      case 'predictive_analytics':
        systemPrompt = `You are a quantitative analyst specializing in predictive trading analytics. Use historical data to forecast potential outcomes and identify patterns.`;
        userPrompt = `Based on this trading performance data: ${JSON.stringify(context.trades.slice(0, 30))}, predict: 1) Expected win rate for next month, 2) Optimal position sizing, 3) Best trading times, 4) Risk of drawdown. Format as JSON: { predictions: { winRate: number, optimalSize: number, bestTimes: string[], drawdownRisk: string }, confidence: number }`;
        break;

      case 'strategy_optimization':
        systemPrompt = `You are a trading strategy optimization expert. Analyze strategy performance and suggest specific parameter improvements.`;
        userPrompt = `Review these strategies: ${JSON.stringify(context.strategies)} and recent performance: ${JSON.stringify(context.trades.slice(0, 15))}. Suggest specific parameter optimizations for each strategy including: risk percentage, lot size adjustments, and timing improvements. Format as JSON: { optimizations: [{ strategyName, currentParams, suggestedParams, expectedImprovement, reasoning }] }`;
        break;

      default:
        throw new Error('Invalid analysis type');
    }

    // Call Lovable AI
    const LOVABLE_API_KEY = Deno.env.get('LOVABLE_API_KEY');
    if (!LOVABLE_API_KEY) {
      throw new Error('LOVABLE_API_KEY not configured');
    }

    const aiResponse = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LOVABLE_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'google/gemini-2.5-flash',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.7,
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
    const aiContent = aiData.choices[0].message.content;
    
    // Parse AI response
    let parsedData;
    try {
      // Extract JSON from response (handle markdown code blocks)
      const jsonMatch = aiContent.match(/```json\s*([\s\S]*?)\s*```/) || 
                       aiContent.match(/\{[\s\S]*\}/);
      const jsonStr = jsonMatch ? (jsonMatch[1] || jsonMatch[0]) : aiContent;
      parsedData = JSON.parse(jsonStr);
    } catch (e) {
      console.error('Failed to parse AI response:', aiContent);
      parsedData = { rawResponse: aiContent };
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

  } catch (error: any) {
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