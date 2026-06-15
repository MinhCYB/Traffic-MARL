"""
sync_buffer.py — Đồng bộ data từ 3 workers trước khi broadcast

Normal mode: chờ đủ các workers đang active → merge → broadcast
Solo mode:   sau SYNC_TIMEOUT giây → broadcast với data đang có
             Worker chưa gửi → trả về status "reconnecting"
"""

import asyncio
import time
from training.config import SYNC_TIMEOUT

WORKER_MODES = ["gat_marl", "idqn", "fixed_time"]

# Worker được coi là "active" nếu có data trong vòng ACTIVE_TTL giây
ACTIVE_TTL = 10.0


class SyncBuffer:
    """Thread-safe buffer đồng bộ data từ 3 workers."""

    def __init__(self, timeout: float = SYNC_TIMEOUT):
        self.timeout   = timeout
        self._data:    dict[str, dict]  = {}
        self._lock     = asyncio.Lock()
        self._event    = asyncio.Event()
        # Lưu timestamp lần cuối nhận data từ mỗi worker
        self._last_seen: dict[str, float] = {}

    async def push(self, mode: str, payload: dict):
        """Worker gửi data lên — ghi vào buffer và notify."""
        async with self._lock:
            self._data[mode]      = payload
            self._last_seen[mode] = time.time()
            if self._all_active_ready():
                self._event.set()

    async def wait_and_get(self) -> dict:
        """
        Chờ đủ các workers đang active hoặc timeout.

        Returns:
            merged: {mode: payload} — có thể thiếu mode nếu worker chưa connect
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            pass  # solo mode — trả về data đang có

        async with self._lock:
            result = dict(self._data)
            # Reset data cho round tiếp theo, GIỮ LẠI _last_seen để track active
            # Dùng .clear() thay vì tạo object mới để tránh race condition:
            # nếu tạo Event() mới, push() đang chờ lock sẽ .set() object mới
            # trong khi broadcast_loop đang await object cũ → miss notify mãi mãi.
            self._data = {}
            self._event.clear()

        return result

    def _active_modes(self) -> list[str]:
        """Workers đã gửi data trong vòng ACTIVE_TTL giây gần nhất."""
        now = time.time()
        return [m for m in WORKER_MODES if (now - self._last_seen.get(m, 0)) < ACTIVE_TTL]

    def _all_active_ready(self) -> bool:
        """True khi tất cả active workers đã gửi data trong round này."""
        active = self._active_modes()
        if not active:
            return False
        return all(m in self._data for m in active)

    def get_status(self) -> dict[str, str]:
        """
        Trả về status từng worker dựa trên last_seen — KHÔNG phụ thuộc _data
        nên không bị reset về 'reconnecting' sau mỗi broadcast.
        """
        now = time.time()
        return {
            mode: "connected" if (now - self._last_seen.get(mode, 0)) < ACTIVE_TTL
                  else "reconnecting"
            for mode in WORKER_MODES
        }