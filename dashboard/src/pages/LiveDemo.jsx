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
  { value: 0.5, label: "🚗 Thưa"          },
  { value: 1.0, label: "🚗🚗 Bình thường"  },
  { value: 1.8, label: "🚗🚗🚗 Đông"       },
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
// Build map: "SRC_HTM_W" → ["N01","N02"] từ EDGES layout
function buildSrcNodeMap(edges) {
  const srcMap = {};
  Object.values(edges || {}).forEach(e => {
    if (typeof e.from === "object" || typeof e.to === "object") return;
    const srcSide  = [e.from, e.to].find(s => s.startsWith("SRC_"));
    const nodeSide = [e.from, e.to].find(s => /^N\d+$/.test(s));
    if (!srcSide || !nodeSide) return;
    if (!srcMap[srcSide]) srcMap[srcSide] = new Set();
    srcMap[srcSide].add(nodeSide);
  });
  return Object.fromEntries(
    Object.entries(srcMap).map(([k, v]) => [k, [...v].sort()])
  );
}

// Group edges theo SRC, label đổi thành "N01 → N02"
function groupEdgesByJunction(accidentEdges, srcNodeMap) {
  const groups = {};
  accidentEdges.forEach(({ label, value }) => {
    const parts   = label.split(" → ");
    const srcPart = parts.find(p => p.startsWith("SRC_"));
    if (!srcPart) return;
    const groupKey = srcPart.replace(/^SRC_/, "");

    // Lấy node đầu và cuối từ label: "SRC_X → Nxx" hoặc "Nxx → SRC_X"
    const fromNode = /^N\d+$/.test(parts[0]) ? parts[0] : null;
    const toNode   = /^N\d+$/.test(parts[1]) ? parts[1] : null;
    const nodes    = srcNodeMap[srcPart] || [];
    const nodeA    = fromNode || nodes[0] || "?";
    const nodeB    = toNode   || nodes[1] || "?";

    if (!groups[groupKey]) groups[groupKey] = [];
    groups[groupKey].push({ label: `${nodeA} → ${nodeB}`, fullLabel: label, value });
  });
  return groups;
}

