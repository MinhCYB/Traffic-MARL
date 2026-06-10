// dashboard/src/pages/LiveDemo.jsx
import { useState, useRef, useEffect } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { MetricsPanel } from "../components/MetricsPanel";
import { TrafficMap }   from "../components/TrafficMap";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, Cell,
} from "recharts";

const PANELS = [
  { key: "fixed_time", label: "Fixed-time", badge: "Baseline", color: "#e24b4a" },
  { key: "idqn",       label: "IDQN",       badge: "No Comm",  color: "#ba7517" },
  { key: "gat_marl",   label: "GAT-MARL",   badge: "★ Ours",   color: "#534ab7" },
];

const ROUTE_OPTIONS = [
  { value: "peak",    label: "🏙️ Giờ cao điểm" },
  { value: "weekend", label: "🛍️ Cuối tuần"    },
  { value: "night",   label: "🌙 Ban đêm"       },
];

const VOLUME_OPTIONS = [
  { value: 0.5,  label: "🚗 Thưa"         },
  { value: 1.0,  label: "🚗🚗 Bình thường" },
  { value: 1.8,  label: "🚗🚗🚗 Đông"      },
];

const ACCIDENT_EDGE    = "SRC1_N02";
const MAX_CHART_POINTS = 60;
const ZERO_TOTALS      = () => ({ fixed_time: 0, idqn: 0, gat_marl: 0 });

function StatusDot({ state }) {
  const c = state === "connected" ? "#1d9e75" : "#ef9f27";
  return <span style={{ display:"inline-block", width:7, height:7, borderRadius:"50%", background:c, marginRight:6 }}/>;
}

// ── Start Dropdown ────────────────────────────────────────────────────────────
function StartDropdown({ onStart }) {
  const [open,   setOpen]   = useState(false);
  const [route,  setRoute]  = useState("peak");
  const [volume, setVolume] = useState(1.0);
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return (
    <div className="start-dropdown" ref={ref}>
      <div style={{ display:"flex", gap:0 }}>
        <button className="ctrl-btn ctrl-btn--start"
          style={{ borderRadius:"7px 0 0 7px", borderRight:"1px solid rgba(255,255,255,0.3)" }}
          onClick={() => { onStart(route, volume); setOpen(false); }}>
          ▶ Start
        </button>
        <button className="ctrl-btn ctrl-btn--start"
          style={{ borderRadius:"0 7px 7px 0", padding:"6px 8px" }}
          onClick={() => setOpen(o => !o)}>
          ▾
        </button>
      </div>
      {open && (
        <div className="start-menu">
          <div className="start-menu-section">
            <div className="start-menu-label">Khung giờ</div>
            {ROUTE_OPTIONS.map(r => (
              <button key={r.value}
                className={`start-option ${route === r.value ? "start-option--active" : ""}`}
                onClick={() => setRoute(r.value)}>
                {r.label}
              </button>
            ))}
          </div>
          <div className="start-menu-divider"/>
          <div className="start-menu-section">
            <div className="start-menu-label">Lưu lượng xe</div>
            {VOLUME_OPTIONS.map(v => (
              <button key={v.value}
                className={`start-option ${volume === v.value ? "start-option--active" : ""}`}
                onClick={() => setVolume(v.value)}>
                {v.label}
              </button>
            ))}
          </div>
          <div className="start-menu-divider"/>
          <button className="ctrl-btn ctrl-btn--start"
            style={{ width:"100%", borderRadius:6, marginTop:4 }}
            onClick={() => { onStart(route, volume); setOpen(false); }}>
            ▶ Bắt đầu
          </button>
        </div>
      )}
    </div>
  );
}

// ── Accident Dropdown ─────────────────────────────────────────────────────────
function AccidentDropdown({ onInject }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  return (
    <div className="accident-dropdown" ref={ref}>
      <button className="ctrl-btn ctrl-btn--accident" onClick={() => setOpen(o => !o)}>
        🚨 Tai nạn ▾
      </button>
      {open && (
        <div className="accident-menu">
          <button className="accident-option" onClick={() => { onInject("1");   setOpen(false); }}>⚠️ Block 1 lane</button>
          <button className="accident-option" onClick={() => { onInject("all"); setOpen(false); }}>🚨 Block tất cả lanes</button>
        </div>
      )}
    </div>
  );
}

