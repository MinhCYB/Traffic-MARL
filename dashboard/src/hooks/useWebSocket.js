// dashboard/src/hooks/useWebSocket.js
import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useWebSocket() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState({ gat_marl: "reconnecting", idqn: "reconnecting", fixed_time: "reconnecting" });
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      clearTimeout(reconnectRef.current);
    };

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setData(parsed.workers || null);
        setStatus(parsed.status || {});
      } catch (_) {}
    };

    ws.onclose = () => {
      setConnected(false);
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

  const sendCommand = useCallback(async (command) => {
    try {
      await fetch(`${API_URL}/command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command }),
      });
    } catch (_) {}
  }, []);

  return { data, status, connected, sendCommand };
}
