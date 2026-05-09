"""Structure-from-motion + Poisson meshing.

Pipeline:

    images -> COLMAP feature_extractor + matcher + mapper
            -> sparse cloud + recovered camera poses
            -> Open3D normal estimation + Poisson surface reconstruction
            -> textured mesh

The CUDA path of COLMAP (`patch_match_stereo`) is unavailable on the
CPU build, so dense MVS is replaced with Poisson surface reconstruction
on the SfM sparse cloud — common alternative pipeline. Mesh-export
quality is the headline trade-off this method occupies; the
photogrammetric trade signature still applies.
"""

from __future__ import annotations

import logging
import os
import shutil
import struct
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image as PILImage

from ._splat import splat_render
from .base import (
    Camera,
    Capture,
    GeometryExport,
    Image,
    Mesh,
    Method,
    MethodConfig,
    Reconstruction,
)
from .registry import register
from ..metrics.mesh_io import sample_surface


log = logging.getLogger("spiral_sandbox.methods.photogrammetry")


def _resolve_colmap_bin(preferred: Optional[str] = None) -> Path:
    """Find the colmap binary itself, not the .bat launcher.

    The portable Windows zip ships a COLMAP.bat launcher whose `%*`
    forwarding mangles quoted paths-with-spaces — so we always reach
    past it to `colmap.exe` and replicate the env setup ourselves in
    `_colmap_env`. Order: explicit arg, $COLMAP_BIN env var, on PATH,
    portable-zip drop site.
    """
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    if os.environ.get("COLMAP_BIN"):
        candidates.append(os.environ["COLMAP_BIN"])
    # Explicit portable-zip path FIRST — Windows PATHEXT lets shutil.which
    # find COLMAP.bat under the name "colmap", but the .bat mangles
    # quoted-path-with-spaces args, so we always reach past it.
    candidates.extend(
        [
            r"C:\Users\Owner\bin\bin\colmap.exe",
            r"C:\Users\Owner\bin\colmap.exe",
            "/usr/bin/colmap",
        ]
    )
    for name in ("colmap.exe", "colmap"):
        found = shutil.which(name)
        if found and not found.lower().endswith(".bat"):
            candidates.append(found)
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    raise FileNotFoundError(
        "colmap binary not found. Tried: "
        + ", ".join(filter(None, candidates))
    )


def _colmap_env(colmap_path: Path) -> dict[str, str]:
    """Build a subprocess env that points DLL/Qt-plugin lookup at the
    portable zip's bin/ and plugins/ folders alongside `colmap.exe`."""
    env = os.environ.copy()
    bin_dir = colmap_path.parent
    plugins_dir = bin_dir.parent / "plugins"
    env["PATH"] = f"{bin_dir};{env.get('PATH', '')}"
    if plugins_dir.exists():
        env["QT_PLUGIN_PATH"] = (
            f"{plugins_dir};{env.get('QT_PLUGIN_PATH', '')}"
        )
    return env


class PhotogrammetryConfig(MethodConfig):
    """Knobs for the photogrammetry method."""

    colmap_bin: Optional[str] = None  # auto-resolved when None
    max_image_size: int = 1024
    poisson_depth: int = 8
    use_gpu: bool = False
    surface_samples_per_render: int = 200_000


@dataclass
class MeshReconstruction(Reconstruction):
    """A textured triangle mesh, in world frame."""

    mesh: Mesh = field(
        default_factory=lambda: Mesh(
            vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64)
        )
    )
    surface_samples: Optional[np.ndarray] = None  # cached for render
    surface_colors: Optional[np.ndarray] = None

    def geometry_export(self) -> GeometryExport:
        return self.mesh


