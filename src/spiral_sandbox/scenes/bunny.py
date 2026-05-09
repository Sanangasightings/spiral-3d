"""Bunny baseline scene generator.

Designed to run inside headless Blender:

    blender --background --python src/spiral_sandbox/scenes/bunny.py -- \
        --output scenes/bunny_baseline \
        --densities sparse,medium,dense \
        --seed 42 \
        [--bunny-ply path/to/bunny.ply]

Outputs:

    <output>/bunny_baseline.blend
    <output>/ground_truth.obj
    <output>/manifest.json     # SceneManifest

The "bunny" mesh defaults to a high-resolution subdivided UV sphere so
the script runs without external assets — the Stanford bunny .ply can be
swapped in via --bunny-ply once Zach has it on disk. The scene is a
single mesh on a textured plane lit by one area light: well-conditioned
input, the baseline against which every other scene's stress test reads.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import asdict
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Add the project's `src/` to sys.path so we can import the manifest
    schema even when Blender's bundled Python is the active interpreter."""
    here = Path(__file__).resolve()
    src = here.parents[2]
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


_ensure_src_on_path()


def _split_args() -> list[str]:
    """Blender runs us as `blender ... -- <our args>`. Take the tail."""
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return sys.argv[1:]


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bunny_scene")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--densities", type=str, default="sparse,medium,dense")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--bunny-ply", type=Path, default=None)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    return p.parse_args(_split_args())


DENSITY_VIEWS = {"sparse": 8, "medium": 24, "dense": 64}


def _density_count(name: str) -> int:
    if name not in DENSITY_VIEWS:
        raise ValueError(f"Unknown density '{name}'. Valid: {list(DENSITY_VIEWS)}")
    return DENSITY_VIEWS[name]


def _intrinsics_from_blender(camera, width: int, height: int) -> list[list[float]]:
    """Convert a Blender camera into a 3x3 pixel-units intrinsics matrix."""
    cam = camera.data
    sensor_w = cam.sensor_width
    sensor_h = cam.sensor_height if cam.sensor_height > 0 else sensor_w * height / width
    fx = (cam.lens / sensor_w) * width
    fy = (cam.lens / sensor_h) * height
    cx = width / 2.0
    cy = height / 2.0
    return [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]]


def _world_to_camera(camera) -> list[list[float]]:
    """4x4 world-to-camera (Blender camera looks down -Z, +Y up).

    Blender's `matrix_world` is camera-to-world. We invert and flip the
    axis convention from OpenGL (Blender) to OpenCV (the convention every
    reconstruction library expects): keep X right, flip Y down, flip Z
    forward.
    """
    import mathutils  # bpy-bundled

    m = camera.matrix_world.inverted()
    flip = mathutils.Matrix(
        ((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1))
    )
    m = flip @ m
    return [list(row) for row in m]


