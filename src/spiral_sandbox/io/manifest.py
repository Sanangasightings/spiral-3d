"""Stdlib-only manifest schemas.

These dataclasses describe the JSON shape produced by the Blender-side
scene generators and capture renderers, and consumed by every method.
Stdlib-only so the same module can be imported from inside Blender's
bundled Python (which does not have pydantic).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class CameraPose:
    """One camera, world-to-camera 4x4 + intrinsics in pixels."""

    pose_id: str
    extrinsics: list[list[float]]  # 4x4 row-major, world->camera
    intrinsics: list[list[float]]  # 3x3 row-major, pixel units
    width: int
    height: int


@dataclass
class LightSpec:
    name: str
    kind: str  # "area", "point", "sun"
    location: list[float]
    energy: float
    color: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneManifest:
    """Sits next to a generated `.blend` describing what's inside."""

    name: str
    version: int
    blend_path: str
    ground_truth_mesh: str  # OBJ or PLY path, relative to manifest
    cameras: dict[str, list[CameraPose]]  # density -> list of poses
    lights: list[LightSpec]
    notes: str = ""

    def write(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "SceneManifest":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        cameras = {
            density: [CameraPose(**c) for c in poses]
            for density, poses in raw["cameras"].items()
        }
        lights = [LightSpec(**l) for l in raw["lights"]]
        return cls(
            name=raw["name"],
            version=raw["version"],
            blend_path=raw["blend_path"],
            ground_truth_mesh=raw["ground_truth_mesh"],
            cameras=cameras,
            lights=lights,
            notes=raw.get("notes", ""),
        )


@dataclass
class RenderedView:
    """One rendered viewpoint on disk."""

    pose_id: str
    image_path: str          # relative to capture manifest
    depth_path: Optional[str] = None
    camera: Optional[CameraPose] = None  # filled in by load step


@dataclass
class CaptureManifest:
    """Describes a (scene, density) capture set on disk."""

    scene: str
    density: str
    blend_path: str
    ground_truth_mesh: str
    width: int
    height: int
    views: list[RenderedView]
    seed: int = 42

    def write(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "CaptureManifest":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        views = []
        for v in raw["views"]:
            cam = CameraPose(**v["camera"]) if v.get("camera") else None
            views.append(
                RenderedView(
                    pose_id=v["pose_id"],
                    image_path=v["image_path"],
                    depth_path=v.get("depth_path"),
                    camera=cam,
                )
            )
        return cls(
            scene=raw["scene"],
            density=raw["density"],
            blend_path=raw["blend_path"],
            ground_truth_mesh=raw["ground_truth_mesh"],
            width=raw["width"],
            height=raw["height"],
            views=views,
            seed=raw.get("seed", 42),
        )
