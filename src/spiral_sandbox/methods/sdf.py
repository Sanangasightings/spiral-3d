"""Neural signed distance function via nerfstudio (neus-facto)."""

from __future__ import annotations

from .base import Camera, Capture, Image, Method, MethodConfig, Reconstruction
from .registry import register


@register("sdf")
class SDFMethod(Method):
    """An implicit surface represented as a learned signed distance
    function — an MLP from world position to signed distance — paired
    with a small radiance head for appearance. Trained on posed images
    via volumetric rendering with an SDF-derived density (NeuS / VolSDF
    family). nerfstudio's neus-facto is the working backend.

    Trade signature: produces the cleanest watertight surface among the
    neural methods — sphere tracing or marching cubes both yield a
    usable mesh. Volumetric and view-dependent appearance is harder to
    capture than NeRF's free-form radiance field. Strong on the
    geometric fidelity axis, middling on visual fidelity, and the best
    bridge between neural reconstruction and the standard mesh pipeline.

    Implemented in Phase 7.
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        raise NotImplementedError("SDFMethod.fit lands in Phase 7.")

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        raise NotImplementedError("SDFMethod.render lands in Phase 7.")
