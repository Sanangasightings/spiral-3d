"""Scene generators. Each scene is a Blender script that runs headlessly.

Scenes registered here advertise the script the orchestrator should
launch in headless Blender. The methods layer reads the resulting
`SceneManifest` and never talks to Blender directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SceneSpec:
    name: str
    script_path: Path
    description: str


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

register_scene(
    SceneSpec(
        name="bunny_baseline",
        script_path=_HERE / "bunny.py",
        description=(
            "Baseline scene: subdivided UV sphere (or Stanford bunny if "
            "--bunny-ply is supplied) on a textured plane with one area light."
        ),
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
    """Build the headless-Blender command for a scene generator."""
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
    ]
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
