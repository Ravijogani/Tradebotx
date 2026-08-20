import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";

/**
 * Keep a panel current without the user pressing refresh.
 *
 * WHY THIS EXISTS
 * ---------------
 * The dashboard had 20 realtime subscriptions across 19 components, and not
 * one of them checked whether its subscription actually succeeded. When the
 * websocket does not deliver -- an expired token on the socket, a proxy or
 * corporate network that blocks websockets, a laptop waking from sleep with
 * a dead connection, or simply a channel that errored on join -- every panel
 * silently degrades to "correct as of page load" and stays there. Nothing in
 * the UI says so, so the only symptom is the one the user reported: you have
 * to refresh the page to see anything.
 *
 * A websocket is a nice-to-have for freshness. It must not be the only way
 * data arrives.
 *
 * WHAT IT DOES
 * ------------
 *   1. subscribes to the tables you name, and REPORTS the channel status;
 *   2. polls on an interval whenever the channel is not live, so a broken
 *      socket costs you latency instead of correctness;
 *   3. refetches when the tab becomes visible or the window regains focus.
 *      This is the case that makes people think the dashboard is broken:
 *      a sleeping laptop drops the socket, and on waking the page shows
 *      prices from hours ago until it is reloaded.
 *
 * Polling is deliberately SLOW while the socket is healthy (a safety net for
 * missed events, not a data source) and fast while it is not.
 */

export type LiveStatus = "connecting" | "live" | "polling";

interface Options {
  /** Tables to watch. Any change fires a refetch. */
  tables: string[];
  /** Column used to scope events to this user; omit for unfiltered. */
  userId?: string | null;
  /** Unique channel name. Two channels sharing a name collide silently. */
  channel: string;
  /** Poll interval while the socket is healthy. */
  healthyPollMs?: number;
  /** Poll interval while it is not. */
  degradedPollMs?: number;
  /** Skip work entirely (e.g. before the user is known). */
  enabled?: boolean;
}

/**
 * Calls `refetch` whenever the data behind it may have changed.
 *
 * `refetch` is called on mount, on every relevant realtime event, on each
 * poll tick, and whenever the tab regains focus. It must therefore be safe
 * to call often and in overlapping succession -- keep it a plain reload of
 * the panel's own query.
 */
export function useLiveData(refetch: () => void | Promise<void>, opts: Options): LiveStatus {
  const {
    tables,
    userId,
    channel,
    healthyPollMs = 60_000,
    degradedPollMs = 10_000,
    enabled = true,
  } = opts;

  const [status, setStatus] = useState<LiveStatus>("connecting");

  // Held in a ref so changing the callback identity every render does not
  // tear down and rebuild the subscription -- that churn is itself a common
  // cause of "realtime stopped working after a while".
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;

  const tableKey = tables.join(",");

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;
    const run = () => {
      if (cancelled) return;
      void refetchRef.current();
    };

    run();

    const sub = supabase.channel(channel);
    for (const table of tables) {
      sub.on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table,
          ...(userId ? { filter: `user_id=eq.${userId}` } : {}),
        },
        run,
      );
    }

    sub.subscribe((state) => {
      if (cancelled) return;
      // SUBSCRIBED is the only state that means events will arrive. Everything
      // else -- CHANNEL_ERROR, TIMED_OUT, CLOSED -- has to fall back to
      // polling rather than leaving the panel frozen.
      setStatus(state === "SUBSCRIBED" ? "live" : "polling");
    });

    return () => {
      cancelled = true;
      supabase.removeChannel(sub);
    };
  }, [channel, tableKey, userId, enabled]);

  // Poll. Fast when the socket is down, slow when it is up -- a healthy
  // socket still drops the occasional event, and a minute-old backstop costs
  // nothing while a frozen panel costs trust.
  useEffect(() => {
    if (!enabled) return;
    const every = status === "live" ? healthyPollMs : degradedPollMs;
    const id = window.setInterval(() => void refetchRef.current(), every);
    return () => window.clearInterval(id);
  }, [status, healthyPollMs, degradedPollMs, enabled]);

  // Waking up. A backgrounded tab has its timers throttled and often loses
  // the socket entirely, so the moment the user looks at the page again is
  // exactly when it is most likely to be stale.
  useEffect(() => {
    if (!enabled) return;
    const onWake = () => {
      if (document.visibilityState === "visible") void refetchRef.current();
    };
    document.addEventListener("visibilitychange", onWake);
    window.addEventListener("focus", onWake);
    return () => {
      document.removeEventListener("visibilitychange", onWake);
      window.removeEventListener("focus", onWake);
    };
  }, [enabled]);

  return status;
}
