// dashboard/src/components/AttentionArrows.jsx
// Vẽ mũi tên attention giữa các ngã tư (chỉ GAT-MARL panel)
// Attention weight > 0.5 → mũi tên đứt nét tím, độ dày tỉ lệ weight

const THRESHOLD = 0.5;
const NODE_POS = {
  N01: { x: 80,  y: 60  },
  N02: { x: 220, y: 60  },
  N03: { x: 80,  y: 160 },
  N04: { x: 220, y: 160 },
};
const NODE_IDS = ["N01", "N02", "N03", "N04"];

// attention_weights là matrix 4x4: [dst][src]
export function AttentionArrows({ attentionWeights }) {
  if (!attentionWeights) return null;

  const arrows = [];

  NODE_IDS.forEach((dst, di) => {
    NODE_IDS.forEach((src, si) => {
      if (src === dst) return;
      const w = attentionWeights[di]?.[si] ?? 0;
      if (w < THRESHOLD) return;

      const from = NODE_POS[src];
      const to   = NODE_POS[dst];
      const opacity = 0.4 + w * 0.6;
      const strokeW = 1 + w * 3;

      arrows.push(
        <line
          key={`${src}-${dst}`}
          x1={from.x} y1={from.y}
          x2={to.x}   y2={to.y}
          stroke="#a855f7"
          strokeWidth={strokeW}
          strokeDasharray="5 3"
          opacity={opacity}
          markerEnd="url(#arrow-attn)"
        />
      );
    });
  });

  return (
    <svg
      className="attention-svg"
      viewBox="0 0 300 220"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <marker
          id="arrow-attn"
          viewBox="0 0 10 10"
          refX="8" refY="5"
          markerWidth="5" markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M2 1L8 5L2 9" fill="none" stroke="#a855f7" strokeWidth="2" strokeLinecap="round"/>
        </marker>
      </defs>

      {/* Edges nền mờ */}
      {[["N01","N02"],["N03","N04"],["N01","N03"],["N02","N04"]].map(([a,b]) => (
        <line
          key={`bg-${a}-${b}`}
          x1={NODE_POS[a].x} y1={NODE_POS[a].y}
          x2={NODE_POS[b].x} y2={NODE_POS[b].y}
          stroke="#334155" strokeWidth="1" opacity="0.4"
        />
      ))}

      {/* Attention arrows */}
      {arrows}

      {/* Nodes */}
      {NODE_IDS.map((nid) => (
        <g key={nid}>
          <circle
            cx={NODE_POS[nid].x} cy={NODE_POS[nid].y}
            r="18" fill="#1e293b" stroke="#6366f1" strokeWidth="2"
          />
          <text
            x={NODE_POS[nid].x} y={NODE_POS[nid].y}
            textAnchor="middle" dominantBaseline="central"
            fontSize="11" fill="#e2e8f0" fontWeight="600"
          >
            {nid}
          </text>
        </g>
      ))}
    </svg>
  );
}
