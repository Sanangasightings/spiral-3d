"""Symmetric Chamfer distance between predicted geometry and a
ground-truth mesh."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..methods.base import Mesh, PointCloud, Reconstruction
from .mesh_io import load_obj, sample_surface
from .registry import GroundTruth, register_metric


def _predicted_points(reconstruction: Reconstruction) -> np.ndarray:
    geom = reconstruction.geometry_export()
    if isinstance(geom, PointCloud):
        return geom.points
    if isinstance(geom, Mesh):
        # Sample the predicted mesh surface to point-cloud density.
        n = max(10_000, geom.vertices.shape[0])
        return sample_surface(geom.vertices, geom.faces, n_samples=n)
    raise TypeError(
        f"Chamfer cannot operate on geometry_export of type {type(geom)}"
    )


def _nearest_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distance from each point in `a` to its nearest neighbor in `b`.
    Uses scipy's cKDTree when available; otherwise a chunked numpy
    fallback so the test suite runs without scipy."""
    try:
        from scipy.spatial import cKDTree
    except ImportError:
        return _numpy_nn(a, b)
    tree = cKDTree(b)
    d, _ = tree.query(a, k=1)
    return d


def _numpy_nn(a: np.ndarray, b: np.ndarray, chunk: int = 1024) -> np.ndarray:
    out = np.empty(a.shape[0], dtype=np.float64)
    for i in range(0, a.shape[0], chunk):
        block = a[i : i + chunk]
        d2 = ((block[:, None, :] - b[None, :, :]) ** 2).sum(-1)
        out[i : i + block.shape[0]] = np.sqrt(d2.min(axis=1))
    return out


@register_metric("chamfer")
def chamfer(
    reconstruction: Reconstruction, gt: GroundTruth
) -> tuple[float, dict[str, Any]]:
    """Symmetric mean L2 nearest-neighbor distance.

    Lower is better. Reported in scene units (meters in our scenes).
    """
    if gt.mesh_path is None:
        raise ValueError("Chamfer needs a ground-truth mesh path.")

    pred = _predicted_points(reconstruction)
    if pred.shape[0] == 0:
        return float("inf"), {"reason": "empty predicted geometry"}

    verts, faces = load_obj(gt.mesh_path)
    n = min(50_000, max(10_000, pred.shape[0]))
    gt_samples = sample_surface(verts, faces, n_samples=n, seed=0)

    d_pred_to_gt = _nearest_distances(pred, gt_samples)
    d_gt_to_pred = _nearest_distances(gt_samples, pred)
    value = 0.5 * (d_pred_to_gt.mean() + d_gt_to_pred.mean())
    return float(value), {
        "pred_to_gt_mean": float(d_pred_to_gt.mean()),
        "gt_to_pred_mean": float(d_gt_to_pred.mean()),
        "n_pred": int(pred.shape[0]),
        "n_gt": int(gt_samples.shape[0]),
    }
