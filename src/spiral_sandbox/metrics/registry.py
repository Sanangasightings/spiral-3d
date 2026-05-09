"""Metric registry. A metric is a callable from (Reconstruction,
ground-truth bundle) to a (value, extra) pair, registered by name."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

import numpy as np

from ..methods.base import Reconstruction


@dataclass
class GroundTruth:
    """Everything a metric might need to compare against."""

    mesh_path: Optional[Path] = None
    held_out_renders: list[np.ndarray] | None = None  # (H, W, 3) per held-out view
    held_out_cameras: list[Any] | None = None         # methods.Camera


MetricFn = Callable[[Reconstruction, GroundTruth], tuple[float, dict[str, Any]]]


_REGISTRY: dict[str, MetricFn] = {}


def register_metric(name: str):
    def decorator(fn: MetricFn) -> MetricFn:
        if name in _REGISTRY:
            raise ValueError(f"Metric '{name}' already registered")
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_metric(name: str) -> MetricFn:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown metric '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def list_metrics() -> list[str]:
    return sorted(_REGISTRY)
