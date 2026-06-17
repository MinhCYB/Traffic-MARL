"""
train.py — Main training loop (optimized & synchronized with train_parallel.py)

Cải tiến:
- UPDATES_PER_STEP: update nhiều lần/step để GPU không idle khi SUMO chạy
- Đã đồng bộ logic tính throughput, reward và log CSV với train_parallel.py
- Sử dụng hệ thống obstacle (vật cản) thay thế cho accident cũ.

Chạy:
    python -m training.train --model gat_marl
    python -m training.train --model idqn
    python -m training.train --model fixed_time

    # Finetune với vật cản:
    python -m training.train --model gat_marl \
        --finetune checkpoints/final/gat_marl_mydinh_best.pt \
        --obstacle-prob 0.3 --obstacle-max-count 2
"""

import argparse
import csv
import random
import time
from pathlib import Path

import numpy as np

from training.config import (
    NUM_EPISODES, BATCH_SIZE, REPLAY_BUFFER_SIZE, MIN_REPLAY_SIZE,
    SAVE_FREQ, SEED, PORT_GAT, PORT_IDQN, PORT_FIXED,
    CHECKPOINT_DIR, FINAL_DIR, LOG_DIR,
    EPSILON_START, EPSILON_MIN, EPSILON_DECAY,
    LR, GAMMA, TARGET_UPDATE_FREQ,
    STATE_DIM, HIDDEN_DIM, NUM_HEADS, NUM_ACTIONS, DROPOUT,
    TOPOLOGY, DELTA_TIME, SIM_END,
    OBSTACLE_PROB, OBSTACLE_MAX_COUNT,
    OBSTACLE_DURATION_MIN, OBSTACLE_DURATION_MAX,
)
from training.replay_buffer import ReplayBuffer
from environment.traffic_env import TrafficEnv
from environment.state_builder import build_node_features, INTERSECTION_IDS, INCOMING_EDGES

# ── Tuning knobs ──────────────────────────────────────────────────────────────
UPDATES_PER_STEP = 4

# ── Danh sách tất cả edge có thể xảy ra tai nạn/vật cản ──────────────────────
_ALL_ACCIDENT_EDGES: list[str] = list(
    {edge for edges in INCOMING_EDGES.values() for edge in edges}
)


def build_agent(model_name: str, device: str = "auto"):
    if model_name == "gat_marl":
        from agents.gat_agent import GATAgent
        return GATAgent(
            state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
            num_heads=NUM_HEADS, num_actions=NUM_ACTIONS,
            lr=LR, gamma=GAMMA,
            epsilon=EPSILON_START, epsilon_min=EPSILON_MIN,
            epsilon_decay=EPSILON_DECAY,
            target_update_freq=TARGET_UPDATE_FREQ,
            device=device,
        )
    elif model_name == "idqn":
        from agents.idqn_agent import IDQNAgent
        return IDQNAgent(
            state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
            num_actions=NUM_ACTIONS,
            lr=LR, gamma=GAMMA,
            epsilon=EPSILON_START, epsilon_min=EPSILON_MIN,
            epsilon_decay=EPSILON_DECAY,
            target_update_freq=TARGET_UPDATE_FREQ,
            device=device,
        )
    elif model_name == "fixed_time":
        from agents.fixed_agent import FixedAgent
        return FixedAgent()
    else:
        raise ValueError(f"Unknown model: {model_name}")


def get_port(model_name: str) -> int:
    return {
        "gat_marl":   PORT_GAT,
        "idqn":       PORT_IDQN,
        "fixed_time": PORT_FIXED,
    }[model_name]


