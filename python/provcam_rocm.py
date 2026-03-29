#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

try:
    import cv2
    cv2.setNumThreads(1)
    import numpy as np
    import torch
    torch.set_num_threads(1)
    import math
    import torchvision.transforms.functional as TF
    from provcam_io import SharedFrameStore, V4L2RawWriter

except ImportError as exc:
    missing = str(exc).split()[-1].strip("'")
    print(
        f"Missing Python dependency: {missing}. "
        "Install the virtualenv described in PYTHON_BACKEND.md first.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def sanitize_dimension(value: int, fallback: int) -> int:
    if value <= 0:
        value = fallback
    return value if value % 2 == 0 else value - 1
def get_ksize(sigma: float) -> int:
    k = int(math.ceil(sigma * 2.5))
    return k if k % 2 == 1 else k + 1


def refine_alpha_torch(alpha: torch.Tensor, matte_mode: str) -> torch.Tensor:
    alpha = torch.clamp(alpha, 0.0, 1.0)
    blur_sigma = 1.2
    power = 0.95
    low_cut = 0.04
    high_cut = 0.96

    if matte_mode == "clean":
        blur_sigma = 1.0
        power = 1.0
        low_cut = 0.06
        high_cut = 0.94
    elif matte_mode == "soft":
        blur_sigma = 1.5
        power = 0.92
        low_cut = 0.03
        high_cut = 0.97
    
    # Gaussian blur
    alpha = TF.gaussian_blur(alpha, [get_ksize(blur_sigma), get_ksize(blur_sigma)], [blur_sigma, blur_sigma])
    alpha = torch.pow(alpha, power)
    
    alpha = -torch.nn.functional.max_pool2d(-alpha, 3, stride=1, padding=1)
    alpha = torch.nn.functional.max_pool2d(alpha, 3, stride=1, padding=1)
    alpha = torch.nn.functional.max_pool2d(alpha, 3, stride=1, padding=1)
    alpha = -torch.nn.functional.max_pool2d(-alpha, 3, stride=1, padding=1)

    low_mask = alpha < 0.02
    high_mask = alpha > 0.98
    alpha = torch.where(low_mask, torch.zeros_like(alpha), alpha)
    alpha = torch.where(high_mask, torch.ones_like(alpha), alpha)

    tight_low = (alpha > 0.0) & (alpha < low_cut)
    tight_high = (alpha > high_cut) & (alpha < 1.0)
    alpha = torch.where(tight_low, torch.zeros_like(alpha), alpha)
    alpha = torch.where(tight_high, torch.ones_like(alpha), alpha)
    return alpha


def build_edge_mask_torch(alpha: torch.Tensor, matte_mode: str) -> torch.Tensor:
    edge = torch.clamp(alpha * (1.0 - alpha) * 4.0, 0.0, 1.0)
    sigma = 2.0
    if matte_mode == "clean":
        sigma = 1.4
    elif matte_mode == "soft":
        sigma = 2.4
    edge = TF.gaussian_blur(edge, [get_ksize(sigma), get_ksize(sigma)], [sigma, sigma])
    return torch.clamp(edge, 0.0, 1.0)


def fast_refine_alpha_torch(alpha: torch.Tensor) -> torch.Tensor:
    alpha = torch.clamp(alpha, 0.0, 1.0)
    alpha = TF.gaussian_blur(alpha, [3, 3], [0.8, 0.8])
    low_mask = alpha < 0.05
    high_mask = alpha > 0.95
    alpha = torch.where(low_mask, torch.zeros_like(alpha), alpha)
    alpha = torch.where(high_mask, torch.ones_like(alpha), alpha)
    return alpha


def clean_foreground_colors_torch(
    foreground_fgr: torch.Tensor,
    original_float: torch.Tensor,
    edge_mask: torch.Tensor,
    matte_mode: str,
    backbone: str,
) -> torch.Tensor:
    edge_mix_strength = 0.30
    if matte_mode == "clean":
        edge_mix_strength = 0.18
    elif matte_mode == "soft":
        edge_mix_strength = 0.36
    if backbone == "hybrid":
        if matte_mode == "clean":
            edge_mix_strength = 0.10
        elif matte_mode == "balanced":
            edge_mix_strength = 0.22

    edge_mix = edge_mask * edge_mix_strength
    cleaned = foreground_fgr * (1.0 - edge_mix) + original_float * edge_mix
    return torch.clamp(cleaned, 0.0, 1.0)


def stabilize_hybrid_edges_torch(
    alpha: torch.Tensor,
    edge_mask: torch.Tensor,
    matte_mode: str,
) -> tuple[torch.Tensor, torch.Tensor]:
    if matte_mode != "clean":
        return alpha, edge_mask

    # Hybrid mode aims to sit between MobileNet and ResNet, so we keep the edge
    # band tighter while slightly boosting confident foreground to avoid
    # semi-transparent hands/heads.
    boosted_alpha = torch.clamp(alpha * 1.08 + 0.015, 0.0, 1.0)
    dilated_alpha = torch.nn.functional.max_pool2d(alpha, 5, stride=1, padding=2)
    protected_alpha = torch.maximum(boosted_alpha, dilated_alpha * 0.992)
    alpha = torch.where(alpha > 0.32, protected_alpha, alpha)
    alpha = torch.clamp(alpha, 0.0, 1.0)
    edge_mask = build_edge_mask_torch(alpha, "clean")
    edge_mask = torch.clamp(edge_mask * 0.76, 0.0, 1.0)
    return alpha, edge_mask


def despill_for_green_screen_torch(
    foreground: torch.Tensor,
    original_float: torch.Tensor,
    alpha: torch.Tensor,
    edge_mask: torch.Tensor,
) -> torch.Tensor:
    r = foreground[:, 0:1, :, :]
    g = foreground[:, 1:2, :, :]
    b = foreground[:, 2:3, :, :]
    rb_max = torch.maximum(r, b)
    allowed_green = rb_max + 0.03
    green = torch.minimum(g, allowed_green)
    despilled = torch.cat([r, green, b], dim=1)

    mix = torch.clamp(edge_mask * 1.5 + (1.0 - alpha) * 0.55, 0.0, 1.0)
    recovered = despilled * (1.0 - mix) + original_float * mix
    return torch.clamp(recovered, 0.0, 1.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Linux Pro VCam Python ROCm backend")
    parser.add_argument("--camera-id", type=int, default=0, help="Input camera index")
    parser.add_argument("--camera-device", default="", help="Input camera device path such as /dev/video0")
    parser.add_argument("--width", type=int, default=1280, help="Processing width")
    parser.add_argument("--height", type=int, default=720, help="Processing height")
    parser.add_argument("--fps", type=int, default=30, help="Capture/inference fps target")
    parser.add_argument("--output-fps", type=int, default=30, help="Output/preview fps target")
    parser.add_argument("--output-device", default="", help="V4L2 loopback device such as /dev/video2")
    parser.add_argument("--frame-store", default="", help="Shared frame store path for persistent output")
    parser.add_argument("--capture-store", default="", help="Shared raw capture store path")
    parser.add_argument(
        "--background",
        choices=["none", "blur", "green", "black", "image"],
        default="blur",
        help="Background composition mode",
    )
    parser.add_argument("--background-image", default="", help="Background image path")
    parser.add_argument("--no-preview", action="store_true", help="Disable preview window")
    parser.add_argument(
        "--device",
        choices=["auto", "cuda", "cpu"],
        default="auto",
        help="Preferred torch device",
    )
    parser.add_argument(
        "--precision",
        choices=["auto", "fp16", "fp32"],
        default="auto",
        help="Model precision on GPU",
    )
    parser.add_argument(
        "--backbone",
        choices=["mobilenetv3", "hybrid", "resnet50"],
        default="mobilenetv3",
        help="RVM model backbone",
    )
    parser.add_argument(
        "--matte-mode",
        choices=["balanced", "clean", "soft"],
        default="balanced",
        help="Edge behavior preset: balanced, cleaner edges, or softer hair detail",
    )
    parser.add_argument(
        "--downsample-ratio",
        type=float,
        default=0.0,
        help="Override RVM downsample ratio. 0 means auto.",
    )
    return parser


@dataclass
class AppOptions:
    camera_id: int
    camera_device: str
    width: int
    height: int
    fps: int
    output_fps: int
    output_device: str
    frame_store: str
    capture_store: str
    background: str
    background_image: str
    show_preview: bool
    device: str
    precision: str
    backbone: str
    matte_mode: str
    downsample_ratio: float


def configure_preview_backend() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")


class LatestFrameBuffer:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._frame: Optional[np.ndarray] = None
        self._version = 0
        self._stopped = False

    def publish(self, frame: np.ndarray) -> None:
        with self._condition:
            self._frame = frame
            self._version += 1
            self._condition.notify_all()

    def wait_for_new(self, known_version: int, running: threading.Event) -> tuple[int, Optional[np.ndarray]]:
        with self._condition:
            self._condition.wait_for(lambda: self._stopped or self._version > known_version or not running.is_set())
            if (self._stopped or not running.is_set()) and self._version <= known_version:
                return known_version, None
            return self._version, self._frame

    def get_latest_if_newer(self, known_version: int) -> tuple[int, Optional[np.ndarray]]:
        with self._condition:
            if self._frame is None or self._version <= known_version:
                return known_version, None
            return self._version, self._frame

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()


class BackgroundComposer:
    def __init__(self, options: AppOptions) -> None:
        self.mode = options.background
        self.background_image_path = options.background_image
        self._background_image: Optional[np.ndarray] = None
        self._cached_cover: Optional[np.ndarray] = None
        self._cached_size: Optional[tuple[int, int]] = None
        self._cached_blur: Optional[np.ndarray] = None
        self._cached_blur_size: Optional[tuple[int, int]] = None

        if self.mode == "image":
            if not self.background_image_path:
                raise RuntimeError("--background image requires --background-image")
            image = cv2.imread(self.background_image_path, cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"Background image could not be loaded: {self.background_image_path}")
            self._background_image = image

    def _resize_cover(self, width: int, height: int) -> np.ndarray:
        assert self._background_image is not None
        if self._cached_cover is not None and self._cached_size == (width, height):
            return self._cached_cover
        scale = max(width / self._background_image.shape[1], height / self._background_image.shape[0])
        resized = cv2.resize(self._background_image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        x = max(0, (resized.shape[1] - width) // 2)
        y = max(0, (resized.shape[0] - height) // 2)
        cover = resized[y : y + height, x : x + width].copy()
        self._cached_cover = cover
        self._cached_size = (width, height)
        return cover

    def get_background(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        if self.mode == "none":
            return frame
        if self.mode == "green":
            return np.full((height, width, 3), (0, 255, 0), dtype=np.uint8)
        if self.mode == "black":
            return np.zeros((height, width, 3), dtype=np.uint8)
        if self.mode == "image":
            return self._resize_cover(width, height)
        # blur: cache the result — GaussianBlur(sigma=17) is expensive, skip if size unchanged
        if self._cached_blur is not None and self._cached_blur_size == (width, height):
            return self._cached_blur
        blurred = cv2.GaussianBlur(frame, (0, 0), 17, borderType=cv2.BORDER_REPLICATE)
        self._cached_blur = blurred
        self._cached_blur_size = (width, height)
        return blurred


class RvmTorchBackend:
    def __init__(self, options: AppOptions) -> None:
        self.options = options
        self.device = self._select_device(options.device)
        self.use_fp16 = self._select_precision(options.precision)
        self.model_backbone = self._resolve_model_backbone(options.backbone)
        self.model = self._load_model(self.model_backbone)
        self.rec = [None] * 4
        self.downsample_ratio = self._resolve_downsample_ratio(options.downsample_ratio, options.width, options.height)
        self.inference_size = self._resolve_inference_size(options.width, options.height)
        print(f"PyTorch device: {self.device}")
        print(f"Precision: {'fp16' if self.use_fp16 else 'fp32'}")
        if self.options.backbone == "hybrid":
            print("Model profile: hybrid (mobilenetv3 enhanced)")
        print(f"Downsample ratio: {self.downsample_ratio:.3f}")
        print(f"Inference resolution: {self.inference_size[0]}x{self.inference_size[1]}")

    def _select_device(self, requested: str) -> torch.device:
        if requested == "cpu":
            return torch.device("cpu")
        if requested == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA/HIP device requested but torch.cuda.is_available() is false")
            return torch.device("cuda")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    def _select_precision(self, requested: str) -> bool:
        if self.device.type != "cuda":
            return False
        if requested == "fp32":
            return False
        if requested == "fp16":
            return True
        return True

    def _resolve_model_backbone(self, backbone: str) -> str:
        if backbone == "hybrid":
            return "mobilenetv3"
        return backbone

    def _load_model(self, backbone: str):
        import os
        hub_dir = torch.hub.get_dir()
        repo_dir = os.path.join(hub_dir, "PeterL1n_RobustVideoMatting_master")
        model = None
        
        if os.path.exists(repo_dir):
            try:
                model = torch.hub.load(repo_dir, backbone, source="local")
                print("Loaded AI model from local cache.")
            except Exception as e:
                print(f"Local cache load failed, trying online: {e}")
        
        if model is None:
            try:
                model = torch.hub.load("PeterL1n/RobustVideoMatting", backbone, trust_repo=True)
            except TypeError:
                model = torch.hub.load("PeterL1n/RobustVideoMatting", backbone)

        model = model.eval().to(self.device)
        if self.use_fp16:
            model = model.half()
        return model

    def _resolve_downsample_ratio(self, requested: float, width: int, height: int) -> float:
        if requested > 0:
            return requested
        longest = max(width, height)
        if self.options.backbone == "resnet50":
            if longest >= 1920:
                return 0.25
            if longest >= 1280:
                return 0.28
            if longest >= 960:
                return 0.30
            return 0.35
        if self.options.backbone == "hybrid":
            if longest >= 1920:
                return 0.28
            if longest >= 1280:
                return 0.33
            if longest >= 960:
                return 0.38
            return 0.42
        if longest >= 1920:
            return 0.25
        if longest >= 1280:
            return 0.30
        if longest >= 960:
            return 0.35
        return 0.40

    def reset(self) -> None:
        self.rec = [None] * 4

    def _resolve_inference_size(self, width: int, height: int) -> tuple[int, int]:
        longest = max(width, height)
        if self.options.backbone == "hybrid":
            if longest >= 1280:
                return 768, 432
            if longest >= 960:
                return 704, 396
        if self.options.backbone == "mobilenetv3":
            if longest >= 1280:
                return 640, 360
            if longest >= 960:
                return 640, 360
        if self.options.backbone == "resnet50" and longest >= 1280:
            return 960, 540
        return width, height

    def _use_fast_postprocess(self) -> bool:
        return (
            self.options.backbone == "mobilenetv3"
            and max(self.inference_size) <= 640
            and self.options.matte_mode in {"balanced", "clean"}
        )

    def process_frame(self, frame_bgr: np.ndarray, composer: BackgroundComposer) -> np.ndarray:
        if composer.mode == "none":
            return cv2.resize(
                frame_bgr,
                (self.options.width, self.options.height),
                interpolation=cv2.INTER_AREA if frame_bgr.shape[1] >= self.options.width else cv2.INTER_CUBIC,
            )

        inference_width, inference_height = self.inference_size
        working = cv2.resize(
            frame_bgr,
            (inference_width, inference_height),
            interpolation=cv2.INTER_AREA if frame_bgr.shape[1] >= inference_width else cv2.INTER_CUBIC,
        )
        # Upload BGR directly — channel swap done on GPU to avoid CPU copy
        src_tensor = torch.from_numpy(working).permute(2, 0, 1).unsqueeze(0).to(self.device, non_blocking=True)
        src_tensor = src_tensor[:, [2, 1, 0], :, :]  # BGR→RGB on GPU
        if self.use_fp16:
            src_tensor = src_tensor.half().div_(255.0)
        else:
            src_tensor = src_tensor.float().div_(255.0)

        with torch.inference_mode():
            if self.device.type == "cuda" and self.use_fp16:
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    fgr, pha, *self.rec = self.model(src_tensor, *self.rec, self.downsample_ratio)
            else:
                fgr, pha, *self.rec = self.model(src_tensor, *self.rec, self.downsample_ratio)

            if not torch.isfinite(pha).all() or not torch.isfinite(fgr).all():
                print("Warning: NaN/Inf in model output — resetting RVM state.", file=sys.stderr)
                self.reset()
                return cv2.resize(
                    frame_bgr,
                    (self.options.width, self.options.height),
                    interpolation=cv2.INTER_LINEAR,
                )

            fast_postprocess = self._use_fast_postprocess()
            if fast_postprocess:
                pha = fast_refine_alpha_torch(pha)
                edge_mask = torch.clamp(pha * (1.0 - pha) * 4.0, 0.0, 1.0)
            else:
                pha = refine_alpha_torch(pha, self.options.matte_mode)
                edge_mask = build_edge_mask_torch(pha, self.options.matte_mode)
                if self.options.backbone == "hybrid":
                    pha, edge_mask = stabilize_hybrid_edges_torch(pha, edge_mask, self.options.matte_mode)
            
            options_background_is_green = (composer.mode == "green")
            if options_background_is_green:
                pha = torch.clamp((pha - 0.02) / 0.90, 0.0, 1.0)
                pha = torch.pow(pha, 0.85)
                edge_mask = build_edge_mask_torch(pha, "clean")

            foreground_fgr = torch.clamp(fgr, 0.0, 1.0)
            original_float = src_tensor
            
            if not fast_postprocess:
                foreground_fgr = clean_foreground_colors_torch(
                    foreground_fgr,
                    original_float,
                    edge_mask,
                    self.options.matte_mode,
                    self.options.backbone,
                )
            
            edge_foreground_strength = 0.9
            if self.options.matte_mode == "clean":
                edge_foreground_strength = 0.72
            elif self.options.matte_mode == "soft":
                edge_foreground_strength = 0.95
            if self.options.backbone == "hybrid" and self.options.matte_mode == "clean":
                edge_foreground_strength = 0.88

            foreground = (
                original_float * (1.0 - edge_mask * edge_foreground_strength)
                + foreground_fgr * (edge_mask * edge_foreground_strength)
            )

            if not hasattr(self, "_cached_bg_tensor") or getattr(self, "_cached_bg_tensor_mode", None) != composer.mode:
                bg_np = composer.get_background(working)
                # Upload BGR directly — channel swap done on GPU, no CPU copy
                background = torch.from_numpy(bg_np).permute(2, 0, 1).unsqueeze(0).to(self.device, non_blocking=True)
                background = background[:, [2, 1, 0], :, :].float().div_(255.0)  # BGR→RGB on GPU
                if self.use_fp16:
                    background = background.half()
                if composer.mode in ("green", "black", "image", "blur"):
                    self._cached_bg_tensor = background
                    self._cached_bg_tensor_mode = composer.mode
            else:
                background = self._cached_bg_tensor

            if options_background_is_green:
                foreground = despill_for_green_screen_torch(foreground, original_float, pha, edge_mask)

            if composer.mode == "image" and not fast_postprocess:
                if self.options.backbone == "mobilenetv3":
                    wrap_strength = 0.015
                elif self.options.backbone == "hybrid":
                    wrap_strength = 0.020
                else:
                    wrap_strength = 0.025
                wrap_power = 1.8
                if self.options.matte_mode == "clean":
                    if self.options.backbone == "hybrid":
                        wrap_strength = 0.0
                    else:
                        wrap_strength *= 0.2
                    wrap_power = 2.2
                elif self.options.matte_mode == "soft":
                    wrap_strength *= 1.15
                    wrap_power = 1.6
                wrap_mask = torch.pow(edge_mask, wrap_power) * wrap_strength
                foreground = foreground * (1.0 - wrap_mask) + background * wrap_mask

            composed = foreground * pha + background * (1.0 - pha)
            composed = torch.clamp(composed * 255.0, 0.0, 255.0).to(torch.uint8)

            # Upscale on GPU if inference size differs from output size
            if (inference_width, inference_height) != (self.options.width, self.options.height):
                composed = torch.nn.functional.interpolate(
                    composed.float(),
                    size=(self.options.height, self.options.width),
                    mode="bilinear",
                    align_corners=False,
                ).to(torch.uint8)

            composed_cpu = composed[0].cpu().permute(1, 2, 0).numpy()
            return np.ascontiguousarray(composed_cpu)


def create_options(args: argparse.Namespace) -> AppOptions:
    width = sanitize_dimension(args.width, 1280)
    height = sanitize_dimension(args.height, 720)
    return AppOptions(
        camera_id=args.camera_id,
        camera_device=args.camera_device.strip(),
        width=width,
        height=height,
        fps=max(1, args.fps),
        output_fps=max(1, args.output_fps),
        output_device=args.output_device,
        frame_store=args.frame_store.strip(),
        capture_store=args.capture_store.strip(),
        background=args.background,
        background_image=args.background_image,
        show_preview=not args.no_preview,
        device=args.device,
        precision=args.precision,
        backbone=args.backbone,
        matte_mode=args.matte_mode,
        downsample_ratio=args.downsample_ratio,
    )


def main() -> int:
    options = create_options(build_parser().parse_args())
    print("Pro VCam Python ROCm backend starting...")
    if options.show_preview:
        configure_preview_backend()

    input_device_guess = options.camera_device or f"/dev/video{options.camera_id}"
    if options.output_device and options.output_device == input_device_guess:
        raise RuntimeError(f"Input camera and output device cannot be the same V4L2 node: {options.output_device}")

    capture_store: Optional[SharedFrameStore] = None
    cap: Optional[cv2.VideoCapture] = None
    if options.capture_store:
        capture_store = SharedFrameStore(options.capture_store)
        print(f"Using capture store: {options.capture_store}")
    else:
        camera_source: int | str = options.camera_device if options.camera_device else options.camera_id
        capture_attempts: list[cv2.VideoCapture] = []
        if options.camera_device:
            capture_attempts.append(cv2.VideoCapture(options.camera_device))
            capture_attempts.append(cv2.VideoCapture(options.camera_device, cv2.CAP_ANY))
        else:
            capture_attempts.append(cv2.VideoCapture(options.camera_id, cv2.CAP_V4L2))
            capture_attempts.append(cv2.VideoCapture(options.camera_id))

        cap = None
        for candidate in capture_attempts:
            if candidate.isOpened():
                cap = candidate
                break
        # Release every candidate that was not selected
        for candidate in capture_attempts:
            if candidate is not cap:
                try:
                    candidate.release()
                except Exception:
                    pass
        if cap is None or not cap.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_source}")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, max(options.width, 1280))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, max(options.height, 720))
        cap.set(cv2.CAP_PROP_FPS, options.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        print(
            f"Camera opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}"
            f"x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {cap.get(cv2.CAP_PROP_FPS):.0f} fps"
        )
    print(f"Processing resolution: {options.width}x{options.height}")
    print(f"Output target: {options.output_fps} fps")

    composer = BackgroundComposer(options)
    backend = RvmTorchBackend(options)

    captured = LatestFrameBuffer()
    processed = LatestFrameBuffer()
    running = threading.Event()
    running.set()
    error_lock = threading.Lock()
    error_message: list[str] = []

    def stop_all() -> None:
        running.clear()
        captured.stop()
        processed.stop()

    def fail(message: str) -> None:
        with error_lock:
            if not error_message:
                error_message.append(message)
        stop_all()

    def capture_loop() -> None:
        nonlocal cap
        empty_frames = 0
        capture_version = 0
        try:
            while running.is_set():
                if capture_store is not None:
                    capture_version, frame_rgb = capture_store.read(capture_version)
                    if frame_rgb is None:
                        time.sleep(0.005)
                        continue
                    frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                    captured.publish(frame)
                    continue

                assert cap is not None
                ok, frame = cap.read()
                if not ok or frame is None or frame.size == 0:
                    empty_frames += 1
                    if empty_frames == 1 or empty_frames % 30 == 0:
                        print(f"Warning: camera returned an empty frame ({empty_frames}).", file=sys.stderr)
                    time.sleep(0.005)
                    continue
                empty_frames = 0
                captured.publish(frame)
        except Exception as exc:
            fail(f"Capture thread failed: {exc}")
        finally:
            captured.stop()

    def processing_loop() -> None:
        version = 0
        processed_count = 0
        last_report = time.perf_counter()
        frame_interval = 1.0 / max(1, options.fps)
        next_deadline = time.perf_counter()
        try:
            while running.is_set():
                version, frame = captured.wait_for_new(version, running)
                if frame is None:
                    break

                now = time.perf_counter()
                sleep_for = next_deadline - now
                if sleep_for > 0:
                    time.sleep(sleep_for)
                else:
                    next_deadline = now

                processed_frame = backend.process_frame(frame, composer)
                processed.publish(processed_frame)
                next_deadline += frame_interval
                processed_count += 1
                now = time.perf_counter()
                if now - last_report >= 5.0:
                    print(f"Processed frames: {processed_count} in {now - last_report:.1f}s")
                    processed_count = 0
                    last_report = now
        except Exception as exc:
            fail(f"AI thread failed: {exc}")
        finally:
            processed.stop()

    capture_thread = threading.Thread(target=capture_loop, daemon=True)
    processing_thread = threading.Thread(target=processing_loop, daemon=True)
    capture_thread.start()
    processing_thread.start()

    version = 0
    version, current_output = processed.wait_for_new(version, running)
    if current_output is None:
        fail("No processed frame became available.")
        current_output = np.zeros((options.height, options.width, 3), dtype=np.uint8)

    writer: Optional[V4L2RawWriter] = None
    frame_store: Optional[SharedFrameStore] = None
    try:
        if options.frame_store:
            frame_store = SharedFrameStore(options.frame_store)
            frame_store.publish(current_output)
            print(f"Shared frame store ready: {options.frame_store}")
        elif options.output_device:
            writer = V4L2RawWriter(options.output_device, current_output.shape[1], current_output.shape[0], options.output_fps)
            print(f"Virtual camera ready: {options.output_device} ({current_output.shape[1]}x{current_output.shape[0]})")

        if options.show_preview:
            print("Press q in the preview window to stop.")

        frame_interval = 1.0 / max(1, options.output_fps)
        next_deadline = time.perf_counter()

        while running.is_set():
            # frame_store path: block until new frame — output_writer handles V4L2 rate
            if frame_store is not None:
                version, latest = processed.wait_for_new(version, running)
                if latest is None:
                    break
                current_output = latest
                frame_store.publish(current_output)
                if options.show_preview:
                    current_output_bgr = cv2.cvtColor(current_output, cv2.COLOR_RGB2BGR)
                    cv2.imshow("Pro VCam - Python ROCm Backend", current_output_bgr)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), ord("Q")):
                        stop_all()
                        break
                continue

            # Direct V4L2 path: must write at output_fps even without new frames
            version, latest = processed.get_latest_if_newer(version)
            if latest is not None:
                current_output = latest

            if writer is not None:
                writer.write(current_output)

            if options.show_preview:
                current_output_bgr = cv2.cvtColor(current_output, cv2.COLOR_RGB2BGR)
                cv2.imshow("Pro VCam - Python ROCm Backend", current_output_bgr)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    stop_all()
                    break

            next_deadline += frame_interval
            now = time.perf_counter()
            sleep_for = next_deadline - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_deadline = now
    except Exception as exc:
        fail(f"Output loop failed: {exc}")
    finally:
        stop_all()
        capture_thread.join(timeout=2)
        processing_thread.join(timeout=2)
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        if writer is not None:
            writer.close()
        if frame_store is not None:
            frame_store.close()
        if capture_store is not None:
            capture_store.close()

    if error_message:
        print(f"Fatal error: {error_message[0]}", file=sys.stderr)
        return 1

    print("Pro VCam Python ROCm backend stopped.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
