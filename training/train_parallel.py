"""
train_parallel.py — Parallel rollout training (Ape-X style)

Architecture:
    N RolloutWorkers (mỗi cái 1 SUMO process, 1 CPU core)
        └─ collect experience  → exp_queue   → Learner (GPU update)
        └─ episode summary     → stats_queue → Learner (CSV log)
    1 Learner (main process, GPU)
        └─ update → broadcast weights → workers

CSV output: logs/<topology>/<model>/training_log.csv
    Cùng format với train.py → merge_logs.py + dashboard dùng được bình thường.

Thêm (finetune accident):
- --accident-prob  : xác suất sinh tai nạn mỗi episode ở mỗi worker (default 0.0)
- --accident-duration: thời gian kéo dài sự cố tính bằng giây (default 300)
- Log ghi mode "a" (append) khi resume/finetune, "w" (overwrite) khi fresh train

Chạy:
    python -m training.train_parallel --model gat_marl --num-workers 3
    python -m training.train_parallel --model gat_marl --num-workers 3 \\
        --resume checkpoints/final/gat_marl_mydinh_best.pt

    # Finetune với tai nạn:
    python -m training.train_parallel --model gat_marl --num-workers 3 \\
        --finetune checkpoints/final/gat_marl_mydinh_best.pt \\
        --accident-prob 0.3 --accident-duration 300
"""

import argparse
import csv
import os
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.multiprocessing as mp

from training.config import (
    NUM_EPISODES, BATCH_SIZE, REPLAY_BUFFER_SIZE, MIN_REPLAY_SIZE,
    SAVE_FREQ, SEED,
    CHECKPOINT_DIR, FINAL_DIR, LOG_DIR,
    EPSILON_START, EPSILON_MIN, EPSILON_DECAY,
    LR, GAMMA, TARGET_UPDATE_FREQ,
    STATE_DIM, HIDDEN_DIM, NUM_HEADS, NUM_ACTIONS,
    TOPOLOGY, DELTA_TIME, SIM_END,
    OBSTACLE_PROB, OBSTACLE_MAX_COUNT,
    OBSTACLE_DURATION_MIN, OBSTACLE_DURATION_MAX,
)
from training.replay_buffer import ReplayBuffer
from environment.state_builder import INTERSECTION_IDS, INCOMING_EDGES

# ── Parallel-specific knobs ───────────────────────────────────────────────────
BASE_PORT          = 8820   # worker i dùng port BASE_PORT + i
SYNC_EVERY         = 50     # sync thường hơn → workers dùng policy mới hơn
                            # 200 = sync ~3 lần/episode, đủ fresh mà không overhead
MAX_EXP_QUEUE      = 12000  # tăng buffer để worker ít drop hơn khi GPU bận
WORKER_EPSILON_MIN = 0.10   # workers luôn explore tối thiểu 10%

# ── Danh sách tất cả edge có thể xảy ra tai nạn ──────────────────────────────
# Mỗi worker process có bản copy riêng sau fork/spawn nên thread-safe
_ALL_ACCIDENT_EDGES: list[str] = list(
    {edge for edges in INCOMING_EDGES.values() for edge in edges}
)


# ══════════════════════════════════════════════════════════════════════════════
# Obstacle helper — dùng trong worker
# "Tai nạn" → "Vật cản" (công trình, xe hỏng, sửa đường...)
# Duration có thể xuyên suốt episode (OBSTACLE_DURATION_MAX = None)
# ══════════════════════════════════════════════════════════════════════════════

