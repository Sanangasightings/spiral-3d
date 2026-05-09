"""Typed config schema. YAML in, validated dataclasses out."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


Density = Literal["sparse", "medium", "dense"]


class SceneEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    enabled: bool = True
    densities: list[Density] = Field(default_factory=lambda: ["medium"])


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometric: list[str] = Field(default_factory=list)
    visual: list[str] = Field(default_factory=list)
    resource: list[str] = Field(default_factory=list)
    affordance: list[str] = Field(default_factory=list)

    def all_names(self) -> list[str]:
        return [
            *self.geometric,
            *self.visual,
            *self.resource,
            *self.affordance,
        ]


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results_db: Path = Path("results/spiral.db")
    artifacts_dir: Path = Path("results/artifacts")
    figures_dir: Path = Path("results/figures")
    scenes_dir: Path = Path("scenes")
    captures_dir: Path = Path("results/captures")
    publish: bool = False
    site_dir: Path = Path("site")


class RunConfig(BaseModel):
    """Top-level config. Mirrors `configs/full_run.yaml`."""

    model_config = ConfigDict(extra="forbid")

    seed: int = 42
    scenes: list[SceneEntry] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def load(cls, path: Path) -> "RunConfig":
        with Path(path).open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if raw is None:
            raise ValueError(f"Empty config: {path}")
        return cls.model_validate(raw)

    def enabled_scenes(self) -> list[SceneEntry]:
        return [s for s in self.scenes if s.enabled]

    def resolve_paths(self, root: Path) -> "RunConfig":
        """Return a copy with all output paths resolved against `root`."""
        root = Path(root).resolve()

        def _r(p: Path) -> Path:
            p = Path(p)
            return p if p.is_absolute() else root / p

        out = self.output
        new_output = OutputConfig(
            results_db=_r(out.results_db),
            artifacts_dir=_r(out.artifacts_dir),
            figures_dir=_r(out.figures_dir),
            scenes_dir=_r(out.scenes_dir),
            captures_dir=_r(out.captures_dir),
            publish=out.publish,
            site_dir=_r(out.site_dir),
        )
        return self.model_copy(update={"output": new_output})
