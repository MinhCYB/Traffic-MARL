// dashboard/src/pages/LiveDemo.jsx
import { useState, useRef, useEffect } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { MetricsPanel } from "../components/MetricsPanel";
import { TrafficMap }   from "../components/TrafficMap";
import { getLayout }    from "../mapLayouts/index.js";
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
  { value: "peak",  label: "🏙️ Giờ cao điểm" },
  { value: "night", label: "🌙 Ban đêm"       },
];

const VOLUME_OPTIONS = [
  { value: 0.5,  label: "🚗 Thưa"         },
  { value: 1.0,  label: "🚗🚗 Bình thường" },
  { value: 1.8,  label: "🚗🚗🚗 Đông"      },
];

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
function AccidentDropdown({ onInject, topology }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const layout       = getLayout(topology || "2x2");
  const accidentEdges = layout.DEMO_ACCIDENT_EDGES || [];

  return (
    <div className="accident-dropdown" ref={ref}>
      <button className="ctrl-btn ctrl-btn--accident" onClick={() => setOpen(o => !o)}>
        🚨 Tai nạn ▾
      </button>
      {open && (
        <div className="accident-menu">
          {accidentEdges.map(({ label, value }) => (
            <div key={value} style={{ borderBottom: "1px solid rgba(0,0,0,0.06)", paddingBottom: 2 }}>
              <button className="accident-option" onClick={() => { onInject(value, "1");   setOpen(false); }}>⚠️ {label} — 1 lane</button>
              <button className="accident-option" onClick={() => { onInject(value, "all"); setOpen(false); }}>🚨 {label} — chặn hết</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Rank Table ───────────────────────────────────────────────────────────────
function RankTable({ history, totalWait, speedHistory }) {
  if (!history.length) return null;

  const last = history[history.length - 1];

  // Score: normalize mỗi metric rồi tổng hợp (higher = better)
  const raw = PANELS.map(p => ({
    ...p,
    completed: last?.[`${p.key}_cum`]          ?? 0,
    wait:      totalWait[p.key]                 ?? 0,  // lower better
    speed:     speedHistory[speedHistory.length - 1]?.[`${p.key}_speed`] ?? 0,
  }));

  const maxCompleted = Math.max(...raw.map(r => r.completed)) || 1;
  const maxWait      = Math.max(...raw.map(r => r.wait))      || 1;
  const maxSpeed     = Math.max(...raw.map(r => r.speed))     || 1;

  const ranked = raw.map(r => ({
    ...r,
    score: Math.round(
      (r.completed / maxCompleted) * 40 +       // throughput 40%
      (1 - r.wait / maxWait)       * 40 +       // ít chờ 40%
      (r.speed / maxSpeed)         * 20          // tốc độ 20%
    ),
  })).sort((a, b) => b.score - a.score);

  const medals = ["🥇", "🥈", "🥉"];

  return (
    <div className="chart-card rank-table-card">
      <div className="chart-card-title">Bảng xếp hạng</div>
      <table className="rank-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Model</th>
            <th title="Xe đã qua mạng">🚗 Xe HT</th>
            <th title="Tổng thời gian chờ tích lũy">⏱ Chờ (k s)</th>
            <th title="Tốc độ trung bình hiện tại">⚡ Tốc độ</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((r, i) => (
            <tr key={r.key} style={{ "--row-color": r.color }}>
              <td className="rank-medal">{medals[i]}</td>
              <td className="rank-name">
                <span className="rank-dot" style={{ background: r.color }}/>
                {r.label}
              </td>
              <td>{r.completed}</td>
              <td>{(r.wait / 1000).toFixed(1)}</td>
              <td>{r.speed > 0 ? `${r.speed} km/h` : "—"}</td>
              <td className="rank-score" style={{ color: r.color }}>{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Realtime Charts ───────────────────────────────────────────────────────────
function RealtimeCharts({ history, totalWait, speedHistory }) {
  if (!history.length) return null;

  // Bar chart gộp: xe hoàn thành + tổng chờ cạnh nhau theo model
  const summaryData = PANELS.map(p => ({
    name:      p.label,
    completed: history[history.length - 1]?.[`${p.key}_cum`] ?? 0,
    wait:      Math.round((totalWait[p.key] ?? 0) / 1000 * 10) / 10, // đổi sang nghìn giây
    color:     p.color,
  }));

  return (
    <div className="realtime-charts">

      {/* Bảng xếp hạng */}
      <RankTable history={history} totalWait={totalWait} speedHistory={speedHistory}/>

      {/* Bar chart gộp — xe hoàn thành + tổng chờ */}
      <div className="chart-card">
        <div className="chart-card-title">
          So sánh tổng kết
          <span style={{ fontSize:10, color:"#888780", fontWeight:400, marginLeft:6 }}>
            xe hoàn thành (cao hơn tốt hơn) · tổng chờ nghìn giây (thấp hơn tốt hơn)
          </span>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={summaryData} margin={{ top:4, right:48, bottom:0, left:-8 }} barCategoryGap="28%" barGap={3}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e6df" vertical={false}/>
            <XAxis dataKey="name" tick={{ fontSize:11, fill:"#888780" }} axisLine={false} tickLine={false}/>
            <YAxis yAxisId="left"  orientation="left"  tick={{ fontSize:10, fill:"#888780" }} width={36}
              label={{ value:"xe", angle:-90, position:"insideLeft", offset:14, style:{ fontSize:9, fill:"#aaa9a3" } }}/>
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize:10, fill:"#888780" }} width={36}
              tickFormatter={v => v >= 1 ? `${v}k` : v}
              label={{ value:"k s", angle:90, position:"insideRight", offset:14, style:{ fontSize:9, fill:"#aaa9a3" } }}/>
            <Tooltip
              contentStyle={{ background:"white", border:"1px solid #e2e0d8", borderRadius:6, fontSize:11 }}
              formatter={(v, name) => name === "Xe hoàn thành" ? [`${v} xe`, name] : [`${v}k s`, name]}/>
            <Legend wrapperStyle={{ fontSize:11 }}/>
            <Bar yAxisId="left"  dataKey="completed" name="Xe hoàn thành" radius={[3,3,0,0]} maxBarSize={48}>
              {summaryData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={0.9}/>)}
            </Bar>
            <Bar yAxisId="right" dataKey="wait" name="Tổng chờ (k s)" radius={[3,3,0,0]} maxBarSize={48}>
              {summaryData.map((e, i) => <Cell key={i} fill={e.color} fillOpacity={0.35}/>)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Line chart — tốc độ TB realtime, thể hiện recovery sau tai nạn */}
      <div className="chart-card">
        <div className="chart-card-title">
          Tốc độ trung bình (km/h) theo thời gian
          <span style={{ fontSize:10, color:"#888780", fontWeight:400, marginLeft:6 }}>— recovery sau tai nạn</span>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={speedHistory} margin={{ top:4, right:8, bottom:0, left:-16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e6df"/>
            <XAxis dataKey="step" tick={{ fontSize:10, fill:"#888780" }} interval="preserveStartEnd"/>
            <YAxis tick={{ fontSize:10, fill:"#888780" }} width={40} domain={[0, "auto"]}/>
            <Tooltip
              contentStyle={{ background:"white", border:"1px solid #e2e0d8", borderRadius:6, fontSize:11 }}
              labelStyle={{ color:"#888780" }}
              formatter={(v, name) => [v != null ? `${v} km/h` : "—", name]}/>
            <Legend wrapperStyle={{ fontSize:11 }}/>
            {PANELS.map(p => (
              <Line key={p.key} type="monotone"
                dataKey={`${p.key}_speed`} name={p.label}
                stroke={p.color} dot={false} strokeWidth={2}
                connectNulls={false}
                isAnimationActive={false}/>
            ))}
          </LineChart>
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
  const [visible,   setVisible]   = useState({ fixed_time:true, idqn:true, gat_marl:true });
  const [history,   setHistory]   = useState([]);
  const [totalWait, setTotalWait] = useState(ZERO_TOTALS());

  const lastStepRef    = useRef(0);
  const cumulativeRef  = useRef(ZERO_TOTALS());
  const totalWaitRef   = useRef(ZERO_TOTALS());

  const [speedHistory, setSpeedHistory] = useState([]);

  // Detect topology từ data của bất kỳ worker nào
  // Default về TOPOLOGY từ import config — tránh dropdown accident show sai map trước khi worker connect
  const topology = PANELS.reduce((t, p) => data?.[p.key]?.topology || t, null)
                ?? (import.meta.env.VITE_TOPOLOGY || "2x2");

  useEffect(() => {
    if (!data) return;

    // Lấy step từ bất kỳ worker nào đang connected
    const anyStep = PANELS.reduce((s, p) => data?.[p.key]?.step ?? s, 0);
    if (!anyStep || anyStep <= lastStepRef.current) return;
    lastStepRef.current = anyStep;

    const point = { step: anyStep };

    // Cập nhật cumulative bằng ref — synchronous, không phụ thuộc setState callback
    PANELS.forEach(p => {
      const completed = data?.[p.key]?.metrics?.vehicles_completed ?? 0;
      cumulativeRef.current[p.key] = (cumulativeRef.current[p.key] ?? 0) + completed;
      point[`${p.key}_cum`] = cumulativeRef.current[p.key];

      const tw = data?.[p.key]?.metrics?.total_waiting_time ?? 0;
      totalWaitRef.current[p.key] = (totalWaitRef.current[p.key] ?? 0) + tw;
    });

    // Tốc độ TB snapshot — không cộng dồn, lấy giá trị tức thời
    const speedPoint = { step: anyStep };
    PANELS.forEach(p => {
      speedPoint[`${p.key}_speed`] = data?.[p.key]?.metrics?.avg_speed ?? null;
    });

    // setState chỉ để trigger re-render UI — giá trị đã tính xong ở trên
    setTotalWait({ ...totalWaitRef.current });
    setHistory(prev => [...prev, point].slice(-MAX_CHART_POINTS));
    setSpeedHistory(prev => [...prev, speedPoint].slice(-MAX_CHART_POINTS));

  }, [data]);

  const doReset = () => {
    lastStepRef.current       = 0;
    cumulativeRef.current     = ZERO_TOTALS();
    totalWaitRef.current      = ZERO_TOTALS();
    setHistory([]);
    setTotalWait(ZERO_TOTALS());
    setSpeedHistory([]);
  };

  const handleStart  = (route, volume) => { doReset(); sendCommand(`start:${route}:${volume}`); };
  const handleInject = (edgeId, mode)  => sendCommand(`inject_accident:${edgeId}:${mode}`);
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
          <AccidentDropdown onInject={handleInject} topology={topology}/>
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
        totalWait={totalWait}
        speedHistory={speedHistory}
      />
    </div>
  );
}
