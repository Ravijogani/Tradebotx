import { serve } from "https://deno.land/std@0.190.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface NotificationRequest {
  userId: string;
  type: 'trade_alert' | 'pnl_update' | 'strategy_status' | 'account_notification';
  title: string;
  message: string;
  metadata?: Record<string, any>;
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const botToken = Deno.env.get('TELEGRAM_BOT_TOKEN');
    if (!botToken) {
      throw new Error('TELEGRAM_BOT_TOKEN not configured');
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const { userId, type, title, message, metadata }: NotificationRequest = await req.json();

    console.log(`Processing notification for user ${userId}, type: ${type}`);

    // Get user's Telegram Chat ID
    const { data: setup, error: setupError } = await supabase
      .from('user_setup')
      .select('telegram_chat_id')
      .eq('user_id', userId)
      .single();

    if (setupError || !setup?.telegram_chat_id) {
      console.log('User has not configured Telegram chat ID');
      
      // Log notification attempt
      await supabase.from('notification_log').insert({
        user_id: userId,
        notification_type: type,
        channel: 'telegram',
        title,
        message,
        status: 'skipped',
        metadata: { reason: 'no_chat_id', ...metadata }
      });

      return new Response(
        JSON.stringify({ success: false, reason: 'User has not configured Telegram' }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
      );
    }

    // Format message with emojis based on type
    let emoji = '📢';
    if (type === 'trade_alert') emoji = '📈';
    if (type === 'pnl_update') emoji = '💰';
    if (type === 'strategy_status') emoji = '⚙️';
    if (type === 'account_notification') emoji = '🔔';

    const formattedMessage = `${emoji} *${title}*\n\n${message}`;

    // Send Telegram message
    const telegramResponse = await fetch(
      `https://api.telegram.org/bot${botToken}/sendMessage`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: setup.telegram_chat_id,
          text: formattedMessage,
          parse_mode: 'Markdown'
        })
      }
    );

    const telegramResult = await telegramResponse.json();

    if (!telegramResponse.ok) {
      console.error('Telegram API error:', telegramResult);
      
      // Log failed notification
      await supabase.from('notification_log').insert({
        user_id: userId,
        notification_type: type,
        channel: 'telegram',
        title,
        message,
        status: 'failed',
        metadata: { error: telegramResult, ...metadata }
      });

      throw new Error(`Telegram API error: ${telegramResult.description}`);
    }

    console.log('Telegram notification sent successfully');

    // Log successful notification
    await supabase.from('notification_log').insert({
      user_id: userId,
      notification_type: type,
      channel: 'telegram',
      title,
      message,
      status: 'sent',
      metadata: { telegram_message_id: telegramResult.result?.message_id, ...metadata }
    });

    return new Response(
      JSON.stringify({ success: true, messageId: telegramResult.result?.message_id }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
    );

  } catch (error: any) {
    console.error('Error in send-telegram-notification:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 500 }
    );
  }
});
