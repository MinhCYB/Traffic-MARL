#!/bin/bash
# scripts/run_training.sh
# Train cả 3 models tuần tự
# Dùng: bash scripts/run_training.sh
# Hoặc train từng model: bash scripts/run_training.sh gat_marl

set -e

PYTHON="python"
LOG_DIR="logs"

echo "================================================"
echo "  Smart Traffic MARL — Training"
echo "================================================"

train_model() {
    local model=$1
    echo ""
    echo ">>> Training: $model"
    echo "------------------------------------------------"
    $PYTHON training/train.py --model "$model" --device auto
    echo ">>> Done: $model"
}

# Nếu có argument thì train model đó thôi
if [ -n "$1" ]; then
    train_model "$1"
else
    train_model "fixed_time"
    train_model "gat_marl"
    # IDQN do đồng đội chạy
    # train_model "idqn"
fi

echo ""
echo "================================================"
echo "  Training hoàn tất. Logs: $LOG_DIR/"
echo "================================================"