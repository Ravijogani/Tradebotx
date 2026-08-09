import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import type { Tables } from "@/integrations/supabase/types";

type BotStrategy = Tables<"user_strategies"> & {
  strategies?: Pick<Tables<"strategies">, "name" | "description"> | null;
};

export const useRealtimeTrades = (userId: string) => {
  const [trades, setTrades] = useState<Tables<"trades">[]>([]);
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
          const newTrade = payload.new as Tables<"trades">;
          setTrades(prev => [newTrade, ...prev]);
          toast({
            title: "New Trade",
            description: `${newTrade.trade_type} ${newTrade.symbol} opened`,
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
          const updatedTrade = payload.new as Tables<"trades">;
          const oldTrade = payload.old as Partial<Tables<"trades">>;
          setTrades(prev =>
            prev.map(trade =>
              trade.id === updatedTrade.id ? updatedTrade : trade
            )
          );

          // Show notification for closed trades
          if (updatedTrade.status === 'closed' && oldTrade.status !== 'closed') {
            const profitLoss = updatedTrade.profit_loss || 0;
            toast({
              title: "Trade Closed",
              description: `${updatedTrade.symbol}: ${profitLoss >= 0 ? '+' : ''}$${profitLoss.toFixed(2)}`,
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
  const [strategies, setStrategies] = useState<BotStrategy[]>([]);
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
          const updated = payload.new as Tables<"user_strategies">;
          const previous = payload.old as Partial<Tables<"user_strategies">>;
          setStrategies(prev =>
            prev.map(strategy =>
              strategy.id === updated.id ? { ...strategy, ...updated } : strategy
            )
          );

          // Show notification for status changes
          if (updated.is_running !== previous.is_running) {
            toast({
              title: updated.is_running ? "Bot Started" : "Bot Stopped",
              description: `Strategy ${updated.is_running ? 'activated' : 'deactivated'}`,
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