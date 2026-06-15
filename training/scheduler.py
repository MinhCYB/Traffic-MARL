"""
scheduler.py — Epsilon decay và learning rate schedule

Tách riêng để dễ tune mà không đụng vào agent code.
"""


class EpsilonScheduler:
    """
    Exponential epsilon decay theo episode.

        epsilon = max(epsilon_min, epsilon * decay^episode)
    """

    def __init__(
        self,
        epsilon_start: float = 1.0,
        epsilon_min:   float = 0.05,
        decay:         float = 0.995,
    ):
        self.epsilon     = epsilon_start
        self.epsilon_min = epsilon_min
        self.decay       = decay

    def step(self):
        """Gọi cuối mỗi episode."""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.decay)

    def get(self) -> float:
        return self.epsilon

    def reset(self):
        """Dùng khi fine-tune từ checkpoint — giữ epsilon thấp."""
        self.epsilon = self.epsilon_min


class WarmupScheduler:
    """
    Linear warmup + cosine decay cho learning rate.
    Dùng với torch.optim.lr_scheduler nếu cần.

    Đơn giản hơn: dùng Adam với lr cố định đã đủ cho project này.
    Class này để dành nếu muốn experiment sau.
    """

    def __init__(self, optimizer, warmup_episodes: int = 50, total_episodes: int = 500,
                 lr_min: float = 1e-6):
        self.optimizer        = optimizer
        self.warmup_episodes  = warmup_episodes
        self.total_episodes   = total_episodes
        self._episode         = 0
        self._base_lr         = optimizer.param_groups[0]["lr"]
        self._lr_min          = lr_min

    def step(self):
        self._episode += 1
        if self._episode <= self.warmup_episodes:
            lr = self._base_lr * (self._episode / self.warmup_episodes)
        else:
            import math
            progress = (self._episode - self.warmup_episodes) / (
                self.total_episodes - self.warmup_episodes
            )
            lr = self._base_lr * 0.5 * (1 + math.cos(math.pi * progress))

        for pg in self.optimizer.param_groups:
            pg["lr"] = max(lr, self._lr_min)

    def get_lr(self) -> float:
        return self.optimizer.param_groups[0]["lr"]