function AccidentDropdown({ onInject, onClear, topology }) {
  const [open,     setOpen]     = useState(false);
  const [search,   setSearch]   = useState("");
  const [expanded, setExpanded] = useState({});
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  // Reset khi đóng — KHÔNG auto-expand
  useEffect(() => {
    if (!open) { setSearch(""); setExpanded({}); }
  }, [open]);

  const layout        = getLayout(topology || "2x2");
  const accidentEdges = layout.DEMO_ACCIDENT_EDGES || [];
  const srcNodeMap    = buildSrcNodeMap(layout.EDGES || {});
  const groups        = groupEdgesByJunction(accidentEdges, srcNodeMap);

  // Filter theo search
  const filteredGroups = Object.entries(groups).reduce((acc, [gk, edges]) => {
    const q = search.toLowerCase();
    const matched = edges.filter(e =>
      !q || e.label.toLowerCase().includes(q) || gk.toLowerCase().includes(q)
    );
    if (matched.length) acc[gk] = matched;
    return acc;
  }, {});

  // Chỉ expand khi search hoặc user click
  const isExpanded  = (gk) => search ? true : !!expanded[gk];
  const toggleGroup = (gk) => setExpanded(e => ({ ...e, [gk]: !e[gk] }));

  return (
    <div className="accident-dropdown" ref={ref}>
      <div style={{ display:"flex", gap:0 }}>
        <button className="ctrl-btn ctrl-btn--accident" onClick={() => setOpen(o => !o)}>
          🚨 Tai nạn ▾
        </button>
        <button
          className="ctrl-btn ctrl-btn--clear"
          style={{ borderRadius:"0 7px 7px 0", padding:"6px 10px", marginLeft:1 }}
          title="Xóa tất cả chặn"
          onClick={() => { onClear(); setOpen(false); }}>
          ✕
        </button>
      </div>

      {open && (
        <div className="accident-menu-v2">
          {/* Search bar */}
          <div className="acc-search-wrap">
            <span className="acc-search-icon">🔍</span>
            <input
              className="acc-search-input"
              placeholder="Tìm đoạn đường..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus
            />
            {search && (
              <button className="acc-search-clear" onClick={() => setSearch("")}>✕</button>
            )}
          </div>

          {/* Clear all */}
          <button className="acc-clear-all" onClick={() => { onClear(); setOpen(false); }}>
            ✕ Xóa tất cả vật cản
          </button>

          <div className="acc-divider"/>

          {/* Groups */}
          <div className="acc-groups">
            {Object.keys(filteredGroups).length === 0 ? (
              <div className="acc-empty">Không tìm thấy đoạn đường</div>
            ) : (
              Object.entries(filteredGroups).map(([gk, edges]) => (
                <div key={gk} className="acc-group">
                  {/* Group header */}
                  <button className="acc-group-header" onClick={() => toggleGroup(gk)}>
                    <span className="acc-group-chevron">{isExpanded(gk) ? "▾" : "▸"}</span>
                    <span className="acc-group-name">{gk}</span>
                    <span className="acc-group-count">{edges.length} đoạn</span>
                  </button>

                  {/* Edges */}
                  {isExpanded(gk) && (
                    <div className="acc-group-body">
                      {edges.map(({ label, fullLabel, value }) => (
                        <div key={value} className="acc-edge-row">
                          <span className="acc-edge-label" title={fullLabel}>
                            {label}
                          </span>
                          <div className="acc-edge-actions">
                            <button className="acc-btn acc-btn--left"
                              title="Chặn lane trái"
                              onClick={() => { onInject(value, "left"); setOpen(false); }}>
                              ◀ Trái
                            </button>
                            <button className="acc-btn acc-btn--right"
                              title="Chặn lane phải"
                              onClick={() => { onInject(value, "right"); setOpen(false); }}>
                              Phải ▶
                            </button>
                            <button className="acc-btn acc-btn--all"
                              title="Chặn toàn bộ"
                              onClick={() => { onInject(value, "all"); setOpen(false); }}>
                              🚨
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Score Tooltip ─────────────────────────────────────────────────────────────
function ScoreTooltip() {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position:"relative", display:"inline-block", marginLeft:6 }}>
      <span
        style={{ cursor:"pointer", fontSize:12, color:"#888780", userSelect:"none" }}
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}>
        ❓
      </span>
      {show && (
        <div style={{
          position:"absolute", bottom:"calc(100% + 6px)", left:"50%",
          transform:"translateX(-50%)", background:"white",
          border:"1px solid #e2e0d8", borderRadius:8, padding:"10px 14px",
          width:240, zIndex:999, fontSize:11, color:"#444",
          boxShadow:"0 4px 16px rgba(0,0,0,0.10)", lineHeight:1.6,
        }}>
          <div style={{ fontWeight:600, marginBottom:6 }}>Cách tính điểm</div>
          <div>⏱ Ít chờ: <b>50%</b></div>
          <div>🚗 Xe hoàn thành: <b>30%</b></div>
          <div>⚡ Tốc độ TB: <b>20%</b></div>
          <div style={{ color:"#e24b4a" }}>🚫 Teleport penalty: <b>−10%</b></div>
          <div style={{ marginTop:6, color:"#888780" }}>
            Tốc độ = avg toàn bộ session.<br/>
            Mỗi tiêu chí normalize 0–1 so với model tốt/tệ nhất.<br/>
            Max score = 100 (khi không có xe teleport).
          </div>
        </div>
      )}
    </span>
  );
}

// ── Rank Table ───────────────────────────────────────────────────────────────
function RankTable({ history, totalWait, speedHistory, totalTeleport }) {
  if (!history.length) return null;

  const last = history[history.length - 1];

  // Speed = avg toàn bộ session (không phải snapshot cuối)
  const avgSpeed = (key) => {
    const pts = speedHistory.map(p => p[`${key}_speed`]).filter(v => v != null && v > 0);
    return pts.length ? Math.round(pts.reduce((a, b) => a + b, 0) / pts.length * 10) / 10 : 0;
  };
  const minSpeed = (key) => {
    const pts = speedHistory.map(p => p[`${key}_speed`]).filter(v => v != null && v > 0);
    return pts.length ? Math.round(Math.min(...pts) * 10) / 10 : 0;
  };
  const maxSpeed = (key) => {
    const pts = speedHistory.map(p => p[`${key}_speed`]).filter(v => v != null && v > 0);
    return pts.length ? Math.round(Math.max(...pts) * 10) / 10 : 0;
  };

  const raw = PANELS.map(p => ({
    ...p,
    completed:  last?.[`${p.key}_cum`]    ?? 0,
    wait:       totalWait[p.key]           ?? 0,
    speed:      avgSpeed(p.key),
    minSpd:     minSpeed(p.key),
    maxSpd:     maxSpeed(p.key),
    teleported: totalTeleport?.[p.key]    ?? 0,
  }));

  const maxCompleted  = Math.max(...raw.map(r => r.completed))  || 1;
  const maxWait       = Math.max(...raw.map(r => r.wait))       || 1;
  const maxSpd        = Math.max(...raw.map(r => r.speed))      || 1;
  const maxTeleported = Math.max(...raw.map(r => r.teleported)) || 1;

  const ranked = raw.map(r => {
    // teleport_penalty normalize 0-1 so với model tệ nhất → trừ tối đa 10 điểm
    const teleportPenalty = r.teleported / maxTeleported;
    return {
      ...r,
      teleportPenalty,
      score: Math.round(
        (1 - r.wait  / maxWait)      * 50 +   // ít chờ 50%
        (r.completed / maxCompleted) * 30 +   // throughput 30%
        (r.speed     / maxSpd)       * 20 -   // tốc độ 20%
        teleportPenalty              * 10      // teleport penalty -10%
      ),
    };
  }).sort((a, b) => b.score - a.score);

  const medals = ["🥇", "🥈", "🥉"];

  return (
    <div className="chart-card rank-table-card">
      <div className="chart-card-title">
        Bảng xếp hạng
        <ScoreTooltip/>
      </div>
      <table className="rank-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Model</th>
            <th title="Xe đã qua mạng">🚗 Xe HT</th>
            <th title="Tổng thời gian chờ tích lũy">⏱ Chờ (k s)</th>
            <th title="Tốc độ trung bình toàn session (min – max)">⚡ Tốc độ</th>
            <th title="Tổng xe bị SUMO teleport do kẹt quá lâu">🚫 Teleport</th>
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
              <td>
                {r.speed > 0
                  ? <span>
                      <b>{r.speed}</b>
                      <span style={{ fontSize:10, color:"#888780", marginLeft:4 }}>
                        ({r.minSpd}–{r.maxSpd}) km/h
                      </span>
                    </span>
                  : "—"}
              </td>
              <td className="rank-teleport">
                {r.teleported > 0
                  ? <span style={{ color: "#e24b4a" }}>
                      {r.teleported}
                      <span style={{ fontSize:10, color:"#e24b4a88", marginLeft:3 }}>
                        (−{Math.round(r.teleportPenalty * 10)})
                      </span>
                    </span>
                  : <span style={{ color:"#1d9e75" }}>0</span>}
              </td>
              <td className="rank-score" style={{ color: r.color }}>{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Realtime Charts ───────────────────────────────────────────────────────────
function RealtimeCharts({ history, totalWait, speedHistory, totalTeleport }) {
  if (!history.length) return null;

  const summaryData = PANELS.map(p => ({
    name:      p.label,
    completed: history[history.length - 1]?.[`${p.key}_cum`] ?? 0,
    wait:      Math.round((totalWait[p.key] ?? 0) / 1000 * 10) / 10,
    color:     p.color,
  }));

  return (
    <div className="realtime-charts">
      <RankTable history={history} totalWait={totalWait} speedHistory={speedHistory} totalTeleport={totalTeleport}/>

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
                connectNulls={false} isAnimationActive={false}/>
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
      <MetricsPanel metrics={workerData?.metrics} mode={cfg.key} workerData={workerData}/>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function LiveDemo() {
  const { data, status, connected, sendCommand } = useWebSocket();
  const [visible,   setVisible]   = useState({ fixed_time:true, idqn:true, gat_marl:true });
  const [history,   setHistory]   = useState([]);
  const [totalWait,     setTotalWait]     = useState(ZERO_TOTALS());
  const [totalTeleport, setTotalTeleport] = useState(ZERO_TOTALS());

  const lastStepRef      = useRef(0);
  const cumulativeRef    = useRef(ZERO_TOTALS());
  const totalWaitRef     = useRef(ZERO_TOTALS());
  const totalTeleportRef = useRef(ZERO_TOTALS());

  const [speedHistory, setSpeedHistory] = useState([]);

  const topology = PANELS.reduce((t, p) => data?.[p.key]?.topology || t, null)
                ?? (import.meta.env.VITE_TOPOLOGY || "2x2");

  useEffect(() => {
    if (!data) return;
    const anyStep = PANELS.reduce((s, p) => data?.[p.key]?.step ?? s, 0);
    if (!anyStep || anyStep <= lastStepRef.current) return;
    lastStepRef.current = anyStep;

    const point = { step: anyStep };
    PANELS.forEach(p => {
      const completed = data?.[p.key]?.metrics?.vehicles_completed ?? 0;
      cumulativeRef.current[p.key] = (cumulativeRef.current[p.key] ?? 0) + completed;
      point[`${p.key}_cum`] = cumulativeRef.current[p.key];
      const tw = data?.[p.key]?.metrics?.total_waiting_time ?? 0;
      totalWaitRef.current[p.key] = (totalWaitRef.current[p.key] ?? 0) + tw;
      const tp = data?.[p.key]?.metrics?.vehicles_teleported ?? 0;
      totalTeleportRef.current[p.key] = (totalTeleportRef.current[p.key] ?? 0) + tp;
    });

    const speedPoint = { step: anyStep };
    PANELS.forEach(p => {
      speedPoint[`${p.key}_speed`] = data?.[p.key]?.metrics?.avg_speed ?? null;
    });

    setTotalWait({ ...totalWaitRef.current });
    setTotalTeleport({ ...totalTeleportRef.current });
    setHistory(prev => [...prev, point].slice(-MAX_CHART_POINTS));
    setSpeedHistory(prev => [...prev, speedPoint].slice(-MAX_CHART_POINTS));
  }, [data]);

  const doReset = () => {
    lastStepRef.current      = 0;
    cumulativeRef.current    = ZERO_TOTALS();
    totalWaitRef.current     = ZERO_TOTALS();
    totalTeleportRef.current = ZERO_TOTALS();
    setHistory([]);
    setTotalWait(ZERO_TOTALS());
    setTotalTeleport(ZERO_TOTALS());
    setSpeedHistory([]);
  };

  const handleStart  = (route, volume) => { doReset(); sendCommand(`start:${route}:${volume}`); };
  const handleInject = (edgeId, mode)  => sendCommand(`inject_accident:${edgeId}:${mode}`);
  const handleClear  = ()              => sendCommand("clear_accident");
  const handleReset  = ()              => { doReset(); sendCommand("reset"); };
  const togglePanel  = (key)           => setVisible(v => ({ ...v, [key]: !v[key] }));

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
          <AccidentDropdown onInject={handleInject} onClear={handleClear} topology={topology}/>
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

      <RealtimeCharts history={history} totalWait={totalWait} speedHistory={speedHistory} totalTeleport={totalTeleport}/>
    </div>
  );
}