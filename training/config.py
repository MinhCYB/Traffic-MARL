"""
config.py — Tất cả hyperparameters tập trung 1 chỗ

Import từ đây thay vì hardcode rải rác trong code.
Thay đổi ở đây = thay đổi toàn bộ hệ thống.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR        = Path(__file__).parent.parent

# ── Simulation ────────────────────────────────────────────────────────────────
TOPOLOGY            = "uet"  # "2x2" | "mydinh" | "uet" — đổi ở đây khi scale
DELTA_TIME          = 5         # giây — agent quyết định mỗi 5s
MIN_GREEN_TIME      = 20        # giây — enforce ở env wrapper
YELLOW_TIME         = 3         # giây
SIM_END             = 1800      # giây — 1 episode = 30 phút (đổi từ 3600)

# ── Obstacle (vật cản: công trình, xe hỏng, sửa đường...) ────────────────────
OBSTACLE_PROB         = 0.4    # xác suất có vật cản trong episode
OBSTACLE_MAX_COUNT    = 3      # tối đa 3 vật cản đồng thời
OBSTACLE_DURATION_MIN = 300    # giây — tối thiểu
OBSTACLE_DURATION_MAX = 600   # None = xuyên suốt episode
SEED                = 42

# ── Checkpoint & log dirs ─────────────────────────────────────────────────────
# Structure:
#   checkpoints/<topology>/<model>/   ← periodic saves (gitignore nếu nặng)
#   checkpoints/final/                ← best/final weights — push lên git
#   logs/<topology>/<model>/          ← training CSV logs
CHECKPOINT_DIR  = ROOT_DIR / "checkpoints" / TOPOLOGY
FINAL_DIR       = ROOT_DIR / "checkpoints" / "final"
LOG_DIR         = ROOT_DIR / "logs" / TOPOLOGY

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
FINAL_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Model ─────────────────────────────────────────────────────────────────────
from environment.state_builder import STATE_DIM  # tự tính theo map
HIDDEN_DIM          = 64
NUM_HEADS           = 4
NUM_ACTIONS         = 2
DROPOUT             = 0.1

# ── Training ──────────────────────────────────────────────────────────────────
NUM_EPISODES        = 500
BATCH_SIZE          = 64       # tăng từ 32 → gradient ổn hơn với GAT 4 nodes
REPLAY_BUFFER_SIZE  = 50_000
MIN_REPLAY_SIZE     = 1_000   # bắt đầu update sau khi có đủ experience
TARGET_UPDATE_FREQ  = 400      # gradient updates → 400/4 = 100 sim steps thực tế
SAVE_FREQ           = 50      # episodes

# ── Optimizer ─────────────────────────────────────────────────────────────────
LR                  = 1e-4     # giảm từ 3e-4 → ổn định hơn với Q scale lớn
GAMMA               = 0.95     # giảm từ 0.99 → Q range [-200, 0] thay vì [-1000, 0]
GRAD_CLIP           = 10.0

# ── Epsilon-greedy ────────────────────────────────────────────────────────────
EPSILON_START       = 1.0
EPSILON_MIN         = 0.05
EPSILON_DECAY       = 0.996   # train.py solo only — parallel dùng fixed-role epsilon

# ── TraCI ports (1 port per process) ──────────────────────────────────────────
PORT_GAT            = 8813
PORT_IDQN           = 8814
PORT_FIXED          = 8815

# ── Server ────────────────────────────────────────────────────────────────────
SERVER_HOST         = "localhost"
SERVER_PORT         = 8000
SYNC_TIMEOUT        = 2.0     # giây — solo mode fallback