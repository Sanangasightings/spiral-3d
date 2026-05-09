"""Render captures from a scene manifest.

Designed to run inside headless Blender:

    blender --background <scene>.blend --python \
        src/spiral_sandbox/capture/render.py -- \
        --manifest scenes/bunny_baseline/manifest.json \
        --output results/captures/bunny_baseline \
        --densities sparse,medium,dense

For each (density, pose) the script renders RGB to PNG and depth to
EXR, and writes a CaptureManifest per density into the output dir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    here = Path(__file__).resolve()
    src = here.parents[2]
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


_ensure_src_on_path()


def _split_args() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return sys.argv[1:]


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="capture_render")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--densities", type=str, default="sparse,medium,dense")
    return p.parse_args(_split_args())


def _enable_depth_pass(scene) -> "DepthOutput":
    """Wire Cycles' Z pass through a compositor node into a file output.

    Returns the file-output node so the caller can change `base_path` per
    pose.
    """
    import bpy  # noqa: F401

    scene.view_layers[0].use_pass_z = True
    scene.use_nodes = True
    tree = scene.node_tree
    for node in list(tree.nodes):
        tree.nodes.remove(node)

    rl = tree.nodes.new("CompositorNodeRLayers")
    fo = tree.nodes.new("CompositorNodeOutputFile")
    fo.format.file_format = "OPEN_EXR"
    fo.format.color_depth = "32"
    fo.file_slots[0].path = "depth_"
    tree.links.new(rl.outputs["Depth"], fo.inputs[0])
    return fo


def _set_pose(cam, pose) -> None:
    """Apply a CameraPose's extrinsics back to a Blender camera.

    The manifest stores world-to-camera in OpenCV convention; Blender
    expects camera-to-world in its own convention (Y up, -Z forward).
    Invert and flip back.
    """
    import mathutils

    flip = mathutils.Matrix(
        ((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1))
    )
    w2c = mathutils.Matrix(pose.extrinsics)
    c2w = (flip @ w2c).inverted()
    cam.matrix_world = c2w


def main() -> int:
    args = _parse()
    args.output.mkdir(parents=True, exist_ok=True)

    import bpy
    from spiral_sandbox.io.manifest import (
        CaptureManifest,
        RenderedView,
        SceneManifest,
    )

    scene_manifest = SceneManifest.read(args.manifest)
    scene_dir = args.manifest.parent

    scene = bpy.context.scene
    cam = bpy.data.objects.get("cam") or scene.camera
    if cam is None:
        raise RuntimeError("No camera 'cam' or scene.camera in the .blend")

    depth_node = _enable_depth_pass(scene)

    densities = [d.strip() for d in args.densities.split(",") if d.strip()]
    for density in densities:
        if density not in scene_manifest.cameras:
            print(f"[capture] skipping '{density}' — not in scene manifest")
            continue
        density_dir = args.output / density
        density_dir.mkdir(parents=True, exist_ok=True)
        rgb_dir = density_dir / "rgb"
        depth_dir = density_dir / "depth"
        rgb_dir.mkdir(exist_ok=True)
        depth_dir.mkdir(exist_ok=True)

        views: list[RenderedView] = []
        poses = scene_manifest.cameras[density]
        for pose in poses:
            _set_pose(cam, pose)
            scene.render.resolution_x = pose.width
            scene.render.resolution_y = pose.height

            rgb_path = rgb_dir / f"{pose.pose_id}.png"
            scene.render.filepath = str(rgb_path)
            depth_node.base_path = str(depth_dir)
            depth_node.file_slots[0].path = f"{pose.pose_id}_"

            bpy.ops.render.render(write_still=True)

            # Compositor file-output names like "<base>_0001.exr"; rename
            # to a stable name so the manifest references the actual file.
            for f in depth_dir.glob(f"{pose.pose_id}_*.exr"):
                stable = depth_dir / f"{pose.pose_id}.exr"
                if f != stable:
                    if stable.exists():
                        stable.unlink()
                    f.rename(stable)

            views.append(
                RenderedView(
                    pose_id=pose.pose_id,
                    image_path=str(rgb_path.relative_to(density_dir)),
                    depth_path=f"depth/{pose.pose_id}.exr",
                    camera=pose,
                )
            )

        capture = CaptureManifest(
            scene=scene_manifest.name,
            density=density,
            blend_path=str((scene_dir / scene_manifest.blend_path).resolve()),
            ground_truth_mesh=str(
                (scene_dir / scene_manifest.ground_truth_mesh).resolve()
            ),
            width=poses[0].width,
            height=poses[0].height,
            views=views,
            seed=42,
        )
        capture.write(density_dir / "captures.json")
        print(f"[capture] {density}: rendered {len(views)} views to {density_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
