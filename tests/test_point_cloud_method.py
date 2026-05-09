"""Synthetic depth-fusion test for the point cloud method.

We construct two captures of a known plane at z=2 (in world frame) from
two known cameras, hand a clean depth map to each, and verify that
fitting reproduces the plane within a tight tolerance. This exercises
the full unproject + cam-to-world transform path without needing
Blender or Open3D.
"""

from __future__ import annotations

import numpy as np
import pytest

from spiral_sandbox.methods import MethodConfig, get_method
from spiral_sandbox.methods.base import Camera, Capture, Image
from spiral_sandbox.methods.point_cloud import (
    PointCloudConfig,
    PointCloudMethod,
    PointCloudReconstruction,
)


def _identity_camera(width=64, height=64, fx=64.0):
    K = np.array([[fx, 0, width / 2], [0, fx, height / 2], [0, 0, 1.0]])
    Rt = np.eye(4)  # camera at origin, looking down +Z (OpenCV convention)
    return Camera(intrinsics=K, extrinsics=Rt, width=width, height=height)


def _shifted_camera(width=64, height=64, fx=64.0, dx=0.5):
    K = np.array([[fx, 0, width / 2], [0, fx, height / 2], [0, 0, 1.0]])
    Rt = np.eye(4)
    Rt[0, 3] = -dx  # world->camera: camera at world x=+dx → translation -dx
    return Camera(intrinsics=K, extrinsics=Rt, width=width, height=height)


def _flat_capture(camera, depth_value=2.0):
    H, W = camera.height, camera.width
    depth = np.full((H, W), depth_value, dtype=np.float32)
    rgb = np.full((H, W, 3), 0.5, dtype=np.float32)
    return Capture(image=Image(pixels=rgb), camera=camera, depth=depth)


def test_fit_recovers_planar_depth():
    cap1 = _flat_capture(_identity_camera())
    cap2 = _flat_capture(_shifted_camera())
    method = get_method("point_cloud")
    cfg = PointCloudConfig(voxel_size=None, max_points_per_view=10_000)
    recon = method.fit([cap1, cap2], cfg)

    assert isinstance(recon, PointCloudReconstruction)
    assert recon.points.shape[0] > 0

    # Every point should sit on the z=2 plane within numerical noise.
    z = recon.points[:, 2]
    assert np.allclose(z, 2.0, atol=1e-5)


def test_render_z_buffer_picks_nearest():
    """Build a recon with two points at the same pixel but different
    depths; the renderer must keep the nearer color."""
    method = PointCloudMethod()
    pts = np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 2.0]])
    colors = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    recon = PointCloudReconstruction(
        method_name="point_cloud",
        artifact_dir=__import__("pathlib").Path("."),
        metadata={},
        points=pts,
        colors=colors,
    )
    cam = _identity_camera()
    img = method.render(recon, cam)
    cx, cy = cam.width // 2, cam.height // 2
    # Center pixel should be red (the nearer point) — splat radius=2.
    assert img.pixels[cy, cx, 0] == pytest.approx(1.0)
    assert img.pixels[cy, cx, 2] == pytest.approx(0.0)


def test_fit_raises_when_no_depth():
    cam = _identity_camera()
    cap = Capture(
        image=Image(pixels=np.zeros((4, 4, 3), dtype=np.float32)),
        camera=cam,
        depth=None,
    )
    method = get_method("point_cloud")
    with pytest.raises(ValueError):
        method.fit([cap], MethodConfig())
