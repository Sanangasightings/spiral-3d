from pathlib import Path

from spiral_sandbox.io.config import RunConfig


REPO = Path(__file__).resolve().parent.parent


def test_full_run_yaml_loads():
    cfg = RunConfig.load(REPO / "configs" / "full_run.yaml")
    assert cfg.seed == 42
    assert [s.name for s in cfg.scenes] == ["bunny_baseline"]
    assert "point_cloud" in cfg.methods
    assert "chamfer" in cfg.metrics.geometric
    assert "psnr" in cfg.metrics.visual


def test_resolve_paths_makes_paths_absolute(tmp_path):
    cfg = RunConfig.load(REPO / "configs" / "full_run.yaml")
    resolved = cfg.resolve_paths(tmp_path)
    assert resolved.output.results_db.is_absolute()
    assert resolved.output.scenes_dir.is_absolute()
    assert tmp_path in resolved.output.results_db.parents


def test_enabled_scenes_filters_disabled():
    cfg = RunConfig.load(REPO / "configs" / "full_run.yaml")
    cfg.scenes[0].enabled = False
    assert cfg.enabled_scenes() == []


def test_metrics_all_names_concatenates():
    cfg = RunConfig.load(REPO / "configs" / "full_run.yaml")
    names = cfg.metrics.all_names()
    # Order is geometric, visual, resource, affordance — stable for the
    # orchestrator's "metrics it intends to compute" log line.
    assert names[0] == cfg.metrics.geometric[0]
    assert "psnr" in names
