"""Minimal OBJ reader + area-weighted surface sampling.

Stays stdlib + numpy. The OBJ files we read are produced by our own
Blender export, which writes plain `v` / `f` lines without normals,
materials, or UVs (see scenes/bunny.py). Nothing fancy here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def load_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (vertices (V,3) float64, faces (F,3) int64). Triangulates
    quads on the fly via fan triangulation."""
    vs: list[list[float]] = []
    fs: list[list[int]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            parts = line.split()
            vs.append([float(parts[1]), float(parts[2]), float(parts[3])])
        elif line.startswith("f "):
            parts = line.split()[1:]
            idxs = [int(p.split("/")[0]) - 1 for p in parts]
            for i in range(1, len(idxs) - 1):
                fs.append([idxs[0], idxs[i], idxs[i + 1]])
    return (
        np.asarray(vs, dtype=np.float64),
        np.asarray(fs, dtype=np.int64),
    )


def sample_surface(
    vertices: np.ndarray,
    faces: np.ndarray,
    n_samples: int,
    seed: int = 0,
) -> np.ndarray:
    """Uniform area-weighted sample of N points on the mesh surface."""
    rng = np.random.default_rng(seed)
    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    areas = 0.5 * np.linalg.norm(
        np.cross(v1 - v0, v2 - v0), axis=1
    )
    total = areas.sum()
    if total <= 0:
        raise ValueError("Mesh has zero total area; cannot sample.")
    probs = areas / total
    face_idx = rng.choice(faces.shape[0], size=n_samples, p=probs)
    u = rng.random(n_samples)
    v = rng.random(n_samples)
    swap = u + v > 1.0
    u[swap] = 1.0 - u[swap]
    v[swap] = 1.0 - v[swap]
    w = 1.0 - u - v
    a = vertices[faces[face_idx, 0]]
    b = vertices[faces[face_idx, 1]]
    c = vertices[faces[face_idx, 2]]
    return (
        a * w[:, None] + b * u[:, None] + c * v[:, None]
    )
