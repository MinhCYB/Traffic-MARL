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

Chạy:
    python -m training.train_parallel --model gat_marl --num-workers 3
    python -m training.train_parallel --model gat_marl --num-workers 3 --resume checkpoints/final/gat_marl_mydinh_best.pt
"""

import argparse
import csv
import os
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
    TOPOLOGY, DELTA_TIME,
)
from training.replay_buffer import ReplayBuffer
from environment.state_builder import INTERSECTION_IDS

# ── Parallel-specific knobs ───────────────────────────────────────────────────
BASE_PORT          = 8820   # worker i dùng port BASE_PORT + i
SYNC_EVERY         = 200    # RTX 3050 Ti: 50 quá thường → interrupt GPU liên tục
                            # 200 = sync ~3 lần/episode, đủ fresh mà không overhead
MAX_EXP_QUEUE      = 12000  # tăng buffer để worker ít drop hơn khi GPU bận
WORKER_EPSILON_MIN = 0.10   # workers luôn explore tối thiểu 10%


# ══════════════════════════════════════════════════════════════════════════════
# Rollout Worker
# ══════════════════════════════════════════════════════════════════════════════

def rollout_worker(
    worker_id:    int,
    model_name:   str,
    exp_queue:    mp.Queue,   # push raw transitions
    stats_queue:  mp.Queue,   # push episode summary dict
    weight_queue: mp.Queue,   # nhận state_dict từ learner
    stop_event:   mp.Event,
    episodes:     int,
    delta_time:   int,
):
    """Chạy SUMO, collect experience, gửi episode stats về learner."""
    os.environ["CUDA_VISIBLE_DEVICES"] = ""   # worker chỉ dùng CPU

    from environment.traffic_env import TrafficEnv

    port   = BASE_PORT + worker_id
    seed   = SEED + worker_id
    # Epsilon staggered: đa dạng exploration giữa các workers
    eps    = max(WORKER_EPSILON_MIN, EPSILON_START - worker_id * 0.15)

    print(f"[Worker-{worker_id}] port={port} | ε_start={eps:.2f}")

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

        # Sync weights mới nhất từ learner trước mỗi episode
        _pull_weights(agent, weight_queue)

        while not done and not stop_event.is_set():
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
    ]

    total_updates  = 0
    best_reward    = float("-inf")
    ready          = False
    steps_per_ep   = 3600 // DELTA_TIME   # ~720

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

    with open(log_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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

            # ── 4. GPU update ─────────────────────────────────────────────
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
                    q_size = exp_queue.qsize()
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
    model_name:          str,
    num_workers:         int   = 2,   # RTX 3050 Ti Laptop: 2 là sweet-spot
    episodes:            int   = NUM_EPISODES,
    delta_time:          int   = DELTA_TIME,
    resume:              str | None = None,
    finetune:            str | None = None,
    freeze_gat_episodes: int   = 20,
):
    mp.set_start_method("spawn", force=True)

    log_dir = LOG_DIR / model_name
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "training_log.csv"   # ← tên giống train.py → merge_logs hoạt động

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
    print(f"  Log               : {log_path}")
    print(f"{'='*55}\n")

    exp_queue     = mp.Queue(maxsize=MAX_EXP_QUEUE)
    stats_queue   = mp.Queue(maxsize=episodes * num_workers + 100)
    weight_queues = [mp.Queue(maxsize=2) for _ in range(num_workers)]
    stop_event    = mp.Event()

    worker_procs = []
    for i in range(num_workers):
        p = mp.Process(
            target=rollout_worker,
            args=(i, model_name, exp_queue, stats_queue,
                  weight_queues[i], stop_event, episodes, delta_time),
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
    args = parser.parse_args()

    train_parallel(
        model_name          = args.model,
        num_workers         = args.num_workers,
        episodes            = args.episodes,
        delta_time          = args.delta_time,
        resume              = args.resume,
        finetune            = args.finetune,
        freeze_gat_episodes = args.freeze_gat_episodes,
    )