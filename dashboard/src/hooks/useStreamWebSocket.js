// dashboard/src/hooks/useStreamWebSocket.js
//
// Subscribe vào /ws/stream — nhận vehicle positions + traffic light state mỗi ~1s.
// Tách biệt với useWebSocket (metrics + attention mỗi 5s).
//
// Trả về: streamData = { gat_marl: { vehicles, intersections }, idqn: {...}, ... }

import { useEffect, useRef, useState, useCallback } from "react";

const STREAM_WS_URL =
  import.meta.env.VITE_STREAM_WS_URL || "ws://localhost:8000/ws/stream";

export function useStreamWebSocket() {
  const [streamData, setStreamData] = useState(null);
  const wsRef        = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(STREAM_WS_URL);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        if (parsed.stream) setStreamData(parsed.stream);
      } catch (err) {
        console.error("[StreamWS] parse error:", err);
      }
    };

    ws.onclose = () => {
      reconnectRef.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { streamData };
}
