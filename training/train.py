"""
train.py — Main training loop

Chạy:
    python training/train.py --model gat_marl
    python training/train.py --model idqn
    python training/train.py --model fixed_time

Log CSV mỗi episode → logs/<model>/episode_*.csv
Checkpoint mỗi SAVE_FREQ episodes → checkpoints/<model>_ep<N>.pt
"""

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from training.config import (
    NUM_EPISODES, BATCH_SIZE, REPLAY_BUFFER_SIZE, MIN_REPLAY_SIZE,
    SAVE_FREQ, SEED, PORT_GAT, PORT_IDQN, PORT_FIXED,
    CHECKPOINT_DIR, LOG_DIR,
    EPSILON_START, EPSILON_MIN, EPSILON_DECAY,
    LR, GAMMA, TARGET_UPDATE_FREQ,
    STATE_DIM, HIDDEN_DIM, NUM_HEADS, NUM_ACTIONS, DROPOUT,
    TOPOLOGY, DELTA_TIME,
)
from training.replay_buffer import ReplayBuffer
from environment.traffic_env import TrafficEnv
from environment.state_builder import build_node_features


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


def setup_logger(model_name: str) -> tuple[Path, list[str]]:
    log_dir = LOG_DIR / model_name
    log_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "episode", "total_steps", "global_reward",
        "avg_speed", "avg_waiting_time", "throughput",
        "loss", "epsilon", "duration_s",
    ]
    return log_dir, fieldnames


def train(model_name: str, device: str = "auto", resume: str | None = None,
          episodes: int | None = None, delta_time: int | None = None):

    num_episodes = episodes or NUM_EPISODES
    dt           = delta_time or DELTA_TIME

    import torch
    actual_device = "cuda" if (device == "auto" and torch.cuda.is_available()) else device
    device_name   = torch.cuda.get_device_name(0) if actual_device == "cuda" else "CPU"

    print(f"\n{'='*50}")
    print(f"  Training: {model_name.upper()}")
    print(f"  Device  : {actual_device.upper()} ({device_name})")
    print(f"  Episodes: {num_episodes}")
    print(f"  Delta T : {dt}s/step")
    print(f"{'='*50}\n")

    agent  = build_agent(model_name, device)
    buffer = ReplayBuffer(REPLAY_BUFFER_SIZE)
    port   = get_port(model_name)
    env    = TrafficEnv(port=port, topology=TOPOLOGY, use_gui=False, seed=SEED, delta_time=dt)

    log_dir, fieldnames = setup_logger(model_name)
    log_path = log_dir / "training_log.csv"

    # Resume từ checkpoint
    start_episode = 0
    if resume:
        agent.load(resume)
        print(f"Resumed from {resume}")
        # Parse episode number từ filename nếu có
        try:
            start_episode = int(Path(resume).stem.split("ep")[-1])
        except Exception:
            pass

    with open(log_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        total_steps = 0

        for episode in range(start_episode, num_episodes):
            t_start = time.time()
            obs = env.reset()

            episode_reward  = 0.0
            episode_loss    = 0.0
            loss_count      = 0
            done            = False

            if hasattr(agent, "reset"):
                agent.reset()

            while not done:
                # Select actions
                actions = agent.select_actions(obs)

                # Step environment
                next_obs, rewards, done, info = env.step(actions)

                # Push vào replay buffer (bỏ qua fixed_time)
                if model_name != "fixed_time":
                    buffer.push(
                        states=obs["node_features"],
                        actions=actions,
                        rewards=rewards,
                        next_states=next_obs["node_features"],
                        done=done,
                    )

                # Update agent
                if (
                    model_name != "fixed_time"
                    and buffer.is_ready(MIN_REPLAY_SIZE)
                    and total_steps % 1 == 0
                ):
                    batch   = buffer.sample(BATCH_SIZE)
                    metrics = agent.update(batch)
                    episode_loss += metrics.get("loss", 0.0)
                    loss_count   += 1

                episode_reward += info["global_reward"]
                obs = next_obs
                total_steps += 1

            # ── End of episode ────────────────────────────────────────────────
            duration = time.time() - t_start
            avg_loss = episode_loss / loss_count if loss_count > 0 else 0.0
            epsilon  = getattr(agent, "epsilon", 0.0)

            log_row = {
                "episode":          episode,
                "total_steps":      total_steps,
                "global_reward":    round(episode_reward, 4),
                "avg_speed":        round(info["avg_speed"], 2),
                "avg_waiting_time": round(info["avg_waiting_time"], 2),
                "throughput":       info["throughput"],
                "loss":             round(avg_loss, 6),
                "epsilon":          round(epsilon, 4),
                "duration_s":       round(duration, 1),
            }
            writer.writerow(log_row)
            f.flush()

            # Console log mỗi 10 episode
            if episode % 10 == 0:
                eps_left     = num_episodes - episode - 1
                eta_s        = eps_left * duration
                eta_str      = (
                    f"{int(eta_s // 3600)}h {int((eta_s % 3600) // 60)}m"
                    if eta_s >= 3600
                    else f"{int(eta_s // 60)}m {int(eta_s % 60)}s"
                )
                print(
                    f"Ep {episode:4d}/{num_episodes} | "
                    f"Reward: {episode_reward:8.2f} | "
                    f"Speed: {info['avg_speed']:5.1f} km/h | "
                    f"Wait: {info['avg_waiting_time']:5.1f}s | "
                    f"Loss: {avg_loss:.5f} | "
                    f"ε: {epsilon:.3f} | "
                    f"{duration:.1f}s/ep | "
                    f"ETA: {eta_str}"
                )

            # Checkpoint
            if (
                model_name != "fixed_time"
                and (episode + 1) % SAVE_FREQ == 0
            ):
                ckpt_path = CHECKPOINT_DIR / f"{model_name}_ep{episode+1}.pt"
                agent.save(str(ckpt_path))
                print(f"  ✓ Checkpoint saved: {ckpt_path}")

    # Final checkpoint
    if model_name != "fixed_time":
        final_path = CHECKPOINT_DIR / f"{model_name}_final.pt"
        agent.save(str(final_path))
        print(f"\n✓ Final checkpoint: {final_path}")

    env.close()
    print(f"\n✓ Training done. Log: {log_path}")


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
        help="Path tới checkpoint để resume training",
    )
    parser.add_argument(
        "--episodes", type=int, default=None,
        help="Override NUM_EPISODES trong config (vd: 100 cho fixed_time)",
    )
    parser.add_argument(
        "--delta-time", type=int, default=None,
        help="Override DELTA_TIME trong config (vd: 10 để train nhanh hơn)",
    )
    args = parser.parse_args()
    train(args.model, args.device, args.resume, args.episodes, args.delta_time)