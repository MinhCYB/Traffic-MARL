"""
scripts/merge_logs.py — Merge CSV logs thành JSON cho dashboard Results tab

Đọc logs/<topology>/gat_marl/training_log.csv (+ finetune_log.csv nếu có)
   + logs/<topology>/idqn/training_log.csv
   + logs/<topology>/fixed_time/training_log.csv
→ Tạo logs/<topology>/merged.json  (+ copy ra logs/merged.json cho backward compat)

Dashboard CompareTab fetch /logs/merged.json → server có route riêng serve JSON này
(xem server/main.py — route phải đứng trước /logs/{model} để không bị "model=merged.json" nuốt mất).

finetune_log.csv — chỉ gat_marl mới có, mỗi lần finetune tạo 1 file riêng trong
cùng folder model, 2 dòng đầu là metadata (comment '#'):
    # finetune_from: checkpoints/final/gat_marl_mydinh_best.pt
    # topology: uet
    episode,worker_id,...
Khi merge cho 1 (topology, model): training_log được nối TRƯỚC, finetune_log nối SAU,
episode của finetune_log được renumber liên tục tiếp theo training_log (không đè lẫn
vào episode index của training) — xem load_model_series().

Dùng:
    # Merge 3 model trong 1 topology (mặc định, backward compat) ────────────
    python scripts/merge_logs.py
    python scripts/merge_logs.py --topology mydinh
    python scripts/merge_logs.py --tail 100              # dùng 100 ep cuối cho summary

    # So sánh tuỳ ý N series log với nhau (cross model / cross topology / cross log-type)
    # Mỗi series: 'topology/model' (full timeline) hoặc 'topology/model/log_type'
    # log_type ∈ {training, finetune, auto}; mặc định 'auto' = training nối finetune.
    python scripts/merge_logs.py --compare uet/gat_marl/finetune uet/idqn/training
    python scripts/merge_logs.py --compare uet/gat_marl/finetune uet/idqn/training \
        --labels "GAT-MARL (finetune uet)" "IDQN (fresh train uet)" \
        --out logs/comparisons/gat_finetune_vs_idqn_uet.json
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

# Field order chuẩn dùng làm fallback khi file CSV bị thiếu header
# (vd: logs/uet/gat_marl/training_log.csv — file ghi đè log_file_mode bug cũ
# khiến header không được viết). Phải khớp đúng fieldnames trong train.py/train_parallel.py.
DEFAULT_FIELDNAMES = [
    "episode", "worker_id", "total_steps", "global_reward",
    "avg_speed", "avg_waiting_time", "throughput",
    "loss", "epsilon", "duration_s",
    "had_obstacle", "obstacle_edges", "obstacle_count",
    "vehicles_teleported", "learning_rate",
]

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


def _parse_value(key: str, val: str):
    """Parse 1 giá trị CSV: thử float/int, giữ string nếu fail, None nếu rỗng."""
    if val is None or val == "":
        return None
    try:
        f = float(val)
        if f == int(f) and key in (
            "episode", "worker_id", "total_steps", "throughput",
            "had_obstacle", "obstacle_count", "vehicles_teleported",
        ):
            return int(f)
        return f
    except (ValueError, TypeError):
        return val


def read_csv_with_meta(path: Path) -> tuple[dict, list[dict]]:
    """
    Đọc 1 file CSV log, skip các dòng comment '#' ở đầu file (metadata finetune).
    Tự fallback dùng DEFAULT_FIELDNAMES nếu file thiếu header (data cũ bị lỗi).

    Trả về (metadata: dict, rows: list[dict]).
    Metadata format trong file: "# key: value" → {"key": "value"}.
    """
    if not path.exists():
        return {}, []

    meta: dict = {}
    data_lines: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for line in f:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                body = stripped[1:].strip()
                if ":" in body:
                    k, _, v = body.partition(":")
                    meta[k.strip()] = v.strip()
                continue
            data_lines.append(line)

    if not data_lines:
        return meta, []

    first_field = data_lines[0].split(",", 1)[0].strip()
    if first_field == "episode":
        reader = csv.DictReader(data_lines)
    else:
        print(f"  ⚠ {path.name}: thiếu header CSV, dùng field order chuẩn")
        reader = csv.DictReader(data_lines, fieldnames=DEFAULT_FIELDNAMES)

    rows = [
        {k: _parse_value(k, v) for k, v in row.items()}
        for row in reader
    ]
    return meta, rows


def load_model_series(
    log_dir: Path, model: str, log_type: str = "auto"
) -> tuple[list[dict], dict | None, bool, int | None]:
    """
    Load rows cho 1 (model, log_type) trong log_dir (= logs/<topology>).

    log_type:
      - "training": chỉ training_log.csv
      - "finetune": chỉ finetune_log.csv
      - "auto"    : training_log.csv nối finetune_log.csv (nếu có), episode của
                    finetune được renumber liên tục ngay sau episode cuối của training
                    → full timeline của model, không lẫn lộn thứ tự.

    Trả về (rows, finetune_meta | None, has_finetune, finetune_start_episode | None).
    finetune_start_episode = episode (đã renumber) mà finetune bắt đầu trong timeline gộp.
    """
    model_dir     = log_dir / model
    train_path    = model_dir / "training_log.csv"
    finetune_path = model_dir / "finetune_log.csv"
    has_finetune  = finetune_path.exists()

    if log_type == "training":
        _, rows = read_csv_with_meta(train_path)
        if not rows:
            print(f"  ⚠ Không tìm thấy: {train_path}")
        return rows, None, has_finetune, None

    if log_type == "finetune":
        meta, rows = read_csv_with_meta(finetune_path)
        if not rows:
            print(f"  ⚠ Không tìm thấy: {finetune_path}")
        return rows, (meta or None), has_finetune, None

    # log_type == "auto" — training trước, finetune sau, renumber liên tục
    _, train_rows = read_csv_with_meta(train_path)
    if not has_finetune:
        return train_rows, None, False, None

    meta, ft_rows = read_csv_with_meta(finetune_path)
    if not ft_rows:
        return train_rows, None, True, None

    offset = 0
    if train_rows:
        last_ep = max(int(r.get("episode", i)) for i, r in enumerate(train_rows))
        offset = last_ep + 1

    combined = list(train_rows)
    for i, r in enumerate(ft_rows):
        r2 = dict(r)
        r2["episode"] = offset + int(r.get("episode", i))
        combined.append(r2)

    return combined, (meta or None), True, offset


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


def _build_episodes(data: dict[str, list[dict]]) -> list[dict]:
    """Index theo episode, gộp nhiều series thành 1 list episodes[] cho chart."""
    max_ep = 0
    for rows in data.values():
        if not rows:
            continue
        last_ep = max((int(r.get("episode", i)) for i, r in enumerate(rows)), default=0)
        max_ep = max(max_ep, last_ep + 1, len(rows))

    if max_ep == 0:
        return []

    indexed: dict[str, dict[int, dict]] = {}
    for key, rows in data.items():
        by_ep: dict[int, dict] = {}
        for i, row in enumerate(rows):
            ep = int(row.get("episode", i))
            by_ep[ep] = row  # nếu trùng episode (multi-worker), lấy cái cuối
        indexed[key] = by_ep

    episodes = []
    for ep in range(max_ep):
        row_out = {"episode": ep}
        for key in data:
            src = indexed.get(key, {}).get(ep)
            if src is None:
                continue
            for metric in CHART_METRICS:
                val = src.get(metric)
                if val is not None:
                    try:
                        row_out[f"{key}_{metric}"] = float(val)
                    except (ValueError, TypeError):
                        pass
            if src.get("had_obstacle") or src.get("had_accident"):
                row_out[f"{key}_had_obstacle"] = True
                row_out[f"{key}_obstacle_count"] = int(src.get("obstacle_count", 0) or 0)
        episodes.append(row_out)

    return episodes


def _build_summary(data: dict[str, list[dict]], tail_n: int) -> dict:
    """Mean ± std của tail_n episode cuối cho mỗi series."""
    summary = {}
    for key, rows in data.items():
        if not rows:
            continue
        tail = rows[-tail_n:]
        s = {}
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
            s[metric] = mean
            s[f"{metric}_std"] = std
        s["obstacle_episodes"] = sum(
            1 for r in tail if r.get("had_obstacle") or r.get("had_accident")
        )
        s["total_episodes"] = len(rows)
        summary[key] = s
    return summary


def _print_summary_table(summary: dict, labels: dict, tail_n: int):
    keys = list(summary.keys())
    if not keys:
        print("Không có dữ liệu nào.")
        return

    print(f"\nSummary ({tail_n} episode cuối):")
    print(f"{'':>20s}", end="")
    for key in keys:
        print(f"  {labels.get(key, key):>20s}", end="")
    print()
    print("─" * (20 + 22 * len(keys)))

    for metric in SUMMARY_METRICS:
        print(f"  {metric:>18s}", end="")
        for key in keys:
            s = summary[key]
            mean, std = s.get(metric), s.get(f"{metric}_std")
            if mean is not None and std is not None:
                print(f"  {mean:>10.2f} ± {std:<7.2f}", end="")
            else:
                print(f"  {'—':>20s}", end="")
        print()

    for key in keys:
        obs, total = summary[key].get("obstacle_episodes", 0), summary[key].get("total_episodes", 0)
        print(f"  {labels.get(key, key)}: {total} total episodes, {obs} with obstacles (trong {tail_n} cuối)")


# ── Mode 1: merge mặc định (3 model, 1 topology, backward compat) ──────────────
def merge(topology: str, tail_n: int = TAIL_N):
    log_dir = ROOT_DIR / "logs" / topology
    print(f"Đang merge logs cho topology '{topology}'...")
    print(f"  Log dir: {log_dir}")

    data: dict[str, list[dict]] = {}
    finetune_info: dict[str, dict] = {}

    for m in MODELS:
        rows, meta, has_ft, ft_start = load_model_series(log_dir, m, log_type="auto")
        data[m] = rows
        if rows:
            extra = f" (training + finetune từ episode {ft_start})" if has_ft and ft_start is not None else ""
            print(f"  ✓ {m}: {len(rows)} rows{extra}")

        info = {"has_finetune": has_ft}
        if has_ft:
            info["finetune_start_episode"] = ft_start
            if meta:
                info["finetune_from"] = meta.get("finetune_from")
                info["topology"]      = meta.get("topology")
        finetune_info[m] = info

    episodes = _build_episodes(data)
    if not episodes:
        print("Không có dữ liệu nào.")
        return

    summary = _build_summary(data, tail_n)

    out = {
        "topology": topology,
        "tail_n": tail_n,
        "episodes": episodes,
        "summary": summary,
        "finetune_info": finetune_info,   # { model: {has_finetune, finetune_from, topology, finetune_start_episode} }
    }

    # Primary: logs/<topology>/merged.json
    out_path = log_dir / "merged.json"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"\n✓ Output: {out_path} ({len(episodes)} episodes)")

    # Backward compat: logs/merged.json (server có route /logs/merged.json serve riêng)
    compat_path = ROOT_DIR / "logs" / "merged.json"
    with open(compat_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"✓ Compat: {compat_path}")

    _print_summary_table(summary, {m: m for m in MODELS}, tail_n)


# ── Mode 2: --compare — so sánh N series tuỳ ý ──────────────────────────────────
def parse_series_spec(spec: str) -> dict:
    """
    Parse 'topology/model' hoặc 'topology/model/log_type' → dict.
    log_type ∈ {training, finetune, auto}, mặc định 'auto' nếu không chỉ định.
    """
    parts = spec.split("/")
    if len(parts) == 2:
        topology, model, log_type = parts[0], parts[1], "auto"
    elif len(parts) == 3:
        topology, model, log_type = parts
    else:
        raise ValueError(
            f"Series spec không hợp lệ: '{spec}' — dùng dạng 'topology/model' "
            f"hoặc 'topology/model/log_type'"
        )
    if log_type not in ("training", "finetune", "auto"):
        raise ValueError(f"log_type '{log_type}' không hợp lệ — chỉ nhận: training | finetune | auto")
    return {"topology": topology, "model": model, "log_type": log_type}


def compare(specs: list[str], labels: list[str] | None, tail_n: int, out_path: str | None):
    parsed = [parse_series_spec(s) for s in specs]
    labels = labels or []

    data: dict[str, list[dict]] = {}
    series_meta = []
    label_map = {}

    print(f"Đang so sánh {len(parsed)} series...")
    for i, p in enumerate(parsed):
        log_dir = ROOT_DIR / "logs" / p["topology"]
        rows, meta, has_ft, _ = load_model_series(log_dir, p["model"], p["log_type"])
        key   = f"{p['topology']}_{p['model']}_{p['log_type']}"
        label = labels[i] if i < len(labels) else f"{p['model']} ({p['topology']}, {p['log_type']})"

        if not rows:
            print(f"  ⚠ '{specs[i]}' → không có dữ liệu")
        else:
            print(f"  ✓ {label}: {len(rows)} rows")

        data[key]      = rows
        label_map[key] = label
        info = {"key": key, "label": label, **p}
        if meta:
            info["finetune_meta"] = {"finetune_from": meta.get("finetune_from"), "topology": meta.get("topology")}
        series_meta.append(info)

    episodes = _build_episodes(data)
    if not episodes:
        print("Không có dữ liệu nào để so sánh.")
        return

    summary = _build_summary(data, tail_n)

    out = {
        "mode": "compare",
        "tail_n": tail_n,
        "series": series_meta,
        "episodes": episodes,
        "summary": summary,
    }

    if out_path:
        out_file = Path(out_path)
    else:
        name = "_vs_".join(s["key"] for s in series_meta)
        out_file = ROOT_DIR / "logs" / "comparisons" / f"{name}.json"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"\n✓ Output: {out_file} ({len(episodes)} episodes, {len(series_meta)} series)")

    _print_summary_table(summary, label_map, tail_n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge training logs thành JSON cho dashboard")
    parser.add_argument("--topology", type=str, default=None,
                        help="Topology name (e.g., mydinh, 2x2, uet). Auto-detect từ config nếu không chỉ định.")
    parser.add_argument("--tail", type=int, default=TAIL_N,
                        help=f"Số episode cuối dùng cho summary (default: {TAIL_N})")
    parser.add_argument("--compare", nargs="+", default=None, metavar="SERIES",
                        help="So sánh N series log tuỳ ý — mỗi series 'topology/model' hoặc "
                             "'topology/model/log_type' (log_type: training|finetune|auto). "
                             "Ví dụ: --compare uet/gat_marl/finetune uet/idqn/training")
    parser.add_argument("--labels", nargs="+", default=None,
                        help="Tên hiển thị cho mỗi series trong --compare (theo đúng thứ tự)")
    parser.add_argument("--out", type=str, default=None,
                        help="Đường dẫn output JSON cho --compare (default: logs/comparisons/<auto-name>.json)")
    args = parser.parse_args()

    if args.compare:
        if len(args.compare) < 2:
            parser.error("--compare cần ít nhất 2 series để so sánh")
        compare(args.compare, args.labels, args.tail, args.out)
    else:
        topology = args.topology or _detect_topology()
        merge(topology=topology, tail_n=args.tail)