def _build_scene(args: argparse.Namespace):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.engine = "CYCLES"
    # 16 samples is fine for our flat-lit baseline; bump for paper figures.
    scene.cycles.samples = 16

    # --- Subject ---
    if args.bunny_ply and args.bunny_ply.exists():
        bpy.ops.wm.ply_import(filepath=str(args.bunny_ply))
        subject = bpy.context.selected_objects[0]
        subject.name = "bunny"
        # Normalize size and place at origin.
        max_dim = max(subject.dimensions)
        if max_dim > 0:
            scale = 1.0 / max_dim
            subject.scale = (scale, scale, scale)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        subject.location = (0.0, 0.0, 0.5)
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=64, ring_count=32, radius=0.5, location=(0.0, 0.0, 0.5)
        )
        subject = bpy.context.active_object
        subject.name = "bunny"
        # Catmull-Clark subdivision for curvature stress.
        mod = subject.modifiers.new("subdiv", "SUBSURF")
        mod.levels = 2
        mod.render_levels = 3

    # --- Floor with checker texture ---
    bpy.ops.mesh.primitive_plane_add(size=4.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.active_object
    floor.name = "floor"
    mat = bpy.data.materials.new("floor_mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    checker = mat.node_tree.nodes.new("ShaderNodeTexChecker")
    checker.inputs["Scale"].default_value = 8.0
    mat.node_tree.links.new(bsdf.inputs["Base Color"], checker.outputs["Color"])
    floor.data.materials.append(mat)

    # --- Light ---
    bpy.ops.object.light_add(type="AREA", location=(2.0, -2.0, 4.0))
    light = bpy.context.active_object
    light.data.energy = 1500.0
    light.data.size = 2.0

    # --- Camera (created once, animated for each pose at render time) ---
    bpy.ops.object.camera_add(location=(2.5, -2.5, 1.5))
    cam = bpy.context.active_object
    cam.name = "cam"
    scene.camera = cam

    return scene, subject, floor, light, cam


def _orbit_pose(cam, angle_rad: float, radius: float, height: float, jitter: float, rng: random.Random):
    import mathutils

    jx = (rng.random() - 0.5) * jitter
    jy = (rng.random() - 0.5) * jitter
    jz = (rng.random() - 0.5) * jitter * 0.5
    cam.location = (
        math.cos(angle_rad) * radius + jx,
        math.sin(angle_rad) * radius + jy,
        height + jz,
    )
    direction = mathutils.Vector((0.0, 0.0, 0.5)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _collect_cameras(args, scene, cam) -> dict[str, list]:
    from spiral_sandbox.io.manifest import CameraPose

    rng = random.Random(args.seed)
    cameras: dict[str, list] = {}
    for density in args.densities.split(","):
        density = density.strip()
        if not density:
            continue
        n = _density_count(density)
        poses = []
        for i in range(n):
            angle = (i / n) * math.tau
            _orbit_pose(cam, angle, radius=2.5, height=1.2, jitter=0.05, rng=rng)
            scene.frame_set(i)  # forces matrix_world refresh
            poses.append(
                CameraPose(
                    pose_id=f"{density}_{i:03d}",
                    extrinsics=_world_to_camera(cam),
                    intrinsics=_intrinsics_from_blender(cam, args.width, args.height),
                    width=args.width,
                    height=args.height,
                )
            )
        cameras[density] = poses
    return cameras


def _export_ground_truth(objects, out_path: Path) -> None:
    """Export the listed mesh objects as a single OBJ — the union the
    methods are reconstructing. Excluding any object would create a
    Chamfer asymmetry between predicted and ground-truth coverage."""
    import bpy

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.wm.obj_export(
        filepath=str(out_path),
        export_selected_objects=True,
        export_uv=False,
        export_materials=False,
    )


def main() -> int:
    args = _parse()
    args.output.mkdir(parents=True, exist_ok=True)

    import bpy
    from spiral_sandbox.io.manifest import LightSpec, SceneManifest

    scene, subject, floor, light, cam = _build_scene(args)

    blend_path = args.output / "bunny_baseline.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    gt_mesh_path = args.output / "ground_truth.obj"
    _export_ground_truth([subject, floor], gt_mesh_path)

    cameras = _collect_cameras(args, scene, cam)

    manifest = SceneManifest(
        name="bunny_baseline",
        version=1,
        blend_path=blend_path.name,
        ground_truth_mesh=gt_mesh_path.name,
        cameras=cameras,
        lights=[
            LightSpec(
                name=light.name,
                kind="area",
                location=list(light.location),
                energy=float(light.data.energy),
                color=[float(c) for c in light.data.color],
                extra={"size": float(light.data.size)},
            )
        ],
        notes=(
            "Baseline scene. Subject is a subdivided UV sphere unless "
            "--bunny-ply was supplied. Floor is a 4m checker-textured "
            "plane lit by one area light."
        ),
    )
    manifest.write(args.output / "manifest.json")
    print(f"[bunny] wrote {len(sum(cameras.values(), []))} poses across "
          f"{len(cameras)} densities to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
