"""The math-only side of the metric layer: identical inputs produce the
analytical floor (0 for chamfer, +inf for PSNR), and known noise
produces the textbook value."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from spiral_sandbox.metrics.chamfer import _nearest_distances
from spiral_sandbox.metrics.psnr import _psnr_one
from spiral_sandbox.metrics.mesh_io import load_obj, sample_surface


def test_nearest_distance_identical_zero():
    pts = np.random.default_rng(0).standard_normal((100, 3))
    d = _nearest_distances(pts, pts)
    assert d.max() == pytest.approx(0.0, abs=1e-12)


def test_nearest_distance_unit_offset():
    a = np.zeros((10, 3))
    b = np.zeros((10, 3))
    b[:, 0] = 1.0
    d = _nearest_distances(a, b)
    assert d.max() == pytest.approx(1.0, abs=1e-9)


def test_psnr_identical_is_inf():
    rng = np.random.default_rng(0)
    img = rng.random((32, 32, 3)).astype(np.float32)
    assert _psnr_one(img, img) == float("inf")


def test_psnr_known_noise_textbook_value():
    """A constant offset of 0.1 over a [0,1] image: MSE = 0.01,
    PSNR = -10*log10(0.01) = 20 dB."""
    img = np.full((16, 16, 3), 0.5, dtype=np.float32)
    target = img + 0.1
    # ~1e-5 absolute is the float32 precision floor for the offset image.
    assert _psnr_one(img, target) == pytest.approx(20.0, abs=1e-4)


def test_obj_roundtrip_unit_triangle(tmp_path):
    """Load a hand-written 1-triangle OBJ and check sampler stays on it."""
    obj = tmp_path / "tri.obj"
    obj.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8"
    )
    verts, faces = load_obj(obj)
    assert verts.shape == (3, 3)
    assert faces.shape == (1, 3)

    samples = sample_surface(verts, faces, n_samples=500, seed=1)
    # Every sample lives on z=0 and inside the unit triangle.
    assert np.allclose(samples[:, 2], 0.0)
    assert (samples[:, 0] >= -1e-9).all()
    assert (samples[:, 1] >= -1e-9).all()
    assert (samples[:, 0] + samples[:, 1] <= 1.0 + 1e-9).all()
