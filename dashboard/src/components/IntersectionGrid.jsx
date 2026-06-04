// dashboard/src/components/IntersectionGrid.jsx

const INTERSECTION_IDS = ["N01", "N02", "N03", "N04"];
const LABELS = {
  N01: "Công sở\n+ Trường",
  N02: "Công sở\nMR",
  N03: "Khu\nDân Cư",
  N04: "Vui Chơi\n+ DC",
};

// Speed → màu heatmap
function speedColor(speed) {
  if (speed == null) return "#334155";
  if (speed >= 25) return "#22c55e";   // xanh lá — thông
  if (speed >= 10) return "#eab308";   // vàng — đông dần
  return "#ef4444";                     // đỏ — tắc
}

function phaseLabel(phase) {
  const labels = ["NS 🟢", "NS 🟡", "EW 🟢", "EW 🟡"];
  return labels[phase] ?? "—";
}

export function IntersectionGrid({ intersections, avgSpeed }) {
  // Build lookup nhanh
  const lookup = {};
  (intersections || []).forEach((i) => { lookup[i.id] = i; });

  // Layout 2x2: [N01, N02] / [N03, N04]
  const grid = [
    ["N01", "N02"],
    ["N03", "N04"],
  ];

  return (
    <div className="intersection-grid">
      {grid.map((row, ri) => (
        <div key={ri} className="grid-row">
          {row.map((nid) => {
            const data = lookup[nid];
            const color = speedColor(avgSpeed);
            const queue = data?.queue_per_lane?.reduce((a, b) => a + b, 0).toFixed(0) ?? "--";
            const phase = phaseLabel(data?.phase);
            const wait  = data?.waiting_time?.toFixed(1) ?? "--";

            return (
              <div
                key={nid}
                className="intersection-node"
                style={{ borderColor: color, boxShadow: `0 0 12px ${color}44` }}
              >
                <div className="node-id">{nid}</div>
                <div className="node-label">{LABELS[nid]}</div>
                <div className="node-phase">{phase}</div>
                <div className="node-stats">
                  <span>🚗 {queue} xe</span>
                  <span>⏱ {wait}s</span>
                </div>
                <div
                  className="node-indicator"
                  style={{ background: color }}
                />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
