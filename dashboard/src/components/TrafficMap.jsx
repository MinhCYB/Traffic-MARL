// dashboard/src/components/TrafficMap.jsx

const W = 360;
const H = 320;

const NODE = {
  N01: { x: 110, y: 100 },
  N02: { x: 250, y: 100 },
  N03: { x: 110, y: 220 },
  N04: { x: 250, y: 220 },
};

const SRC = {
  SRC1: { x: 180, y: 100 },
  SRC2: { x: 180, y: 220 },
  SRC3: { x: 110, y: 160 },
  SRC4: { x: 250, y: 160 },
};

const EDGES = {
  "N01_SRC1": { from: "N01", to: "SRC1", type: "main" },
  "SRC1_N02": { from: "SRC1", to: "N02", type: "main" },
  "N02_SRC1": { from: "N02", to: "SRC1", type: "main" },
  "SRC1_N01": { from: "SRC1", to: "N01", type: "main" },
  "N03_SRC2": { from: "N03", to: "SRC2", type: "main" },
  "SRC2_N04": { from: "SRC2", to: "N04", type: "main" },
  "N04_SRC2": { from: "N04", to: "SRC2", type: "main" },
  "SRC2_N03": { from: "SRC2", to: "N03", type: "main" },
  "N01_SRC3": { from: "N01", to: "SRC3", type: "alley" },
  "SRC3_N03": { from: "SRC3", to: "N03", type: "alley" },
  "N03_SRC3": { from: "N03", to: "SRC3", type: "alley" },
  "SRC3_N01": { from: "SRC3", to: "N01", type: "alley" },
  "N02_SRC4": { from: "N02", to: "SRC4", type: "alley" },
  "SRC4_N04": { from: "SRC4", to: "N04", type: "alley" },
  "N04_SRC4": { from: "N04", to: "SRC4", type: "alley" },
  "SRC4_N02": { from: "SRC4", to: "N02", type: "alley" },
  "NT_N_W_N01": { from: { x: 110, y: 20  }, to: "N01", type: "outskirts" },
  "N01_NT_N_W": { from: "N01", to: { x: 110, y: 20  }, type: "outskirts" },
  "NT_N_E_N02": { from: { x: 250, y: 20  }, to: "N02", type: "outskirts" },
  "N02_NT_N_E": { from: "N02", to: { x: 250, y: 20  }, type: "outskirts" },
  "NT_S_W_N03": { from: { x: 110, y: 300 }, to: "N03", type: "outskirts" },
  "N03_NT_S_W": { from: "N03", to: { x: 110, y: 300 }, type: "outskirts" },
  "NT_S_E_N04": { from: { x: 250, y: 300 }, to: "N04", type: "outskirts" },
  "N04_NT_S_E": { from: "N04", to: { x: 250, y: 300 }, type: "outskirts" },
  "NT_W_N_N01": { from: { x: 20,  y: 100 }, to: "N01", type: "outskirts" },
  "N01_NT_W_N": { from: "N01", to: { x: 20,  y: 100 }, type: "outskirts" },
  "NT_W_S_N03": { from: { x: 20,  y: 220 }, to: "N03", type: "outskirts" },
  "N03_NT_W_S": { from: "N03", to: { x: 20,  y: 220 }, type: "outskirts" },
  "NT_E_N_N02": { from: { x: 340, y: 100 }, to: "N02", type: "outskirts" },
  "N02_NT_E_N": { from: "N02", to: { x: 340, y: 100 }, type: "outskirts" },
  "NT_E_S_N04": { from: { x: 340, y: 220 }, to: "N04", type: "outskirts" },
  "N04_NT_E_S": { from: "N04", to: { x: 340, y: 220 }, type: "outskirts" },
};

