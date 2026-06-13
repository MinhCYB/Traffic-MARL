// dashboard/src/components/IntersectionGrid.jsx
// Grid hiển thị trạng thái từng ngã tư — dynamic theo topology

import { useMemo } from "react";
import { getLayout } from "../mapLayouts/index.js";

function speedColor(speed) {
  if (speed == null) return "#334155";
  if (speed >= 25) return "#1d9e75";
  if (speed >= 10) return "#ef9f27";
  return "#e24b4a";
}

function phaseLabel(phase) {
  const labels = ["NS 🟢", "NS 🟡", "EW 🟢", "EW 🟡"];
  return labels[phase] ?? "—";
}

export function IntersectionGrid({ intersections, avgSpeed, topology = "2x2" }) {
  const layout = useMemo(() => getLayout(topology), [topology]);
  const { GRID, NODE_LABELS } = layout;

  const lookup = {};
  (intersections || []).forEach((i) => { lookup[i.id] = i; });

  const color = speedColor(avgSpeed);

  return (
    <div className="intersection-grid">
      {GRID.map((row, ri) => (
        <div key={ri} className="grid-row">
          {row.map((nid, ci) => {
            // null slot trong GRID (ví dụ mydinh hàng 3 chỉ có 2 ngã tư)
            if (!nid) return <div key={`empty-${ri}-${ci}`} className="intersection-node intersection-node--empty"/>;

            const data  = lookup[nid];
            const queue = data?.queue_per_lane?.reduce((a, b) => a + b, 0).toFixed(0) ?? "--";
            const phase = phaseLabel(data?.phase);
            const wait  = data?.waiting_time?.toFixed(1) ?? "--";
            const label = NODE_LABELS?.[nid] ?? nid;

            return (
              <div
                key={nid}
                className="intersection-node"
                style={{ borderColor: color, boxShadow: `0 0 12px ${color}44` }}
              >
                <div className="node-id">{nid}</div>
                <div className="node-label">{label}</div>
                <div className="node-phase">{phase}</div>
                <div className="node-stats">
                  <span>🚗 {queue} xe</span>
                  <span>⏱ {wait}s</span>
                </div>
                <div className="node-indicator" style={{ background: color }}/>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
