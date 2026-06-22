"""
scripts/eval_parallel.py — Đánh giá song song 4 model trên cùng seed + kịch bản

Spawn 4 process con chạy song song, mỗi model 1 process.
Obstacle schedule được gen 1 lần ở process cha rồi truyền xuống tất cả
→ đảm bảo 100% cùng kịch bản, so sánh công bằng.

Chạy:
    python -m scripts.eval_parallel
    python -m scripts.eval_parallel --runs 10 --route peak_morning --seed 42
    python -m scripts.eval_parallel --runs 5 --route night --seed 123 --topology mydinh
    python -m scripts.eval_parallel --no-obstacle   # tắt vật cản
"""

import argparse
import json
import multiprocessing as mp
import random
import time
from pathlib import Path

import numpy as np

# ── Constants (mirror từ training/config.py, không import để tránh side effects) ──
PORT_MAP = {
    "gat_marl":     8813,
    "shared_dqn":   8814,
    "fixed_time":   8815,
    "sumo_actuated": 8816,
}

MODEL_LABELS = {
    "gat_marl":      "GAT-MARL (ours)",
    "shared_dqn":    "Shared-DQN (MPLight-style)",
    "fixed_time":    "Fixed-time",
    "sumo_actuated": "SUMO Actuated",
}

METRICS = {
    "avg_waiting_time":    ("Avg Waiting Time (s)",  "↓"),
    "avg_speed":           ("Avg Speed (km/h)",       "↑"),
    "throughput":          ("Throughput (vehicles)",  "↑"),
    "global_reward":       ("Global Reward",          "↑"),
    "vehicles_teleported": ("Teleported Vehicles",    "↓"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Obstacle scheduler (copy từ training/train.py để không phụ thuộc)
# ─────────────────────────────────────────────────────────────────────────────

def _gen_obstacle_schedule(
    rng: random.Random,
    all_edges: list[str],
    obstacle_prob: float,
    max_count: int,
    duration_min: int,
    sim_end: int,
    delta_time: int,
) -> list[tuple[int, int, str]]:
    """Gen obstacle schedule từ rng cố định — gọi 1 lần ở process cha."""
    if not all_edges or rng.random() >= obstacle_prob:
        return []

    count = rng.randint(1, min(max_count, len(all_edges)))
    edges = rng.sample(all_edges, count)

    start_step_min = max(1, 60 // delta_time)
    start_step_max = max(start_step_min + 1, 600 // delta_time)

    obstacles = []
    for edge in edges:
        inject_step = rng.randint(start_step_min, start_step_max)
        clear_step  = sim_end // delta_time + 1          # giữ đến hết episode
        obstacles.append((inject_step, clear_step, edge))
    return obstacles


# ─────────────────────────────────────────────────────────────────────────────
# Worker function — chạy trong process con
# ─────────────────────────────────────────────────────────────────────────────

def _run_model(
    model_name:       str,
    topology:         str,
    seed:             int,
    route_type:       str,
    runs:             int,
    obstacle_plans:   list[list[tuple[int, int, str]]],  # 1 plan / run
    result_queue:     mp.Queue,
    delta_time:       int = 5,
    sim_end:          int = 1800,
):
    """Chạy N episode cho 1 model, gửi kết quả vào queue."""
    try:
        from training.config import FINAL_DIR
        from environment.traffic_env import TrafficEnv
        from environment.state_builder import INTERSECTION_IDS

        port = PORT_MAP[model_name]
        env  = TrafficEnv(
            port=port, topology=topology,
            use_gui=False, seed=seed, delta_time=delta_time,
        )

        # ── Load agent ────────────────────────────────────────────────────────
        if model_name == "gat_marl":
            from agents.gat_agent import GATAgent
            from training.config import (STATE_DIM, HIDDEN_DIM, NUM_HEADS,
                                         NUM_ACTIONS, DROPOUT)
            agent = GATAgent(
                state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
                num_heads=NUM_HEADS, num_actions=NUM_ACTIONS,
                lr=1e-4, gamma=0.99,
                epsilon=0.0, epsilon_min=0.0, epsilon_decay=1.0,
                target_update_freq=999999,
            )
            ckpt = FINAL_DIR / f"gat_marl_{topology}_best.pt"
            agent.load(str(ckpt))

        elif model_name == "shared_dqn":
            from agents.idqn_agent import IDQNAgent
            from training.config import STATE_DIM, HIDDEN_DIM, NUM_ACTIONS
            agent = IDQNAgent(
                state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
                num_actions=NUM_ACTIONS,
                lr=1e-4, gamma=0.99,
                epsilon=0.0, epsilon_min=0.0, epsilon_decay=1.0,
                target_update_freq=999999,
            )
            ckpt = FINAL_DIR / f"idqn_{topology}_best.pt"
            agent.load(str(ckpt))

        elif model_name == "fixed_time":
            from agents.fixed_agent import FixedAgent
            agent = FixedAgent()

        elif model_name == "sumo_actuated":
            from agents.sumo_actuated_agent import SumoActuatedAgent
            agent = SumoActuatedAgent()

        else:
            raise ValueError(f"Unknown model: {model_name}")

        # ── Chạy N episode ────────────────────────────────────────────────────
        episode_results = []

        for run_idx in range(runs):
            obs  = env.reset(route_type=route_type)
            done = False
            step = 0

            # Activate SUMO actuated sau reset
            if model_name == "sumo_actuated" and hasattr(agent, "activate"):
                agent.activate()
            if hasattr(agent, "reset"):
                agent.reset()

            obstacles       = obstacle_plans[run_idx]
            active_obstacles = set()

            ep_reward     = 0.0
            ep_throughput = 0
            last_info     = {}

            while not done:
                # Inject / clear obstacles
                for (inj, clr, edge) in obstacles:
                    if step == inj and edge not in active_obstacles:
                        env.inject_accident(edge)
                        active_obstacles.add(edge)
                    if step == clr and edge in active_obstacles:
                        env.clear_accident(edge)
                        active_obstacles.discard(edge)

                actions                  = agent.select_actions(obs)
                obs, rewards, done, info = env.step(actions)

                ep_reward     += sum(rewards.values())
                ep_throughput += info.get("arrived_count", 0)
                last_info      = info
                step          += 1

            episode_results.append({
                "run":                run_idx,
                "global_reward":      ep_reward,
                "avg_waiting_time":   last_info.get("avg_waiting_time", float("nan")),
                "avg_speed":          last_info.get("avg_speed",         float("nan")),
                "throughput":         ep_throughput,
                "vehicles_teleported": last_info.get("teleport_count",  0),
                "had_obstacle":       len(obstacles) > 0,
                "obstacle_count":     len(obstacles),
            })
            print(f"  [{model_name}] run {run_idx+1}/{runs} done — "
                  f"reward={ep_reward:.1f}  wait={last_info.get('avg_waiting_time', 0):.2f}s")

        env.close()
        result_queue.put({"model": model_name, "episodes": episode_results, "error": None})

    except Exception as e:
        import traceback
        result_queue.put({"model": model_name, "episodes": [], "error": traceback.format_exc()})


# ─────────────────────────────────────────────────────────────────────────────
# Bảng so sánh
# ─────────────────────────────────────────────────────────────────────────────

def _compute_stats(episodes: list[dict], metric: str) -> tuple[float, float]:
    vals = [e[metric] for e in episodes if not np.isnan(e.get(metric, float("nan")))]
    if not vals:
        return float("nan"), float("nan")
    return float(np.mean(vals)), float(np.std(vals))


def _build_table(all_results: dict[str, list[dict]], models: list[str]) -> str:
    header_models = [MODEL_LABELS[m] for m in models]
    lines = []
    lines.append("| Metric | Direction | " + " | ".join(header_models) + " |")
    lines.append("|--------|:---------:|" + "|".join([":-------:"] * len(models)) + "|")

    for metric, (label, direction) in METRICS.items():
        stats = {m: _compute_stats(all_results[m], metric) for m in models}
        valid  = {m: s[0] for m, s in stats.items() if not np.isnan(s[0])}
        if valid:
            best = max(valid, key=valid.get) if direction == "↑" else min(valid, key=valid.get)
        else:
            best = None

        cells = []
        for m in models:
            mean, std = stats[m]
            if np.isnan(mean):
                cells.append("N/A")
            else:
                cell = f"{mean:.3f} ± {std:.3f}"
                cells.append(f"**{cell}**" if m == best else cell)

        lines.append(f"| {label} | {direction} | " + " | ".join(cells) + " |")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Đánh giá song song 4 model trên cùng seed + kịch bản"
    )
    parser.add_argument("--runs",      type=int,   default=10,
                        help="Số lần chạy mỗi model (default: 10)")
    parser.add_argument("--seed",      type=int,   default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--route",     type=str,   default="peak_morning",
                        choices=["peak_morning", "peak_evening", "night"],
                        help="Loại kịch bản giao thông (default: peak_morning)")
    parser.add_argument("--topology",  type=str,   default=None,
                        help="Topology (default: lấy từ config.py)")
    parser.add_argument("--obstacle-prob", type=float, default=0.3,
                        help="Xác suất xuất hiện vật cản mỗi episode (default: 0.3)")
    parser.add_argument("--no-obstacle",   action="store_true",
                        help="Tắt hoàn toàn vật cản")
    parser.add_argument("--out",       type=str,   default=None,
                        help="Thư mục output (default: logs/<topology>/eval/)")
    args = parser.parse_args()

    # ── Config ────────────────────────────────────────────────────────────────
    from training.config import TOPOLOGY, DELTA_TIME, SIM_END
    from environment.state_builder import INCOMING_EDGES

    topology   = args.topology or TOPOLOGY
    delta_time = DELTA_TIME
    sim_end    = SIM_END
    obstacle_prob = 0.0 if args.no_obstacle else args.obstacle_prob

    all_edges = list({edge for edges in INCOMING_EDGES.values() for edge in edges})

    out_dir = Path(args.out) if args.out else Path("logs") / topology / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Gen obstacle schedule 1 lần ───────────────────────────────────────────
    rng = random.Random(args.seed)
    obstacle_plans = [
        _gen_obstacle_schedule(rng, all_edges, obstacle_prob, 2, 300, sim_end, delta_time)
        for _ in range(args.runs)
    ]
    n_with_obstacle = sum(1 for p in obstacle_plans if p)

    print(f"\n{'='*60}")
    print(f"  EVAL PARALLEL — {topology.upper()}")
    print(f"  Seed     : {args.seed}")
    print(f"  Route    : {args.route}")
    print(f"  Runs     : {args.runs}")
    print(f"  Obstacle : {obstacle_prob:.0%} prob → {n_with_obstacle}/{args.runs} episodes có vật cản")
    print(f"  Output   : {out_dir}")
    print(f"{'='*60}\n")

    # ── Spawn 4 process song song ─────────────────────────────────────────────
    models = list(PORT_MAP.keys())
    result_queue: mp.Queue = mp.Queue()
    processes = []

    for model_name in models:
        p = mp.Process(
            target=_run_model,
            args=(model_name, topology, args.seed, args.route,
                  args.runs, obstacle_plans, result_queue, delta_time, sim_end),
            daemon=True,
        )
        p.start()
        processes.append(p)
        print(f"  ✓ Started {model_name} (pid={p.pid})")

    print()

    # ── Gom kết quả ──────────────────────────────────────────────────────────
    all_results: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}

    for _ in models:
        result = result_queue.get(timeout=3600)   # chờ tối đa 60 phút
        m = result["model"]
        if result["error"]:
            errors[m] = result["error"]
            print(f"\n  ✗ {m} ERROR:\n{result['error']}")
            all_results[m] = []
        else:
            all_results[m] = result["episodes"]
            print(f"  ✓ {m} hoàn thành {len(result['episodes'])} runs")

    for p in processes:
        p.join(timeout=10)

    # ── In bảng so sánh ──────────────────────────────────────────────────────
    table_md = _build_table(all_results, models)

    print(f"\n{'='*60}")
    print(f"BẢNG SO SÁNH — {topology.upper()} — {args.runs} runs — seed={args.seed}")
    print(f"Route: {args.route}  |  Obstacle prob: {obstacle_prob:.0%}")
    print(f"{'='*60}")
    print(table_md)
    print(f"(** = tốt nhất trong hàng, Mean ± Std)\n")

    # ── Ghi file ─────────────────────────────────────────────────────────────
    tag = f"{args.route}_seed{args.seed}_{args.runs}runs"

    md_content = (
        f"# Evaluation — {topology} — {args.route} — seed={args.seed} — {args.runs} runs\n\n"
        f"**Obstacle prob:** {obstacle_prob:.0%} "
        f"({n_with_obstacle}/{args.runs} episodes có vật cản)  \n"
        f"**Models:** {', '.join(MODEL_LABELS.values())}\n\n"
        + table_md
        + "\n\n> Bold = tốt nhất. Mean ± Std trên {args.runs} runs cùng seed.\n"
    )
    (out_dir / f"comparison_{tag}.md").write_text(md_content)

    json_out = {
        "topology":       topology,
        "seed":           args.seed,
        "route":          args.route,
        "runs":           args.runs,
        "obstacle_prob":  obstacle_prob,
        "obstacle_plans": obstacle_plans,
        "models":         models,
        "results":        all_results,
    }
    (out_dir / f"comparison_{tag}.json").write_text(
        json.dumps(json_out, indent=2, ensure_ascii=False)
    )

    if errors:
        print(f"⚠️  {len(errors)} model bị lỗi: {list(errors.keys())}")
    else:
        print(f"✅ Kết quả đã ghi vào: {out_dir}/comparison_{tag}.*")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()