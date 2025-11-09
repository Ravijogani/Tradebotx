import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { z } from "https://deno.land/x/zod@v3.22.4/mod.ts";
import { handleError } from "../_shared/error-handler.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

const onboardingRequestSchema = z.object({
  question: z.string().min(1).max(1000),
  context: z.object({
    currentStep: z.string().max(100).optional(),
    fieldName: z.string().max(100).optional(),
    userInput: z.string().max(500).optional()
  }).optional()
});

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const requestBody = await req.json();
    const { question, context } = onboardingRequestSchema.parse(requestBody);

    const LOVABLE_API_KEY = Deno.env.get('LOVABLE_API_KEY');
    if (!LOVABLE_API_KEY) {
      throw new Error('LOVABLE_API_KEY is not configured');
    }

    // Build context-aware system prompt
    let systemPrompt = `You are a helpful onboarding assistant for TradeBotX, an automated trading platform. Your role is to help new users complete their account setup.

Key information about TradeBotX setup:
- Users need to connect their MT5 (MetaTrader 5) trading account
- Free plan users must use partner brokers (XM, Vantage, PepperStone)
- MT5 Account Number: A 5-20 digit number found in MT5 under Tools → Options
- MT5 Password: We recommend using investor (read-only) passwords for security
- MT5 Server: The server address shown in MT5 (e.g., BrokerName-Demo or BrokerName-Live)
- Account Size: The trading account balance in USD (minimum $100)
- Risk Per Trade: Recommended 1-2% per trade (0.1-10% allowed)
- Max Positions: How many trades can run simultaneously (1-20)
- Telegram Chat ID: Optional - for trade notifications

Be concise, friendly, and helpful. If users ask about trading strategies or financial advice, remind them you're here to help with setup only.`;

    if (context?.currentStep) {
      systemPrompt += `\n\nCurrent setup step: ${context.currentStep}`;
    }
    if (context?.fieldName) {
      systemPrompt += `\n\nUser is currently on field: ${context.fieldName}`;
    }

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
          { role: 'user', content: question }
        ],
        temperature: 0.7,
        max_tokens: 500
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(
          JSON.stringify({ 
            error: 'Too many requests. Please wait a moment and try again.' 
          }),
          {
            status: 429,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      }
      if (response.status === 402) {
        return new Response(
          JSON.stringify({ 
            error: 'Service temporarily unavailable. Please try again later.' 
          }),
          {
            status: 402,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          }
        );
      }
      
      const errorText = await response.text();
      console.error('AI gateway error:', response.status, errorText);
      throw new Error('AI service error');
    }

    const data = await response.json();
    const answer = data.choices?.[0]?.message?.content || 'I apologize, but I could not generate a response. Please try rephrasing your question.';

    return new Response(
      JSON.stringify({ 
        success: true, 
        answer 
      }),
      {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      }
    );

  } catch (error: any) {
    return handleError(error, corsHeaders);
  }
});