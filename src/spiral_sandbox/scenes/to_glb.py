"""One-shot OBJ -> GLB converter, run inside headless Blender:

    blender --background --python src/spiral_sandbox/scenes/to_glb.py -- \
        --input scenes/bunny_baseline/ground_truth.obj \
        --output site/models/bunny.glb

Produces a binary glTF that `<model-viewer>` can render directly on
mobile, including touch rotate and AR on supported devices.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _split_args() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return sys.argv[1:]


def main() -> int:
    p = argparse.ArgumentParser(prog="to_glb")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(_split_args())

    args.output.parent.mkdir(parents=True, exist_ok=True)

    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(args.input))
    bpy.ops.export_scene.gltf(
        filepath=str(args.output),
        export_format="GLB",
        export_apply=True,
    )
    print(f"[to_glb] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
