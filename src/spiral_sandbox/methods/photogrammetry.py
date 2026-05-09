"""Structure-from-motion + Poisson meshing + texture baking."""

from __future__ import annotations

from .base import Camera, Capture, Image, Method, MethodConfig, Reconstruction
from .registry import register


@register("photogrammetry")
class PhotogrammetryMethod(Method):
    """COLMAP runs feature detection, matching, and incremental SfM on
    the source images to recover a sparse cloud and refined camera
    poses. The sparse cloud is fed into Poisson surface reconstruction
    (via Open3D) to produce a watertight triangle mesh, and a texture
    atlas is baked from the source views projected onto the mesh.

    Trade signature: surfaces are explicit, meshable, and slot directly
    into standard 3D pipelines — strong downstream affordance for
    editing and asset reuse. Specular and featureless regions starve
    SfM of correspondences and collapse into geometry holes; thin
    structures get filled in or smoothed away by Poisson.

    Implemented in Phase 7 (after the point-cloud smoke test).
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        raise NotImplementedError("PhotogrammetryMethod.fit lands in Phase 7.")

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        raise NotImplementedError("PhotogrammetryMethod.render lands in Phase 7.")
