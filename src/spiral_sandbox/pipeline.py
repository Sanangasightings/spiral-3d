"""Pipeline helpers: stage gating, artifact persistence, holdout split.

The orchestrator in `run.py` calls into here. Every helper is idempotent
in the "skip if output already exists" sense, so a re-run resumes
cleanly.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import numpy as np

from .io.manifest import SceneManifest
from .methods.base import Capture, Mesh, PointCloud, Reconstruction
from .scenes import SceneSpec, blender_command


log = logging.getLogger("spiral_sandbox.pipeline")


# ----- Stage A: scene generation -----

def ensure_scene(
    spec: SceneSpec,
    scene_dir: Path,
    densities: list[str],
    seed: int,
    blender_bin: str = "blender",
) -> Path:
    """Ensure `<scene_dir>/manifest.json` exists AND covers `densities`.

    A cached manifest from an earlier run with a narrower density list
    triggers regeneration — otherwise the capture step would silently
    skip the missing densities.
    """
    manifest_path = scene_dir / "manifest.json"
    if manifest_path.exists():
        manifest = SceneManifest.read(manifest_path)
        missing = [d for d in densities if d not in manifest.cameras]
        if not missing:
            log.info("scene cached: %s", manifest_path)
            return manifest_path
        log.info(
            "scene manifest missing densities %s, regenerating", missing
        )

    scene_dir.mkdir(parents=True, exist_ok=True)
    cmd = blender_command(spec, scene_dir, densities, seed, blender_bin)
    log.info("running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Could not invoke '{blender_bin}'. Install Blender and put it "
            f"on PATH, or pass --blender-bin to run.py. Underlying: {exc}"
        ) from exc
    if not manifest_path.exists():
        raise RuntimeError(
            f"Blender exited 0 but {manifest_path} was not produced."
        )
    return manifest_path


# ----- Stage B: capture rendering -----

def ensure_captures(
    scene_manifest_path: Path,
    capture_dir: Path,
    densities: list[str],
    blender_bin: str = "blender",
) -> dict[str, Path]:
    """Ensure each density's `captures.json` exists. Returns a dict
    mapping density -> manifest path."""
    needed: list[str] = []
    out: dict[str, Path] = {}
    for d in densities:
        cap_manifest = capture_dir / d / "captures.json"
        if cap_manifest.exists():
            log.info("captures cached: %s", cap_manifest)
            out[d] = cap_manifest
        else:
            needed.append(d)

    if needed:
        # Launch the capture render driver inside Blender, opening the
        # already-generated .blend.
        from . import capture as capture_pkg  # for path lookup
        scene_manifest = SceneManifest.read(scene_manifest_path)
        blend_path = scene_manifest_path.parent / scene_manifest.blend_path

        render_script = Path(capture_pkg.__file__).parent / "render.py"
        cmd = [
            blender_bin,
            "--background",
            str(blend_path),
            "--python",
            str(render_script),
            "--",
            "--manifest",
            str(scene_manifest_path),
            "--output",
            str(capture_dir),
            "--densities",
            ",".join(needed),
        ]
        log.info("running: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Could not invoke '{blender_bin}'. Install Blender and put "
                f"it on PATH. Underlying: {exc}"
            ) from exc
        for d in needed:
            cap_manifest = capture_dir / d / "captures.json"
            if not cap_manifest.exists():
                raise RuntimeError(
                    f"Blender exited 0 but {cap_manifest} was not produced."
                )
            out[d] = cap_manifest
    return out


# ----- Stage C: holdout split -----

def split_holdout(
    captures: list[Capture], n_holdout: int = 1
) -> tuple[list[Capture], list[Capture]]:
    """Split captures into (training, held-out). Held-out are spaced
    evenly through the trajectory so they exercise novel-view metrics."""
    n = len(captures)
    if n_holdout >= n:
        raise ValueError(
            f"Asked for {n_holdout} held-out from {n} captures; refusing."
        )
    holdout_idx = set(
        int(round(i * n / max(n_holdout, 1)))
        for i in range(n_holdout)
    )
    holdout_idx = {min(i, n - 1) for i in holdout_idx}
    train = [c for i, c in enumerate(captures) if i not in holdout_idx]
    held = [c for i, c in enumerate(captures) if i in holdout_idx]
    return train, held


# ----- Stage D: artifact persistence -----

def save_reconstruction(
    recon: Reconstruction, artifact_dir: Path
) -> Reconstruction:
    """Write the reconstruction to disk. Updates `recon.artifact_dir`."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    recon.artifact_dir = artifact_dir

    # Always write metadata.
    (artifact_dir / "metadata.json").write_text(
        json.dumps(
            {"method_name": recon.method_name, **recon.metadata}, indent=2
        ),
        encoding="utf-8",
    )

    # Method-specific dumps.
    geom = None
    try:
        geom = recon.geometry_export()
    except NotImplementedError:
        geom = None

    if isinstance(geom, PointCloud):
        np.savez(
            artifact_dir / "points.npz",
            points=geom.points.astype(np.float32),
            colors=(
                geom.colors.astype(np.float32)
                if geom.colors is not None
                else np.zeros((0, 3), dtype=np.float32)
            ),
        )
    elif isinstance(geom, Mesh):
        _write_mesh_obj(geom, artifact_dir / "mesh.obj")
    return recon


def _write_mesh_obj(mesh: Mesh, out_path: Path) -> None:
    """Write a minimal `v` / `f` OBJ for the reconstructed mesh. Matches
    the format the metrics layer's mesh_io can read back."""
    lines: list[str] = []
    for v in mesh.vertices:
        lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    for f in mesh.faces:
        lines.append(f"f {int(f[0]) + 1} {int(f[1]) + 1} {int(f[2]) + 1}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----- Stage E: ground-truth bundle -----

def build_ground_truth(
    scene_manifest_path: Path,
    held_out: list[Capture],
):
    from .metrics import GroundTruth

    scene_manifest = SceneManifest.read(scene_manifest_path)
    return GroundTruth(
        mesh_path=scene_manifest_path.parent / scene_manifest.ground_truth_mesh,
        held_out_renders=[c.image.pixels for c in held_out],
        held_out_cameras=[c.camera for c in held_out],
    )


__all__ = [
    "build_ground_truth",
    "ensure_captures",
    "ensure_scene",
    "save_reconstruction",
    "split_holdout",
]
