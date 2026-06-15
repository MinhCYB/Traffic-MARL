// dashboard/src/components/TrafficMap.jsx
import { useMemo, useRef, useEffect, useState } from "react";

// Hook lưu giá trị step trước để detect phase change
function usePrevious(value) {
  const ref = useRef(null);
  useEffect(() => { ref.current = value; });
  return ref.current;
}
import { getLayout } from "../mapLayouts/index.js";

// Phase → đèn 4 hướng
const PHASE_LIGHTS = {
  0: { N: "green",  S: "green",  E: "red",    W: "red"    },
  1: { N: "yellow", S: "yellow", E: "red",    W: "red"    },
  2: { N: "red",    S: "red",    E: "green",  W: "green"  },
  3: { N: "red",    S: "red",    E: "yellow", W: "yellow" },
};
const LIGHT_C = { green: "#1d9e75", yellow: "#ef9f27", red: "#e24b4a" };
const ROAD_W  = { arterial: 12, main: 10, secondary: 7, alley: 6, outskirts: 8 };
const MODEL_C = { fixed_time: "#e24b4a", idqn: "#ba7517", gat_marl: "#534ab7" };

function speedColor(kmh) {
  if (kmh == null || kmh < 0) return "#d3d1c7";
  if (kmh >= 25) return "#1d9e75";
  if (kmh >= 10) return "#ef9f27";
  return "#e24b4a";
}

function getPos(key, NODE, SRC) {
  if (!key) return null;
  if (typeof key === "object") return key;
  return NODE[key] || SRC[key] || null;
}

