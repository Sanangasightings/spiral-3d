"""Name-keyed registry of reconstruction methods.

Methods register themselves at import time via the `@register("name")`
decorator. Importing `spiral_sandbox.methods` triggers all registrations.
"""

from __future__ import annotations

from typing import Type

from .base import Method


_REGISTRY: dict[str, Type[Method]] = {}


def register(name: str):
    """Decorator: bind `name` to a Method subclass in the registry."""

    def decorator(cls: Type[Method]) -> Type[Method]:
        if name in _REGISTRY:
            raise ValueError(f"Method '{name}' is already registered")
        cls.name = name
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_method(name: str) -> Method:
    """Instantiate the registered method class for `name`."""
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown method '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]()


def list_methods() -> list[str]:
    return sorted(_REGISTRY)
