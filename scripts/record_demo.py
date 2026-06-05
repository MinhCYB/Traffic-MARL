"""
scripts/record_demo.py — Tạo video backup cho demo

Record 3 hồi demo bằng cách chụp màn hình browser theo từng step.
Dùng trước ngày demo để có video backup phòng khi live demo lỗi.

Yêu cầu:
    pip install pillow pyautogui opencv-python
    Dashboard đang chạy tại localhost:5173/demo

Dùng:
    python scripts/record_demo.py --output demo_backup.mp4 --duration 120
"""

import time
import argparse
from pathlib import Path


def record(output: str, duration: int, fps: int = 5):
    try:
        import pyautogui
        import cv2
        import numpy as np
        from PIL import ImageGrab
    except ImportError:
        print("Cài thêm: pip install pillow pyautogui opencv-python")
        return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Lấy kích thước màn hình
    screen_w, screen_h = pyautogui.size()
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (screen_w, screen_h))

    total_frames = duration * fps
    interval     = 1.0 / fps

    print(f"Bắt đầu record {duration}s → {output_path}")
    print("Chuyển sang cửa sổ browser ngay!")
    time.sleep(3)  # Thời gian chuyển cửa sổ

    for i in range(total_frames):
        t0     = time.time()
        frame  = ImageGrab.grab()
        frame  = np.array(frame)
        frame  = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        writer.write(frame)

        elapsed = time.time() - t0
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

        if i % (fps * 10) == 0:
            print(f"  {i // fps}s / {duration}s...")

    writer.release()
    print(f"Done: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",   default="logs/demo_backup.mp4")
    parser.add_argument("--duration", type=int, default=120, help="Giây cần record")
    parser.add_argument("--fps",      type=int, default=5)
    args = parser.parse_args()
    record(args.output, args.duration, args.fps)