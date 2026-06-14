"""
train.py — Main training loop (optimized)

Cải tiến so với v1:
- UPDATES_PER_STEP: update nhiều lần/step để GPU không idle khi SUMO chạy
- Prefetch buffer check tránh gọi is_ready() mỗi step
- ReplayBuffer pre-allocated nhanh hơn

Thêm (finetune accident):
- --accident-prob  : xác suất sinh tai nạn mỗi episode (default 0.0)
- --accident-duration: thời gian kéo dài sự cố tính bằng giây (default 300)
- Log ghi mode "a" (append) khi resume/finetune, "w" (overwrite) khi fresh train

Chạy:
    python -m training.train --model gat_marl
    python -m training.train --model idqn
    python -m training.train --model fixed_time

    # Finetune với tai nạn:
    python -m training.train --model gat_marl \
        --finetune checkpoints/final/gat_marl_mydinh_best.pt \
        --accident-prob 0.3 --accident-duration 300
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
    TOPOLOGY, DELTA_TIME,
)
from training.replay_buffer import ReplayBuffer
from environment.traffic_env import TrafficEnv
from environment.state_builder import build_node_features, INTERSECTION_IDS, INCOMING_EDGES

# ── Tuning knobs ──────────────────────────────────────────────────────────────
# Số lần update GPU mỗi simulation step.
# GPU RTX 3050 Ti nhỏ → 4-6 là sweet-spot; tăng nếu GPU vẫn idle
UPDATES_PER_STEP = 4

# ── Danh sách tất cả edge có thể xảy ra tai nạn ──────────────────────────────
# Flatten INCOMING_EDGES → list các edge_id duy nhất để random chọn
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


def _schedule_accident(
    accident_prob: float,
    accident_duration: int,
    delta_time: int,
) -> tuple[int | None, int | None, str | None]:
    """
    Quyết định có sinh tai nạn cho episode này không.

    Returns:
        (inject_step, clear_step, edge_id) nếu có tai nạn,
        (None, None, None) nếu không có.

    inject_step / clear_step tính theo đơn vị step (1 step = delta_time giây).
    """
    if not _ALL_ACCIDENT_EDGES or random.random() >= accident_prob:
        return None, None, None

    # Thời điểm bắt đầu: 60s → 600s kể từ đầu episode (tính ra step)
    start_step_min = max(1, 60 // delta_time)
    start_step_max = max(start_step_min + 1, 600 // delta_time)
    inject_step = random.randint(start_step_min, start_step_max)

    duration_steps = max(1, accident_duration // delta_time)
    clear_step = inject_step + duration_steps

    edge_id = random.choice(_ALL_ACCIDENT_EDGES)
    return inject_step, clear_step, edge_id


def train(
    model_name: str,
    device: str = "auto",
    resume: str | None = None,
    finetune: str | None = None,
    freeze_gat_epochs: int = 0,
    episodes: int | None = None,
    delta_time: int | None = None,
    updates_per_step: int = UPDATES_PER_STEP,
    accident_prob: float = 0.0,
    accident_duration: int = 300,
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
    if accident_prob > 0.0:
        print(f"  Accident prob    : {accident_prob:.0%}")
        print(f"  Accident duration: {accident_duration}s")
    if finetune:
        print(f"  Finetune: {finetune}")
        print(f"  Freeze GAT: {freeze_gat_epochs} episodes")
    print(f"{'='*50}\n")

    agent  = build_agent(model_name, device)
    buffer = ReplayBuffer(REPLAY_BUFFER_SIZE, state_dim=STATE_DIM, n_agents=len(INTERSECTION_IDS))
    port   = get_port(model_name)
    env    = TrafficEnv(port=port, topology=TOPOLOGY, use_gui=False, seed=SEED, delta_time=dt)

    # ── Per-model dirs ────────────────────────────────────────────────────────
    ckpt_dir = CHECKPOINT_DIR / model_name
    log_dir  = LOG_DIR / model_name
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "training_log.csv"
    fieldnames = [
        "episode", "total_steps", "global_reward",
        "avg_speed", "avg_waiting_time", "throughput",
        "loss", "epsilon", "duration_s",
        "had_accident", "accident_edge",          # ← cột mới để track sự cố
    ]

    # ── Load checkpoint ───────────────────────────────────────────────────────
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

    # ── Chọn file mode: "a" khi resume/finetune để không mất data cũ ─────────
    log_file_mode = "a" if (resume or finetune) else "w"

    with open(log_path, log_file_mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Chỉ ghi header khi tạo file mới
        if log_file_mode == "w":
            writer.writeheader()

        total_steps  = 0
        best_reward  = float("-inf")
        ready        = False  # cache buffer readiness — tránh check mỗi step

        for episode in range(start_episode, num_episodes):
            t_start = time.time()

            # Unfreeze GAT sau freeze_gat_epochs
            if (
                finetune
                and freeze_gat_epochs > 0
                and episode == freeze_gat_epochs
                and hasattr(agent, "unfreeze_gat")
            ):
                agent.unfreeze_gat()
                print(f"\n  ✓ GAT unfrozen at episode {episode}")

            obs = env.reset()

            # ── Lập lịch tai nạn cho episode này ─────────────────────────────
            inject_step, clear_step, acc_edge = _schedule_accident(
                accident_prob, accident_duration, dt
            )
            had_accident   = False
            accident_active = False

            if inject_step is not None:
                print(
                    f"  [Ep {episode}] Tai nạn → edge={acc_edge} "
                    f"@ step {inject_step} → clear @ step {clear_step}"
                )

            episode_reward  = 0.0
            episode_loss    = 0.0
            loss_count      = 0
            done            = False
            ep_step         = 0   # bước trong episode hiện tại

            if hasattr(agent, "reset"):
                agent.reset()

            while not done:
                # ── Inject tai nạn ────────────────────────────────────────────
                if inject_step is not None and ep_step == inject_step and not accident_active:
                    env.inject_accident(acc_edge)
                    accident_active = True
                    had_accident    = True

                # ── Clear tai nạn ─────────────────────────────────────────────
                if accident_active and ep_step == clear_step:
                    env.clear_accident(acc_edge)
                    accident_active = False

                actions = agent.select_actions(obs)
                next_obs, rewards, done, info = env.step(actions)

                if model_name != "fixed_time":
                    buffer.push(
                        states=obs["node_features"],
                        actions=actions,
                        rewards=rewards,
                        next_states=next_obs["node_features"],
                        done=done,
                    )

                    # Cache readiness — chỉ flip 1 lần, không check mỗi step
                    if not ready and buffer.is_ready(MIN_REPLAY_SIZE):
                        ready = True

                    if ready:
                        # Multiple gradient updates per sim step
                        # → GPU bận trong khi SUMO chạy step tiếp theo
                        for _ in range(updates_per_step):
                            batch   = buffer.sample(BATCH_SIZE)
                            metrics = agent.update(batch)
                            episode_loss += metrics.get("loss", 0.0)
                            loss_count   += 1

                episode_reward += info["global_reward"]
                obs = next_obs
                total_steps += 1
                ep_step     += 1

            # ── Đảm bảo clear tai nạn nếu episode kết thúc sớm ───────────────
            if accident_active:
                env.clear_accident(acc_edge)

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
                "had_accident":     int(had_accident),
                "accident_edge":    acc_edge or "",
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
                acc_flag = f" | 🚨 ACC({acc_edge})" if had_accident else ""
                print(
                    f"Ep {episode:4d}/{num_episodes} | "
                    f"Reward: {episode_reward:8.2f} | "
                    f"Speed: {info['avg_speed']:5.1f} km/h | "
                    f"Wait: {info['avg_waiting_time']:5.1f}s | "
                    f"Loss: {avg_loss:.5f} | "
                    f"ε: {epsilon:.3f} | "
                    f"{duration:.1f}s/ep | "
                    f"ETA: {eta_str}"
                    f"{acc_flag}"
                )

            # ── Periodic checkpoint ───────────────────────────────────────────
            if model_name != "fixed_time" and (episode + 1) % SAVE_FREQ == 0:
                ckpt_path = ckpt_dir / f"{model_name}_ep{episode+1}.pt"
                agent.save(str(ckpt_path))
                print(f"  ✓ Checkpoint: {ckpt_path.relative_to(ckpt_dir.parent.parent)}")

            # ── Best checkpoint → final/ ──────────────────────────────────────
            if model_name != "fixed_time" and episode_reward > best_reward:
                best_reward = episode_reward
                best_path   = FINAL_DIR / f"{model_name}_{TOPOLOGY}_best.pt"
                agent.save(str(best_path))

    # ── Final checkpoint ──────────────────────────────────────────────────────
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
    # ── Accident args ─────────────────────────────────────────────────────────
    parser.add_argument(
        "--accident-prob", type=float, default=0.0,
        help=(
            "Xác suất xảy ra tai nạn trong 1 episode (0.0–1.0). "
            "Mặc định 0.0 — không ảnh hưởng fresh train."
        ),
    )
    parser.add_argument(
        "--accident-duration", type=int, default=300,
        help="Thời gian kéo dài sự cố tính bằng giây (default: 300s)",
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
        accident_prob=args.accident_prob,
        accident_duration=args.accident_duration,
    )
