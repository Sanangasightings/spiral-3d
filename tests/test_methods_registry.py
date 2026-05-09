import pytest

from spiral_sandbox.methods import (
    Method,
    MethodConfig,
    get_method,
    list_methods,
)


EXPECTED = {
    "point_cloud",
    "photogrammetry",
    "mvs",
    "nerf",
    "gaussian_splatting",
    "sdf",
}


def test_all_six_methods_register():
    assert set(list_methods()) == EXPECTED


def test_get_method_returns_subclass_with_name_set():
    for name in EXPECTED:
        m = get_method(name)
        assert isinstance(m, Method)
        assert m.name == name


def test_unknown_method_raises():
    with pytest.raises(KeyError):
        get_method("does_not_exist")


def test_unimplemented_methods_raise_not_implemented():
    """All methods except point_cloud are stubs through Phase 7. Each
    one's fit should still raise NotImplementedError without crashing
    on import or instantiation."""
    for name in EXPECTED - {"point_cloud"}:
        m = get_method(name)
        with pytest.raises(NotImplementedError):
            m.fit([], MethodConfig())
