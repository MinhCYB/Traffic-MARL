"""
scripts/merge_logs.py — Merge CSV logs thành JSON cho dashboard Results tab

Đọc logs/gat_marl/training_log.csv + logs/idqn/training_log.csv
       + logs/fixed_time/training_log.csv
→ Tạo logs/merged.json để Results.jsx load

Dùng sau khi train xong:
    python scripts/merge_logs.py
"""

import csv
import json
from pathlib import Path

LOG_DIR   = Path("logs")
OUT_FILE  = LOG_DIR / "merged.json"
MODELS    = ["gat_marl", "idqn", "fixed_time"]
METRICS   = ["global_reward", "avg_speed", "avg_waiting_time", "throughput"]
TAIL_N    = 50   # số episode cuối để tính summary


def load_csv(model: str) -> list[dict]:
    path = LOG_DIR / model / "training_log.csv"
    if not path.exists():
        print(f"  Không tìm thấy: {path}")
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def merge():
    print("Đang merge logs...")
    data = {m: load_csv(m) for m in MODELS}

    # Tìm số episode tối đa
    max_ep = max((len(rows) for rows in data.values() if rows), default=0)
    if max_ep == 0:
        print("Không có dữ liệu.")
        return

    # Build merged episodes list
    episodes = []
    for ep in range(max_ep):
        row = {"episode": ep}
        for model, rows in data.items():
            if ep < len(rows):
                for metric in METRICS:
                    val = rows[ep].get(metric)
                    try:
                        row[f"{model}_{metric}"] = float(val) if val else None
                    except (ValueError, TypeError):
                        row[f"{model}_{metric}"] = None
        episodes.append(row)

    # Summary: trung bình TAIL_N episode cuối
    summary = {}
    for model, rows in data.items():
        if not rows:
            continue
        tail = rows[-TAIL_N:]
        summary[model] = {}
        for metric in METRICS:
            vals = []
            for r in tail:
                try:
                    vals.append(float(r[metric]))
                except (ValueError, TypeError, KeyError):
                    pass
            summary[model][metric] = round(sum(vals) / len(vals), 4) if vals else None

    out = {"episodes": episodes, "summary": summary}
    LOG_DIR.mkdir(exist_ok=True)
    with open(OUT_FILE, "w") as f:
        json.dump(out, f)

    print(f"Done: {OUT_FILE} ({max_ep} episodes)")
    print("Summary:")
    for model, s in summary.items():
        print(f"  {model}: {s}")


if __name__ == "__main__":
    merge()