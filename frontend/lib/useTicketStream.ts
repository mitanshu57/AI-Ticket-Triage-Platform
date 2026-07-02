"use client";

import { useEffect, useRef, useState } from "react";
import type { TicketEvent } from "./types";
import { wsUrl } from "./api";

/**
 * Subscribe to the backend's ticket event stream. Returns the most recent
 * event and a connection flag; reconnects on drop.
 */
export function useTicketStream(onEvent: (e: TicketEvent) => void) {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(wsUrl());
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 2000);
      };
      ws.onmessage = (evt) => {
        try {
          onEventRef.current(JSON.parse(evt.data) as TicketEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
    };
    connect();

    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, []);

  return { connected };
}
