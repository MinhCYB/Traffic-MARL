// dashboard/src/pages/Results.jsx
// Training charts từ CSV logs — load static JSON sau khi train xong
import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const MODEL_COLORS = {
  gat_marl:   "#22c55e",
  idqn:       "#f59e0b",
  fixed_time: "#ef4444",
};
const MODEL_LABELS = {
  gat_marl:   "GAT-MARL",
  idqn:       "IDQN",
  fixed_time: "Fixed-time",
};

// Metrics để hiển thị
const CHART_METRICS = [
  { key: "global_reward",    label: "Global Reward",      yLabel: "Reward" },
  { key: "avg_speed",        label: "Tốc độ TB (km/h)",   yLabel: "km/h" },
  { key: "avg_waiting_time", label: "Thời gian chờ TB (s)", yLabel: "s" },
  { key: "throughput",       label: "Throughput",          yLabel: "xe/step" },
];

function ChartCard({ title, dataKey, mergedData, visibleModels }) {
  return (
    <div className="chart-card">
      <div className="chart-card-title">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={mergedData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="episode"
            stroke="#64748b"
            tick={{ fontSize: 11, fill: "#64748b" }}
            label={{ value: "Episode", position: "insideBottom", offset: -4, fill: "#64748b", fontSize: 11 }}
          />
          <YAxis stroke="#64748b" tick={{ fontSize: 11, fill: "#64748b" }} width={48} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
            labelStyle={{ color: "#94a3b8" }}
            itemStyle={{ fontSize: 12 }}
          />
          <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          {Object.keys(MODEL_COLORS).map((model) =>
            visibleModels[model] ? (
              <Line
                key={model}
                type="monotone"
                dataKey={`${model}_${dataKey}`}
                name={MODEL_LABELS[model]}
                stroke={MODEL_COLORS[model]}
                dot={false}
                strokeWidth={2}
                activeDot={{ r: 4 }}
              />
            ) : null
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ComparisonTable({ summary }) {
  if (!summary) return null;
  const models = Object.keys(summary);
  const metrics = [
    { key: "avg_waiting_time", label: "Chờ TB (s)",  better: "lower" },
    { key: "avg_speed",        label: "Tốc độ (km/h)", better: "higher" },
    { key: "throughput",       label: "Throughput",   better: "higher" },
    { key: "global_reward",    label: "Reward",       better: "higher" },
  ];

  return (
    <div className="comparison-table-wrap">
      <div className="chart-card-title">So sánh kết quả (trung bình 50 episode cuối)</div>
      <table className="comparison-table">
        <thead>
          <tr>
            <th>Metric</th>
            {models.map((m) => <th key={m} style={{ color: MODEL_COLORS[m] }}>{MODEL_LABELS[m]}</th>)}
          </tr>
        </thead>
        <tbody>
          {metrics.map(({ key, label, better }) => {
            const vals = models.map((m) => summary[m]?.[key] ?? null);
            const best = better === "lower"
              ? Math.min(...vals.filter(Boolean))
              : Math.max(...vals.filter(Boolean));
            return (
              <tr key={key}>
                <td>{label}</td>
                {vals.map((v, i) => (
                  <td
                    key={models[i]}
                    style={{ color: v === best ? MODEL_COLORS[models[i]] : "#94a3b8", fontWeight: v === best ? 700 : 400 }}
                  >
                    {v != null ? v.toFixed(2) : "—"}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function Results() {
  const [mergedData, setMergedData] = useState([]);
  const [summary, setSummary]       = useState(null);
  const [loading, setLoading]       = useState(true);
  const [visibleModels, setVisibleModels] = useState({
    gat_marl: true, idqn: true, fixed_time: true,
  });

  useEffect(() => {
    // Load từ /logs/merged.json — được generate sau khi train xong
    // Format: [{episode, gat_marl_global_reward, idqn_global_reward, ...}, ...]
    fetch("/logs/merged.json")
      .then((r) => r.json())
      .then((d) => {
        setMergedData(d.episodes || []);
        setSummary(d.summary || null);
        setLoading(false);
      })
      .catch(() => {
        // Chưa có data — hiển thị placeholder
        setLoading(false);
      });
  }, []);

  const toggleModel = (model) =>
    setVisibleModels((v) => ({ ...v, [model]: !v[model] }));

  if (loading) return <div className="results-loading">Đang tải dữ liệu...</div>;

  if (!mergedData.length) return (
    <div className="results-empty">
      <div className="empty-icon">📊</div>
      <div className="empty-title">Chưa có kết quả training</div>
      <div className="empty-sub">Chạy training xong rồi quay lại đây</div>
      <code className="empty-cmd">python training/train.py --model gat_marl</code>
    </div>
  );

  return (
    <div className="results-page">
      <div className="results-header">
        <span className="results-title">Kết quả Training</span>
        <div className="model-toggles">
          {Object.keys(MODEL_COLORS).map((m) => (
            <button
              key={m}
              className={`toggle-btn ${visibleModels[m] ? "toggle-btn--on" : "toggle-btn--off"}`}
              style={{ "--model-color": MODEL_COLORS[m] }}
              onClick={() => toggleModel(m)}
            >
              {MODEL_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      <div className="charts-grid">
        {CHART_METRICS.map(({ key, label }) => (
          <ChartCard
            key={key}
            title={label}
            dataKey={key}
            mergedData={mergedData}
            visibleModels={visibleModels}
          />
        ))}
      </div>

      <ComparisonTable summary={summary} />
    </div>
  );
}
