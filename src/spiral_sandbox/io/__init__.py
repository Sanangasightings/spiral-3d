"""Persistence layer.

`io.manifest` is stdlib-only by design so the Blender-side scripts can
import it from inside Blender's bundled Python (which does not have
pydantic / pyyaml). `io.config` and `io.results_db` are pipeline-side
only — import them directly via their full path when needed:

    from spiral_sandbox.io.config import RunConfig
    from spiral_sandbox.io.results_db import ResultsDB
"""

from .manifest import (
    CameraPose,
    CaptureManifest,
    LightSpec,
    RenderedView,
    SceneManifest,
)

__all__ = [
    "CameraPose",
    "CaptureManifest",
    "LightSpec",
    "RenderedView",
    "SceneManifest",
]
