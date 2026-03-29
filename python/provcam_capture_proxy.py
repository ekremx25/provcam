#!/usr/bin/env python3
from __future__ import annotations

import argparse
import signal
import time

import cv2

from provcam_io import SharedFrameStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent camera capture proxy for ProVCam")
    parser.add_argument("--camera-id", type=int, default=0, help="Input camera index")
    parser.add_argument("--camera-device", default="", help="Input camera path such as /dev/video0")
    parser.add_argument("--width", type=int, default=1280, help="Capture width")
    parser.add_argument("--height", type=int, default=720, help="Capture height")
    parser.add_argument("--fps", type=int, default=30, help="Capture fps")
    parser.add_argument("--frame-store", required=True, help="Shared raw frame store path")
    return parser


def open_capture(args: argparse.Namespace) -> cv2.VideoCapture:
    attempts: list[cv2.VideoCapture] = []
    source: int | str = args.camera_device if args.camera_device else args.camera_id
    if args.camera_device:
        attempts.append(cv2.VideoCapture(args.camera_device))
        attempts.append(cv2.VideoCapture(args.camera_device, cv2.CAP_ANY))
    else:
        attempts.append(cv2.VideoCapture(args.camera_id, cv2.CAP_V4L2))
        attempts.append(cv2.VideoCapture(args.camera_id))

    for capture in attempts:
        if capture.isOpened():
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, max(args.width, 1280))
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, max(args.height, 720))
            capture.set(cv2.CAP_PROP_FPS, args.fps)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return capture

    for capture in attempts:
        try:
            capture.release()
        except Exception:
            pass
    raise RuntimeError(f"Failed to open camera {source}")


def main() -> int:
    args = build_parser().parse_args()
    running = True
    capture = open_capture(args)
    store = SharedFrameStore(args.frame_store)

    def handle_signal(_signum, _frame) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        frame_interval = 1.0 / max(1, args.fps)
        next_deadline = time.perf_counter()
        while running:
            ok, frame_bgr = capture.read()
            if not ok or frame_bgr is None or frame_bgr.size == 0:
                time.sleep(0.02)
                try:
                    capture.release()
                except Exception:
                    pass
                capture = open_capture(args)
                continue
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            store.publish(frame_rgb)
            next_deadline += frame_interval
            now = time.perf_counter()
            sleep_for = next_deadline - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_deadline = now
    finally:
        capture.release()
        store.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
