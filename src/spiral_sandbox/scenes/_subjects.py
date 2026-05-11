"""Resolve a subject-mesh name to a local file path.

Each subject is one of Open3D's bundled data fixtures. First lookup
downloads via the Open3D CDN; subsequent lookups read from
`~/open3d_data/`. The mesh formats are mixed (PLY / OBJ / GLB / glTF);
the Blender side dispatches by extension.

This module imports Open3D at function level so the scenes package
stays importable in Blender's bundled Python (which has no Open3D).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubjectSource:
    name: str
    open3d_class: str  # name on `o3d.data`
    description: str


SUBJECTS: dict[str, SubjectSource] = {
    "stanford_bunny": SubjectSource(
        "stanford_bunny", "BunnyMesh",
        "Stanford bunny — fine ear/foot relief, the canonical test mesh.",
    ),
    "armadillo": SubjectSource(
        "armadillo", "ArmadilloMesh",
        "Stanford armadillo — complex skin folds, sharp creases.",
    ),
    "knot": SubjectSource(
        "knot", "KnotMesh",
        "Torus knot — non-trivial topology, tests genus and connectivity.",
    ),
    "monkey": SubjectSource(
        "monkey", "MonkeyModel",
        "Blender's Suzanne — sharp edges, hollow eye sockets.",
    ),
    "crate": SubjectSource(
        "crate", "CrateModel",
        "Wooden crate — flat planes plus texture, baseline for sharp corners.",
    ),
    "avocado": SubjectSource(
        "avocado", "AvocadoModel",
        "glTF avocado — PBR textures, real-world subsurface look.",
    ),
    "damaged_helmet": SubjectSource(
        "damaged_helmet", "DamagedHelmetModel",
        "PBR helmet — fine surface detail with metallic/roughness texture; "
        "the case where gaussian splatting is expected to outperform "
        "mesh-based methods.",
    ),
    "flight_helmet": SubjectSource(
        "flight_helmet", "FlightHelmetModel",
        "Multi-part glTF — separable primitives, tests downstream "
        "affordance (mesh export quality).",
    ),
    "sword": SubjectSource(
        "sword", "SwordModel",
        "Long, thin sword — elongated geometry, tests methods on "
        "high-aspect-ratio subjects.",
    ),
}


def resolve_subject_mesh(name: str) -> Path:
    """Return a local Path to the subject's mesh file. Downloads on
    first call; cached on subsequent calls."""
    if name not in SUBJECTS:
        raise KeyError(
            f"Unknown subject '{name}'. Known: {sorted(SUBJECTS)}"
        )
    import open3d as o3d  # heavy; lazy

    src = SUBJECTS[name]
    cls = getattr(o3d.data, src.open3d_class)
    return Path(cls().path)
