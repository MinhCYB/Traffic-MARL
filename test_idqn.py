"""
test_idqn.py — Verify toàn bộ IDQN implementation không cần SUMO

Chạy:
    python test_idqn.py

Kỳ vọng: tất cả 6 test đều in ✅
"""

import sys
import traceback
import numpy as np
import torch

PASS = "✅"
FAIL = "❌"


def run_test(name, fn):
    try:
        fn()
        print(f"{PASS} {name}")
        return True
    except Exception as e:
        print(f"{FAIL} {name}")
        traceback.print_exc()
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: IDQNNet — shape check
# ─────────────────────────────────────────────────────────────────────────────
def test_idqnnet_shape():
    from models.idqn import IDQNNet
    net = IDQNNet()
    x   = torch.randn(4, 21)
    out = net(x)
    assert out.shape == (4, 2), f"Sai output shape: {out.shape}, kỳ vọng (4, 2)"
    # Test với batch size khác
    x2  = torch.randn(32 * 4, 21)
    out2 = net(x2)
    assert out2.shape == (128, 2), f"Sai batch shape: {out2.shape}"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: IDQNAgent init
# ─────────────────────────────────────────────────────────────────────────────
def test_agent_init():
    from agents.idqn_agent import IDQNAgent
    agent = IDQNAgent()
    assert hasattr(agent, "online_net")
    assert hasattr(agent, "target_net")
    assert hasattr(agent, "optimizer")
    assert agent.epsilon == 1.0
    assert agent._update_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: select_actions — output format
# ─────────────────────────────────────────────────────────────────────────────
def test_select_actions():
    from agents.idqn_agent import IDQNAgent
    agent = IDQNAgent(epsilon=0.0)  # greedy hoàn toàn
    obs   = {"node_features": np.random.randn(4, 21).astype("float32")}
    actions = agent.select_actions(obs)

    assert isinstance(actions, dict), "actions phải là dict"
    assert set(actions.keys()) == {"N01", "N02", "N03", "N04"}, \
        f"Sai keys: {actions.keys()}"
    assert all(v in [0, 1] for v in actions.values()), \
        f"Action phải là 0 hoặc 1, nhận được: {actions}"

    # Test với epsilon = 1.0 (random)
    agent2   = IDQNAgent(epsilon=1.0)
    actions2 = agent2.select_actions(obs)
    assert set(actions2.keys()) == {"N01", "N02", "N03", "N04"}


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: update — loss và epsilon
# ─────────────────────────────────────────────────────────────────────────────
def test_update():
    from agents.idqn_agent import IDQNAgent
    agent = IDQNAgent()

    # Tạo fake batch đúng format của ReplayBuffer.sample()
    B = 32
    batch = {
        "states":      np.random.randn(B, 4, 21).astype("float32"),
        "actions":     np.random.randint(0, 2, (B, 4)).astype(np.int64),
        "rewards":     np.random.randn(B, 4).astype("float32"),
        "next_states": np.random.randn(B, 4, 21).astype("float32"),
        "dones":       np.zeros(B, dtype="float32"),
        "edge_index":  np.zeros((2, 8), dtype=np.int64),  # có nhưng không dùng
    }

    epsilon_before = agent.epsilon
    metrics = agent.update(batch)

    assert "loss"    in metrics, "metrics phải có key 'loss'"
    assert "epsilon" in metrics, "metrics phải có key 'epsilon'"
    assert isinstance(metrics["loss"],    float), "loss phải là float"
    assert isinstance(metrics["epsilon"], float), "epsilon phải là float"
    assert metrics["loss"] >= 0, f"loss phải >= 0, nhận {metrics['loss']}"
    assert metrics["epsilon"] <= epsilon_before, "epsilon phải giảm sau update"
    assert agent._update_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: save / load
# ─────────────────────────────────────────────────────────────────────────────
def test_save_load():
    import tempfile, os
    from agents.idqn_agent import IDQNAgent

    agent = IDQNAgent(epsilon=0.5)
    # Update 1 lần để có state khác mặc định
    batch = {
        "states":      np.random.randn(8, 4, 21).astype("float32"),
        "actions":     np.random.randint(0, 2, (8, 4)).astype(np.int64),
        "rewards":     np.random.randn(8, 4).astype("float32"),
        "next_states": np.random.randn(8, 4, 21).astype("float32"),
        "dones":       np.zeros(8, dtype="float32"),
    }
    agent.update(batch)
    saved_epsilon = agent.epsilon
    saved_count   = agent._update_count

    with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
        path = f.name

    try:
        agent.save(path)

        agent2 = IDQNAgent()
        agent2.load(path)

        assert abs(agent2.epsilon - saved_epsilon) < 1e-6, \
            f"epsilon mismatch: {agent2.epsilon} vs {saved_epsilon}"
        assert agent2._update_count == saved_count, \
            f"update_count mismatch: {agent2._update_count} vs {saved_count}"

        # Verify weights giống nhau
        for p1, p2 in zip(agent.online_net.parameters(),
                           agent2.online_net.parameters()):
            assert torch.allclose(p1, p2), "Weights không khớp sau load"
    finally:
        os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Target network sync
# ─────────────────────────────────────────────────────────────────────────────
def test_target_sync():
    from agents.idqn_agent import IDQNAgent
    agent = IDQNAgent(target_update_freq=5)

    batch = {
        "states":      np.random.randn(8, 4, 21).astype("float32"),
        "actions":     np.random.randint(0, 2, (8, 4)).astype(np.int64),
        "rewards":     np.random.randn(8, 4).astype("float32"),
        "next_states": np.random.randn(8, 4, 21).astype("float32"),
        "dones":       np.zeros(8, dtype="float32"),
    }

    # Update 5 lần → target sync phải xảy ra ở update thứ 5
    for _ in range(5):
        agent.update(batch)

    assert agent._update_count == 5

    # Sau sync, target_net weights == online_net weights
    for p_online, p_target in zip(agent.online_net.parameters(),
                                   agent.target_net.parameters()):
        assert torch.allclose(p_online, p_target), \
            "Target net chưa được sync đúng sau target_update_freq bước"


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  IDQN Implementation Test Suite")
    print("=" * 55)

    tests = [
        ("IDQNNet — output shape",         test_idqnnet_shape),
        ("IDQNAgent — __init__",           test_agent_init),
        ("IDQNAgent — select_actions",     test_select_actions),
        ("IDQNAgent — update (loss/eps)",  test_update),
        ("IDQNAgent — save / load",        test_save_load),
        ("IDQNAgent — target net sync",    test_target_sync),
    ]

    results = [run_test(name, fn) for name, fn in tests]

    print("=" * 55)
    passed = sum(results)
    total  = len(results)
    status = "🎉 TẤT CẢ PASS" if passed == total else f"⚠️  {passed}/{total} pass"
    print(f"  Kết quả: {status}")
    print("=" * 55)

    sys.exit(0 if passed == total else 1)