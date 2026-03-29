#!/usr/bin/env python3
from __future__ import annotations

import argparse
import signal
import time

import cv2
import numpy as np

from provcam_io import SharedFrameStore, V4L2RawWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent output writer for ProVCam")
    parser.add_argument("--frame-store", required=True, help="Shared frame store path")
    parser.add_argument("--output-device", required=True, help="V4L2 loopback device")
    parser.add_argument("--width", type=int, required=True, help="Output width")
    parser.add_argument("--height", type=int, required=True, help="Output height")
    parser.add_argument("--fps", type=int, required=True, help="Output fps")
    parser.add_argument("--fallback-timeout", type=float, default=0.25, help="Seconds to wait before recovery overlay")
    return parser


def build_recovery_frame(base_frame: np.ndarray, stale_for: float) -> np.ndarray:
    frame_bgr = cv2.cvtColor(base_frame, cv2.COLOR_RGB2BGR)
    overlay = frame_bgr.copy()
    height, width = overlay.shape[:2]
    t = time.time()

    panel_w = min(420, width - 40)
    panel_h = 96
    x1 = 20
    y1 = height - panel_h - 20
    x2 = x1 + panel_w
    y2 = y1 + panel_h

    cv2.rectangle(overlay, (x1, y1), (x2, y2), (15, 15, 20), -1)
    cv2.addWeighted(overlay, 0.72, frame_bgr, 0.28, 0.0, frame_bgr)

    elapsed_label = f"{stale_for:.1f}s"
    pulse = int(time.time() * 3) % 4
    dots = "." * pulse
    bar_w = panel_w - 36
    bar_h = 8
    bar_x = x1 + 18
    bar_y = y2 - 18
    progress = ((t * 140) % max(40, bar_w + 40)) - 40

    cv2.rectangle(frame_bgr, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (38, 48, 60), -1)
    glow_left = max(bar_x, bar_x + int(progress))
    glow_right = min(bar_x + bar_w, glow_left + 72)
    if glow_right > glow_left:
        cv2.rectangle(frame_bgr, (glow_left, bar_y), (glow_right, bar_y + bar_h), (90, 220, 255), -1)

    cv2.putText(
        frame_bgr,
        f"ProVCam reconnecting{dots}",
        (x1 + 18, y1 + 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame_bgr,
        f"GPU worker recovering, holding last frame  {elapsed_label}",
        (x1 + 18, y1 + 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (170, 220, 255),
        1,
        cv2.LINE_AA,
    )

    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def build_starting_frame(width: int, height: int, waiting_for: float) -> np.ndarray:
    frame_bgr = np.zeros((height, width, 3), dtype=np.uint8)
    frame_bgr[:] = (18, 20, 24)
    pulse = int(time.time() * 3) % 4
    dots = "." * pulse
    progress = int((time.time() * 180) % max(80, width - 96))
    bar_x1 = 24
    bar_x2 = min(width - 24, width - 24)
    bar_y1 = max(96, height - 24)
    bar_y0 = bar_y1 - 10
    cv2.rectangle(frame_bgr, (bar_x1, bar_y0), (bar_x2, bar_y1), (40, 48, 56), -1)
    glow_right = min(bar_x2, bar_x1 + progress)
    if glow_right > bar_x1:
        cv2.rectangle(frame_bgr, (bar_x1, bar_y0), (glow_right, bar_y1), (90, 220, 255), -1)
    cv2.putText(
        frame_bgr,
        f"ProVCam starting{dots}",
        (24, max(48, height - 72)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame_bgr,
        f"Waiting for first processed frame  {waiting_for:.1f}s",
        (24, max(80, height - 36)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (170, 220, 255),
        1,
        cv2.LINE_AA,
    )
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def main() -> int:
    args = build_parser().parse_args()
    running = True

    def handle_signal(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    store = SharedFrameStore(args.frame_store)
    writer = V4L2RawWriter(args.output_device, args.width, args.height, args.fps)
    current_frame = np.zeros((args.height, args.width, 3), dtype=np.uint8)
    version = 0
    last_processed_at = 0.0
    started_at = time.perf_counter()
    frame_interval = 1.0 / max(1, args.fps)
    next_deadline = time.perf_counter()

    try:
        while running:
            version, latest = store.read(version)
            if latest is not None:
                current_frame = latest
                last_processed_at = time.perf_counter()

            stale_for = time.perf_counter() - last_processed_at if last_processed_at > 0 else float("inf")
            output_frame = current_frame
            if last_processed_at <= 0:
                output_frame = build_starting_frame(args.width, args.height, time.perf_counter() - started_at)
            elif stale_for >= max(0.1, args.fallback_timeout):
                output_frame = build_recovery_frame(current_frame, stale_for)

            writer.write(output_frame)

            next_deadline += frame_interval
            now = time.perf_counter()
            sleep_for = next_deadline - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_deadline = now
    finally:
        writer.close()
        store.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
