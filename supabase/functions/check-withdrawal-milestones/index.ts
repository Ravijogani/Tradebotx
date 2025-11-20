import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.80.0';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    );

    console.log('Checking withdrawal milestones for all users...');

    // Get all users with their current equity and initial balance
    const { data: users, error: usersError } = await supabaseClient
      .from('user_setup')
      .select('user_id, account_size')
      .eq('is_completed', true);

    if (usersError) throw usersError;

    for (const user of users || []) {
      // Get current equity from latest heartbeat
      const { data: heartbeat } = await supabaseClient
        .from('bot_heartbeats')
        .select('equity')
        .eq('user_id', user.user_id)
        .order('last_heartbeat', { ascending: false })
        .limit(1)
        .single();

      if (!heartbeat || !heartbeat.equity) continue;

      const currentEquity = heartbeat.equity;
      const initialEquity = user.account_size || 10000;

      // Check for 2x milestone
      if (currentEquity >= initialEquity * 2) {
        const { data: existing2x } = await supabaseClient
          .from('withdrawal_milestones')
          .select('id')
          .eq('user_id', user.user_id)
          .eq('milestone_type', '2x')
          .single();

        if (!existing2x) {
          const safeWithdrawal = (currentEquity - initialEquity) * 0.7; // 70% of profit
          
          await supabaseClient.from('withdrawal_milestones').insert({
            user_id: user.user_id,
            milestone_type: '2x',
            trigger_equity: currentEquity,
            initial_equity: initialEquity,
            safe_withdrawal_amount: safeWithdrawal,
            notified: false
          });

          // Create notification
          await supabaseClient.from('user_notifications').insert({
            user_id: user.user_id,
            title: '🎉 Milestone Achieved: 2x Equity!',
            message: `Your account has doubled! Consider withdrawing $${safeWithdrawal.toFixed(2)} while keeping your initial capital safe.`,
            type: 'success',
            metadata: { milestone_type: '2x', safe_withdrawal: safeWithdrawal }
          });

          console.log(`Created 2x milestone for user ${user.user_id}`);
        }
      }

      // Check for 50% growth milestones after 2x
      const { data: milestones } = await supabaseClient
        .from('withdrawal_milestones')
        .select('trigger_equity')
        .eq('user_id', user.user_id)
        .order('trigger_equity', { ascending: false })
        .limit(1)
        .single();

      if (milestones && milestones.trigger_equity) {
        const lastMilestone = milestones.trigger_equity;
        const nextMilestone = lastMilestone * 1.5;

        if (currentEquity >= nextMilestone) {
          const profit = currentEquity - initialEquity;
          const safeWithdrawal = profit * 0.5; // 50% of total profit

          await supabaseClient.from('withdrawal_milestones').insert({
            user_id: user.user_id,
            milestone_type: '50_percent',
            trigger_equity: currentEquity,
            initial_equity: initialEquity,
            safe_withdrawal_amount: safeWithdrawal,
            notified: false
          });

          // Create notification
          await supabaseClient.from('user_notifications').insert({
            user_id: user.user_id,
            title: '📈 50% Growth Milestone!',
            message: `Your equity grew by 50%! Consider withdrawing $${safeWithdrawal.toFixed(2)} to secure your profits.`,
            type: 'success',
            metadata: { milestone_type: '50_percent', safe_withdrawal: safeWithdrawal }
          });

          console.log(`Created 50% milestone for user ${user.user_id}`);
        }
      }

      // Store equity snapshot
      await supabaseClient.from('equity_snapshots').insert({
        user_id: user.user_id,
        equity: currentEquity,
        balance: heartbeat.equity,
        snapshot_date: new Date().toISOString()
      });
    }

    return new Response(
      JSON.stringify({ success: true, message: 'Milestone check completed' }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (error) {
    console.error('Error checking withdrawal milestones:', error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : 'Unknown error' }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});