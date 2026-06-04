"""
sync_buffer.py — Đồng bộ data từ 3 workers trước khi broadcast

Normal mode: chờ đủ 3 workers → merge → broadcast
Solo mode:   sau SYNC_TIMEOUT giây → broadcast với data đang có
             Worker chưa gửi → trả về status "reconnecting"
"""

import asyncio
import time
from training.config import SYNC_TIMEOUT

WORKER_MODES = ["gat_marl", "idqn", "fixed_time"]


class SyncBuffer:
    """Thread-safe buffer đồng bộ data từ 3 workers."""

    def __init__(self, timeout: float = SYNC_TIMEOUT):
        self.timeout  = timeout
        self._data:   dict[str, dict] = {}
        self._lock    = asyncio.Lock()
        self._event   = asyncio.Event()

    async def push(self, mode: str, payload: dict):
        """Worker gửi data lên — ghi vào buffer và notify."""
        async with self._lock:
            self._data[mode] = payload
            if self._all_ready():
                self._event.set()

    async def wait_and_get(self) -> dict:
        """
        Chờ đủ 3 workers hoặc timeout.

        Returns:
            merged: {mode: payload} — có thể thiếu mode nếu timeout
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            pass  # solo mode — trả về data đang có

        async with self._lock:
            result = dict(self._data)
            # Reset cho round tiếp theo
            self._data  = {}
            self._event = asyncio.Event()

        return result

    def _all_ready(self) -> bool:
        return all(m in self._data for m in WORKER_MODES)

    def get_status(self) -> dict[str, str]:
        """Trả về status từng worker — dùng cho dashboard."""
        return {
            mode: "connected" if mode in self._data else "reconnecting"
            for mode in WORKER_MODES
        }