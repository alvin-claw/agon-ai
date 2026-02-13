"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Turn } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface LiveDebateState {
  isLive: boolean;
  viewerCount: number;
  cooldownSeconds: number;
  latestTurn: Turn | null;
}

export function useLiveDebate(debateId: string, enabled: boolean): LiveDebateState {
  const [isLive, setIsLive] = useState(false);
  const [viewerCount, setViewerCount] = useState(0);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [latestTurn, setLatestTurn] = useState<Turn | null>(null);
  const retryCount = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!enabled) return;

    const es = new EventSource(`${API_BASE}/api/debates/${debateId}/live`);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsLive(true);
      retryCount.current = 0;
    };

    es.addEventListener("viewer_count", (e) => {
      try {
        const data = JSON.parse(e.data);
        setViewerCount(data.count ?? 0);
      } catch { /* ignore */ }
    });

    es.addEventListener("turn_start", (e) => {
      try {
        const data = JSON.parse(e.data);
        setLatestTurn(data.turn ?? null);
      } catch { /* ignore */ }
    });

    es.addEventListener("turn_complete", (e) => {
      try {
        const data = JSON.parse(e.data);
        setLatestTurn(data.turn ?? null);
      } catch { /* ignore */ }
    });

    es.addEventListener("cooldown_start", (e) => {
      try {
        const data = JSON.parse(e.data);
        setCooldownSeconds(data.seconds ?? 0);
      } catch { /* ignore */ }
    });

    es.addEventListener("debate_complete", () => {
      setIsLive(false);
      es.close();
    });

    es.addEventListener("ping", () => {
      // keepalive, no-op
    });

    es.onerror = () => {
      setIsLive(false);
      es.close();

      // Exponential backoff reconnect
      const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
      retryCount.current += 1;
      setTimeout(connect, delay);
    };
  }, [debateId, enabled]);

  useEffect(() => {
    if (!enabled) return;
    connect();

    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [connect, enabled]);

  return { isLive, viewerCount, cooldownSeconds, latestTurn };
}
