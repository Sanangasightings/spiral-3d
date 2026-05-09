"""Peak signal-to-noise ratio between method renders and held-out GT."""

from __future__ import annotations

from typing import Any

import numpy as np

from ..methods.base import Reconstruction
from ..methods.registry import get_method
from .registry import GroundTruth, register_metric


def _psnr_one(pred: np.ndarray, gt: np.ndarray, max_val: float = 1.0) -> float:
    pred = pred.astype(np.float64)
    gt = gt.astype(np.float64)
    if pred.shape != gt.shape:
        raise ValueError(
            f"PSNR shape mismatch: pred {pred.shape} vs gt {gt.shape}"
        )
    mse = ((pred - gt) ** 2).mean()
    if mse <= 0:
        return float("inf")
    return float(20.0 * np.log10(max_val) - 10.0 * np.log10(mse))


@register_metric("psnr")
def psnr(
    reconstruction: Reconstruction, gt: GroundTruth
) -> tuple[float, dict[str, Any]]:
    """Mean PSNR across held-out renders.

    Higher is better. The method's `render` is invoked at each held-out
    camera; the result is compared per-pixel to the captured RGB.
    """
    if not gt.held_out_renders or not gt.held_out_cameras:
        raise ValueError("PSNR needs held-out renders and cameras.")
    if len(gt.held_out_renders) != len(gt.held_out_cameras):
        raise ValueError(
            "held_out_renders and held_out_cameras length mismatch."
        )

    method = get_method(reconstruction.method_name)
    values: list[float] = []
    for cam, target in zip(gt.held_out_cameras, gt.held_out_renders):
        pred_img = method.render(reconstruction, cam)
        values.append(_psnr_one(pred_img.pixels, target))
    finite = [v for v in values if np.isfinite(v)]
    mean = float(np.mean(finite)) if finite else float("inf")
    return mean, {
        "per_view": values,
        "n_views": len(values),
        "n_finite": len(finite),
    }