def _read_points3d_bin(path: Path) -> np.ndarray:
    """Parse COLMAP's `points3D.bin` into an (N, 6) array of XYZ + RGB."""
    pts: list[list[float]] = []
    with path.open("rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            _pid = struct.unpack("<Q", f.read(8))[0]
            x, y, z = struct.unpack("<3d", f.read(24))
            r, g, b = struct.unpack("<3B", f.read(3))
            _err = struct.unpack("<d", f.read(8))[0]
            track_len = struct.unpack("<Q", f.read(8))[0]
            f.read(track_len * 8)  # (image_id, point2d_idx) pairs
            pts.append([x, y, z, r / 255.0, g / 255.0, b / 255.0])
    return np.asarray(pts, dtype=np.float64) if pts else np.zeros((0, 6))


def _read_images_bin(path: Path) -> dict[str, np.ndarray]:
    """Parse COLMAP's `images.bin` -> {image_name: 4x4 world-to-camera}."""
    out: dict[str, np.ndarray] = {}
    with path.open("rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            _img_id = struct.unpack("<I", f.read(4))[0]
            qw, qx, qy, qz = struct.unpack("<4d", f.read(32))
            tx, ty, tz = struct.unpack("<3d", f.read(24))
            _cam_id = struct.unpack("<I", f.read(4))[0]
            name_chars: list[bytes] = []
            while True:
                ch = f.read(1)
                if ch == b"\x00":
                    break
                name_chars.append(ch)
            name = b"".join(name_chars).decode("utf-8")
            n_pts2d = struct.unpack("<Q", f.read(8))[0]
            f.read(n_pts2d * 24)  # 2D points (xy float64 + point3d_id u64)

            # Quaternion -> rotation matrix (qw, qx, qy, qz convention).
            R = np.array(
                [
                    [
                        1 - 2 * (qy * qy + qz * qz),
                        2 * (qx * qy - qz * qw),
                        2 * (qx * qz + qy * qw),
                    ],
                    [
                        2 * (qx * qy + qz * qw),
                        1 - 2 * (qx * qx + qz * qz),
                        2 * (qy * qz - qx * qw),
                    ],
                    [
                        2 * (qx * qz - qy * qw),
                        2 * (qy * qz + qx * qw),
                        1 - 2 * (qx * qx + qy * qy),
                    ],
                ],
                dtype=np.float64,
            )
            extr = np.eye(4)
            extr[:3, :3] = R
            extr[:3, 3] = [tx, ty, tz]
            out[name] = extr
    return out


def _umeyama(src: np.ndarray, dst: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Similarity transform (s, R, t) that best maps `src` (N,3) to `dst`
    (N,3) under ||s*R*x + t - y||^2 (Umeyama 1991). Returns (s, R, t)."""
    assert src.shape == dst.shape and src.shape[1] == 3
    cs = src.mean(axis=0)
    cd = dst.mean(axis=0)
    src0 = src - cs
    dst0 = dst - cd
    H = src0.T @ dst0 / src.shape[0]
    U, sigma, Vt = np.linalg.svd(H)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0
    R = (Vt.T @ S @ U.T)
    var_src = (src0 ** 2).sum() / src.shape[0]
    s = (sigma * np.diag(S)).sum() / var_src
    t = cd - s * R @ cs
    return float(s), R, t


def _camera_centers(extrinsics_per_name: dict[str, np.ndarray]) -> np.ndarray:
    """World-frame camera positions, one row per (sorted) name."""
    rows = []
    for name in sorted(extrinsics_per_name.keys()):
        E = extrinsics_per_name[name]
        R = E[:3, :3]
        t = E[:3, 3]
        # Camera center C satisfies E * [C; 1] = 0 => C = -R^T t
        rows.append(-R.T @ t)
    return np.asarray(rows)


def _write_capture_images(
    captures: list[Capture], out_dir: Path, max_size: int
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, cap in enumerate(captures):
        pixels = cap.image.pixels
        if pixels.dtype != np.uint8:
            pixels = (np.clip(pixels, 0.0, 1.0) * 255).astype(np.uint8)
        img = PILImage.fromarray(pixels)
        if max(img.size) > max_size:
            scale = max_size / max(img.size)
            img = img.resize(
                (int(img.size[0] * scale), int(img.size[1] * scale)),
                PILImage.LANCZOS,
            )
        img.save(out_dir / f"image_{i:04d}.png")


def _run(
    cmd: list[str],
    env: Optional[dict[str, str]] = None,
    cwd: Path | None = None,
) -> None:
    log.info("colmap: %s", " ".join(str(c) for c in cmd))
    subprocess.run(
        cmd, cwd=cwd, env=env, check=True, capture_output=True, text=True
    )


@register("photogrammetry")
class PhotogrammetryMethod(Method):
    """COLMAP runs feature detection, matching, and incremental SfM on
    the source images to recover a sparse cloud and refined camera
    poses. Open3D estimates normals on the cloud and runs Poisson
    surface reconstruction to produce a watertight mesh.

    Trade signature: surfaces are explicit, meshable, and slot directly
    into standard 3D pipelines — strong downstream affordance for
    editing and asset reuse. Specular and featureless regions starve
    SfM of correspondences and collapse into geometry holes; thin
    structures get filled in or smoothed away by Poisson.

    GPU note: COLMAP's `patch_match_stereo` (dense MVS) is CUDA-only.
    On the CPU build we substitute Poisson on the SfM sparse cloud — a
    common alternative pipeline that still produces a textured mesh.
    """

    def fit(
        self, captures: list[Capture], config: MethodConfig
    ) -> Reconstruction:
        cfg = (
            config
            if isinstance(config, PhotogrammetryConfig)
            else PhotogrammetryConfig.model_validate(config.model_dump())
        )

        try:
            import open3d as o3d
        except ImportError as exc:
            raise RuntimeError(
                "photogrammetry requires open3d for normal estimation + "
                "Poisson reconstruction"
            ) from exc

        colmap = _resolve_colmap_bin(cfg.colmap_bin)
        env = _colmap_env(colmap)
        workspace = Path(".spiral_colmap_ws").resolve()
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)

        images_dir = workspace / "images"
        sparse_dir = workspace / "sparse"
        sparse_dir.mkdir()
        db_path = workspace / "database.db"

        _write_capture_images(captures, images_dir, cfg.max_image_size)

        gpu_flag = "1" if cfg.use_gpu else "0"
        try:
            _run(
                [
                    str(colmap), "feature_extractor",
                    "--database_path", str(db_path),
                    "--image_path", str(images_dir),
                    "--ImageReader.single_camera", "1",
                    "--ImageReader.camera_model", "SIMPLE_PINHOLE",
                    "--FeatureExtraction.use_gpu", gpu_flag,
                ],
                env=env,
            )
            _run(
                [
                    str(colmap), "exhaustive_matcher",
                    "--database_path", str(db_path),
                    "--FeatureMatching.use_gpu", gpu_flag,
                ],
                env=env,
            )
            _run(
                [
                    str(colmap), "mapper",
                    "--database_path", str(db_path),
                    "--image_path", str(images_dir),
                    "--output_path", str(sparse_dir),
                ],
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else exc.stderr
            raise RuntimeError(
                f"COLMAP step failed: {' '.join(map(str, exc.cmd))}\n{stderr}"
            ) from exc

        # COLMAP writes sparse/0/, sparse/1/, ... per reconstructed model.
        models = sorted(p for p in sparse_dir.iterdir() if p.is_dir())
        if not models:
            raise RuntimeError(
                f"COLMAP mapper produced no reconstruction in {sparse_dir}. "
                f"This typically means too few feature matches — try denser "
                f"input or a more textured scene."
            )
        points3d_bin = models[0] / "points3D.bin"
        images_bin = models[0] / "images.bin"
        if not points3d_bin.exists():
            raise RuntimeError(
                f"Expected {points3d_bin} from COLMAP mapper; not found."
            )

        cloud = _read_points3d_bin(points3d_bin)

        # COLMAP recovers the scene in an arbitrary scale + frame. Align
        # to the GT world frame using the captures' known camera centers
        # vs the SfM-recovered ones (Umeyama similarity). Without this,
        # chamfer-vs-GT compares different coordinate systems.
        align_meta: dict = {}
        if images_bin.exists():
            colmap_extrinsics = _read_images_bin(images_bin)
            if colmap_extrinsics:
                gt_centers, sfm_centers = [], []
                # Capture image filenames were written as image_NNNN.png
                # by `_write_capture_images`, in the order `captures`
                # was passed. COLMAP keys by the same filename.
                for i, cap in enumerate(captures):
                    name = f"image_{i:04d}.png"
                    if name not in colmap_extrinsics:
                        continue
                    E = colmap_extrinsics[name]
                    sfm_centers.append(-E[:3, :3].T @ E[:3, 3])
                    gt_E = cap.camera.extrinsics
                    gt_centers.append(-gt_E[:3, :3].T @ gt_E[:3, 3])
                if len(gt_centers) >= 3:
                    src = np.asarray(sfm_centers)
                    dst = np.asarray(gt_centers)
                    s, R, t = _umeyama(src, dst)
                    cloud[:, :3] = (s * (cloud[:, :3] @ R.T)) + t
                    align_meta = {
                        "alignment_scale": float(s),
                        "alignment_paired_views": int(len(gt_centers)),
                    }
                    log.info(
                        "Aligned SfM cloud to GT frame: scale=%.4f, "
                        "paired_views=%d", s, len(gt_centers),
                    )
        if cloud.shape[0] < 50:
            raise RuntimeError(
                f"COLMAP recovered only {cloud.shape[0]} sparse points; "
                f"too few for Poisson reconstruction."
            )

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(cloud[:, :3])
        pcd.colors = o3d.utility.Vector3dVector(cloud[:, 3:])
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
        )
        pcd.orient_normals_consistent_tangent_plane(20)

        mesh, _densities = (
            o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=cfg.poisson_depth
            )
        )
        mesh.compute_vertex_normals()

        verts = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.triangles, dtype=np.int64)
        normals = np.asarray(mesh.vertex_normals, dtype=np.float64)
        colors = (
            np.asarray(mesh.vertex_colors, dtype=np.float64)
            if mesh.has_vertex_colors()
            else None
        )

        spiral_mesh = Mesh(
            vertices=verts,
            faces=faces,
            vertex_normals=normals,
            vertex_colors=colors,
        )

        # Pre-sample surface for render-time splat.
        if faces.shape[0] > 0:
            surface_samples = sample_surface(
                verts, faces, n_samples=cfg.surface_samples_per_render, seed=0
            )
            # Color the samples by nearest vertex (cheap proxy).
            if colors is not None:
                _, idx = _nearest_vertex_index(surface_samples, verts)
                surface_colors = colors[idx]
            else:
                surface_colors = None
        else:
            surface_samples = np.zeros((0, 3))
            surface_colors = None

        recon = MeshReconstruction(
            method_name=self.name,
            artifact_dir=Path("."),
            metadata={
                "n_sparse_points": int(cloud.shape[0]),
                "n_vertices": int(verts.shape[0]),
                "n_faces": int(faces.shape[0]),
                "poisson_depth": cfg.poisson_depth,
                **align_meta,
            },
            mesh=spiral_mesh,
            surface_samples=surface_samples,
            surface_colors=surface_colors,
        )
        return recon

    def render(
        self, reconstruction: Reconstruction, camera: Camera
    ) -> Image:
        if not isinstance(reconstruction, MeshReconstruction):
            raise TypeError(
                f"PhotogrammetryMethod.render expects MeshReconstruction, "
                f"got {type(reconstruction).__name__}"
            )
        if reconstruction.surface_samples is None:
            return Image(
                pixels=np.zeros((camera.height, camera.width, 3), dtype=np.float32)
            )
        return splat_render(
            reconstruction.surface_samples,
            reconstruction.surface_colors,
            camera,
            radius=2,
        )


def _nearest_vertex_index(
    samples: np.ndarray, vertices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """For each sample, the (distance, vertex_index) of its nearest mesh
    vertex. Used for cheap per-sample color lookup at render time."""
    try:
        from scipy.spatial import cKDTree

        tree = cKDTree(vertices)
        d, idx = tree.query(samples, k=1)
        return d, idx
    except ImportError:
        d_out = np.empty(samples.shape[0])
        idx_out = np.empty(samples.shape[0], dtype=np.int64)
        for i, s in enumerate(samples):
            d2 = ((vertices - s) ** 2).sum(axis=1)
            j = int(np.argmin(d2))
            idx_out[i] = j
            d_out[i] = float(np.sqrt(d2[j]))
        return d_out, idx_out
