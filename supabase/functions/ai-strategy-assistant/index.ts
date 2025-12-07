import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { prompt, availableBlocks } = await req.json();
    
    const LOVABLE_API_KEY = Deno.env.get('LOVABLE_API_KEY');
    if (!LOVABLE_API_KEY) {
      throw new Error('LOVABLE_API_KEY is not configured');
    }

    console.log('AI Strategy Assistant - Processing prompt:', prompt);
    console.log('Available blocks count:', availableBlocks?.length || 0);

    // Build the system prompt with available blocks info
    const blockCategories = availableBlocks.reduce((acc: Record<string, any[]>, block: any) => {
      const cat = block.category || block.block_type || 'other';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(block);
      return acc;
    }, {});

    const blocksDescription = Object.entries(blockCategories)
      .map(([cat, blocks]) => `${cat}: ${(blocks as any[]).map(b => b.name).join(', ')}`)
      .join('\n');

    const systemPrompt = `You are an expert trading strategy builder assistant. Your job is to convert natural language trading strategy descriptions into structured block configurations.

Available blocks by category:
${blocksDescription}

When a user describes a trading strategy, you must:
1. Identify which blocks from the available list would implement their strategy
2. Configure each block with appropriate parameters
3. Suggest logical connections between blocks

Respond with a JSON object containing:
- "blocks": an array of block configurations, each with:
  - "blockId": the ID of the block to use (from the available blocks)
  - "name": the block name
  - "config": the configuration parameters
  - "connections": array of block indices this block connects to
- "suggestions": an array of 2-3 tips to improve or optimize the strategy
- "explanation": a brief explanation of how the strategy works

Example response:
{
  "blocks": [
    {"blockId": "rsi-block-id", "name": "RSI", "config": {"period": 14, "overbought": 70, "oversold": 30}, "connections": [1]},
    {"blockId": "condition-id", "name": "Price Condition", "config": {"condition": "less_than", "value": 30}, "connections": [2]},
    {"blockId": "buy-action-id", "name": "Buy", "config": {"order_type": "market", "position_size": "1%"}, "connections": []}
  ],
  "suggestions": ["Consider adding a trend filter", "Add stop loss for risk management"],
  "explanation": "This strategy buys when RSI indicates oversold conditions"
}

IMPORTANT: Only use blocks that are in the available blocks list. Match block names as closely as possible.`;

    const response = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LOVABLE_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'google/gemini-2.5-flash',
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: `Create a trading strategy based on this description: "${prompt}"` }
        ],
        temperature: 0.7,
        max_tokens: 2000
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(JSON.stringify({ error: 'Rate limit exceeded. Please try again later.' }), {
          status: 429,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }
      if (response.status === 402) {
        return new Response(JSON.stringify({ error: 'AI credits exhausted. Please add credits to continue.' }), {
          status: 402,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }
      const errorText = await response.text();
      console.error('AI Gateway error:', response.status, errorText);
      throw new Error(`AI Gateway error: ${response.status}`);
    }

    const aiResponse = await response.json();
    const content = aiResponse.choices?.[0]?.message?.content;

    if (!content) {
      throw new Error('No response from AI');
    }

    console.log('AI Response:', content);

    // Parse the JSON from the response
    let parsedResponse;
    try {
      // Try to extract JSON from the response
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        parsedResponse = JSON.parse(jsonMatch[0]);
      } else {
        throw new Error('No JSON found in response');
      }
    } catch (parseError) {
      console.error('Failed to parse AI response:', parseError);
      // Return a helpful fallback
      parsedResponse = {
        blocks: [],
        suggestions: [
          "Try being more specific about entry and exit conditions",
          "Mention specific indicators like RSI, MACD, or Moving Averages",
          "Include risk management parameters like stop loss percentages"
        ],
        message: "I couldn't fully understand your strategy. Please try describing it with more specific indicators and conditions."
      };
    }

    return new Response(JSON.stringify(parsedResponse), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error) {
    console.error('AI Strategy Assistant error:', error);
    return new Response(JSON.stringify({ 
      error: error instanceof Error ? error.message : 'Unknown error',
      blocks: [],
      suggestions: []
    }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
});