function interp(a, b, t) {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

// Tính hướng xe đến ngã tư (N/S/E/W) dựa vào vector from→to
function approachDir(from, to) {
  const dx = to.x - from.x, dy = to.y - from.y;
  if (Math.abs(dx) >= Math.abs(dy)) return dx > 0 ? "E" : "W";
  return dy > 0 ? "S" : "N";
}

function getVehicleXY(v, NODE, SRC, EDGES, phaseLookup) {
  const e = EDGES[v.edge];
  if (!e) return null;
  const from = getPos(e.from, NODE, SRC);
  const to   = getPos(e.to,   NODE, SRC);
  if (!from || !to) return null;

  const dx  = to.x - from.x, dy = to.y - from.y;
  const len = Math.sqrt(dx*dx + dy*dy) || 1;

  // Clamp xe trước stop line nếu đèn đỏ/vàng
  // Stop line nằm cách tâm ngã tư SZ=9 px → tính thành tỉ lệ pos
  const SZ         = 9;
  const STOP_RATIO = Math.min(0.97, Math.max(0, (len - SZ) / len));
  let pos = Math.max(0, Math.min(1, v.pos));

  const toNodeId = typeof e.to === "string" ? e.to : null;
  if (toNodeId && NODE[toNodeId] && phaseLookup) {
    const nodeData = phaseLookup[toNodeId];
    if (nodeData) {
      const lights = PHASE_LIGHTS[nodeData.phase] || PHASE_LIGHTS[0];
      const dir    = approachDir(from, to);
      if (lights[dir] === "red" || lights[dir] === "yellow") {
        pos = Math.min(pos, STOP_RATIO);
      }
    }
  }

  const p  = interp(from, to, pos);
  const nx = -dy/len, ny = dx/len;
  const off = v.lane === 0 ? 2.5 : -2.5;
  return { x: p.x + nx*off, y: p.y + ny*off, angle: Math.atan2(dy,dx)*180/Math.PI };
}

// ── Roads with heatmap ────────────────────────────────────────────────────────
function Roads({ EDGES, NODE, SRC, edgeSpeeds, accidentEdges }) {
  // useMemo để drawn Set không bị reset khi React re-render (Strict Mode double-render)
  const segments = useMemo(() => {
    const drawn = new Set();
    return Object.entries(EDGES).filter(([, e]) => {
      const key = [JSON.stringify(e.from), JSON.stringify(e.to)].sort().join("|");
      if (drawn.has(key)) return false;
      drawn.add(key);
      return true;
    });
  }, [EDGES]);

  return (
    <g>
      {segments.map(([id, e]) => {
        const key  = [JSON.stringify(e.from), JSON.stringify(e.to)].sort().join("|");
        const from = getPos(e.from, NODE, SRC);
        const to   = getPos(e.to,   NODE, SRC);
        if (!from || !to) return null;
        const w     = ROAD_W[e.type] ?? 8;
        const speed = edgeSpeeds?.[id] ?? edgeSpeeds?.[id.split("_").reverse().join("_")];
        const isAcc = accidentEdges?.[id] != null;
        const color = isAcc ? "#e24b4a" : speedColor(speed);
        return (
          <g key={key}>
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="#c8c6be" strokeWidth={w+2} strokeLinecap="round"/>
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={color} strokeWidth={w} strokeLinecap="round" opacity={isAcc ? 1 : 0.75}/>
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="white" strokeWidth={0.5} strokeDasharray="6 4" opacity={0.5}/>
          </g>
        );
      })}
    </g>
  );
}

// ── CountdownPill — hiển thị tsc trực tiếp từ server, không dùng client tick
function CountdownPill({ tsc, dt, px, py }) {
  const SZ     = 9;
  const CD_OFF = SZ + 10;

  // Còn lại = dt - tsc, lấy thẳng từ server — không fake bằng client tick
  const remaining = Math.max(0, Math.round(dt - tsc));
  const cdColor   = remaining <= 4 ? "#534ab7" : "#888780";
  const PW = 22; const PH = 11;

  return (
    <g>
      <rect x={px+CD_OFF-PW/2} y={py+CD_OFF-PH/2}
        width={PW} height={PH} rx={PH/2}
        fill={cdColor} opacity={0.85}/>
      <text x={px+CD_OFF} y={py+CD_OFF+0.5}
        textAnchor="middle" dominantBaseline="central"
        fontSize={7} fontWeight="800" fill="white">
        {remaining}s
      </text>
    </g>
  );
}

// ── Intersections: bo tròn + stop line đổi màu + countdown ──────────────────
function Intersections({ NODE, intersections, deltaTime, modelColor }) {
  const lookup = {};
  (intersections||[]).forEach(i => { lookup[i.id] = i; });

  // Track phase changes để hiển thị SWITCH/HOLD badge
  const prevLookup = usePrevious(lookup);
  const [pulseNodes, setPulseNodes] = useState({});

  useEffect(() => {
    if (!prevLookup) return;
    const switched = {};
    Object.keys(lookup).forEach(nid => {
      const cur  = lookup[nid]?.phase;
      const prev = prevLookup[nid]?.phase;
      if (cur !== undefined && prev !== undefined && cur !== prev) {
        switched[nid] = Date.now();
      }
    });
    if (Object.keys(switched).length > 0) {
      setPulseNodes(p => ({ ...p, ...switched }));
      setTimeout(() => {
        setPulseNodes(p => {
          const next = { ...p };
          Object.keys(switched).forEach(k => delete next[k]);
          return next;
        });
      }, 1500);
    }
  }, [intersections]);

  const SZ       = 9;
  const STOP_OFF = SZ;
  const STOP_LEN = SZ;
  const R        = 3;

  return (
    <g>
      {Object.entries(NODE).map(([nid, pos]) => {
        const data   = lookup[nid];
        const phase  = data?.phase ?? 0;
        const lights = PHASE_LIGHTS[phase] || PHASE_LIGHTS[0];
        const tsc    = data?.time_since_change ?? 0;
        const dt     = deltaTime ?? 13;

        return (
          <g key={nid}>
            {/* Ngã tư bo tròn */}
            <rect x={pos.x-SZ} y={pos.y-SZ} width={SZ*2} height={SZ*2}
              rx={R} ry={R}
              fill="#e8e6df" stroke="#c8c6be" strokeWidth={0.5}/>

            {/* Stop lines — 4 hướng, màu theo pha đèn */}
            {[
              { dir:"N", x1:pos.x-STOP_LEN, y1:pos.y-STOP_OFF, x2:pos.x+STOP_LEN, y2:pos.y-STOP_OFF },
              { dir:"S", x1:pos.x-STOP_LEN, y1:pos.y+STOP_OFF, x2:pos.x+STOP_LEN, y2:pos.y+STOP_OFF },
              { dir:"W", x1:pos.x-STOP_OFF, y1:pos.y-STOP_LEN, x2:pos.x-STOP_OFF, y2:pos.y+STOP_LEN },
              { dir:"E", x1:pos.x+STOP_OFF, y1:pos.y-STOP_LEN, x2:pos.x+STOP_OFF, y2:pos.y+STOP_LEN },
            ].map(({ dir, x1, y1, x2, y2 }) => (
              <line key={dir} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={LIGHT_C[lights[dir]]}
                strokeWidth={lights[dir] === "green" ? 2.5 : 2}
                strokeLinecap="round"
                opacity={lights[dir] === "yellow" ? 0.8 : 1}/>
            ))}

            {/* Label ngã tư */}
            <text x={pos.x} y={pos.y+1} textAnchor="middle" dominantBaseline="central"
              fontSize={6} fontWeight="700" fill="#5f5e5a">{nid}</text>

            {/* Countdown pill — component riêng, tick của riêng nó */}
            <CountdownPill tsc={tsc} dt={dt} px={pos.x} py={pos.y}/>

            {/* Pulse ring khi SWITCH */}
            {pulseNodes[nid] && (
              <rect
                x={pos.x-SZ-4} y={pos.y-SZ-4}
                width={(SZ+4)*2} height={(SZ+4)*2}
                rx={R+3} ry={R+3}
                fill="none"
                stroke={modelColor || "#534ab7"}
                strokeWidth={2}
                opacity={0.7}
                style={{
                  animation: "pulse-ring 1.5s ease-out forwards",
                }}
              />
            )}

            {/* SWITCH / HOLD badge — góc trên trái */}
            {data && (() => {
              const switched = pulseNodes[nid];
              return (
                <g>
                  <rect
                    x={pos.x - SZ} y={pos.y - SZ - 11}
                    width={switched ? 36 : 28} height={10}
                    rx={3}
                    fill={switched ? (modelColor || "#534ab7") : "#94a3b8"}
                    opacity={switched ? 0.92 : 0.55}
                  />
                  <text
                    x={pos.x - SZ + (switched ? 18 : 14)}
                    y={pos.y - SZ - 5}
                    textAnchor="middle" dominantBaseline="central"
                    fontSize={6} fontWeight="700" fill="white">
                    {switched ? "↺ SWITCH" : "⏸ HOLD"}
                  </text>
                </g>
              );
            })()}
          </g>
        );
      })}
    </g>
  );
}

// ── Vehicles ──────────────────────────────────────────────────────────────────
function Vehicles({ vehicles, color, NODE, SRC, EDGES, phaseLookup }) {
  return (
    <g>
      {(vehicles||[]).slice(0,300).map(v => {
        const xy = getVehicleXY(v, NODE, SRC, EDGES, phaseLookup);
        if (!xy) return null;
        const isBus  = v.type?.includes("bus");
        const isMoto = v.type?.includes("moto");
        const w = isBus ? 13 : isMoto ? 7 : 9;
        const h = isBus ? 6  : isMoto ? 3 : 5;
        const rx = isBus ? 1 : 1.5;
        const arrowSize = isMoto ? 2.5 : 3;
        return (
          <g key={v.id}
            transform={`translate(${xy.x.toFixed(1)},${xy.y.toFixed(1)}) rotate(${xy.angle.toFixed(1)})`}>
            <rect x={-w/2} y={-h/2} width={w} height={h} rx={rx}
              fill={color} opacity={0.9} stroke="white" strokeWidth={0.3}/>
            <polygon
              points={`${w/2},0 ${w/2-arrowSize},${-arrowSize*0.7} ${w/2-arrowSize},${arrowSize*0.7}`}
              fill="white" opacity={0.7}/>
          </g>
        );
      })}
    </g>
  );
}

// ── Accident markers ──────────────────────────────────────────────────────────
function AccidentMarkers({ accidentEdges, EDGES, NODE, SRC }) {
  if (!accidentEdges || Object.keys(accidentEdges).length === 0) return null;
  return (
    <g>
      {Object.entries(accidentEdges).map(([edgeId, mode]) => {
        const e = EDGES[edgeId];
        if (!e) return null;
        const from = getPos(e.from, NODE, SRC);
        const to   = getPos(e.to,   NODE, SRC);
        if (!from || !to) return null;

        const dx  = to.x - from.x, dy = to.y - from.y;
        const len = Math.sqrt(dx*dx + dy*dy) || 1;
        const nx  = -dy/len, ny = dx/len;  // normal vector

        // Thanh chắn ngang đường, đặt ở giữa edge
        const mid = interp(from, to, 0.5);
        const BAR_W = 16;  // độ dài thanh chắn
        const BAR_H = 4;   // độ dày

        // all=đỏ, left/right=vàng lệch sang 1 bên
        const isAll   = mode === "all";
        const barColor = isAll ? "#e24b4a" : "#ef9f27";
        const offset  = isAll ? 0 : (mode === "left" ? -5 : 5);

        const bx = mid.x + nx * offset;
        const by = mid.y + ny * offset;
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;

        return (
          <g key={edgeId}>
            {/* Vùng đỏ/vàng nhạt nền */}
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={barColor} strokeWidth={isAll ? 10 : 6} opacity={0.15}/>
            {/* Thanh chắn */}
            <g transform={`translate(${bx},${by}) rotate(${angle + 90})`}>
              <rect x={-BAR_W/2} y={-BAR_H/2} width={BAR_W} height={BAR_H}
                rx={2} fill={barColor} opacity={0.9}/>
              {/* Sọc cảnh báo */}
              {[0.25, 0.5, 0.75].map(t => (
                <line key={t}
                  x1={-BAR_W/2 + t*BAR_W} y1={-BAR_H/2}
                  x2={-BAR_W/2 + t*BAR_W} y2={BAR_H/2}
                  stroke="white" strokeWidth={1} opacity={0.6}/>
              ))}
            </g>
            <text x={mid.x} y={mid.y - 14} textAnchor="middle"
              fontSize={8} fill={barColor} fontWeight="700">
              {isAll ? "🚨 CHẶN" : mode === "left" ? "⚠️ LANE TRÁI" : "⚠️ LANE PHẢI"}
            </text>
          </g>
        );
      })}
    </g>
  );
}

// ── Attention arrows (GAT-MARL only) ─────────────────────────────────────────
function AttentionArrows({ attn, NODE }) {
  if (!attn || !NODE) return null;
  const IDS = Object.keys(NODE);
  const n = IDS.length;
  // Threshold động theo số nodes:
  // Softmax trên n neighbors → weight trung bình = 1/n
  // Hiện "đáng chú ý" khi weight > 1.5× trung bình
  const threshold = Math.max(0.08, 1.5 / n);
  const arrows = [];
  IDS.forEach((dst, di) => IDS.forEach((src, si) => {
    if (src === dst) return;
    const w = attn[di]?.[si] ?? 0;
    if (w < threshold) return;
    const f = NODE[src], t = NODE[dst];
    if (!f || !t) return;
    // Normalize opacity/strokeWidth theo threshold để visual scale đẹp
    const norm = Math.min(1, (w - threshold) / (1 - threshold));
    arrows.push(
      <line key={`${src}-${dst}`}
        x1={f.x} y1={f.y} x2={t.x} y2={t.y}
        stroke="#534ab7" strokeWidth={0.5+norm*2.5}
        strokeDasharray="4 3" opacity={0.25+norm*0.6}
        markerEnd="url(#attn-a)"/>
    );
  }));
  return (
    <g>
      <defs>
        <marker id="attn-a" viewBox="0 0 8 8" refX="6" refY="4"
          markerWidth="4" markerHeight="4" orient="auto">
          <path d="M1 1L7 4L1 7" fill="none" stroke="#534ab7" strokeWidth="1.5"/>
        </marker>
      </defs>
      {arrows}
    </g>
  );
}

// ── Speed legend ──────────────────────────────────────────────────────────────
function SpeedLegend({ H }) {
  return (
    <g>
      <rect x={8} y={H-22} width={110} height={14} rx={3}
        fill="white" stroke="#d3d1c7" strokeWidth={0.5} opacity={0.9}/>
      {[
        { color:"#1d9e75", label:">25 km/h", x:14 },
        { color:"#ef9f27", label:"10-25",    x:52 },
        { color:"#e24b4a", label:"<10",      x:82 },
      ].map(({color,label,x})=>(
        <g key={label}>
          <rect x={x} y={H-18} width={6} height={6} rx={1} fill={color}/>
          <text x={x+8} y={H-12} fontSize={6.5} fill="#5f5e5a">{label}</text>
        </g>
      ))}
    </g>
  );
}

// ── Topology badge ────────────────────────────────────────────────────────────
function TopologyBadge({ topology }) {
  if (!topology) return null;
  return (
    <g>
      <rect x={8} y={8} width={topology.length * 6.5 + 12} height={14} rx={3}
        fill="#534ab7" opacity={0.85}/>
      <text x={14} y={18} fontSize={8} fill="white" fontWeight="600">
        {topology}
      </text>
    </g>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export function TrafficMap({ data, modelName }) {
  const topology = data?.topology || "2x2";
  const layout   = useMemo(() => getLayout(topology), [topology]);
  const { W, H, NODE, SRC, EDGES } = layout;

  const color         = MODEL_C[modelName] || "#534ab7";
  const edgeSpeeds    = data?.edge_speeds    || {};
  const accidentEdges = data?.accident_edges || {};

  return (
    <div className="traffic-map-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="traffic-map-svg">
        <rect width={W} height={H} fill="#f5f4f1" rx="8"/>
        <Roads EDGES={EDGES} NODE={NODE} SRC={SRC} edgeSpeeds={edgeSpeeds} accidentEdges={accidentEdges}/>
        <AttentionArrows attn={modelName==="gat_marl" ? data?.attention_weights : null} NODE={NODE}/>
        <AccidentMarkers accidentEdges={accidentEdges} EDGES={EDGES} NODE={NODE} SRC={SRC}/>
        <Vehicles vehicles={data?.vehicles} color={color} NODE={NODE} SRC={SRC} EDGES={EDGES}
          phaseLookup={Object.fromEntries((data?.intersections||[]).map(i => [i.id, i]))}/>
        <Intersections NODE={NODE} intersections={data?.intersections} deltaTime={data?.phase_duration ?? 13} modelColor={color}/>
        <TopologyBadge topology={topology}/>
        <SpeedLegend H={H}/>
      </svg>
    </div>
  );
}
