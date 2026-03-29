#!/usr/bin/env python3
from __future__ import annotations

import glob
import mmap
import os
import shutil
import struct
import subprocess
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


FRAME_HEADER = struct.Struct("<QQIIII")
MAX_FRAME_WIDTH = 1920
MAX_FRAME_HEIGHT = 1080
MAX_FRAME_CHANNELS = 3
MAX_FRAME_BYTES = MAX_FRAME_WIDTH * MAX_FRAME_HEIGHT * MAX_FRAME_CHANNELS
FRAME_STORE_SIZE = FRAME_HEADER.size + MAX_FRAME_BYTES


class SharedFrameStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            current_size = os.fstat(fd).st_size
            if current_size != FRAME_STORE_SIZE:
                os.ftruncate(fd, FRAME_STORE_SIZE)
        except Exception:
            os.close(fd)
            raise
        self._fd = fd
        self._mmap = mmap.mmap(fd, FRAME_STORE_SIZE, access=mmap.ACCESS_WRITE)
        self._seq = self._load_existing_seq()

    def close(self) -> None:
        if hasattr(self, "_mmap"):
            self._mmap.close()
        if hasattr(self, "_fd") and self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def _load_existing_seq(self) -> int:
        try:
            self._mmap.seek(0)
            header = self._mmap.read(FRAME_HEADER.size)
            begin_seq, end_seq, width, height, channels, payload_size = FRAME_HEADER.unpack(header)
        except Exception:
            return 0

        valid_header = (
            begin_seq != 0
            and begin_seq == end_seq
            and begin_seq % 2 == 0
            and 0 < width <= MAX_FRAME_WIDTH
            and 0 < height <= MAX_FRAME_HEIGHT
            and channels == MAX_FRAME_CHANNELS
            and 0 < payload_size <= MAX_FRAME_BYTES
        )
        return begin_seq if valid_header else 0

    def publish(self, frame_rgb: np.ndarray) -> None:
        if frame_rgb.dtype != np.uint8:
            frame_rgb = frame_rgb.astype(np.uint8, copy=False)
        frame_rgb = np.ascontiguousarray(frame_rgb)
        height, width = frame_rgb.shape[:2]
        channels = frame_rgb.shape[2] if frame_rgb.ndim == 3 else 1
        payload = memoryview(frame_rgb).cast("B")
        payload_size = len(payload)
        if payload_size > MAX_FRAME_BYTES:
            raise ValueError(f"Frame payload too large for store: {payload_size}")

        self._seq += 1
        odd_seq = self._seq
        header = FRAME_HEADER.pack(odd_seq, odd_seq, width, height, channels, payload_size)
        self._mmap.seek(0)
        self._mmap.write(header)
        self._mmap.write(payload)

        self._seq += 1
        even_seq = self._seq
        final_header = FRAME_HEADER.pack(even_seq, even_seq, width, height, channels, payload_size)
        self._mmap.seek(0)
        self._mmap.write(final_header)
        self._mmap.flush()

    def read(self, known_version: int = 0) -> tuple[int, Optional[np.ndarray]]:
        for _ in range(3):
            self._mmap.seek(0)
            header_before = self._mmap.read(FRAME_HEADER.size)
            begin_seq, end_seq, width, height, channels, payload_size = FRAME_HEADER.unpack(header_before)
            if begin_seq == 0:
                return known_version, None
            if begin_seq != end_seq or begin_seq % 2 == 1:
                # Write in progress — spin briefly and retry
                time.sleep(0.001)
                continue
            if begin_seq <= known_version:
                return known_version, None
            if width == 0 or height == 0 or channels != 3:
                return known_version, None
            if payload_size == 0 or payload_size > MAX_FRAME_BYTES:
                return known_version, None

            payload = self._mmap.read(payload_size)
            self._mmap.seek(0)
            header_after = self._mmap.read(FRAME_HEADER.size)
            if header_before != header_after:
                continue

            frame = np.frombuffer(payload, dtype=np.uint8).reshape((height, width, channels)).copy()
            return begin_seq, frame
        return known_version, None


class V4L2RawWriter:
    def __init__(self, device_path: str, width: int, height: int, fps: int) -> None:
        if not os.path.exists(device_path):
            devices = ", ".join(sorted(glob.glob("/dev/video*"))) or "none"
            raise RuntimeError(f"Virtual camera device {device_path} does not exist. Available devices: {devices}")
        self.device_path = device_path
        self.width = width
        self.height = height
        self.fps = max(1, fps)
        self._configure_device()
        self._fd = os.open(device_path, os.O_WRONLY | os.O_CLOEXEC)

    def write(self, frame_rgb: np.ndarray) -> None:
        if frame_rgb.shape[1] != self.width or frame_rgb.shape[0] != self.height:
            frame_rgb = cv2.resize(frame_rgb, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        converted = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2YUV_I420)
        data = memoryview(converted).cast("B")
        total_written = 0
        while total_written < len(data):
            written = os.write(self._fd, data[total_written:])
            if written <= 0:
                raise RuntimeError(f"Failed to write frame to {self.device_path}")
            total_written += written

    def close(self) -> None:
        if hasattr(self, "_fd") and self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def _configure_device(self) -> None:
        ctl = shutil.which("v4l2-ctl")
        if ctl is None:
            raise RuntimeError("v4l2-ctl is required for the Python V4L2 writer")

        subprocess.run(
            [
                ctl,
                "-d",
                self.device_path,
                "--set-fmt-video-out",
                f"width={self.width},height={self.height},pixelformat=YU12,field=none,colorspace=srgb",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [ctl, "-d", self.device_path, "--set-ctrl", "keep_format=1,sustain_framerate=1"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
