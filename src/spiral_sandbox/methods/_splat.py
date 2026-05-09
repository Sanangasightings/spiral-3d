"""Shared numpy point-splat renderer.

Used by both `point_cloud` (which is natively a cloud) and
`photogrammetry` (which surface-samples its mesh into a cloud for
rendering). Keeping the rasterizer shared means a single z-buffer
implementation under test rather than two."""

from __future__ import annotations

import numpy as np

from .base import Camera, Image


def _project(
    points_world: np.ndarray, camera: Camera
) -> tuple[np.ndarray, np.ndarray]:
    homog = np.concatenate(
        [points_world, np.ones((points_world.shape[0], 1))], axis=-1
    )
    cam = homog @ camera.extrinsics.T
    cam = cam[:, :3]
    depths = cam[:, 2]
    valid = depths > 1e-6
    pix = np.zeros((points_world.shape[0], 2))
    pix[valid] = (cam[valid, :2] / depths[valid, None]) @ camera.intrinsics[
        :2, :2
    ].T + camera.intrinsics[:2, 2]
    return pix, depths


def splat_render(
    points: np.ndarray,
    colors: np.ndarray | None,
    camera: Camera,
    radius: int = 2,
) -> Image:
    """Project (N, 3) world points through `camera` and z-buffer them
    onto an (H, W, 3) image, splatting each as a square of radius
    `radius` pixels."""
    H, W = camera.height, camera.width
    canvas = np.zeros((H, W, 3), dtype=np.float32)
    zbuf = np.full((H, W), np.inf, dtype=np.float64)

    pix, depths = _project(points, camera)
    valid = (
        (depths > 1e-6)
        & (pix[:, 0] >= 0)
        & (pix[:, 0] < W)
        & (pix[:, 1] >= 0)
        & (pix[:, 1] < H)
    )
    pix = pix[valid]
    depths = depths[valid]
    if colors is None:
        colors = np.full((pix.shape[0], 3), 0.5, dtype=np.float32)
    else:
        colors = colors[valid]

    for (u, v), z, c in zip(pix, depths, colors):
        iu, iv = int(round(u)), int(round(v))
        for du in range(-radius, radius + 1):
            for dv in range(-radius, radius + 1):
                x, y = iu + du, iv + dv
                if 0 <= x < W and 0 <= y < H and z < zbuf[y, x]:
                    zbuf[y, x] = z
                    canvas[y, x] = c
    return Image(pixels=canvas)
