"""3D Gaussian splatting via gsplat."""

from __future__ import annotations

from .base import Camera, Capture, Image, Method, MethodConfig, Reconstruction
from .registry import register


@register("gaussian_splatting")
class GaussianSplattingMethod(Method):
    """A set of anisotropic 3D Gaussians — each with position,
    covariance, opacity, and (typically spherical-harmonic) color — fit
    to the posed source images by differentiable splatting onto image
    planes and gradient-descent on per-Gaussian parameters. gsplat is
    the working backend; the optional `gpu` extras pull it in.

    Trade signature: visual fidelity competitive with NeRF at far
    cheaper render cost. Primitives are addressable Gaussians, but they
    do not form a surface and individual Gaussian semantics are weak.
    Stronger render-time affordance than NeRF; weaker mesh-export
    affordance than photogrammetry. The other half of the H3 perceptual–
    structural divergence test.

    Implemented in Phase 7.
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        raise NotImplementedError(
            "GaussianSplattingMethod.fit lands in Phase 7."
        )

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        raise NotImplementedError(
            "GaussianSplattingMethod.render lands in Phase 7."
        )
