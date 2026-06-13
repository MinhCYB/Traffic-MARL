// dashboard/src/components/TrafficMap.jsx
import { useMemo, useRef } from "react";
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

function getVehicleXY(v, NODE, SRC, EDGES) {
  const e = EDGES[v.edge];
  if (!e) return null;
  const from = getPos(e.from, NODE, SRC);
  const to   = getPos(e.to,   NODE, SRC);
  if (!from || !to) return null;
  const p   = interp(from, to, Math.max(0, Math.min(1, v.pos)));
  const dx  = to.x - from.x, dy = to.y - from.y;
  const len = Math.sqrt(dx*dx + dy*dy) || 1;
  const nx  = -dy/len, ny = dx/len;
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

// ── Intersections ─────────────────────────────────────────────────────────────
function Intersections({ NODE, intersections }) {
  const lookup = {};
  (intersections||[]).forEach(i => { lookup[i.id] = i; });
  const LIGHT_OFF = 14;

  return (
    <g>
      {Object.entries(NODE).map(([nid, pos]) => {
        const data   = lookup[nid];
        const phase  = data?.phase ?? 0;
        const lights = PHASE_LIGHTS[phase] || PHASE_LIGHTS[0];
        const sz     = 12;
        return (
          <g key={nid}>
            <rect x={pos.x-sz} y={pos.y-sz} width={sz*2} height={sz*2}
              fill="#e8e6df" stroke="#c8c6be" strokeWidth={0.5}/>
            <line x1={pos.x-sz} y1={pos.y-sz+3} x2={pos.x-sz+3} y2={pos.y-sz+3} stroke="white" strokeWidth={1.5}/>
            <line x1={pos.x+sz-3} y1={pos.y-sz+3} x2={pos.x+sz} y2={pos.y-sz+3} stroke="white" strokeWidth={1.5}/>
            <line x1={pos.x-sz} y1={pos.y+sz-3} x2={pos.x-sz+3} y2={pos.y+sz-3} stroke="white" strokeWidth={1.5}/>
            <line x1={pos.x+sz-3} y1={pos.y+sz-3} x2={pos.x+sz} y2={pos.y+sz-3} stroke="white" strokeWidth={1.5}/>
            <text x={pos.x} y={pos.y+1} textAnchor="middle" dominantBaseline="central"
              fontSize={7} fontWeight="700" fill="#5f5e5a">{nid}</text>
            {[
              { dir:"N", x: pos.x,         y: pos.y-LIGHT_OFF },
              { dir:"S", x: pos.x,         y: pos.y+LIGHT_OFF },
              { dir:"W", x: pos.x-LIGHT_OFF, y: pos.y },
              { dir:"E", x: pos.x+LIGHT_OFF, y: pos.y },
            ].map(({dir, x, y}) => (
              <g key={dir}>
                <circle cx={x} cy={y} r={4} fill="#2c2c2a" opacity={0.7}/>
                <circle cx={x} cy={y} r={2.5} fill={LIGHT_C[lights[dir]]}/>
              </g>
            ))}
          </g>
        );
      })}
    </g>
  );
}

// ── Vehicles ──────────────────────────────────────────────────────────────────
function Vehicles({ vehicles, color, NODE, SRC, EDGES }) {
  return (
    <g>
      {(vehicles||[]).slice(0,100).map(v => {
        const xy = getVehicleXY(v, NODE, SRC, EDGES);
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
        const mid = interp(from, to, 0.5);
        return (
          <g key={edgeId}>
            <circle cx={mid.x} cy={mid.y} r={12} fill="#e24b4a" opacity={0.15}/>
            <circle cx={mid.x} cy={mid.y} r={6}  fill="#e24b4a" opacity={0.6}/>
            <text x={mid.x} y={mid.y-14} textAnchor="middle" fontSize={9} fill="#e24b4a" fontWeight="600">
              {mode === "all" ? "🚨 CHẶN" : "⚠️ TAI NẠN"}
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
  const arrows = [];
  IDS.forEach((dst, di) => IDS.forEach((src, si) => {
    if (src === dst) return;
    const w = attn[di]?.[si] ?? 0;
    if (w < 0.4) return;
    const f = NODE[src], t = NODE[dst];
    if (!f || !t) return;
    arrows.push(
      <line key={`${src}-${dst}`}
        x1={f.x} y1={f.y} x2={t.x} y2={t.y}
        stroke="#534ab7" strokeWidth={0.5+w*2}
        strokeDasharray="4 3" opacity={0.2+w*0.5}
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
        <Vehicles vehicles={data?.vehicles} color={color} NODE={NODE} SRC={SRC} EDGES={EDGES}/>
        <Intersections NODE={NODE} intersections={data?.intersections}/>
        <TopologyBadge topology={topology}/>
        <SpeedLegend H={H}/>
      </svg>
    </div>
  );
}
