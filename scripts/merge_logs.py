"""
scripts/merge_logs.py — Merge CSV logs thành JSON cho dashboard Results tab

Đọc logs/<topology>/gat_marl/training_log.csv
   + logs/<topology>/idqn/training_log.csv
   + logs/<topology>/fixed_time/training_log.csv
→ Tạo logs/<topology>/merged.json  (+ copy ra logs/merged.json cho backward compat)

Dashboard CompareTab fetch /logs/merged.json → server serve static file.

Dùng sau khi train xong:
    python scripts/merge_logs.py
    python scripts/merge_logs.py --topology mydinh
    python scripts/merge_logs.py --tail 100   # dùng 100 ep cuối cho summary
"""

import argparse
import csv
import json
import math
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────────────────
ROOT_DIR  = Path(__file__).parent.parent
MODELS    = ["gat_marl", "idqn", "fixed_time"]
TAIL_N    = 50   # số episode cuối để tính summary

# Metrics xuất ra merged.json cho dashboard CompareTab charts
CHART_METRICS = [
    "global_reward",
    "avg_speed",
    "avg_waiting_time",
    "throughput",
    "loss",
    "vehicles_teleported",
    "learning_rate",
]

# Metrics dùng cho bảng summary (mean ± std)
SUMMARY_METRICS = [
    "global_reward",
    "avg_speed",
    "avg_waiting_time",
    "throughput",
    "vehicles_teleported",
]


def _detect_topology() -> str:
    """Import TOPOLOGY từ training config nếu có, fallback 'mydinh'."""
    try:
        from training.config import TOPOLOGY
        return TOPOLOGY
    except Exception:
        return "mydinh"


def load_csv(log_dir: Path, model: str) -> list[dict]:
    """Đọc CSV log, trả về list of dicts với giá trị đã parse."""
    path = log_dir / model / "training_log.csv"
    if not path.exists():
        print(f"  ⚠ Không tìm thấy: {path}")
        return []

    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            parsed = {}
            for key, val in row.items():
                if val is None or val == "":
                    parsed[key] = None
                    continue
                # Thử parse float, nếu không được thì giữ string
                try:
                    parsed[key] = float(val)
                    # Convert lại int nếu không có phần thập phân
                    if parsed[key] == int(parsed[key]) and key in (
                        "episode", "worker_id", "total_steps", "throughput",
                        "had_obstacle", "obstacle_count", "vehicles_teleported",
                    ):
                        parsed[key] = int(parsed[key])
                except (ValueError, TypeError):
                    parsed[key] = val
            rows.append(parsed)

    print(f"  ✓ {model}: {len(rows)} rows từ {path}")
    return rows


def _mean_std(values: list[float]) -> tuple[float | None, float | None]:
    """Tính mean và std, trả (None, None) nếu list rỗng."""
    if not values:
        return None, None
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return round(mean, 4), 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std = math.sqrt(variance)
    return round(mean, 4), round(std, 4)


