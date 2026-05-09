"""Depth-and-pose fusion via Open3D (with numpy fallback)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .base import (
    Camera,
    Capture,
    GeometryExport,
    Image,
    Method,
    MethodConfig,
    PointCloud,
    Reconstruction,
)
from .registry import register


class PointCloudConfig(MethodConfig):
    """Knobs for the point-cloud method."""

    voxel_size: Optional[float] = 0.01
    max_points_per_view: int = 50_000
    background_depth_clip: float = 1e3
    splat_radius_px: int = 2


@dataclass
class PointCloudReconstruction(Reconstruction):
    """A point cloud, in world frame."""

    points: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    colors: Optional[np.ndarray] = None
    normals: Optional[np.ndarray] = None

    def geometry_export(self) -> GeometryExport:
        return PointCloud(
            points=self.points, colors=self.colors, normals=self.normals
        )


def _unproject(
    depth: np.ndarray, intrinsics: np.ndarray
) -> np.ndarray:
    """(H, W) depth → (H, W, 3) camera-frame points. NaN depths → NaN."""
    h, w = depth.shape
    fx, fy = intrinsics[0, 0], intrinsics[1, 1]
    cx, cy = intrinsics[0, 2], intrinsics[1, 2]
    us, vs = np.meshgrid(np.arange(w), np.arange(h))
    z = depth
    x = (us - cx) * z / fx
    y = (vs - cy) * z / fy
    return np.stack([x, y, z], axis=-1)


def _camera_to_world(points_cam: np.ndarray, extrinsics: np.ndarray) -> np.ndarray:
    """(N, 3) camera-frame → world-frame, given world->camera extrinsics."""
    cam_to_world = np.linalg.inv(extrinsics)
    homog = np.concatenate(
        [points_cam, np.ones((points_cam.shape[0], 1))], axis=-1
    )
    world = homog @ cam_to_world.T
    return world[:, :3]


def _project(
    points_world: np.ndarray, camera: Camera
) -> tuple[np.ndarray, np.ndarray]:
    """Project (N, 3) world points to (N, 2) pixels and (N,) depths."""
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


@register("point_cloud")
class PointCloudMethod(Method):
    """Per-view depths unprojected into 3D, transformed to world frame
    via known extrinsics, concatenated, and (when Open3D is available)
    voxel-downsampled with statistical outlier removal.

    Trade signature: structural primitives are explicit and addressable;
    surfaces, normals, and connectivity are implicit at best. Cheapest
    method on the roster, with the strongest editability affordance.
    Weakness: thin and sub-pixel geometry collapses to noise; specular
    surfaces produce phantom points where depth is unreliable.
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        cfg = (
            config
            if isinstance(config, PointCloudConfig)
            else PointCloudConfig.model_validate(config.model_dump())
        )

        all_pts: list[np.ndarray] = []
        all_cols: list[np.ndarray] = []
        for cap in captures:
            if cap.depth is None:
                continue
            depth = cap.depth.astype(np.float64)
            mask = np.isfinite(depth) & (depth > 0) & (
                depth < cfg.background_depth_clip
            )
            if not mask.any():
                continue
            cam_points = _unproject(depth, cap.camera.intrinsics)
            pts = cam_points[mask]
            world_pts = _camera_to_world(pts, cap.camera.extrinsics)

            colors = cap.image.pixels[mask] if cap.image is not None else None

            if cfg.max_points_per_view and pts.shape[0] > cfg.max_points_per_view:
                rng = np.random.default_rng(0)
                idx = rng.choice(
                    pts.shape[0], cfg.max_points_per_view, replace=False
                )
                world_pts = world_pts[idx]
                if colors is not None:
                    colors = colors[idx]

            all_pts.append(world_pts)
            if colors is not None:
                all_cols.append(colors)

        if not all_pts:
            raise ValueError(
                "point_cloud.fit: no captures had usable depth maps."
            )

        points = np.concatenate(all_pts, axis=0)
        colors = (
            np.concatenate(all_cols, axis=0) if all_cols else None
        )

        points, colors = self._postprocess(points, colors, cfg)

        recon = PointCloudReconstruction(
            method_name=self.name,
            artifact_dir=Path("."),  # set by orchestrator
            metadata={
                "n_points": int(points.shape[0]),
                "n_views": len(captures),
                "voxel_size": cfg.voxel_size,
            },
            points=points,
            colors=colors,
        )
        return recon

    def _postprocess(
        self,
        points: np.ndarray,
        colors: Optional[np.ndarray],
        cfg: PointCloudConfig,
    ) -> tuple[np.ndarray, Optional[np.ndarray]]:
        try:
            import open3d as o3d
        except ImportError:
            return self._numpy_voxel_downsample(points, colors, cfg.voxel_size)

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        if colors is not None:
            pcd.colors = o3d.utility.Vector3dVector(colors)
        if cfg.voxel_size:
            pcd = pcd.voxel_down_sample(cfg.voxel_size)
        pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        out_points = np.asarray(pcd.points)
        out_colors = np.asarray(pcd.colors) if pcd.has_colors() else None
        return out_points, out_colors

    @staticmethod
    def _numpy_voxel_downsample(
        points: np.ndarray,
        colors: Optional[np.ndarray],
        voxel_size: Optional[float],
    ) -> tuple[np.ndarray, Optional[np.ndarray]]:
        if not voxel_size:
            return points, colors
        grid = np.floor(points / voxel_size).astype(np.int64)
        # Hash each grid cell, keep first occurrence.
        keys = grid[:, 0].astype(np.int64) * 73856093 ^ \
            grid[:, 1].astype(np.int64) * 19349663 ^ \
            grid[:, 2].astype(np.int64) * 83492791
        _, idx = np.unique(keys, return_index=True)
        idx.sort()
        return points[idx], (colors[idx] if colors is not None else None)

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        if not isinstance(reconstruction, PointCloudReconstruction):
            raise TypeError(
                f"PointCloudMethod.render expects PointCloudReconstruction, "
                f"got {type(reconstruction).__name__}"
            )
        H, W = camera.height, camera.width
        canvas = np.zeros((H, W, 3), dtype=np.float32)
        zbuf = np.full((H, W), np.inf, dtype=np.float64)

        pix, depths = _project(reconstruction.points, camera)
        valid = (
            (depths > 1e-6)
            & (pix[:, 0] >= 0)
            & (pix[:, 0] < W)
            & (pix[:, 1] >= 0)
            & (pix[:, 1] < H)
        )
        pix = pix[valid]
        depths = depths[valid]
        colors = (
            reconstruction.colors[valid]
            if reconstruction.colors is not None
            else np.full((pix.shape[0], 3), 0.5)
        )

        radius = 2  # default splat radius in pixels
        for (u, v), z, c in zip(pix, depths, colors):
            iu, iv = int(round(u)), int(round(v))
            for du in range(-radius, radius + 1):
                for dv in range(-radius, radius + 1):
                    x, y = iu + du, iv + dv
                    if 0 <= x < W and 0 <= y < H and z < zbuf[y, x]:
                        zbuf[y, x] = z
                        canvas[y, x] = c
        return Image(pixels=canvas)
