// dashboard/src/pages/LiveDemo.jsx
import { useState, useRef, useEffect } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { MetricsPanel } from "../components/MetricsPanel";
import { TrafficMap }   from "../components/TrafficMap";

const PANELS = [
  { key: "fixed_time", label: "Fixed-time", badge: "Baseline", color: "#e24b4a" },
  { key: "idqn",       label: "IDQN",       badge: "No Comm",  color: "#ba7517" },
  { key: "gat_marl",   label: "GAT-MARL",   badge: "★ Ours",   color: "#534ab7" },
];

const ACCIDENT_EDGE = "SRC1_N02";

function StatusDot({ state }) {
  const c = state === "connected" ? "#1d9e75" : "#ef9f27";
  return (
    <span style={{
      display:"inline-block", width:7, height:7, borderRadius:"50%",
      background:c, marginRight:6,
    }}/>
  );
}

// Dropdown inject accident
function AccidentDropdown({ onInject }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="accident-dropdown" ref={ref}>
      <button className="ctrl-btn ctrl-btn--accident"
        onClick={() => setOpen(o => !o)}>
        🚨 Tai nạn ▾
      </button>
      {open && (
        <div className="accident-menu">
          <button className="accident-option" onClick={() => { onInject("1");   setOpen(false); }}>
            ⚠️ Block 1 lane
          </button>
          <button className="accident-option" onClick={() => { onInject("all"); setOpen(false); }}>
            🚨 Block tất cả lanes
          </button>
        </div>
      )}
    </div>
  );
}

function Panel({ cfg, data, status }) {
  const workerData = data?.[cfg.key];
  const st         = status?.[cfg.key] ?? "reconnecting";

  return (
    <div className="demo-panel" style={{ "--panel-color": cfg.color }}>
      <div className="panel-header">
        <div className="panel-title-row">
          <span className="panel-label">{cfg.label}</span>
          <span className="panel-badge" style={{ color: cfg.color }}>{cfg.badge}</span>
        </div>
        <div className="panel-status">
          <StatusDot state={st}/>
          <span className="status-text">
            {st === "connected" ? `Step ${workerData?.step ?? 0}` : "Đang kết nối..."}
          </span>
        </div>
      </div>

      <TrafficMap data={workerData} modelName={cfg.key}/>
      <MetricsPanel metrics={workerData?.metrics} mode={cfg.key}/>
    </div>
  );
}

export default function LiveDemo() {
  const { data, status, connected, sendCommand } = useWebSocket();
  const [visible, setVisible] = useState({ fixed_time:true, idqn:true, gat_marl:true });

  const togglePanel = (key) => setVisible(v => ({ ...v, [key]: !v[key] }));

  const handleInject = (mode) => {
    sendCommand(`inject_accident:${ACCIDENT_EDGE}:${mode}`);
  };

  const handleReset = () => sendCommand("reset");

  const visiblePanels = PANELS.filter(p => visible[p.key]);
  const cols = visiblePanels.length;

  return (
    <div className="livedemo-page">
      <div className="demo-topbar">
        <div className="demo-topbar-left">
          <span className="demo-title">Live Demo</span>
          <span className={`ws-badge ${connected ? "ws-badge--on" : "ws-badge--off"}`}>
            {connected ? "● LIVE" : "○ Disconnected"}
          </span>
        </div>

        <div className="model-toggles">
          {PANELS.map(p => (
            <button key={p.key}
              className={`toggle-btn ${visible[p.key] ? "toggle-btn--on" : "toggle-btn--off"}`}
              style={{ "--model-color": p.color }}
              onClick={() => togglePanel(p.key)}>
              {p.label}
            </button>
          ))}
        </div>

        <div className="demo-controls">
          <button className="ctrl-btn ctrl-btn--start" onClick={() => sendCommand("start")}>▶ Start</button>
          <AccidentDropdown onInject={handleInject}/>
          <button className="ctrl-btn ctrl-btn--reset" onClick={handleReset}>↺ Reset</button>
        </div>
      </div>

      {cols === 0 ? (
        <div className="no-panels">Bật ít nhất 1 model để xem demo</div>
      ) : (
        <div className="panels-row" style={{ gridTemplateColumns:`repeat(${cols}, 1fr)` }}>
          {visiblePanels.map(cfg => (
            <Panel key={cfg.key} cfg={cfg} data={data} status={status}/>
          ))}
        </div>
      )}
    </div>
  );
}
