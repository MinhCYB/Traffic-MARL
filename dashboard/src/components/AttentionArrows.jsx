// dashboard/src/components/AttentionArrows.jsx
// Vẽ mũi tên attention giữa các ngã tư (chỉ GAT-MARL panel)
// Attention weight > threshold → mũi tên đứt nét tím, độ dày tỉ lệ weight
// Layout động theo topology — không hardcode 4 ngã tư 2×2

import { useMemo } from "react";
import { getLayout } from "../mapLayouts/index.js";

const THRESHOLD = 0.5;
const VB_W = 300;
const VB_H = 220;

// Scale tọa độ NODE từ layout (có thể lớn hơn) về viewBox nhỏ của component này
function scalePos(pos, srcW, srcH, dstW, dstH, padding = 30) {
  return {
    x: padding + ((pos.x / srcW) * (dstW - padding * 2)),
    y: padding + ((pos.y / srcH) * (dstH - padding * 2)),
  };
}

export function AttentionArrows({ attentionWeights, topology = "2x2" }) {
  if (!attentionWeights) return null;

  const layout   = useMemo(() => getLayout(topology), [topology]);
  const { NODE, W: srcW, H: srcH } = layout;
  const nodeIds  = Object.keys(NODE);

  // Scale tất cả node positions về viewBox nhỏ
  const scaledPos = useMemo(() => {
    const result = {};
    nodeIds.forEach(nid => {
      result[nid] = scalePos(NODE[nid], srcW, srcH, VB_W, VB_H);
    });
    return result;
  // nodeIds đã có trong dependency vì nó phụ thuộc vào NODE (tính từ Object.keys)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [NODE, srcW, srcH]);

  const arrows = [];
  nodeIds.forEach((dst, di) => {
    nodeIds.forEach((src, si) => {
      if (src === dst) return;
      const w = attentionWeights[di]?.[si] ?? 0;
      if (w < THRESHOLD) return;
      const from = scaledPos[src];
      const to   = scaledPos[dst];
      if (!from || !to) return;
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

  // Background edges (các connection thực sự trong adjacency)
  const bgEdges = [];
  nodeIds.forEach((a, ai) => {
    nodeIds.forEach((b, bi) => {
      if (bi <= ai) return;
      const posA = scaledPos[a], posB = scaledPos[b];
      if (!posA || !posB) return;
      // Chỉ vẽ nếu 2 node này là neighbor (có attention weight > 0)
      const hasEdge = (attentionWeights[ai]?.[bi] ?? 0) > 0
                   || (attentionWeights[bi]?.[ai] ?? 0) > 0;
      if (!hasEdge) return;
      bgEdges.push(
        <line key={`bg-${a}-${b}`}
          x1={posA.x} y1={posA.y}
          x2={posB.x} y2={posB.y}
          stroke="#334155" strokeWidth="1" opacity="0.25"/>
      );
    });
  });

  return (
    <svg
      className="attention-svg"
      viewBox={`0 0 ${VB_W} ${VB_H}`}
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

      {bgEdges}
      {arrows}

      {/* Nodes */}
      {nodeIds.map((nid) => (
        <g key={nid}>
          <circle
            cx={scaledPos[nid].x} cy={scaledPos[nid].y}
            r={nodeIds.length > 4 ? 14 : 18}
            fill="#1e293b" stroke="#6366f1" strokeWidth="2"
          />
          <text
            x={scaledPos[nid].x} y={scaledPos[nid].y}
            textAnchor="middle" dominantBaseline="central"
            fontSize={nodeIds.length > 4 ? 9 : 11}
            fill="#e2e8f0" fontWeight="600"
          >
            {nid}
          </text>
        </g>
      ))}
    </svg>
  );
}