def merge(topology: str, tail_n: int = TAIL_N):
    log_dir = ROOT_DIR / "logs" / topology
    print(f"Đang merge logs cho topology '{topology}'...")
    print(f"  Log dir: {log_dir}")

    data = {m: load_csv(log_dir, m) for m in MODELS}

    # Xác định max episodes — dùng 'episode' column nếu có, else len(rows)
    max_ep = 0
    for model, rows in data.items():
        if not rows:
            continue
        # Episode number có thể không liên tục (parallel training)
        # Dùng max episode number hoặc len tuỳ cái nào lớn hơn
        last_ep = max((int(r.get("episode", i)) for i, r in enumerate(rows)), default=0)
        max_ep = max(max_ep, last_ep + 1, len(rows))

    if max_ep == 0:
        print("Không có dữ liệu nào.")
        return

    # ── Build episodes list ────────────────────────────────────────────────────
    # Index rows by episode number cho mỗi model
    indexed: dict[str, dict[int, dict]] = {}
    for model, rows in data.items():
        by_ep: dict[int, dict] = {}
        for i, row in enumerate(rows):
            ep = int(row.get("episode", i))
            by_ep[ep] = row  # nếu trùng episode (multi-worker), lấy cái cuối
        indexed[model] = by_ep

    episodes = []
    for ep in range(max_ep):
        row_out = {"episode": ep}
        for model in MODELS:
            src = indexed.get(model, {}).get(ep)
            if src is None:
                continue
            for metric in CHART_METRICS:
                val = src.get(metric)
                if val is not None:
                    try:
                        row_out[f"{model}_{metric}"] = float(val)
                    except (ValueError, TypeError):
                        row_out[f"{model}_{metric}"] = None
                # Thêm obstacle info
            if src.get("had_obstacle") or src.get("had_accident"):
                row_out[f"{model}_had_obstacle"] = True
                row_out[f"{model}_obstacle_count"] = int(src.get("obstacle_count", src.get("obstacle_count", 0)) or 0)
        episodes.append(row_out)

    # ── Summary: mean ± std của TAIL_N episode cuối ─────────────────────────────
    summary = {}
    for model, rows in data.items():
        if not rows:
            continue
        tail = rows[-tail_n:]
        model_summary = {}
        for metric in SUMMARY_METRICS:
            vals = []
            for r in tail:
                try:
                    v = r.get(metric)
                    if v is not None:
                        vals.append(float(v))
                except (ValueError, TypeError):
                    pass
            mean, std = _mean_std(vals)
            model_summary[metric] = mean
            model_summary[f"{metric}_std"] = std
        # Thêm tổng obstacle episodes
        model_summary["obstacle_episodes"] = sum(
            1 for r in tail
            if r.get("had_obstacle") or r.get("had_accident")
        )
        model_summary["total_episodes"] = len(rows)
        summary[model] = model_summary

    # ── Write output ─────────────────────────────────────────────────────────
    out = {
        "topology": topology,
        "tail_n": tail_n,
        "episodes": episodes,
        "summary": summary,
    }

    # Primary: logs/<topology>/merged.json
    out_path = log_dir / "merged.json"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"\n✓ Output: {out_path} ({len(episodes)} episodes)")

    # Backward compat: logs/merged.json (dashboard serve static từ đây)
    compat_path = ROOT_DIR / "logs" / "merged.json"
    with open(compat_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"✓ Compat: {compat_path}")

    # ── Print summary ────────────────────────────────────────────────────────
    print(f"\nSummary ({tail_n} episode cuối):")
    print(f"{'':>20s}", end="")
    for model in MODELS:
        if model in summary:
            print(f"  {model:>16s}", end="")
    print()
    print("─" * (20 + 18 * len(summary)))

    for metric in SUMMARY_METRICS:
        print(f"  {metric:>18s}", end="")
        for model in MODELS:
            if model not in summary:
                continue
            s = summary[model]
            mean = s.get(metric)
            std  = s.get(f"{metric}_std")
            if mean is not None and std is not None:
                print(f"  {mean:>8.2f} ± {std:<5.2f}", end="")
            else:
                print(f"  {'—':>16s}", end="")
        print()

    for model in MODELS:
        if model in summary:
            obs = summary[model].get("obstacle_episodes", 0)
            total = summary[model].get("total_episodes", 0)
            print(f"  {model}: {total} total episodes, {obs} with obstacles (trong {tail_n} cuối)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge training logs thành JSON cho dashboard")
    parser.add_argument("--topology", type=str, default=None,
                        help="Topology name (e.g., mydinh, 2x2, uet). Auto-detect từ config nếu không chỉ định.")
    parser.add_argument("--tail", type=int, default=TAIL_N,
                        help=f"Số episode cuối dùng cho summary (default: {TAIL_N})")
    args = parser.parse_args()

    topology = args.topology or _detect_topology()
    merge(topology=topology, tail_n=args.tail)