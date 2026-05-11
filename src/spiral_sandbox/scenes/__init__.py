"""Scene generators.

Every scene in the catalog shares the same Blender script
(`bunny.py` — the subject-on-floor template) and differs only in which
subject mesh it imports. The mesh comes from Open3D's bundled data
fixtures via `_subjects.resolve_subject_mesh`; that lookup is lazy
(Blender's bundled Python has no Open3D), so it runs in the
orchestrator before the Blender subprocess is launched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SceneSpec:
    name: str
    script_path: Path
    description: str
    # If set, names a subject in `_subjects.SUBJECTS`. The orchestrator
    # resolves it to a local mesh file and passes via --subject-mesh.
    subject: Optional[str] = None


_REGISTRY: dict[str, SceneSpec] = {}


def register_scene(spec: SceneSpec) -> SceneSpec:
    if spec.name in _REGISTRY:
        raise ValueError(f"Scene '{spec.name}' already registered")
    _REGISTRY[spec.name] = spec
    return spec


def get_scene(name: str) -> SceneSpec:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown scene '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_scenes() -> list[str]:
    return sorted(_REGISTRY)


# --- Built-ins ---

_HERE = Path(__file__).resolve().parent
_SCRIPT = _HERE / "bunny.py"

register_scene(
    SceneSpec(
        name="sphere_baseline",
        script_path=_SCRIPT,
        description=(
            "Smoke-test baseline: a checker-textured UV sphere on a "
            "textured plane. Builds from primitives, no external mesh."
        ),
        subject=None,
    )
)

# Stanford-style test meshes — same scaffolding, different subjects.
register_scene(
    SceneSpec(
        name="stanford_bunny",
        script_path=_SCRIPT,
        description=(
            "Stanford bunny — fine ear/foot relief. Canonical test mesh "
            "for geometric reconstruction quality."
        ),
        subject="stanford_bunny",
    )
)
register_scene(
    SceneSpec(
        name="knot",
        script_path=_SCRIPT,
        description=(
            "Torus knot — non-trivial topology (genus > 0). Tests where "
            "Poisson-on-cloud invents connectivity it can't actually see."
        ),
        subject="knot",
    )
)
register_scene(
    SceneSpec(
        name="monkey",
        script_path=_SCRIPT,
        description=(
            "Blender's Suzanne — sharp edges + hollow eye sockets. Tests "
            "whether methods preserve concavities or fill them in."
        ),
        subject="monkey",
    )
)
register_scene(
    SceneSpec(
        name="damaged_helmet",
        script_path=_SCRIPT,
        description=(
            "PBR helmet — fine surface relief with metallic/roughness "
            "texture. Expected case for gaussian-splat vs. mesh-method "
            "perceptual–structural divergence."
        ),
        subject="damaged_helmet",
    )
)


def blender_command(
    spec: SceneSpec,
    output_dir: Path,
    densities: list[str],
    seed: int,
    blender_bin: str = "blender",
    extra: list[str] | None = None,
) -> list[str]:
    """Build the headless-Blender command for a scene generator.

    Resolves the subject mesh path if the spec names one (lazily imports
    Open3D, which Blender's bundled Python lacks).
    """
    cmd = [
        blender_bin,
        "--background",
        "--python",
        str(spec.script_path),
        "--",
        "--output",
        str(output_dir),
        "--densities",
        ",".join(densities),
        "--seed",
        str(seed),
        "--scene-name",
        spec.name,
    ]
    if spec.subject:
        from ._subjects import resolve_subject_mesh
        mesh_path = resolve_subject_mesh(spec.subject)
        cmd.extend(["--subject-mesh", str(mesh_path)])
    if extra:
        cmd.extend(extra)
    return cmd


__all__ = [
    "SceneSpec",
    "blender_command",
    "get_scene",
    "list_scenes",
    "register_scene",
]
