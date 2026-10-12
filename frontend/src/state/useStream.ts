import { useEffect, useRef, useState } from "react";

export type StreamStatus = "connecting" | "open" | "closed";

/**
 * Live telemetry over a same-origin WebSocket (cookie authenticated). Reconnects with a growing delay.
 * `onMessage` may change between renders; the latest function is always used.
 */
export function useStream(onMessage: (message: { type: string; events?: unknown[] }) => void): StreamStatus {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const handler = useRef(onMessage);
  handler.current = onMessage;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let attempt = 0;
    let stopped = false;

    const open = () => {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      setStatus("connecting");
      socket = new WebSocket(`${scheme}://${window.location.host}/api/v1/stream`);
      socket.onopen = () => {
        attempt = 0;
        setStatus("open");
      };
      socket.onmessage = (event) => {
        try {
          handler.current(JSON.parse(String(event.data)));
        } catch {
          /* ignore a malformed frame */
        }
      };
      socket.onclose = () => {
        setStatus("closed");
        if (stopped) return;
        attempt += 1;
        timer = window.setTimeout(open, Math.min(15000, 500 * 2 ** attempt));
      };
      socket.onerror = () => socket?.close();
    };

    open();
    return () => {
      stopped = true;
      if (timer) window.clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return status;
}
