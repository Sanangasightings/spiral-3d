"""Metric families. Each metric is a callable registered by name; the
orchestrator iterates the names listed in the run config and writes
each result into the SQLite results store."""

from __future__ import annotations

from .registry import (
    GroundTruth,
    MetricFn,
    get_metric,
    list_metrics,
    register_metric,
)

# Side-effect imports so metric registrations fire on package import.
from . import chamfer  # noqa: F401
from . import psnr     # noqa: F401

__all__ = [
    "GroundTruth",
    "MetricFn",
    "get_metric",
    "list_metrics",
    "register_metric",
]
