"""Reconstruction methods.

Importing this package triggers all method registrations via the
side-effect imports below. After import, `get_method(name)` resolves a
config string into a Method instance.
"""

from .base import (
    Camera,
    Capture,
    GeometryExport,
    Image,
    Mesh,
    Method,
    MethodConfig,
    PointCloud,
    Reconstruction,
)
from .registry import get_method, list_methods, register

# Side-effect imports — each module registers its method on import.
from . import gaussian_splatting  # noqa: F401
from . import mvs  # noqa: F401
from . import nerf  # noqa: F401
from . import photogrammetry  # noqa: F401
from . import point_cloud  # noqa: F401
from . import sdf  # noqa: F401

__all__ = [
    "Camera",
    "Capture",
    "GeometryExport",
    "Image",
    "Mesh",
    "Method",
    "MethodConfig",
    "PointCloud",
    "Reconstruction",
    "get_method",
    "list_methods",
    "register",
]