def _schedule_obstacles(
    obstacle_prob: float,
    max_count:     int,
    duration_min:  int,
    duration_max:  int | None,
    sim_end:       int,
    delta_time:    int,
) -> list[tuple[int, int, str]]:
    """
    Quyết định có sinh vật cản cho episode này không.

    Returns:
        list[(inject_step, clear_step, edge_id)]
        List rỗng nếu không có vật cản.

    inject_step / clear_step tính theo đơn vị step (1 step = delta_time giây).
    Nếu duration_max is None → clear_step vượt qua cuối episode (xuyên suốt).
    """
    if not _ALL_ACCIDENT_EDGES or random.random() >= obstacle_prob:
        return []

    count = random.randint(1, min(max_count, len(_ALL_ACCIDENT_EDGES)))
    edges = random.sample(_ALL_ACCIDENT_EDGES, count)

    start_step_min = max(1, 60 // delta_time)
    start_step_max = max(start_step_min + 1, 600 // delta_time)

    obstacles = []
    for edge in edges:
        inject_step = random.randint(start_step_min, start_step_max)
        if duration_max is None:
            # Xuyên suốt episode
            clear_step = sim_end // delta_time + 1
        else:
            dur = random.randint(duration_min, duration_max)
            clear_step = inject_step + max(1, dur // delta_time)
        obstacles.append((inject_step, clear_step, edge))

    return obstacles


# ══════════════════════════════════════════════════════════════════════════════
# Rollout Worker
# ══════════════════════════════════════════════════════════════════════════════

def rollout_worker(
    worker_id:        int,
    model_name:       str,
    exp_queue:        mp.Queue,   # push raw transitions
    stats_queue:      mp.Queue,   # push episode summary dict
    weight_queue:     mp.Queue,   # nhận state_dict từ learner
    stop_event:       mp.Event,
    episodes:         int,
    delta_time:       int,
    obstacle_prob:    float = 0.0,
    obstacle_max_count: int = 3,
    obstacle_duration_min: int = 300,
    obstacle_duration_max: int | None = None,
):
    """Chạy SUMO, collect experience, gửi episode stats về learner."""
    os.environ["CUDA_VISIBLE_DEVICES"] = ""   # worker chỉ dùng CPU

    from environment.traffic_env import TrafficEnv

    port   = BASE_PORT + worker_id
    seed   = SEED + worker_id
    # Epsilon staggered: đa dạng exploration giữa các workers
    eps    = max(WORKER_EPSILON_MIN, EPSILON_START - worker_id * 0.15)

    print(f"[Worker-{worker_id}] port={port} | ε_start={eps:.2f} | obstacle_prob={obstacle_prob:.0%}")

    agent = _build_agent(model_name, device="cpu",
                         epsilon=eps,
                         epsilon_min=WORKER_EPSILON_MIN,
                         epsilon_decay=EPSILON_DECAY)
    env   = TrafficEnv(port=port, topology=TOPOLOGY,
                       use_gui=False, seed=seed, delta_time=delta_time)

    global_episode = 0   # episode counter toàn worker (để log)

    while not stop_event.is_set() and global_episode < episodes:
        t0   = time.time()
        obs  = env.reset()
        done = False

        ep_reward    = 0.0
        ep_steps     = 0
        last_info    = {}

        # ── Lập lịch vật cản cho episode này ────────────────────────────────
        obstacles = _schedule_obstacles(
            obstacle_prob, obstacle_max_count,
            obstacle_duration_min, obstacle_duration_max,
            SIM_END, delta_time,
        )
        active_obstacles: set[str] = set()

        if obstacles:
            edges_str = ", ".join(e for _, _, e in obstacles)
            print(
                f"  [Worker-{worker_id} | Ep {global_episode}] "
                f"Vật cản ({len(obstacles)}) → edges: {edges_str}"
            )

        # Sync weights mới nhất từ learner trước mỗi episode
        _pull_weights(agent, weight_queue)

        while not done and not stop_event.is_set():
            # ── Inject / clear vật cản ───────────────────────────────────────
            for (inj, clr, edge) in obstacles:
                if ep_steps == inj and edge not in active_obstacles:
                    env.inject_accident(edge)
                    active_obstacles.add(edge)
                if ep_steps == clr and edge in active_obstacles:
                    env.clear_accident(edge)
                    active_obstacles.discard(edge)

            actions = agent.select_actions(obs)
            next_obs, rewards, done, info = env.step(actions)

            # Push transition — drop nếu queue full (không block SUMO)
            try:
                exp_queue.put_nowait((
                    obs["node_features"].astype(np.float32),
                    actions,
                    rewards,
                    next_obs["node_features"].astype(np.float32),
                    done,
                ))
            except Exception:
                pass

            ep_reward += info.get("global_reward", 0.0)
            ep_steps  += 1
            last_info  = info
            obs        = next_obs

        # ── Cleanup vật cản còn active khi episode kết thúc / bị ngắt ────────
        for edge in list(active_obstacles):
            try:
                env.clear_accident(edge)
            except Exception:
                pass
        active_obstacles.clear()

        # ── Episode summary — cùng schema với train.py ────────────────────
        duration = time.time() - t0
        summary  = {
            "worker_id":        worker_id,
            "episode":          global_episode,
            "total_steps":      ep_steps,
            "global_reward":    round(ep_reward, 4),
            "avg_speed":        round(last_info.get("avg_speed", 0.0), 2),
            "avg_waiting_time": round(last_info.get("avg_waiting_time", 0.0), 2),
            "throughput":       last_info.get("throughput", 0),
            "epsilon":          round(getattr(agent, "epsilon", 0.0), 4),
            "duration_s":       round(duration, 1),
            "had_obstacle":     int(len(obstacles) > 0),
            "obstacle_edges":   ",".join(e for _, _, e in obstacles) if obstacles else "",
            "obstacle_count":   len(obstacles),
        }
        try:
            stats_queue.put_nowait(summary)
        except Exception:
            pass

        # Decay epsilon
        if hasattr(agent, "epsilon"):
            agent.epsilon = max(WORKER_EPSILON_MIN, agent.epsilon * EPSILON_DECAY)

        global_episode += 1

    env.close()
    print(f"[Worker-{worker_id}] Finished — {global_episode} episodes")


def _pull_weights(agent, weight_queue: mp.Queue):
    """Lấy state_dict mới nhất, bỏ qua nếu queue rỗng."""
    latest = None
    while True:
        try:
            latest = weight_queue.get_nowait()
        except Exception:
            break
    if latest is not None and hasattr(agent, "online_net"):
        try:
            agent.online_net.load_state_dict(latest)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Learner (chạy ở main process để dùng GPU trực tiếp)
# ══════════════════════════════════════════════════════════════════════════════

def run_learner(
    model_name:          str,
    exp_queue:           mp.Queue,
    stats_queue:         mp.Queue,
    weight_queues:       list,
    stop_event:          mp.Event,
    num_workers:         int,
    episodes_per_worker: int,
    log_path:            Path,
    resume:              str | None,
    finetune:            str | None,
    freeze_gat_episodes: int,
    log_file_mode:       str = "w",
):
    device      = "cuda" if torch.cuda.is_available() else "cpu"
    device_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"
    print(f"[Learner] Thiết bị training: {device.upper()} — {device_name}")

    agent  = _build_agent(model_name, device=device,
                          epsilon=0.0, epsilon_min=0.0, epsilon_decay=1.0)
    buffer = ReplayBuffer(REPLAY_BUFFER_SIZE, state_dim=STATE_DIM,
                          n_agents=len(INTERSECTION_IDS))

    if finetune:
        agent.load(finetune)
        print(f"[Learner] Finetune ← {finetune}")
        if freeze_gat_episodes > 0 and hasattr(agent, "freeze_gat"):
            agent.freeze_gat()
    elif resume:
        agent.load(resume)
        print(f"[Learner] Resume ← {resume}")

    ckpt_dir = CHECKPOINT_DIR / model_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # ── CSV — cùng fieldnames với train.py ────────────────────────────────
    # Thêm worker_id để biết episode đến từ worker nào khi debug
    fieldnames = [
        "episode", "worker_id", "total_steps", "global_reward",
        "avg_speed", "avg_waiting_time", "throughput",
        "loss", "epsilon", "duration_s",
        "had_obstacle", "obstacle_edges", "obstacle_count",   # ← obstacle fields
    ]

    total_updates  = 0
    best_reward    = float("-inf")
    ready          = False
    steps_per_ep   = SIM_END // DELTA_TIME   # dùng SIM_END từ config

    # Throttle: chỉ update khi có đủ transitions mới từ workers
    # Tránh overfit vì learner update hàng chục nghìn lần trước khi workers push data mới
    MIN_NEW_TRANSITIONS = BATCH_SIZE * 4   # = 128
    last_buf_size = 0

    # Ước tính tổng episodes để log ETA
    total_episodes = episodes_per_worker * num_workers
    logged_episodes = 0

    print(f"[Learner] Chờ workers collect đủ {MIN_REPLAY_SIZE} transitions...")

    # ── Drain thread riêng — không bị block bởi backprop ─────────────────────
    # Khi GPU backprop liên tục 100%, drain trong main loop không kịp
    # → queue full → workers drop transitions → lãng phí SUMO work
    # Tách ra thread riêng để drain chạy song song với backprop
    import threading

    def _drain_loop():
        while not stop_event.is_set():
            drained = 0
            while drained < 512:
                try:
                    s, a, r, ns, d = exp_queue.get(timeout=0.05)
                    buffer.push(s, a, r, ns, d)
                    drained += 1
                except Exception:
                    break

    drain_thread = threading.Thread(target=_drain_loop, daemon=True, name="DrainThread")
    drain_thread.start()

    with open(log_path, log_file_mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Chỉ ghi header khi tạo file mới
        if log_file_mode == "w":
            writer.writeheader()

        while not stop_event.is_set():
            # ── 1. Check buffer ready ─────────────────────────────────────
            if not ready:
                if buffer.is_ready(MIN_REPLAY_SIZE):
                    ready = True
                    print("[Learner] Buffer sẵn sàng — bắt đầu training (backprop)")
                else:
                    time.sleep(0.05)
                    continue

            # ── 3. Unfreeze GAT nếu đến lúc ──────────────────────────────
            if (finetune and freeze_gat_episodes > 0
                    and logged_episodes >= freeze_gat_episodes
                    and hasattr(agent, "unfreeze_gat")):
                agent.unfreeze_gat()
                freeze_gat_episodes = 0   # chỉ unfreeze 1 lần
                print(f"[Learner] GAT unfrozen tại episode {logged_episodes}")

            # ── 4. GPU update (với throttle — tránh overfit data cũ) ──────────
            # Chỉ update khi drain thread đã push đủ transitions mới vào buffer
            cur_size = len(buffer)
            if cur_size - last_buf_size < MIN_NEW_TRANSITIONS:
                time.sleep(0.02)
                continue
            last_buf_size = cur_size

            batch   = buffer.sample(BATCH_SIZE)
            metrics = agent.update(batch)
            total_updates += 1
            current_loss   = metrics.get("loss", 0.0)

            # ── 5. Sync weights → workers ─────────────────────────────────
            if total_updates % SYNC_EVERY == 0 and hasattr(agent, "online_net"):
                sd = {k: v.cpu() for k, v in agent.online_net.state_dict().items()}
                for wq in weight_queues:
                    while True:
                        try: wq.get_nowait()
                        except Exception: break
                    try: wq.put_nowait(sd)
                    except Exception: pass

            # ── 6. Drain stats_queue → log CSV ────────────────────────────
            while True:
                try:
                    summary = stats_queue.get_nowait()
                except Exception:
                    break

                logged_episodes += 1
                ep_reward = summary["global_reward"]

                row = {
                    "episode":          logged_episodes,       # global episode count
                    "worker_id":        summary["worker_id"],
                    "total_steps":      summary["total_steps"],
                    "global_reward":    ep_reward,
                    "avg_speed":        summary["avg_speed"],
                    "avg_waiting_time": summary["avg_waiting_time"],
                    "throughput":       summary["throughput"],
                    "loss":             round(current_loss, 6),
                    "epsilon":          summary["epsilon"],
                    "duration_s":       summary["duration_s"],
                    "had_obstacle":     summary.get("had_obstacle", 0),
                    "obstacle_edges":   summary.get("obstacle_edges", ""),
                    "obstacle_count":   summary.get("obstacle_count", 0),
                }
                writer.writerow(row)
                f.flush()

                # In progress mỗi 10 episodes
                if logged_episodes % 10 == 0:
                    wall_s  = summary["duration_s"] / num_workers
                    eta_s   = (total_episodes - logged_episodes) * wall_s
                    eta_str = (
                        f"{int(eta_s//3600)}h {int((eta_s%3600)//60)}m"
                        if eta_s >= 3600
                        else f"{int(eta_s//60)}m {int(eta_s%60)}s"
                    )
                    q_size   = exp_queue.qsize()
                    acc_flag = (
                        f" | 🚧 OBS×{summary.get('obstacle_count',0)}"
                        f"({summary.get('obstacle_edges', '')})"
                        if summary.get("had_obstacle") else ""
                    )
                    print(
                        f"Ep {logged_episodes:4d}/{total_episodes} "
                        f"[W{summary['worker_id']}] | "
                        f"Reward: {ep_reward:8.2f} | "
                        f"Speed: {summary['avg_speed']:5.1f} km/h | "
                        f"Wait: {summary['avg_waiting_time']:5.1f}s | "
                        f"Loss: {current_loss:.5f} | "
                        f"ε: {summary['epsilon']:.3f} | "
                        f"Queue: {q_size:4d} | "
                        f"{wall_s:.1f}s/ep (wall) | "
                        f"ETA: {eta_str}"
                        f"{acc_flag}"
                    )

                # Best checkpoint
                if ep_reward > best_reward:
                    best_reward = ep_reward
                    agent.save(str(FINAL_DIR / f"{model_name}_{TOPOLOGY}_best.pt"))

            # ── 7. Periodic checkpoint theo updates ───────────────────────
            if total_updates % (SAVE_FREQ * steps_per_ep) == 0:
                ckpt = ckpt_dir / f"{model_name}_upd{total_updates}.pt"
                agent.save(str(ckpt))
                print(f"[Learner] Checkpoint → {ckpt.name}")

            # ── 8. Dừng khi đủ episodes ───────────────────────────────────
            if logged_episodes >= total_episodes:
                stop_event.set()
                break

    # Final save
    final = FINAL_DIR / f"{model_name}_{TOPOLOGY}_final.pt"
    agent.save(str(final))
    print(f"\n[Learner] Done — {total_updates} updates | {logged_episodes} episodes")
    print(f"[Learner] Final  → {final}")
    print(f"[Learner] Best   → {FINAL_DIR / f'{model_name}_{TOPOLOGY}_best.pt'}")
    print(f"[Learner] Log    → {log_path}")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _build_agent(model_name, device, epsilon, epsilon_min, epsilon_decay):
    if model_name == "gat_marl":
        from agents.gat_agent import GATAgent
        return GATAgent(
            state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
            num_heads=NUM_HEADS, num_actions=NUM_ACTIONS,
            lr=LR, gamma=GAMMA,
            epsilon=epsilon, epsilon_min=epsilon_min,
            epsilon_decay=epsilon_decay,
            target_update_freq=TARGET_UPDATE_FREQ,
            device=device,
        )
    elif model_name == "idqn":
        from agents.idqn_agent import IDQNAgent
        return IDQNAgent(
            state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
            num_actions=NUM_ACTIONS,
            lr=LR, gamma=GAMMA,
            epsilon=epsilon, epsilon_min=epsilon_min,
            epsilon_decay=epsilon_decay,
            target_update_freq=TARGET_UPDATE_FREQ,
            device=device,
        )
    raise ValueError(f"Không hỗ trợ: {model_name}")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def train_parallel(
    model_name:             str,
    num_workers:            int   = 2,
    episodes:               int   = NUM_EPISODES,
    delta_time:             int   = DELTA_TIME,
    resume:                 str | None = None,
    finetune:               str | None = None,
    freeze_gat_episodes:    int   = 20,
    obstacle_prob:          float = OBSTACLE_PROB,
    obstacle_max_count:     int   = OBSTACLE_MAX_COUNT,
    obstacle_duration_min:  int   = OBSTACLE_DURATION_MIN,
    obstacle_duration_max:  int | None = OBSTACLE_DURATION_MAX,
):
    mp.set_start_method("spawn", force=True)

    log_dir = LOG_DIR / model_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "training_log.csv"   # ← tên giống train.py → merge_logs hoạt động

    # ── Chọn file mode: "a" khi resume/finetune để không mất data cũ ─────────
    log_file_mode = "a" if (resume or finetune) else "w"

    mode = "FINETUNE" if finetune else "RESUME" if resume else "FRESH"
    total_eps = episodes * num_workers
    if total_eps > NUM_EPISODES * 1.5:
        print(f"     WARNING: tổng episodes = {total_eps} (= {episodes} × {num_workers} workers)")
        print(f"     Nếu muốn tương đương train.py ({NUM_EPISODES} ep), dùng --episodes {NUM_EPISODES // num_workers}")
    print(f"\n{'='*55}")
    print(f"  Parallel Training : {model_name.upper()}  [{mode}]")
    print(f"  Topology          : {TOPOLOGY}")
    print(f"  Workers           : {num_workers}  (ports {BASE_PORT}–{BASE_PORT+num_workers-1})")
    print(f"  Episodes/worker   : {episodes}  → tổng ~{episodes*num_workers}")
    print(f"  Delta T           : {delta_time}s/step")
    print(f"  GPU Learner       : {'CUDA' if torch.cuda.is_available() else 'CPU'}")
    print(f"  Log               : {log_path}  [mode={log_file_mode!r}]")
    if obstacle_prob > 0.0:
        print(f"  Obstacle prob     : {obstacle_prob:.0%}")
        print(f"  Obstacle max      : {obstacle_max_count}")
        print(f"  Obstacle dur      : {obstacle_duration_min}s – {'∞ (toàn ep)' if obstacle_duration_max is None else str(obstacle_duration_max)+'s'}")
    print(f"{'='*55}\n")

    exp_queue     = mp.Queue(maxsize=MAX_EXP_QUEUE)
    stats_queue   = mp.Queue(maxsize=episodes * num_workers + 100)
    weight_queues = [mp.Queue(maxsize=2) for _ in range(num_workers)]
    stop_event    = mp.Event()

    worker_procs = []
    for i in range(num_workers):
        p = mp.Process(
            target=rollout_worker,
            args=(
                i, model_name, exp_queue, stats_queue,
                weight_queues[i], stop_event, episodes, delta_time,
                obstacle_prob, obstacle_max_count,
                obstacle_duration_min, obstacle_duration_max,
            ),
            daemon=True,
            name=f"RolloutWorker-{i}",
        )
        p.start()
        worker_procs.append(p)
        time.sleep(2.0)   # stagger để tránh SUMO port race

    try:
        run_learner(
            model_name          = model_name,
            exp_queue           = exp_queue,
            stats_queue         = stats_queue,
            weight_queues       = weight_queues,
            stop_event          = stop_event,
            num_workers         = num_workers,
            episodes_per_worker = episodes,
            log_path            = log_path,
            resume              = resume,
            finetune            = finetune,
            freeze_gat_episodes = freeze_gat_episodes,
            log_file_mode       = log_file_mode,
        )
    except KeyboardInterrupt:
        print("\n[Main] Interrupted — stopping...")
    finally:
        stop_event.set()
        for p in worker_procs:
            p.join(timeout=15)
            if p.is_alive():
                p.terminate()
        print("[Main] All workers stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["gat_marl", "idqn"])
    parser.add_argument("--num-workers", type=int, default=2,
                        help="Số SUMO processes song song (recommend: 2 cho RTX 3050 Ti Laptop)")
    parser.add_argument("--episodes", type=int, default=NUM_EPISODES,
                        help="Số episodes mỗi worker chạy")
    parser.add_argument("--delta-time", type=int, default=DELTA_TIME)
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--finetune", type=str, default=None)
    parser.add_argument("--freeze-gat-episodes", type=int, default=20)
    # ── Obstacle args ─────────────────────────────────────────────────────────
    parser.add_argument(
        "--obstacle-prob", type=float, default=OBSTACLE_PROB,
        help=f"Xác suất có vật cản trong 1 episode (0.0–1.0). Default: {OBSTACLE_PROB}",
    )
    parser.add_argument(
        "--obstacle-max-count", type=int, default=OBSTACLE_MAX_COUNT,
        help=f"Tối đa bao nhiêu vật cản đồng thời. Default: {OBSTACLE_MAX_COUNT}",
    )
    parser.add_argument(
        "--obstacle-duration-min", type=int, default=OBSTACLE_DURATION_MIN,
        help=f"Thời gian tối thiểu mỗi vật cản (giây). Default: {OBSTACLE_DURATION_MIN}",
    )
    parser.add_argument(
        "--obstacle-duration-max", type=int, default=None,
        help="Thời gian tối đa mỗi vật cản (giây). None = xuyên suốt episode. Default: None",
    )
    # Backward compat: giữ accident args nhưng map sang obstacle
    parser.add_argument("--accident-prob", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--accident-duration", type=int, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Backward compat: --accident-prob maps sang --obstacle-prob
    obs_prob = args.obstacle_prob
    if args.accident_prob is not None:
        obs_prob = args.accident_prob
    obs_dur_min = args.obstacle_duration_min
    if args.accident_duration is not None:
        obs_dur_min = args.accident_duration

    train_parallel(
        model_name             = args.model,
        num_workers            = args.num_workers,
        episodes               = args.episodes,
        delta_time             = args.delta_time,
        resume                 = args.resume,
        finetune               = args.finetune,
        freeze_gat_episodes    = args.freeze_gat_episodes,
        obstacle_prob          = obs_prob,
        obstacle_max_count     = args.obstacle_max_count,
        obstacle_duration_min  = obs_dur_min,
        obstacle_duration_max  = args.obstacle_duration_max,
    )