"""Capture simulation: render views from a scene manifest, then load
them back as `Capture` objects for the methods layer.

The render step lives in `render.py` and runs inside Blender. The load
step (`load_capture`) is plain Python — it reads the on-disk
CaptureManifest plus the rendered RGB/depth files and returns a list
of `Capture` objects ready to feed `Method.fit`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..io.manifest import CaptureManifest, RenderedView
from ..methods.base import Camera, Capture, Image


def _read_rgb(path: Path) -> np.ndarray:
    """RGB → (H, W, 3) float32 in [0, 1]. Pillow has no LPIPS-grade
    color management; that's fine here — we render and read with the
    same pipeline so PSNR/SSIM are self-consistent."""
    from PIL import Image as PILImage  # pillow is in pyproject base deps

    img = PILImage.open(path).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return arr


def _read_depth_exr(path: Path) -> np.ndarray:
    """Depth EXR → (H, W) float32 in scene units (meters).

    Cycles writes infinity to background pixels; we replace with NaN so
    downstream code can mask cleanly.
    """
    try:
        import OpenEXR  # noqa: F401
        import Imath
    except ImportError:
        # Fallback path: OpenCV-style imread with anydepth, if available.
        try:
            import imageio.v3 as iio
            arr = iio.imread(path)
            arr = np.asarray(arr, dtype=np.float32)
            if arr.ndim == 3:
                arr = arr[..., 0]
            arr = np.where(np.isfinite(arr), arr, np.nan)
            return arr
        except Exception as exc:
            raise RuntimeError(
                f"Cannot read depth EXR at {path}; install `openexr` or "
                f"`imageio[freeimage]`. Underlying error: {exc}"
            ) from exc

    import OpenEXR
    f = OpenEXR.InputFile(str(path))
    header = f.header()
    dw = header["dataWindow"]
    w = dw.max.x - dw.min.x + 1
    h = dw.max.y - dw.min.y + 1
    pt = Imath.PixelType(Imath.PixelType.FLOAT)
    # Cycles' Z-pass writes a single-channel EXR. Channel name varies
    # ('R', 'Y', 'V', 'Z' depending on Blender version + compositor
    # naming) — pick whichever single float channel is present.
    channels = list(header["channels"].keys())
    name = next(
        (c for c in ("R", "Y", "V", "Z") if c in channels), channels[0]
    )
    raw = f.channel(name, pt)
    arr = np.frombuffer(raw, dtype=np.float32).reshape(h, w)
    arr = np.where(np.isfinite(arr), arr, np.nan)
    return arr


def _camera_from_pose(pose) -> Camera:
    return Camera(
        intrinsics=np.asarray(pose.intrinsics, dtype=np.float64),
        extrinsics=np.asarray(pose.extrinsics, dtype=np.float64),
        width=pose.width,
        height=pose.height,
    )


def load_capture(manifest_path: Path) -> list[Capture]:
    """Load every view in a CaptureManifest into in-memory Captures."""
    manifest_path = Path(manifest_path)
    manifest = CaptureManifest.read(manifest_path)
    base = manifest_path.parent

    captures: list[Capture] = []
    for view in manifest.views:
        if view.camera is None:
            raise ValueError(
                f"View {view.pose_id} has no camera — manifest is incomplete."
            )
        rgb = _read_rgb(base / view.image_path)
        depth = (
            _read_depth_exr(base / view.depth_path)
            if view.depth_path
            else None
        )
        cam = _camera_from_pose(view.camera)
        captures.append(
            Capture(image=Image(pixels=rgb), camera=cam, depth=depth)
        )
    return captures


__all__ = ["load_capture"]
