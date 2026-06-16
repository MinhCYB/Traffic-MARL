// dashboard/src/pages/Results.jsx
import { useState, useEffect, useRef, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";

// ── Constants ─────────────────────────────────────────────────────────────────
const MODEL_COLORS  = { gat_marl: "#22c55e", idqn: "#f59e0b", fixed_time: "#ef4444" };
const MODEL_LABELS  = { gat_marl: "GAT-MARL", idqn: "IDQN",   fixed_time: "Fixed-time" };
const POLL_INTERVAL = 15_000; // 15s

const REALTIME_METRICS = [
  { key: "global_reward",       label: "Global Reward",        yLabel: "Reward",  higher: true  },
  { key: "avg_waiting_time",    label: "Thời gian chờ TB (s)", yLabel: "s",       higher: false },
  { key: "avg_speed",           label: "Tốc độ TB (km/h)",     yLabel: "km/h",    higher: true  },
  { key: "loss",                label: "Loss",                 yLabel: "loss",    higher: false },
  { key: "vehicles_teleported", label: "Xe bị teleport",       yLabel: "xe/ep",   higher: false },
  { key: "learning_rate",       label: "Learning Rate",        yLabel: "lr",      higher: false },
];

const COMPARE_METRICS = [
  { key: "avg_waiting_time", label: "Chờ TB (s)",   better: "lower"  },
  { key: "avg_speed",        label: "Tốc độ (km/h)", better: "higher" },
  { key: "throughput",       label: "Throughput",    better: "higher" },
  { key: "global_reward",    label: "Reward",        better: "higher" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function smoothData(rows, key, window = 10) {
  return rows.map((r, i) => {
    const slice = rows.slice(Math.max(0, i - window + 1), i + 1);
    const avg   = slice.reduce((s, x) => s + (x[key] ?? 0), 0) / slice.length;
    return { ...r, [key]: parseFloat(avg.toFixed(3)) };
  });
}

function calcETA(rows, total) {
  if (rows.length < 5) return null;
  const remaining = total - rows.length;
  if (remaining <= 0) return "Hoàn thành";
  // Dùng duration_s thực tế từ log — average 10 ep gần nhất
  const recent = rows.slice(-10).filter(r => r.duration_s > 0);
  if (!recent.length) return null;
  const avgSecPerEp = recent.reduce((s, r) => s + r.duration_s, 0) / recent.length;
  const estSec = remaining * avgSecPerEp;
  const h = Math.floor(estSec / 3600);
  const m = Math.floor((estSec % 3600) / 60);
  return h > 0 ? `~${h}h ${m}m` : `~${m}m`;
}

// ── MiniChart ─────────────────────────────────────────────────────────────────
function MiniChart({ data, metricKey, label, color, accidentEps }) {
  // LR là monotone curve (warmup → cosine decay) — không cần smooth, smooth sẽ làm sai shape
  const smoothed = metricKey === "learning_rate" ? data : smoothData(data, metricKey);

  // Auto-scale Y domain với padding 10%, tránh bị bám sàn khi giá trị nhỏ
  const vals = smoothed.map(d => d[metricKey]).filter(v => v != null && isFinite(v));
  const isLR = metricKey === "learning_rate";
  let yDomain, yTickFormatter;
  if (vals.length > 0) {
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = (hi - lo) * 0.1 || Math.abs(hi) * 0.1 || 1e-7;
    yDomain = [lo - pad, hi + pad];
  } else {
    yDomain = ["auto", "auto"];
  }
  if (isLR) {
    // Hiện dạng 1.0e-4 cho dễ đọc
    yTickFormatter = v => v === 0 ? "0" : v.toExponential(1);
  } else {
    // Format số gọn: tránh bị cắt khi YAxis width hẹp
    yTickFormatter = v => {
      if (!isFinite(v)) return "";
      if (Math.abs(v) >= 1000) return (v / 1000).toFixed(1) + "k";
      if (Math.abs(v) >= 100)  return Math.round(v).toString();
      if (Math.abs(v) >= 1)    return parseFloat(v.toFixed(1)).toString();
      return parseFloat(v.toFixed(3)).toString();
    };
  }

  // Tính width YAxis đủ để chứa label dài nhất
  const sampleLabel = vals.length ? yTickFormatter(Math.min(...vals)) : "-000";
  const yAxisWidth = isLR ? 58 : Math.max(44, sampleLabel.length * 7 + 10);

  return (
    <div className="mini-chart-card">
      <div className="mini-chart-title">{label}</div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={smoothed} margin={{ top: 4, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="episode" stroke="var(--muted)" tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "var(--font-ui)" }} />
          <YAxis
            stroke="var(--muted)"
            tick={{ fontSize: 10, fill: "var(--muted)", fontFamily: "var(--font-ui)" }}
            width={yAxisWidth}
            domain={yDomain}
            tickFormatter={yTickFormatter}
          />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border2)", borderRadius: 6, fontSize: 11, color: "var(--text)", fontFamily: "var(--font-ui)" }}
            labelStyle={{ color: "var(--muted)" }}
            formatter={isLR ? (v) => [v.toExponential(3), label] : undefined}
          />
          {(accidentEps || []).map(ep => (
            <ReferenceLine key={ep} x={ep} stroke="#f97316" strokeDasharray="3 3" strokeWidth={1} />
          ))}
          <Line type="monotone" dataKey={metricKey} stroke={color} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── RealtimeTab ───────────────────────────────────────────────────────────────
function RealtimeTab() {
  const [model,     setModel]     = useState("gat_marl");
  const [rows,      setRows]      = useState([]);
  const [total,     setTotal]     = useState(500);
  const [status,    setStatus]    = useState("loading"); // loading | ok | no_data | error
  const [lastPoll,  setLastPoll]  = useState(null);
  const timerRef = useRef(null);

  const poll = useCallback(async () => {
    try {
      const res  = await fetch(`/logs/${model}`);
      const data = await res.json();
      setStatus(data.status === "ok" && data.rows.length > 0 ? "ok" : data.status);
      setRows(data.rows || []);
      setTotal(data.total_episodes || 500);
      setLastPoll(new Date());
    } catch {
      setStatus("error");
    }
  }, [model]);

  useEffect(() => {
    setRows([]); setStatus("loading");
    poll();
    timerRef.current = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(timerRef.current);
  }, [poll]);

  const current  = rows.length;
  const best     = rows.length ? Math.max(...rows.map(r => r.global_reward)).toFixed(2) : "—";
  const eta      = calcETA(rows, total);
  const accs     = rows.filter(r => r.had_accident).map(r => r.episode);
  const lastSec  = lastPoll ? Math.round((Date.now() - lastPoll) / 1000) : null;
  const isTraining = status === "ok" && current < total;

  return (
    <div className="realtime-tab">
      {/* Header row */}
      <div className="rt-header">
        <div className="rt-model-select">
          <span className="rt-label">Model:</span>
          {Object.keys(MODEL_LABELS).filter(m => m !== "fixed_time").map(m => (
            <button
              key={m}
              className={`toggle-btn ${model === m ? "toggle-btn--on" : "toggle-btn--off"}`}
              style={{ "--model-color": MODEL_COLORS[m] }}
              onClick={() => setModel(m)}
            >
              {MODEL_LABELS[m]}
            </button>
          ))}
        </div>
        <div className="rt-status">
          {isTraining && <span className="rt-dot rt-dot--live"/>}
          <span className="rt-status-text">
            {status === "loading"  && "Đang tải..."}
            {status === "no_data" && "Chưa có log — bắt đầu training trước"}
            {status === "error"   && "Không đọc được log"}
            {status === "ok"      && (isTraining ? "Đang train" : "Hoàn thành")}
          </span>
          {lastSec !== null && status === "ok" &&
            <span className="rt-last-poll">Cập nhật: {lastSec}s trước</span>}
        </div>
      </div>

      {/* No data state */}
      {(status === "no_data" || status === "error") && (
        <div className="results-empty">
          <div className="empty-icon">📈</div>
          <div className="empty-title">
            {status === "no_data" ? "Chưa có log training" : "Lỗi đọc log"}
          </div>
          <div className="empty-sub">
            {status === "no_data"
              ? "Chạy training rồi quay lại đây, trang tự cập nhật mỗi 15 giây"
              : "Kiểm tra server có đang chạy không"}
          </div>
        </div>
      )}

      {/* Charts */}
      {status === "ok" && rows.length > 0 && (
        <>
          <div className="charts-grid-2x2">
            {REALTIME_METRICS.map(({ key, label }) => (
              <MiniChart
                key={key}
                data={rows}
                metricKey={key}
                label={label}
                color={MODEL_COLORS[model]}
                accidentEps={accs}
              />
            ))}
          </div>

          {/* Stats row */}
          <div className="rt-stats-row">
            <div className="rt-stat">
              <span className="rt-stat-label">Episode</span>
              <span className="rt-stat-value">{current} / {total}</span>
            </div>
            <div className="rt-stat">
              <span className="rt-stat-label">Best Reward</span>
              <span className="rt-stat-value" style={{ color: MODEL_COLORS[model] }}>{best}</span>
            </div>
            <div className="rt-stat">
              <span className="rt-stat-label">Obstacles</span>
              <span className="rt-stat-value" style={{ color: "#f97316" }}>{accs.length} ep</span>
            </div>
            <div className="rt-stat">
              <span className="rt-stat-label">Teleported</span>
              <span className="rt-stat-value" style={{ color: rows.length ? (rows[rows.length-1].vehicles_teleported > 0 ? "#ef4444" : "var(--text)") : "var(--text)" }}>
                {rows.length ? rows[rows.length-1].vehicles_teleported : 0}
              </span>
            </div>
            <div className="rt-stat">
              <span className="rt-stat-label">LR</span>
              <span className="rt-stat-value">
                {rows.length && rows[rows.length-1].learning_rate
                  ? rows[rows.length-1].learning_rate.toExponential(1)
                  : "—"}
              </span>
            </div>
            {eta && (
              <div className="rt-stat">
                <span className="rt-stat-label">ETA</span>
                <span className="rt-stat-value">{eta}</span>
              </div>
            )}
          </div>

          {accs.length > 0 && (
            <div className="rt-accident-note">
              <span style={{ color: "#f97316" }}>│</span> đường cam = episode có tai nạn
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── CompareTab ────────────────────────────────────────────────────────────────
const COMPARE_METRICS_CHART = [
  { key: "global_reward",    label: "Global Reward",        yLabel: "Reward" },
  { key: "avg_speed",        label: "Tốc độ TB (km/h)",     yLabel: "km/h"   },
  { key: "avg_waiting_time", label: "Thời gian chờ TB (s)", yLabel: "s"      },
  { key: "throughput",       label: "Throughput",           yLabel: "xe/step"},
];

function CompareTab() {
  const [mergedData, setMergedData] = useState([]);
  const [summary,    setSummary]    = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [visible,    setVisible]    = useState({ gat_marl: true, idqn: true, fixed_time: true });

  useEffect(() => {
    fetch("/logs/merged.json")
      .then(r => r.json())
      .then(d => { setMergedData(d.episodes || []); setSummary(d.summary || null); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="results-loading">Đang tải...</div>;

  if (!mergedData.length) return (
    <div className="results-empty">
      <div className="empty-icon">📊</div>
      <div className="empty-title">Chưa có dữ liệu so sánh</div>
      <div className="empty-sub">Train xong cả 2 model rồi chạy merge_logs.py</div>
      <code className="empty-cmd">python training/merge_logs.py</code>
    </div>
  );

  return (
    <div className="compare-tab">
      <div className="model-toggles" style={{ marginBottom: 16 }}>
        {Object.keys(MODEL_COLORS).map(m => (
          <button
            key={m}
            className={`toggle-btn ${visible[m] ? "toggle-btn--on" : "toggle-btn--off"}`}
            style={{ "--model-color": MODEL_COLORS[m] }}
            onClick={() => setVisible(v => ({ ...v, [m]: !v[m] }))}
          >
            {MODEL_LABELS[m]}
          </button>
        ))}
      </div>

      <div className="charts-grid">
        {COMPARE_METRICS_CHART.map(({ key, label }) => (
          <div key={key} className="chart-card">
            <div className="chart-card-title">{label}</div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={mergedData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="episode" stroke="var(--muted)" tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "var(--font-ui)" }} />
                <YAxis stroke="var(--muted)" tick={{ fontSize: 11, fill: "var(--muted)", fontFamily: "var(--font-ui)" }} width={48} />
                <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border2)", borderRadius: 8, color: "var(--text)", fontFamily: "var(--font-ui)" }} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                {Object.keys(MODEL_COLORS).map(m => visible[m] && (
                  <Line key={m} type="monotone" dataKey={`${m}_${key}`}
                    name={MODEL_LABELS[m]} stroke={MODEL_COLORS[m]}
                    dot={false} strokeWidth={2} activeDot={{ r: 4 }} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>

      {summary && (
        <div className="comparison-table-wrap">
          <div className="chart-card-title">So sánh (TB 50 episode cuối)</div>
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Metric</th>
                {Object.keys(summary).map(m => (
                  <th key={m} style={{ color: MODEL_COLORS[m] }}>{MODEL_LABELS[m]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARE_METRICS.map(({ key, label, better }) => {
                const models = Object.keys(summary);
                const vals   = models.map(m => summary[m]?.[key] ?? null);
                const best   = better === "lower" ? Math.min(...vals.filter(Boolean)) : Math.max(...vals.filter(Boolean));
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    {vals.map((v, i) => (
                      <td key={models[i]}
                        style={{ color: v === best ? MODEL_COLORS[models[i]] : "var(--muted)", fontWeight: v === best ? 700 : 400 }}>
                        {v != null ? v.toFixed(2) : "—"}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Results() {
  const [tab, setTab] = useState("realtime");

  return (
    <div className="results-page">
      <div className="results-header">
        <span className="results-title">Kết quả Training</span>
        <div className="tab-bar">
          <button className={`tab-btn ${tab === "realtime" ? "tab-btn--active" : ""}`} onClick={() => setTab("realtime")}>
            📈 Real-time
          </button>
          <button className={`tab-btn ${tab === "compare"  ? "tab-btn--active" : ""}`} onClick={() => setTab("compare")}>
            📊 So sánh
          </button>
        </div>
      </div>

      {tab === "realtime" ? <RealtimeTab /> : <CompareTab />}
    </div>
  );
}