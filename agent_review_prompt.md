# Agent Task — Deep Code Review: Smart-Traffic-MARL

## Nhiệm vụ

Bạn là senior ML engineer. Đọc toàn bộ source code của project này và thực hiện **deep review toàn bộ luồng hoạt động + logic training**.

## Bước 1 — Đọc file theo thứ tự này

Đọc lần lượt, không bỏ file nào:

```
training/config.py
environment/maps/map_mydinh.py
environment/maps/__init__.py
environment/state_builder.py
environment/reward.py
environment/traffic_env.py
models/gat_marl.py
agents/gat_agent.py
agents/idqn_agent.py
training/replay_buffer.py
training/scheduler.py
training/train_parallel.py
training/train.py
server/schemas.py
server/main.py
workers/worker_base.py
```

## Bước 2 — Sau khi đọc xong, trả lời các câu hỏi sau

### A. Reward & Q-value

1. Với `REWARD_SCALE=5`, `GAMMA=0.95`, episode 360 steps — Q-value tối thiểu lý thuyết là bao nhiêu? Có nguy cơ explode hoặc collapse không?
2. Teleport penalty được tính là `(0.5 * count) / n_agents * REWARD_SCALE` rồi trừ vào reward. Công thức này có đúng unit không? Có thể làm reward âm vô hạn không?
3. `compute_global_reward(pressures)` trả về `-sum(pressures.values())` trong đó `pressures[nid] = -rewards[nid]`. Kết quả có thực sự là tổng hybrid reward không, hay vẫn là pure pressure?

### B. Training consistency

4. Worker tính `shared_r = mean(rewards.values())` rồi push vào buffer. Learner dùng `ep_reward = sum(rewards.values())` để chọn best checkpoint. 2 số này có cùng đơn vị không? Best model có thực sự là model tốt nhất không?
5. `done` signal trong MARL: khi episode kết thúc, tất cả 8 agents nhận cùng `done=True` và được broadcast `(B,) → (B, 8)`. Đây là centralized done hay per-agent done? Có ảnh hưởng đến Bellman target không?
6. GAT agent: `edge_index` được repeat B lần với offset `b * N`. Verify rằng `N = len(INTERSECTION_IDS)` đúng với số nodes thực tế của mydinh topology.

### C. Parallel training

7. `_transitions_pushed` counter trong `_drain_loop` dùng `nonlocal` + `threading.Lock`. Với Python GIL, `nonlocal int +=` có thực sự cần lock không? Lock có gây bottleneck không?
8. `lr_scheduler.step()` được gọi trong inner while loop drain stats — nếu GPU bị throttle và N episodes tích trong stats_queue, step() gọi N lần liên tiếp trong 1 vòng outer. LR sẽ nhảy thế nào?
9. Worker pull weights mỗi 80 sim steps. Learner sync weights mỗi 50 gradient updates. Với `UPDATE_TO_DATA_RATIO=8`, trong 80 steps có ~640 gradient updates → ~12 syncs. Worker near-greedy (ε=0.1) dùng policy 12 versions cũ — có ảnh hưởng đáng kể đến data quality không?

### D. Edge cases & bugs

10. `_schedule_obstacles` dùng `random.sample` (không duplicate edges), nhưng 2 obstacles khác edge có thể có `inject_step` trùng nhau. `env.inject_accident()` được gọi 2 lần trong cùng 1 step có vấn đề gì không?
11. Khi `--resume`, `log_file_mode="a"` và header không được ghi lại. Nếu CSV cũ thiếu column `learning_rate` (mới được thêm), các rows mới có bị misaligned column không?
12. `SAVE_FREQ * steps_per_ep = 50 * 360 = 18000`. Periodic checkpoint trigger `if total_updates % 18000 == 0`. Điều gì xảy ra tại `total_updates=0`?
13. `throughput` trong episode summary lấy từ `last_info.get("throughput", 0)` — là instantaneous throughput của bước cuối. Có misleading khi dùng để so sánh model performance không?
14. Finetune với `freeze_gat_episodes=20`: unfreeze xảy ra khi `logged_episodes >= 20` (global). Với 3 workers, đây là ~7 episodes thực tế mỗi worker. Q-head có đủ thời gian warm-up trước khi GAT được unfreeze không?

### E. Bất kỳ vấn đề nào khác

Sau khi đọc toàn bộ code, liệt kê bất kỳ vấn đề nào bạn phát hiện **ngoài danh sách trên**.

---

## Format kết quả

Với mỗi câu hỏi và vấn đề phát hiện thêm, phân loại:

- 🔴 **Critical** — Sai logic, training không học được, crash
- 🟡 **Medium** — Suboptimal, metric misleading, edge case quan trọng
- 🟢 **Minor** — Nhỏ, ít ảnh hưởng
- ✅ **OK** — Đúng, giải thích ngắn tại sao

Nêu rõ **file + dòng cụ thể**, **vấn đề**, và **hướng fix** nếu có.

---

## Context: những gì đã biết và đã fix (không cần report lại)

- `vehicles_teleported` thiếu trong schema/worker → đã fix
- `transitions_seen` dùng `len(buffer)` bị cap khi buffer đầy → đã fix bằng `_transitions_pushed` counter
- `ReplayBuffer` không có threading lock → đã fix
- `--obstacle-duration-max` argparse default=None override config → đã fix
- Worker pull weights mỗi 80 steps → đã fix (trước đó chỉ pull đầu episode)
- `WarmupScheduler` không được dùng trong train_parallel → đã fix
- Shared reward cho GAT trong train.py → đã fix
- Fixed-role epsilon workers → đã implement
- `EPSILON_DECAY` quá chậm → đã sửa thành 0.996
- `TARGET_UPDATE_FREQ` không tính `UPDATES_PER_STEP` → đã sửa thành 400
- `global_reward` log dùng pure pressure → đã fix
