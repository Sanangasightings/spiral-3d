"""End-to-end orchestrator test without Blender.

Synthesize a minimal (scene_manifest, capture_manifest, ground-truth
mesh, rendered images, depth maps) on disk, point a RunConfig at it,
and invoke the inner _run_one_method loop. Verify the SQLite results
store ends up with a chamfer + psnr value for the point_cloud method.

The non-trivial pieces this exercises:

- artifact persistence (`save_reconstruction` writes points.npz + metadata)
- chamfer math against a real-but-tiny OBJ
- psnr math through the splat renderer
- the orchestrator's per-method try/except behaviour for unimplemented
  methods (NotImplementedError → skip, not crash)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image as PILImage

from spiral_sandbox.io.config import (
    MetricsConfig,
    OutputConfig,
    RunConfig,
    SceneEntry,
)
from spiral_sandbox.io.manifest import (
    CameraPose,
    CaptureManifest,
    LightSpec,
    RenderedView,
    SceneManifest,
)
from spiral_sandbox.io.results_db import ResultsDB
from spiral_sandbox.methods import MethodConfig
from spiral_sandbox.pipeline import build_ground_truth, split_holdout
from spiral_sandbox.capture import load_capture
from spiral_sandbox.run import _Counters, _run_one_method


def _identity_intrinsics(width=64, height=64, fx=64.0):
    return [
        [fx, 0, width / 2],
        [0, fx, height / 2],
        [0, 0, 1.0],
    ]


def _identity_extrinsics(dx=0.0):
    return [
        [1, 0, 0, -dx],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ]


def _write_synthetic_scene(scene_dir: Path) -> Path:
    """Build a 1-quad ground-truth mesh + a SceneManifest pointing at it."""
    scene_dir.mkdir(parents=True, exist_ok=True)
    obj = scene_dir / "ground_truth.obj"
    obj.write_text(
        "v -1 -1 2\nv 1 -1 2\nv 1 1 2\nv -1 1 2\nf 1 2 3\nf 1 3 4\n",
        encoding="utf-8",
    )

    poses = []
    for i, dx in enumerate([0.0, 0.3, -0.3]):
        poses.append(
            CameraPose(
                pose_id=f"medium_{i:03d}",
                extrinsics=_identity_extrinsics(dx),
                intrinsics=_identity_intrinsics(),
                width=64,
                height=64,
            )
        )

    SceneManifest(
        name="planar_synth",
        version=1,
        blend_path="(synthetic, no blend)",
        ground_truth_mesh=obj.name,
        cameras={"medium": poses},
        lights=[
            LightSpec(name="key", kind="area", location=[0, 0, 5], energy=1000)
        ],
        notes="synthesized for the orchestrator end-to-end test",
    ).write(scene_dir / "manifest.json")
    return scene_dir / "manifest.json"


def _write_synthetic_captures(
    scene_manifest_path: Path, capture_dir: Path
) -> Path:
    """Render flat-grey images and constant z=2 depth maps for each pose."""
    capture_dir.mkdir(parents=True, exist_ok=True)
    rgb_dir = capture_dir / "rgb"
    depth_dir = capture_dir / "depth"
    rgb_dir.mkdir(exist_ok=True)
    depth_dir.mkdir(exist_ok=True)

    sm = SceneManifest.read(scene_manifest_path)
    poses = sm.cameras["medium"]

    views: list[RenderedView] = []
    for pose in poses:
        rgb = (np.full((pose.height, pose.width, 3), 0.5) * 255).astype(np.uint8)
        rgb_path = rgb_dir / f"{pose.pose_id}.png"
        PILImage.fromarray(rgb).save(rgb_path)

        depth = np.full((pose.height, pose.width), 2.0, dtype=np.float32)
        depth_path = depth_dir / f"{pose.pose_id}.npy"
        np.save(depth_path, depth)

        views.append(
            RenderedView(
                pose_id=pose.pose_id,
                image_path=str(rgb_path.relative_to(capture_dir)),
                depth_path=str(depth_path.relative_to(capture_dir)),
                camera=pose,
            )
        )

    CaptureManifest(
        scene=sm.name,
        density="medium",
        blend_path=sm.blend_path,
        ground_truth_mesh=str(scene_manifest_path.parent / sm.ground_truth_mesh),
        width=poses[0].width,
        height=poses[0].height,
        views=views,
        seed=42,
    ).write(capture_dir / "captures.json")
    return capture_dir / "captures.json"


@pytest.fixture
def synthetic_run(tmp_path, monkeypatch):
    """Patch capture._read_depth_exr to load .npy depth so we don't need
    OpenEXR for the test-only path."""
    from spiral_sandbox import capture as capture_pkg

    def _read_npy_depth(path: Path) -> np.ndarray:
        return np.load(path)

    monkeypatch.setattr(capture_pkg, "_read_depth_exr", _read_npy_depth)
    return tmp_path


def test_full_orchestrator_inner_loop(synthetic_run):
    tmp = synthetic_run
    scene_dir = tmp / "scenes" / "planar_synth"
    scene_manifest_path = _write_synthetic_scene(scene_dir)

    cap_dir = tmp / "captures" / "planar_synth" / "medium"
    cap_manifest = _write_synthetic_captures(scene_manifest_path, cap_dir)

    captures = load_capture(cap_manifest)
    train, held = split_holdout(captures, n_holdout=1)
    gt = build_ground_truth(scene_manifest_path, held)

    config = RunConfig(
        seed=42,
        scenes=[SceneEntry(name="planar_synth", densities=["medium"])],
        methods=["point_cloud", "nerf"],  # nerf must be skipped, not crash
        metrics=MetricsConfig(geometric=["chamfer"], visual=["psnr"]),
        output=OutputConfig(
            results_db=tmp / "results/spiral.db",
            artifacts_dir=tmp / "results/artifacts",
            figures_dir=tmp / "results/figures",
            scenes_dir=tmp / "scenes",
            captures_dir=tmp / "captures",
        ),
    )

    db = ResultsDB(config.output.results_db)
    run_id = db.begin_run()

    counters = _Counters()
    for method_name in config.methods:
        _run_one_method(
            db=db,
            run_id=run_id,
            config=config,
            scene_name="planar_synth",
            density="medium",
            method_name=method_name,
            captures_train=train,
            gt=gt,
            counters=counters,
        )

    assert counters.fits == 1, "point_cloud should have fit"
    assert counters.fit_skipped == 1, "nerf is a stub, should skip"
    chamfer = db.query_metric("planar_synth", "medium", "point_cloud", "chamfer")
    psnr = db.query_metric("planar_synth", "medium", "point_cloud", "psnr")
    assert chamfer is not None and chamfer < 0.5, (
        f"Chamfer between flat depth-fused points and a planar GT should "
        f"be small, got {chamfer}"
    )
    assert psnr is not None, "PSNR row should be present"