// ── Realtime Charts ───────────────────────────────────────────────────────────
function RealtimeCharts({ history, totalCompleted, totalWait }) {
  if (!history.length) return null;

  const waitBarData = PANELS.map(p => ({
    name:  p.label,
    value: Math.round(totalWait[p.key] ?? 0),
    color: p.color,
  }));

  return (
    <div className="realtime-charts">

      {/* Line chart — xe hoàn thành tích lũy */}
      <div className="chart-card">
        <div className="chart-card-title">
          Tổng xe hoàn thành (cộng dồn)
          <span style={{ fontSize:10, color:"#888780", fontWeight:400, marginLeft:6 }}>— cao hơn = thông thoáng hơn</span>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={history} margin={{ top:4, right:8, bottom:0, left:-16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e6df"/>
            <XAxis dataKey="step" tick={{ fontSize:10, fill:"#888780" }} interval="preserveStartEnd"/>
            <YAxis tick={{ fontSize:10, fill:"#888780" }} width={40}/>
            <Tooltip
              contentStyle={{ background:"white", border:"1px solid #e2e0d8", borderRadius:6, fontSize:11 }}
              labelStyle={{ color:"#888780" }}
              formatter={(v, name) => [`${v} xe`, name]}/>
            <Legend wrapperStyle={{ fontSize:11 }}/>
            {PANELS.map(p => (
              <Line key={p.key} type="monotone"
                dataKey={`${p.key}_cum`} name={p.label}
                stroke={p.color} dot={false} strokeWidth={2}
                isAnimationActive={false}/>
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Bar chart — tổng thời gian chờ tích lũy */}
      <div className="chart-card">
        <div className="chart-card-title">
          Tổng thời gian chờ toàn mạng (cộng dồn, giây)
          <span style={{ fontSize:10, color:"#888780", fontWeight:400, marginLeft:6 }}>— thấp hơn = tốt hơn</span>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={waitBarData} margin={{ top:4, right:8, bottom:0, left:-8 }} barCategoryGap="32%">
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e6df" vertical={false}/>
            <XAxis dataKey="name" tick={{ fontSize:11, fill:"#888780" }} axisLine={false} tickLine={false}/>
            <YAxis
              tick={{ fontSize:10, fill:"#888780" }} width={55}
              tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v}/>
            <Tooltip
              contentStyle={{ background:"white", border:"1px solid #e2e0d8", borderRadius:6, fontSize:11 }}
              formatter={(v, _n, props) => [`${v.toLocaleString()} s`, props.payload.name]}/>
            <Bar dataKey="value" name="Tổng chờ (s)" radius={[4,4,0,0]} maxBarSize={80}>
              {waitBarData.map((entry, i) => <Cell key={i} fill={entry.color} fillOpacity={0.85}/>)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────
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

// ── Main ──────────────────────────────────────────────────────────────────────
export default function LiveDemo() {
  const { data, status, connected, sendCommand } = useWebSocket();
  const [visible, setVisible] = useState({ fixed_time:true, idqn:true, gat_marl:true });
  const [history,        setHistory]        = useState([]);
  const [totalCompleted, setTotalCompleted] = useState(ZERO_TOTALS());
  const [totalWait,      setTotalWait]      = useState(ZERO_TOTALS());

  // useRef để track step đã xử lý — tránh duplicate khi React strict mode re-render
  const lastStepRef = useRef(0);

  useEffect(() => {
    if (!data) return;

    // Lấy step từ bất kỳ worker nào đang connected
    const anyStep = PANELS.reduce((s, p) => data?.[p.key]?.step ?? s, 0);
    if (!anyStep || anyStep <= lastStepRef.current) return;
    lastStepRef.current = anyStep;

    const point = { step: anyStep };

    // Cập nhật totals (dùng functional update để luôn có giá trị mới nhất)
    setTotalCompleted(prev => {
      const next = { ...prev };
      PANELS.forEach(p => {
        const completed = data?.[p.key]?.metrics?.vehicles_completed ?? 0;
        next[p.key] = (prev[p.key] ?? 0) + completed;
        point[`${p.key}_cum`] = next[p.key]; // snapshot tại step này
      });
      return next;
    });

    setTotalWait(prev => {
      const next = { ...prev };
      PANELS.forEach(p => {
        // total_waiting_time = tổng waiting của TẤT CẢ xe hiện tại (snapshot, không phải delta)
        // → cộng dồn qua các step để ra tổng effort chờ đợi của mạng
        const tw = data?.[p.key]?.metrics?.total_waiting_time ?? 0;
        next[p.key] = (prev[p.key] ?? 0) + tw;
      });
      return next;
    });

    setHistory(prev => [...prev, point].slice(-MAX_CHART_POINTS));

  }, [data]);

  const doReset = () => {
    lastStepRef.current = 0;
    setHistory([]);
    setTotalCompleted(ZERO_TOTALS());
    setTotalWait(ZERO_TOTALS());
  };

  const handleStart  = (route, volume) => { doReset(); sendCommand(`start:${route}:${volume}`); };
  const handleInject = (mode)           => sendCommand(`inject_accident:${ACCIDENT_EDGE}:${mode}`);
  const handleReset  = ()               => { doReset(); sendCommand("reset"); };
  const togglePanel  = (key)            => setVisible(v => ({ ...v, [key]: !v[key] }));

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
          <StartDropdown onStart={handleStart}/>
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

      <RealtimeCharts
        history={history}
        totalCompleted={totalCompleted}
        totalWait={totalWait}
      />
    </div>
  );
}
