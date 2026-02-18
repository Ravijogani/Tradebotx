import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

export const useRealtimeTrades = (userId: string) => {
  const [trades, setTrades] = useState<any[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (!userId) return;

    // Load initial trades
    const loadTrades = async () => {
      const { data, error } = await supabase
        .from("trades")
        .select("*")
        .eq("user_id", userId)
        .order("opened_at", { ascending: false });

      if (error) {
        console.error("Error loading trades:", error);
        return;
      }

      setTrades(data || []);
    };

    loadTrades();

    // Set up realtime subscription
    const channel = supabase
      .channel('trades-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'trades',
          filter: `user_id=eq.${userId}`
        },
        (payload) => {
          setTrades(prev => [payload.new, ...prev]);
          toast({
            title: "New Trade",
            description: `${payload.new.trade_type} ${payload.new.symbol} opened`,
          });
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'trades',
          filter: `user_id=eq.${userId}`
        },
        (payload) => {
          setTrades(prev =>
            prev.map(trade =>
              trade.id === payload.new.id ? payload.new : trade
            )
          );

          // Show notification for closed trades
          if (payload.new.status === 'closed' && payload.old.status !== 'closed') {
            const profitLoss = payload.new.profit_loss || 0;
            toast({
              title: "Trade Closed",
              description: `${payload.new.symbol}: ${profitLoss >= 0 ? '+' : ''}$${profitLoss.toFixed(2)}`,
              variant: profitLoss >= 0 ? "default" : "destructive",
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [userId, toast]);

  return trades;
};

export const useRealtimeBotStatus = (userId: string) => {
  const [strategies, setStrategies] = useState<any[]>([]);
  const { toast } = useToast();

  useEffect(() => {
    if (!userId) return;

    // Load initial strategies
    const loadStrategies = async () => {
      const { data, error } = await supabase
        .from("user_strategies")
        .select(`
          *,
          strategies (
            name,
            description
          )
        `)
        .eq("user_id", userId);

      if (error) {
        console.error("Error loading strategies:", error);
        return;
      }

      setStrategies(data || []);
    };

    loadStrategies();

    // Set up realtime subscription
    const channel = supabase
      .channel('strategies-changes')
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'user_strategies',
          filter: `user_id=eq.${userId}`
        },
        (payload) => {
          setStrategies(prev =>
            prev.map(strategy =>
              strategy.id === payload.new.id ? { ...strategy, ...payload.new } : strategy
            )
          );

          // Show notification for status changes
          if (payload.new.is_running !== payload.old.is_running) {
            toast({
              title: payload.new.is_running ? "Bot Started" : "Bot Stopped",
              description: `Strategy ${payload.new.is_running ? 'activated' : 'deactivated'}`,
            });
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [userId, toast]);

  return strategies;
};