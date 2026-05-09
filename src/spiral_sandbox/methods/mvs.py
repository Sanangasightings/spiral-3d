"""Multi-view stereo dense reconstruction."""

from __future__ import annotations

from .base import Camera, Capture, Image, Method, MethodConfig, Reconstruction
from .registry import register


@register("mvs")
class MVSMethod(Method):
    """Per-pixel depth recovered from photometric consistency across
    calibrated source views — COLMAP dense or OpenMVS — and fused into
    a single dense point cloud. Same family as the point_cloud method
    but driven by image consistency rather than rendered ground-truth
    depth, so it produces depth where photogrammetry produces a sparse
    cloud.

    Trade signature: dense surface samples without an explicit surface;
    sits between the point_cloud and photogrammetry methods on the
    affordance axis. Weakness: transparent and specular regions violate
    the photometric-consistency assumption and produce systematic
    failures rather than uniform noise.

    Implemented in Phase 7.
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        raise NotImplementedError("MVSMethod.fit lands in Phase 7.")

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        raise NotImplementedError("MVSMethod.render lands in Phase 7.")
