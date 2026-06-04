// dashboard/src/components/MetricsPanel.jsx
export function MetricsPanel({ metrics, mode }) {
  if (!metrics) return (
    <div className="metrics-panel metrics-panel--empty">
      <span className="reconnecting">Đang kết nối...</span>
    </div>
  );

  const items = [
    { label: "Tốc độ TB", value: `${metrics.avg_speed?.toFixed(1) ?? "--"}`, unit: "km/h" },
    { label: "Chờ TB",    value: `${metrics.avg_waiting_time?.toFixed(1) ?? "--"}`, unit: "s" },
    { label: "Throughput", value: metrics.throughput ?? "--", unit: "xe/step" },
    { label: "Xe hiện tại", value: metrics.n_vehicles ?? "--", unit: "xe" },
  ];

  return (
    <div className="metrics-panel">
      {items.map(({ label, value, unit }) => (
        <div key={label} className="metric-item">
          <span className="metric-label">{label}</span>
          <span className="metric-value">
            {value}
            <span className="metric-unit"> {unit}</span>
          </span>
        </div>
      ))}
    </div>
  );
}
