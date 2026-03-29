#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time

import cv2
import numpy as np

from provcam_io import V4L2RawWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a short clean slate to the ProVCam output device")
    parser.add_argument("--output-device", required=True, help="V4L2 loopback device path")
    parser.add_argument("--width", type=int, required=True, help="Output width")
    parser.add_argument("--height", type=int, required=True, help="Output height")
    parser.add_argument("--fps", type=int, required=True, help="Output fps")
    parser.add_argument("--seconds", type=float, default=0.8, help="How long to write the repair slate")
    return parser


def build_frame(width: int, height: int, elapsed: float) -> np.ndarray:
    frame_bgr = np.zeros((height, width, 3), dtype=np.uint8)
    frame_bgr[:] = (18, 20, 24)

    progress = int((elapsed * 220) % max(80, width - 96))
    dots = "." * (int(elapsed * 4) % 4)

    panel_x1 = 24
    panel_y1 = max(24, height - 118)
    panel_x2 = min(width - 24, panel_x1 + 430)
    panel_y2 = min(height - 24, panel_y1 + 84)
    bar_y = panel_y2 - 16

    cv2.rectangle(frame_bgr, (panel_x1, panel_y1), (panel_x2, panel_y2), (26, 30, 36), -1)
    cv2.rectangle(frame_bgr, (panel_x1 + 16, bar_y), (panel_x2 - 16, bar_y + 8), (52, 60, 72), -1)
    glow_right = min(panel_x2 - 16, panel_x1 + 16 + progress)
    if glow_right > panel_x1 + 16:
        cv2.rectangle(frame_bgr, (panel_x1 + 16, bar_y), (glow_right, bar_y + 8), (90, 220, 255), -1)

    cv2.putText(
        frame_bgr,
        f"ProVCam output reset{dots}",
        (panel_x1 + 16, panel_y1 + 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.76,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame_bgr,
        "Cleaning the virtual camera buffer before restart",
        (panel_x1 + 16, panel_y1 + 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (176, 220, 255),
        1,
        cv2.LINE_AA,
    )

    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def main() -> int:
    args = build_parser().parse_args()
    writer = V4L2RawWriter(args.output_device, args.width, args.height, max(1, args.fps))
    frame_interval = 1.0 / max(1, args.fps)
    deadline = time.perf_counter()
    started_at = time.perf_counter()

    try:
        while True:
            elapsed = time.perf_counter() - started_at
            if elapsed >= max(0.1, args.seconds):
                break
            writer.write(build_frame(args.width, args.height, elapsed))
            deadline += frame_interval
            sleep_for = deadline - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        writer.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
