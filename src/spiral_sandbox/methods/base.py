"""Reconstruction method interface.

Every method in the sandbox traverses the same abstract spiral:

    captures (2D images + camera poses) -> Reconstruction (n-D representation)

The shape of that traversal — how the trade is paid, what affordances
survive, where the error topology concentrates — is the method's
signature. The interface defined here is what the rest of the pipeline
talks to; the per-method files in this package are the paths.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
from pydantic import BaseModel, ConfigDict


@dataclass
class Camera:
    """Pinhole camera with intrinsics and world-to-camera extrinsics."""

    intrinsics: np.ndarray  # (3, 3)
    extrinsics: np.ndarray  # (4, 4) world-to-camera
    width: int
    height: int


@dataclass
class Image:
    """Rendered image. (H, W, 3) RGB, float32 in [0, 1] or uint8."""

    pixels: np.ndarray


@dataclass
class Capture:
    """One viewpoint of a scene fed to a Method."""

    image: Image
    camera: Camera
    depth: Optional[np.ndarray] = None  # (H, W), NaN where unknown


@dataclass
class Mesh:
    vertices: np.ndarray            # (V, 3)
    faces: np.ndarray               # (F, 3) int
    vertex_normals: Optional[np.ndarray] = None
    vertex_colors: Optional[np.ndarray] = None


@dataclass
class PointCloud:
    points: np.ndarray              # (N, 3)
    normals: Optional[np.ndarray] = None
    colors: Optional[np.ndarray] = None


GeometryExport = Union[Mesh, PointCloud, None]


class MethodConfig(BaseModel):
    """Base config for a method run. Subclass to add method-specific knobs."""

    model_config = ConfigDict(extra="allow")


@dataclass
class Reconstruction:
    """Output of `Method.fit`.

    Carries an artifact directory (where the underlying representation
    lives on disk), a metadata dict the metrics layer reads from, and a
    `geometry_export` hook for methods that can emit a mesh or point
    cloud. Methods whose native representation isn't a surface (e.g.
    NeRF, Gaussians) return `None` here unless an extraction step has
    been run.
    """

    method_name: str
    artifact_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    def geometry_export(self) -> GeometryExport:
        raise NotImplementedError(
            f"{self.method_name} has no geometry_export wired yet."
        )


class Method(ABC):
    """Abstract reconstruction method.

    Concrete subclasses implement one path through the spiral. Each is
    registered by name via `methods.registry.register(...)` so the
    pipeline can resolve it from a config string.
    """

    name: str = ""  # set by the @register decorator

    @abstractmethod
    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        """Run the method on a set of captures and return a Reconstruction."""

    @abstractmethod
    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        """Render a novel view from the reconstruction at the given camera."""
