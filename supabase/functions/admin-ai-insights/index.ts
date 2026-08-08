import "https://deno.land/x/xhr@0.1.0/mod.ts";
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from 'npm:@supabase/supabase-js@2';

import { corsHeaders } from "../_shared/cors.ts";

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const LOVABLE_API_KEY = Deno.env.get('LOVABLE_API_KEY');
    const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
    const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

    if (!LOVABLE_API_KEY || !SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
      throw new Error('Missing required environment variables');
    }

    // Auth check: require admin
    const authHeader = req.headers.get('Authorization');
    if (!authHeader?.startsWith('Bearer ')) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
    const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!;
    const authClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authHeader } }
    });
    const { data: userData, error: authErr } = await authClient.auth.getUser();
    if (authErr || !userData?.user) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
    const { data: isAdmin } = await supabase.rpc('has_role', {
      _user_id: userData.user.id, _role: 'admin'
    });
    if (!isAdmin) {
      return new Response(JSON.stringify({ error: 'Forbidden' }), {
        status: 403, headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    // Gather system data
    console.log('Fetching system data...');

    // Get pending approvals
    const { data: pendingSetups } = await supabase
      .from('user_setup')
      .select('*')
      .eq('is_completed', true)
      .is('admin_approved', null);

    // Fetch profiles for pending approvals
    const pendingApprovals = [];
    if (pendingSetups && pendingSetups.length > 0) {
      for (const setup of pendingSetups) {
        const { data: profile } = await supabase
          .from('profiles')
          .select('email, full_name')
          .eq('id', setup.user_id)
          .single();
        if (profile) {
          pendingApprovals.push({ ...setup, profiles: profile });
        }
      }
    }

    // Get recent support tickets
    const { data: openTickets } = await supabase
      .from('support_tickets')
      .select('*')
      .in('status', ['open', 'in_progress'])
      .order('created_at', { ascending: false })
      .limit(20);

    // Get bot heartbeats with errors
    const { data: botErrors } = await supabase
      .from('bot_heartbeats')
      .select('*')
      .not('error_message', 'is', null)
      .order('last_heartbeat', { ascending: false })
      .limit(10);

    // Get user statistics
    const { data: userStats } = await supabase
      .from('profiles')
      .select('id, created_at');

    // Get subscription statistics
    const { data: subscriptionStats } = await supabase
      .from('user_subscriptions')
      .select('status, trial_ends_at, subscription_tier');

    // Get recent trades performance
    const { data: recentTrades } = await supabase
      .from('trades')
      .select('profit_loss, status, created_at')
      .eq('status', 'closed')
      .order('created_at', { ascending: false })
      .limit(100);

    // Get payment history
    const { data: recentPayments } = await supabase
      .from('payment_history')
      .select('amount, status, created_at')
      .order('created_at', { ascending: false })
      .limit(50);

    // Calculate key metrics
    const totalUsers = userStats?.length || 0;
    const newUsersLast7Days = userStats?.filter(u => {
      const created = new Date(u.created_at);
      const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
      return created > sevenDaysAgo;
    }).length || 0;

    const activeSubscriptions = subscriptionStats?.filter(s => s.status === 'active').length || 0;
    const trialUsers = subscriptionStats?.filter(s => s.status === 'trial').length || 0;
    const expiringTrials = subscriptionStats?.filter(s => {
      if (!s.trial_ends_at) return false;
      const endsAt = new Date(s.trial_ends_at);
      const threeDaysFromNow = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
      return endsAt < threeDaysFromNow && endsAt > new Date();
    }).length || 0;

    const totalRevenue = recentPayments?.reduce((sum, p) => sum + (p.status === 'success' ? Number(p.amount) : 0), 0) || 0;
    const totalTradePnL = recentTrades?.reduce((sum, t) => sum + Number(t.profit_loss || 0), 0) || 0;
    const profitableTrades = recentTrades?.filter(t => Number(t.profit_loss || 0) > 0).length || 0;
    const winRate = recentTrades?.length ? (profitableTrades / recentTrades.length * 100).toFixed(1) : 0;

    // Prepare context for AI
    const systemContext = {
      pendingApprovals: pendingApprovals?.length || 0,
      pendingApprovalDetails: pendingApprovals?.slice(0, 5).map(p => ({
        email: p.profiles?.email,
        name: p.profiles?.full_name,
        daysWaiting: Math.floor((Date.now() - new Date(p.submitted_for_approval_at || 0).getTime()) / (1000 * 60 * 60 * 24))
      })),
      openTickets: openTickets?.length || 0,
      openTicketsByType: openTickets?.reduce((acc: any, t) => {
        acc[t.priority] = (acc[t.priority] || 0) + 1;
        return acc;
      }, {}),
      botErrors: botErrors?.length || 0,
      recentBotErrors: botErrors?.slice(0, 5).map(e => ({
        message: e.log_message,
        timestamp: e.created_at
      })),
      totalUsers,
      newUsersLast7Days,
      activeSubscriptions,
      trialUsers,
      expiringTrials,
      totalRevenue,
      totalTradePnL,
      winRate,
      userGrowthRate: totalUsers > 0 ? ((newUsersLast7Days / totalUsers) * 100).toFixed(1) : 0
    };

    console.log('System context:', JSON.stringify(systemContext, null, 2));

    // Call AI for insights
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
            content: `You are an AI admin assistant for a trading bot platform. Analyze system data and provide actionable insights and recommendations. Focus on:
1. Critical issues requiring immediate attention
2. Opportunities to improve user experience
3. Revenue optimization suggestions
4. Risk warnings
5. Growth opportunities

Be concise, specific, and actionable. Prioritize urgent items first. Use emojis for visual clarity.`
          },
          {
            role: 'user',
            content: `Analyze this system data and provide 3-5 prioritized insights with specific recommendations:

${JSON.stringify(systemContext, null, 2)}`
          }
        ],
      }),
    });

    if (!aiResponse.ok) {
      const errorText = await aiResponse.text();
      console.error('AI API error:', aiResponse.status, errorText);
      throw new Error(`AI API error: ${aiResponse.status}`);
    }

    const aiData = await aiResponse.json();
    const insights = aiData.choices[0].message.content;

    console.log('AI insights generated successfully');

    return new Response(
      JSON.stringify({ 
        insights,
        metrics: systemContext,
        timestamp: new Date().toISOString()
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Error in admin-ai-insights:', error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : 'Unknown error' }),
      { 
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      }
    );
  }
});