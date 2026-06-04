// dashboard/src/pages/LiveDemo.jsx
import { useWebSocket } from "../hooks/useWebSocket";
import { MetricsPanel } from "../components/MetricsPanel";
import { IntersectionGrid } from "../components/IntersectionGrid";
import { AttentionArrows } from "../components/AttentionArrows";

const PANELS = [
  { key: "fixed_time", label: "Fixed-time",  badge: "Baseline",  color: "#ef4444" },
  { key: "idqn",       label: "IDQN",         badge: "No Comm",   color: "#f59e0b" },
  { key: "gat_marl",   label: "GAT-MARL",     badge: "★ Ours",    color: "#22c55e" },
];

function StatusDot({ state }) {
  const color = state === "connected" ? "#22c55e" : "#f59e0b";
  return (
    <span
      style={{
        display: "inline-block", width: 8, height: 8,
        borderRadius: "50%", background: color,
        marginRight: 6, boxShadow: `0 0 6px ${color}`,
      }}
    />
  );
}

function Panel({ panelCfg, workerData, workerStatus }) {
  const data   = workerData?.[panelCfg.key];
  const status = workerStatus?.[panelCfg.key] ?? "reconnecting";

  return (
    <div className="demo-panel" style={{ "--panel-color": panelCfg.color }}>
      {/* Header */}
      <div className="panel-header">
        <div className="panel-title-row">
          <span className="panel-label">{panelCfg.label}</span>
          <span className="panel-badge" style={{ color: panelCfg.color }}>
            {panelCfg.badge}
          </span>
        </div>
        <div className="panel-status">
          <StatusDot state={status} />
          <span className="status-text">
            {status === "connected" ? `Step ${data?.step ?? 0}` : "Đang kết nối..."}
          </span>
        </div>
      </div>

      {/* Grid heatmap */}
      <IntersectionGrid
        intersections={data?.intersections}
        avgSpeed={data?.metrics?.avg_speed}
      />

      {/* Attention arrows — chỉ GAT */}
      {panelCfg.key === "gat_marl" && (
        <div className="attention-wrapper">
          <div className="attention-title">Attention Weights</div>
          <AttentionArrows attentionWeights={data?.attention_weights} />
        </div>
      )}

      {/* Metrics */}
      <MetricsPanel metrics={data?.metrics} mode={panelCfg.key} />
    </div>
  );
}

export default function LiveDemo() {
  const { data, status, connected, sendCommand } = useWebSocket();

  const handleCommand = (cmd) => () => sendCommand(cmd);

  return (
    <div className="livedemo-page">
      {/* Top bar */}
      <div className="demo-topbar">
        <div className="demo-topbar-left">
          <span className="demo-title">Live Demo</span>
          <span className={`ws-badge ${connected ? "ws-badge--on" : "ws-badge--off"}`}>
            {connected ? "● LIVE" : "○ Disconnected"}
          </span>
        </div>

        <div className="demo-controls">
          <button
            className="ctrl-btn ctrl-btn--start"
            onClick={handleCommand("start")}
          >
            ▶ Start
          </button>
          <button
            className="ctrl-btn ctrl-btn--accident"
            onClick={handleCommand("inject_accident:SRC1_N02")}
          >
            🚨 Inject tai nạn
          </button>
          <button
            className="ctrl-btn ctrl-btn--reset"
            onClick={handleCommand("reset")}
          >
            ↺ Reset
          </button>
        </div>
      </div>

      {/* 3 panels */}
      <div className="panels-row">
        {PANELS.map((cfg) => (
          <Panel
            key={cfg.key}
            panelCfg={cfg}
            workerData={data}
            workerStatus={status}
          />
        ))}
      </div>
    </div>
  );
}