// Phase → đèn 4 hướng
const PHASE_LIGHTS = {
  0: { N: "green",  S: "green",  E: "red",    W: "red"    },
  1: { N: "yellow", S: "yellow", E: "red",    W: "red"    },
  2: { N: "red",    S: "red",    E: "green",  W: "green"  },
  3: { N: "red",    S: "red",    E: "yellow", W: "yellow" },
};
const LIGHT_C = { green: "#1d9e75", yellow: "#ef9f27", red: "#e24b4a" };
const ROAD_W  = { main: 10, alley: 6, outskirts: 8 };
const MODEL_C = { fixed_time: "#e24b4a", idqn: "#ba7517", gat_marl: "#534ab7" };

// Heatmap: speed km/h → màu
function speedColor(kmh) {
  if (kmh == null || kmh < 0) return "#d3d1c7";
  if (kmh >= 25) return "#1d9e75";
  if (kmh >= 10) return "#ef9f27";
  return "#e24b4a";
}

function getPos(key) {
  if (!key) return null;
  if (typeof key === "object") return key;
  return NODE[key] || SRC[key] || null;
}

function interp(a, b, t) {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t };
}

function getVehicleXY(v) {
  const e = EDGES[v.edge];
  if (!e) return null;
  const from = getPos(e.from);
  const to   = getPos(e.to);
  if (!from || !to) return null;
  const p   = interp(from, to, Math.max(0, Math.min(1, v.pos)));
  const dx  = to.x - from.x, dy = to.y - from.y;
  const len = Math.sqrt(dx*dx + dy*dy) || 1;
  const nx  = -dy/len, ny = dx/len;
  const off = v.lane === 0 ? 2.5 : -2.5;
  return { x: p.x + nx*off, y: p.y + ny*off, angle: Math.atan2(dy,dx)*180/Math.PI };
}

// ── Roads with heatmap ────────────────────────────────────────────────────────
function Roads({ edgeSpeeds, accidentEdges }) {
  const drawn = new Set();
  return (
    <g>
      {Object.entries(EDGES).map(([id, e]) => {
        const key = [JSON.stringify(e.from), JSON.stringify(e.to)].sort().join("|");
        if (drawn.has(key)) return null;
        drawn.add(key);
        const from = getPos(e.from), to = getPos(e.to);
        if (!from || !to) return null;
        const w     = ROAD_W[e.type];
        const speed = edgeSpeeds?.[id] ?? edgeSpeeds?.[id.split("_").reverse().join("_")];
        const isAcc = accidentEdges?.[id] != null;
        const color = isAcc ? "#e24b4a" : speedColor(speed);
        return (
          <g key={key}>
            {/* Shadow */}
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="#c8c6be" strokeWidth={w+2} strokeLinecap="round"/>
            {/* Road surface */}
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={color} strokeWidth={w} strokeLinecap="round" opacity={isAcc ? 1 : 0.75}/>
            {/* Lane divider */}
            <line x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke="white" strokeWidth={0.5} strokeDasharray="6 4" opacity={0.5}/>
          </g>
        );
      })}
    </g>
  );
}

