"""Neural radiance field via nerfstudio (nerfacto)."""

from __future__ import annotations

from .base import Camera, Capture, Image, Method, MethodConfig, Reconstruction
from .registry import register


@register("nerf")
class NerfMethod(Method):
    """A continuous radiance field — an MLP from (position, view
    direction) to (color, density) — fit to the posed source images
    via differentiable volumetric ray marching. Rendering at a novel
    camera marches rays through the field and integrates color along
    each ray. nerfstudio's nerfacto implementation is the working
    backend; the optional `gpu` extras pull it in.

    Trade signature: visual fidelity is high and includes view-dependent
    effects that mesh-based methods erase. Geometry is implicit —
    extracting a mesh requires marching cubes on the density field and
    the result is noisy. Primitives are not addressable: the entire
    scene is a single learned function. The canonical companion to
    Gaussian splatting in the perceptual–structural divergence test
    (H3).

    Implemented in Phase 7.
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        raise NotImplementedError("NerfMethod.fit lands in Phase 7.")

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        raise NotImplementedError("NerfMethod.render lands in Phase 7.")
