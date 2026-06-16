// dashboard/src/components/MetricsPanel.jsx
import { useRef } from "react";
import { LineChart, Line, ResponsiveContainer, Tooltip } from "recharts";

export function MetricsPanel({ metrics, mode, workerData }) {
  if (!metrics) return (
    <div className="metrics-panel metrics-panel--empty">
      <span className="reconnecting">Đang kết nối...</span>
    </div>
  );

  const items = [
    { label: "Tốc độ TB",   value: `${metrics.avg_speed?.toFixed(1) ?? "--"}`,        unit: "km/h"    },
    { label: "Chờ TB",       value: `${metrics.avg_waiting_time?.toFixed(1) ?? "--"}`, unit: "s"       },
    { label: "Throughput",   value: metrics.throughput ?? "--",                         unit: "xe/step" },
    { label: "Xe hiện tại", value: metrics.n_vehicles ?? "--",                         unit: "xe"      },
  ];

  const isGAT      = mode === "gat_marl";
  const avgComm    = workerData?.avg_comm    ?? null;
  const totalComm  = workerData?.total_comm  ?? null;
  const commStep   = workerData?.comm_this_step ?? null;

  return (
    <div className="metrics-panel-wrap">
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

      {isGAT && (
        <div className="metrics-panel metrics-panel--comm">
          <div className="metric-item metric-item--comm">
            <span className="metric-label">Comm TB/step</span>
            <span className="metric-value metric-value--comm">
              {avgComm != null ? avgComm.toFixed(1) : "--"}
              <span className="metric-unit"> cặp</span>
            </span>
          </div>
          <div className="metric-item metric-item--comm">
            <span className="metric-label">Tổng comm</span>
            <span className="metric-value metric-value--comm">
              {totalComm != null ? totalComm.toLocaleString() : "--"}
              <span className="metric-unit"> cặp</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}