def _schedule_obstacles(
    obstacle_prob: float,
    max_count:     int,
    duration_min:  int,
    duration_max:  int | None,
    sim_end:       int,
    delta_time:    int,
) -> list[tuple[int, int, str]]:
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
            clear_step = sim_end // delta_time + 1
        else:
            dur = random.randint(duration_min, duration_max)
            clear_step = inject_step + max(1, dur // delta_time)
        obstacles.append((inject_step, clear_step, edge))

    return obstacles


def train(
    model_name: str,
    device: str = "auto",
    resume: str | None = None,
    finetune: str | None = None,
    freeze_gat_epochs: int = 0,
    episodes: int | None = None,
    delta_time: int | None = None,
    updates_per_step: int = UPDATES_PER_STEP,
    obstacle_prob: float = 0.0,
    obstacle_max_count: int = 3,
    obstacle_duration_min: int = 300,
    obstacle_duration_max: int | None = None,
):

    num_episodes = episodes or NUM_EPISODES
    dt           = delta_time or DELTA_TIME

    import torch
    actual_device = "cuda" if (device == "auto" and torch.cuda.is_available()) else device
    device_name   = torch.cuda.get_device_name(0) if actual_device == "cuda" else "CPU"

    mode = "FINETUNE" if finetune else "RESUME" if resume else "FRESH"
    print(f"\n{'='*50}")
    print(f"  Training: {model_name.upper()}  [{mode}]")
    print(f"  Topology: {TOPOLOGY}")
    print(f"  Device  : {actual_device.upper()} ({device_name})")
    print(f"  Episodes: {num_episodes}")
    print(f"  Delta T : {dt}s/step")
    print(f"  Updates/step: {updates_per_step}")
    if obstacle_prob > 0.0:
        print(f"  Obstacle prob    : {obstacle_prob:.0%}")
        print(f"  Obstacle max     : {obstacle_max_count}")
        print(f"  Obstacle dur     : {obstacle_duration_min}s – {'∞' if obstacle_duration_max is None else str(obstacle_duration_max)+'s'}")
    if finetune:
        print(f"  Finetune: {finetune}")
        print(f"  Freeze GAT: {freeze_gat_epochs} episodes")
    print(f"{'='*50}\n")

    agent  = build_agent(model_name, device)
    buffer = ReplayBuffer(REPLAY_BUFFER_SIZE, state_dim=STATE_DIM, n_agents=len(INTERSECTION_IDS))
    port   = get_port(model_name)
    env    = TrafficEnv(port=port, topology=TOPOLOGY, use_gui=False, seed=SEED, delta_time=dt)

    ckpt_dir = CHECKPOINT_DIR / model_name
    log_dir  = LOG_DIR / model_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # fresh train : training_log.csv mode="w"
    # resume      : training_log.csv mode="a"
    # finetune    : finetune_log.csv  mode="w"
    if finetune:
        log_path      = log_dir / "finetune_log.csv"
    else:
        log_path      = log_dir / "training_log.csv"

    # ── ĐỒNG BỘ HEADER VỚI TRAIN_PARALLEL ──
    fieldnames = [
        "episode", "worker_id", "total_steps", "global_reward",
        "avg_speed", "avg_waiting_time", "throughput",
        "loss", "epsilon", "duration_s",
        "had_obstacle", "obstacle_edges", "obstacle_count",
        "vehicles_teleported", "learning_rate"
    ]

    start_episode = 0

    if finetune:
        agent.load(finetune)
        print(f"  ✓ Loaded weights from: {finetune}")
        if freeze_gat_epochs > 0 and hasattr(agent, "freeze_gat"):
            agent.freeze_gat()
            print(f"  ✓ GAT frozen for first {freeze_gat_epochs} episodes")

    elif resume:
        agent.load(resume)
        print(f"  ✓ Resumed from: {resume}")
        try:
            start_episode = int(Path(resume).stem.split("ep")[-1])
        except Exception:
            pass

    log_file_mode = "a" if resume else "w"

    with open(log_path, log_file_mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if log_file_mode == "w" or f.tell() == 0:
            if finetune:
                f.write(f"# finetune_from: {finetune}\n".encode())
                f.write(f"# topology: {TOPOLOGY}\n".encode())
            writer.writeheader()

        total_steps  = 0
        best_reward  = float("-inf")
        ready        = False

        for episode in range(start_episode, num_episodes):
            t_start = time.time()

            if (
                finetune
                and freeze_gat_epochs > 0
                and episode == freeze_gat_epochs
                and hasattr(agent, "unfreeze_gat")
            ):
                agent.unfreeze_gat()
                print(f"\n  ✓ GAT unfrozen at episode {episode}")

            obs = env.reset()

            # ── Lập lịch vật cản (ĐỒNG BỘ) ──
            obstacles = _schedule_obstacles(
                obstacle_prob, obstacle_max_count,
                obstacle_duration_min, obstacle_duration_max,
                SIM_END, dt
            )
            active_obstacles = set()

            if obstacles:
                edges_str = ", ".join(e for _, _, e in obstacles)
                print(f"  [Ep {episode}] Vật cản ({len(obstacles)}) → edges: {edges_str}")

            episode_reward  = 0.0
            episode_loss    = 0.0
            ep_throughput   = 0     # THÊM MỚI: Cộng dồn xe qua nút
            loss_count      = 0
            done            = False
            ep_step         = 0
            last_info       = {}

            if hasattr(agent, "reset"):
                agent.reset()

            while not done:
                # ── Inject/Clear vật cản ──
                for (inj, clr, edge) in obstacles:
                    if ep_step == inj and edge not in active_obstacles:
                        env.inject_accident(edge)
                        active_obstacles.add(edge)
                    if ep_step == clr and edge in active_obstacles:
                        env.clear_accident(edge)
                        active_obstacles.discard(edge)

                actions = agent.select_actions(obs)
                next_obs, rewards, done, info = env.step(actions)

                if model_name == "gat_marl":
                    shared_r = sum(rewards.values()) / len(rewards)
                    rewards  = {nid: shared_r for nid in rewards}

                if model_name != "fixed_time":
                    buffer.push(
                        states=obs["node_features"],
                        actions=actions,
                        rewards=rewards,
                        next_states=next_obs["node_features"],
                        done=done,
                    )

                    if not ready and buffer.is_ready(MIN_REPLAY_SIZE):
                        ready = True

                    if ready:
                        for _ in range(updates_per_step):
                            batch   = buffer.sample(BATCH_SIZE)
                            metrics = agent.update(batch)
                            episode_loss += metrics.get("loss", 0.0)
                            loss_count   += 1

                # ── Sửa lỗi cộng dồn reward & throughput ──
                episode_reward += sum(rewards.values())
                ep_throughput  += info.get("throughput", 0)
                
                obs = next_obs
                last_info = info
                total_steps += 1
                ep_step     += 1

            # ── Cleanup vật cản ──
            for edge in list(active_obstacles):
                try:
                    env.clear_accident(edge)
                except Exception:
                    pass
            active_obstacles.clear()

            # ── End of episode ──
            duration = time.time() - t_start
            avg_loss = episode_loss / loss_count if loss_count > 0 else 0.0
            epsilon  = getattr(agent, "epsilon", 0.0)
            
            # Khớp learning_rate logic
            current_lr = 0.0
            if model_name != "fixed_time" and hasattr(agent, "optimizer"):
                current_lr = agent.optimizer.param_groups[0]["lr"]

            log_row = {
                "episode":          episode,
                "worker_id":        0,  # single worker
                "total_steps":      total_steps,
                "global_reward":    round(episode_reward, 4),
                "avg_speed":        round(last_info.get("avg_speed", 0.0), 2),
                "avg_waiting_time": round(last_info.get("avg_waiting_time", 0.0), 2),
                "throughput":       ep_throughput,  # Đã sửa lỗi 7.44!
                "loss":             round(avg_loss, 6),
                "epsilon":          round(epsilon, 4),
                "duration_s":       round(duration, 1),
                "had_obstacle":     int(len(obstacles) > 0),
                "obstacle_edges":   ",".join(e for _, _, e in obstacles) if obstacles else "",
                "obstacle_count":   len(obstacles),
                "vehicles_teleported": last_info.get("vehicles_teleported", 0),
                "learning_rate":    round(current_lr, 7),
            }
            writer.writerow(log_row)
            f.flush()

            if episode % 10 == 0:
                eps_left = num_episodes - episode - 1
                eta_s    = eps_left * duration
                eta_str  = (
                    f"{int(eta_s // 3600)}h {int((eta_s % 3600) // 60)}m"
                    if eta_s >= 3600
                    else f"{int(eta_s // 60)}m {int(eta_s % 60)}s"
                )
                acc_flag = f" | 🚧 OBS×{len(obstacles)}({log_row['obstacle_edges']})" if obstacles else ""
                print(
                    f"Ep {episode:4d}/{num_episodes} | "
                    f"Reward: {episode_reward:8.2f} | "
                    f"Speed: {last_info.get('avg_speed', 0):5.1f} km/h | "
                    f"Wait: {last_info.get('avg_waiting_time', 0):5.1f}s | "
                    f"Throughput: {ep_throughput} | "
                    f"Loss: {avg_loss:.5f} | "
                    f"ε: {epsilon:.3f} | "
                    f"{duration:.1f}s/ep | "
                    f"ETA: {eta_str}"
                    f"{acc_flag}"
                )

            if model_name != "fixed_time" and (episode + 1) % SAVE_FREQ == 0:
                ckpt_path = ckpt_dir / f"{model_name}_ep{episode+1}.pt"
                agent.save(str(ckpt_path))
                print(f"  ✓ Checkpoint: {ckpt_path.relative_to(ckpt_dir.parent.parent)}")

            if model_name != "fixed_time" and episode_reward > best_reward:
                best_reward = episode_reward
                best_path   = FINAL_DIR / f"{model_name}_{TOPOLOGY}_best.pt"
                agent.save(str(best_path))

    if model_name != "fixed_time":
        final_path = FINAL_DIR / f"{model_name}_{TOPOLOGY}_final.pt"
        agent.save(str(final_path))
        print(f"\n✓ Final  → {final_path}")
        print(f"✓ Best   → {FINAL_DIR / f'{model_name}_{TOPOLOGY}_best.pt'}")

    env.close()
    print(f"✓ Log    → {log_path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", type=str, required=True,
        choices=["gat_marl", "idqn", "fixed_time"],
        help="Model để train",
    )
    parser.add_argument(
        "--device", type=str, default="auto",
        choices=["auto", "cpu", "cuda"],
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Path checkpoint để resume training cùng map",
    )
    parser.add_argument(
        "--finetune", type=str, default=None,
        help="Path checkpoint để finetune sang map mới (warm-start)",
    )
    parser.add_argument(
        "--freeze-gat-epochs", type=int, default=20,
        help="Số episode freeze GAT layer khi finetune (default: 20)",
    )
    parser.add_argument(
        "--episodes", type=int, default=None,
        help="Override NUM_EPISODES trong config",
    )
    parser.add_argument(
        "--delta-time", type=int, default=None,
        help="Override DELTA_TIME trong config",
    )
    parser.add_argument(
        "--updates-per-step", type=int, default=UPDATES_PER_STEP,
        help=f"Số lần update GPU mỗi sim step (default: {UPDATES_PER_STEP})",
    )
    
    # ── ĐỒNG BỘ ARGPARSE VỚI TRAIN_PARALLEL ──
    parser.add_argument(
        "--obstacle-prob", type=float, default=0.0,
        help="Xác suất có vật cản trong 1 episode (0.0–1.0). Default: 0.0",
    )
    parser.add_argument(
        "--obstacle-max-count", type=int, default=3,
        help="Tối đa bao nhiêu vật cản đồng thời. Default: 3",
    )
    parser.add_argument(
        "--obstacle-duration-min", type=int, default=300,
        help="Thời gian tối thiểu mỗi vật cản (giây). Default: 300",
    )
    parser.add_argument(
        "--obstacle-duration-max", type=int, default=None,
        help="Thời gian tối đa mỗi vật cản (giây). None = xuyên suốt. Default: None",
    )

    args = parser.parse_args()
    
    train(
        args.model, args.device,
        resume=args.resume,
        finetune=args.finetune,
        freeze_gat_epochs=args.freeze_gat_epochs,
        episodes=args.episodes,
        delta_time=args.delta_time,
        updates_per_step=args.updates_per_step,
        obstacle_prob=args.obstacle_prob,
        obstacle_max_count=args.obstacle_max_count,
        obstacle_duration_min=args.obstacle_duration_min,
        obstacle_duration_max=args.obstacle_duration_max,
    )