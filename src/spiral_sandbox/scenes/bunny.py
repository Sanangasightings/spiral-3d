"""Subject-on-floor scene generator.

Designed to run inside headless Blender:

    blender --background --python src/spiral_sandbox/scenes/bunny.py -- \
        --output scenes/<scene_name> \
        --densities sparse,medium,dense \
        --seed 42 \
        [--subject-mesh path/to/mesh.{ply,obj,glb,gltf}] \
        [--scene-name <name>]

Outputs:

    <output>/<scene_name>.blend
    <output>/ground_truth.obj
    <output>/manifest.json     # SceneManifest

When no `--subject-mesh` is given the subject is a checker-textured UV
sphere — that's the `sphere_baseline` smoke-test scene. Otherwise the
subject is imported from disk (PLY / OBJ / GLB / glTF), auto-normalized
to a unit-ish size, and placed on the standard textured floor with one
area light. The same scaffolding is used for every catalog scene; the
only variable is the subject.
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
    p = argparse.ArgumentParser(prog="subject_scene")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--densities", type=str, default="sparse,medium,dense")
    p.add_argument("--seed", type=int, default=42)
    # --subject-mesh is the new generic flag; --bunny-ply is kept as an
    # alias because earlier configs and the README reference it.
    p.add_argument("--subject-mesh", type=Path, default=None)
    p.add_argument("--bunny-ply", type=Path, default=None)
    p.add_argument(
        "--scene-name", type=str, default="bunny_baseline",
        help="Name written into the scene manifest + used for the .blend "
        "filename.",
    )
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=768)
    args = p.parse_args(_split_args())
    if args.subject_mesh is None and args.bunny_ply is not None:
        args.subject_mesh = args.bunny_ply
    return args


DENSITY_VIEWS = {"sparse": 24, "medium": 60, "dense": 120}


# Spiral trajectory: azimuth advances by the golden angle while elevation
# sweeps linearly from `_ELEV_MIN_DEG` (slightly below the equator) up
# toward top-down. This replaces an earlier single-elevation orbit that
# starved SfM of triangulation diversity — every ray was nearly coplanar
# and reconstructions came out as wrinkled sheets.
_GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))
_ELEV_MIN_DEG = -10.0
_ELEV_MAX_DEG = 85.0


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


def _import_subject_mesh(path):
    """Dispatch on file extension. Each format pulls in different material
    semantics: PLY has none, OBJ has optional .mtl, glTF/GLB has full PBR."""
    import bpy

    ext = path.suffix.lower()
    if ext == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        raise ValueError(
            f"Unsupported subject mesh extension '{ext}'. "
            f"Supported: .ply, .obj, .glb, .gltf"
        )


def _normalize_and_place(obj):
    """Scale to fit in a unit cube and translate so it sits on the floor
    (z=0) — common frame so the camera rig is shared across scenes."""
    import bpy

    max_dim = max(obj.dimensions)
    if max_dim > 0:
        scale = 1.0 / max_dim
        obj.scale = (scale, scale, scale)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(
        location=False, rotation=False, scale=True
    )
    # Move the bottom of the bounding box to z=0 so the subject sits on
    # the floor regardless of where the mesh's origin was authored.
    import mathutils
    corners = [
        obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box
    ]
    bbox_min_z = min(c.z for c in corners)
    bbox_center_xy = (
        sum(c.x for c in corners) / 8.0,
        sum(c.y for c in corners) / 8.0,
    )
    obj.location = (
        obj.location.x - bbox_center_xy[0],
        obj.location.y - bbox_center_xy[1],
        obj.location.z - bbox_min_z,
    )


def _apply_fallback_material_if_needed(obj):
    """If the imported mesh has no materials, slap on the same Voronoi
    pattern the sphere uses — SfM needs surface features and the bare
    PLY meshes (BunnyMesh / KnotMesh / ArmadilloMesh) have none."""
    import bpy

    has_material = any(slot.material is not None for slot in obj.material_slots)
    if has_material:
        return
    mat = bpy.data.materials.new(f"{obj.name}_fallback")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    tex_coord = mat.node_tree.nodes.new("ShaderNodeTexCoord")
    voronoi = mat.node_tree.nodes.new("ShaderNodeTexVoronoi")
    voronoi.inputs["Scale"].default_value = 40.0
    ramp = mat.node_tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.90, 0.85, 0.78, 1.0)
    ramp.color_ramp.elements[1].color = (0.22, 0.16, 0.10, 1.0)
    links = mat.node_tree.links
    links.new(tex_coord.outputs["Generated"], voronoi.inputs["Vector"])
    links.new(voronoi.outputs["Distance"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.append(mat)


def _build_scene(args: argparse.Namespace):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.engine = "CYCLES"
    # 32 samples gives clean enough renders at 1024x768 that SfM finds
    # plenty of features. Bump higher (128–256) for paper figures.
    scene.cycles.samples = 32

    # --- Subject ---
    if args.subject_mesh and args.subject_mesh.exists():
        _import_subject_mesh(args.subject_mesh)
        # Collect every imported mesh (multi-part .glb / .gltf import as
        # several objects). Join them so subsequent ops have one target.
        meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"
                  and o.name not in ("floor",)]
        if not meshes:
            raise RuntimeError(
                f"No mesh objects imported from {args.subject_mesh}"
            )
        if len(meshes) > 1:
            bpy.ops.object.select_all(action="DESELECT")
            for m in meshes:
                m.select_set(True)
            bpy.context.view_layer.objects.active = meshes[0]
            bpy.ops.object.join()
        subject = bpy.context.view_layer.objects.active
        subject.name = "subject"
        _normalize_and_place(subject)
        _apply_fallback_material_if_needed(subject)
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

        # Subject material: high-contrast checker, same shader as the
        # floor. A plain or low-frequency-noise sphere was starving SfM
        # of correspondences and breaking COLMAP's initial-pair search.
        # The checker gives every viewpoint dozens of crisp corners.
        sub_mat = bpy.data.materials.new("subject_mat")
        sub_mat.use_nodes = True
        sub_bsdf = sub_mat.node_tree.nodes["Principled BSDF"]
        sub_checker = sub_mat.node_tree.nodes.new("ShaderNodeTexChecker")
        sub_checker.inputs["Scale"].default_value = 18.0
        sub_checker.inputs["Color1"].default_value = (0.92, 0.88, 0.78, 1.0)
        sub_checker.inputs["Color2"].default_value = (0.18, 0.10, 0.05, 1.0)
        sub_mat.node_tree.links.new(
            sub_bsdf.inputs["Base Color"], sub_checker.outputs["Color"]
        )
        subject.data.materials.append(sub_mat)

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


def _spiral_pose(
    cam,
    i: int,
    n: int,
    *,
    radius: float,
    target_z: float,
    jitter: float,
    rng: random.Random,
):
    """Place `cam` at the i-th point along a spherical spiral around
    the subject. Azimuth: golden-angle step. Elevation: linear sweep
    from `_ELEV_MIN_DEG` to `_ELEV_MAX_DEG` as i goes 0..n-1. Every i
    is a distinct viewpoint, so 24 / 60 / 120 cameras give 24 / 60 / 120
    different angles — no near-duplicates."""
    import mathutils

    azimuth = i * _GOLDEN_ANGLE
    elev = math.radians(
        _ELEV_MIN_DEG
        + (_ELEV_MAX_DEG - _ELEV_MIN_DEG) * (i / max(n - 1, 1))
    )
    jx = (rng.random() - 0.5) * jitter
    jy = (rng.random() - 0.5) * jitter
    jz = (rng.random() - 0.5) * jitter * 0.5
    cz = math.sin(elev) * radius
    cr = math.cos(elev) * radius
    cam.location = (
        math.cos(azimuth) * cr + jx,
        math.sin(azimuth) * cr + jy,
        target_z + cz + jz,
    )
    direction = mathutils.Vector((0.0, 0.0, target_z)) - cam.location
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
            _spiral_pose(
                cam, i, n,
                radius=2.5, target_z=0.5, jitter=0.04, rng=rng,
            )
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

    blend_path = args.output / f"{args.scene_name}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    gt_mesh_path = args.output / "ground_truth.obj"
    _export_ground_truth([subject, floor], gt_mesh_path)

    cameras = _collect_cameras(args, scene, cam)

    subject_note = (
        f"subject loaded from {args.subject_mesh.name}"
        if args.subject_mesh
        else "subdivided UV sphere primitive"
    )
    manifest = SceneManifest(
        name=args.scene_name,
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
            f"Subject-on-floor scene. Subject: {subject_note}. "
            f"Floor is a 4m checker-textured plane lit by one area light."
        ),
    )
    manifest.write(args.output / "manifest.json")
    print(f"[bunny] wrote {len(sum(cameras.values(), []))} poses across "
          f"{len(cameras)} densities to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