// ── Intersections ─────────────────────────────────────────────────────────────
function Intersections({ intersections }) {
  const lookup = {};
  (intersections||[]).forEach(i => { lookup[i.id] = i; });
  const LIGHT_OFF = 14; // offset đèn từ tâm ngã tư

  return (
    <g>
      {Object.entries(NODE).map(([nid, pos]) => {
        const data   = lookup[nid];
        const phase  = data?.phase ?? 0;
        const lights = PHASE_LIGHTS[phase] || PHASE_LIGHTS[0];
        const sz     = 12; // half-size của ngã tư

        return (
          <g key={nid}>
            {/* Nền ngã tư */}
            <rect x={pos.x-sz} y={pos.y-sz} width={sz*2} height={sz*2}
              fill="#e8e6df" stroke="#c8c6be" strokeWidth={0.5}/>

            {/* Vạch dừng 4 hướng */}
            <line x1={pos.x-sz} y1={pos.y-sz+3} x2={pos.x-sz+3} y2={pos.y-sz+3}
              stroke="white" strokeWidth={1.5}/>
            <line x1={pos.x+sz-3} y1={pos.y-sz+3} x2={pos.x+sz} y2={pos.y-sz+3}
              stroke="white" strokeWidth={1.5}/>
            <line x1={pos.x-sz} y1={pos.y+sz-3} x2={pos.x-sz+3} y2={pos.y+sz-3}
              stroke="white" strokeWidth={1.5}/>
            <line x1={pos.x+sz-3} y1={pos.y+sz-3} x2={pos.x+sz} y2={pos.y+sz-3}
              stroke="white" strokeWidth={1.5}/>

            {/* Label nhỏ */}
            <text x={pos.x} y={pos.y+1} textAnchor="middle" dominantBaseline="central"
              fontSize={7} fontWeight="700" fill="#5f5e5a">{nid}</text>

            {/* Đèn 4 hướng */}
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

// ── Vehicles with arrow ───────────────────────────────────────────────────────
function Vehicles({ vehicles, color }) {
  return (
    <g>
      {(vehicles||[]).slice(0,100).map(v => {
        const xy = getVehicleXY(v);
        if (!xy) return null;
        const isBus  = v.type?.includes("bus");
        const isMoto = v.type?.includes("moto");
        const w = isBus ? 13 : isMoto ? 7 : 9;
        const h = isBus ? 6  : isMoto ? 3 : 5;
        const rx = isBus ? 1 : 1.5;
        // Mũi tên nhỏ ở đầu xe
        const arrowSize = isMoto ? 2.5 : 3;

        return (
          <g key={v.id}
            transform={`translate(${xy.x.toFixed(1)},${xy.y.toFixed(1)}) rotate(${xy.angle.toFixed(1)})`}>
            {/* Thân xe */}
            <rect x={-w/2} y={-h/2} width={w} height={h} rx={rx}
              fill={color} opacity={0.9} stroke="white" strokeWidth={0.3}/>
            {/* Mũi tên đầu xe */}
            <polygon
              points={`${w/2},0 ${w/2-arrowSize},${-arrowSize*0.7} ${w/2-arrowSize},${arrowSize*0.7}`}
              fill="white" opacity={0.7}/>
          </g>
        );
      })}
    </g>
  );
}

// ── Accident marker ───────────────────────────────────────────────────────────
function AccidentMarkers({ accidentEdges }) {
  if (!accidentEdges || Object.keys(accidentEdges).length === 0) return null;
  return (
    <g>
      {Object.entries(accidentEdges).map(([edgeId, mode]) => {
        const e = EDGES[edgeId];
        if (!e) return null;
        const from = getPos(e.from), to = getPos(e.to);
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

// ── Attention arrows ──────────────────────────────────────────────────────────
function AttentionArrows({ attn }) {
  if (!attn) return null;
  const IDS = ["N01","N02","N03","N04"];
  const arrows = [];
  IDS.forEach((dst,di) => IDS.forEach((src,si) => {
    if (src===dst) return;
    const w = attn[di]?.[si]??0;
    if (w < 0.4) return;
    const f=NODE[src], t=NODE[dst];
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
function SpeedLegend() {
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

// ── Main ──────────────────────────────────────────────────────────────────────
export function TrafficMap({ data, modelName }) {
  const color        = MODEL_C[modelName] || "#534ab7";
  const edgeSpeeds   = data?.edge_speeds   || {};
  const accidentEdges = data?.accident_edges || {};

  return (
    <div className="traffic-map-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="traffic-map-svg">
        <rect width={W} height={H} fill="#f5f4f1" rx="8"/>
        <Roads edgeSpeeds={edgeSpeeds} accidentEdges={accidentEdges}/>
        <AttentionArrows attn={modelName==="gat_marl" ? data?.attention_weights : null}/>
        <AccidentMarkers accidentEdges={accidentEdges}/>
        <Vehicles vehicles={data?.vehicles} color={color}/>
        <Intersections intersections={data?.intersections}/>
        <SpeedLegend/>
      </svg>
    </div>
  );
}
