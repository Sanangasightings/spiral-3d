"""Pipeline entry point.

    python -m spiral_sandbox.run --config configs/full_run.yaml

Runs every enabled (scene, density, method) triple end-to-end:
generate the scene if missing, render captures if missing, fit each
method, persist the reconstruction, then run every metric in the
config and write the result to the SQLite results store.

Each stage is idempotent — re-running picks up where the previous run
left off, gated on the presence of manifest files. Methods whose `fit`
is not yet implemented (`NotImplementedError`) are logged and skipped
rather than aborting the whole run.
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from .io.config import RunConfig
from .io.results_db import MetricRow, ResultsDB
from .metrics import GroundTruth, get_metric, list_metrics
from .methods import MethodConfig, get_method, list_methods
from .pipeline import (
    build_ground_truth,
    ensure_captures,
    ensure_scene,
    save_reconstruction,
    split_holdout,
)
from .scenes import get_scene
from .capture import load_capture


log = logging.getLogger("spiral_sandbox.run")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="spiral_sandbox")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--repo-root", type=Path, default=None,
                   help="Resolve config-relative paths against this dir "
                        "(defaults to the config file's parent's parent).")
    p.add_argument("--blender-bin", type=str, default="blender")
    p.add_argument("--log-level", type=str, default="INFO")
    p.add_argument("--skip-blender", action="store_true",
                   help="Skip stages that need Blender; useful for "
                        "running the metric layer over already-generated "
                        "captures.")
    return p.parse_args()


@dataclass
class _Counters:
    scenes: int = 0
    captures: int = 0
    fits: int = 0
    fit_skipped: int = 0
    metric_writes: int = 0
    metric_errors: int = 0


def _run_one_method(
    *,
    db: ResultsDB,
    run_id: int,
    config: RunConfig,
    scene_name: str,
    density: str,
    method_name: str,
    captures_train,
    gt: GroundTruth,
    counters: _Counters,
) -> None:
    artifact_dir = (
        config.output.artifacts_dir / scene_name / density / method_name
    )
    method = get_method(method_name)
    try:
        recon = method.fit(captures_train, MethodConfig())
    except NotImplementedError as exc:
        log.info("skip %s/%s/%s: %s", scene_name, density, method_name, exc)
        counters.fit_skipped += 1
        return
    except Exception as exc:  # method blew up; log + continue
        log.error(
            "fit failed for %s/%s/%s: %s",
            scene_name, density, method_name, exc,
        )
        log.debug(traceback.format_exc())
        return

    save_reconstruction(recon, artifact_dir)
    db.write_reconstruction(
        run_id=run_id,
        scene=scene_name,
        density=density,
        method=method_name,
        artifact_dir=artifact_dir,
        metadata=recon.metadata,
    )
    counters.fits += 1

    for metric_name in config.metrics.all_names():
        try:
            value, extra = get_metric(metric_name)(recon, gt)
        except KeyError:
            log.warning("metric '%s' not registered, skipping", metric_name)
            continue
        except NotImplementedError as exc:
            log.info(
                "metric '%s' not implemented for %s: %s",
                metric_name, method_name, exc,
            )
            continue
        except Exception as exc:
            log.error(
                "metric '%s' failed for %s/%s/%s: %s",
                metric_name, scene_name, density, method_name, exc,
            )
            log.debug(traceback.format_exc())
            counters.metric_errors += 1
            continue
        db.write_metric(
            run_id=run_id,
            row=MetricRow(
                scene=scene_name,
                density=density,
                method=method_name,
                metric=metric_name,
                value=value,
                extra=extra,
            ),
        )
        counters.metric_writes += 1


def main() -> int:
    args = _parse()
    _setup_logging(args.log_level)

    config = RunConfig.load(args.config)
    repo_root = args.repo_root or args.config.resolve().parent.parent
    config = config.resolve_paths(repo_root)

    log.info("methods registered: %s", list_methods())
    log.info("metrics registered: %s", list_metrics())

    db = ResultsDB(config.output.results_db)
    run_id = db.begin_run(config_path=args.config)
    log.info("run_id=%d  results_db=%s", run_id, config.output.results_db)

    counters = _Counters()
    for scene_entry in config.enabled_scenes():
        spec = get_scene(scene_entry.name)
        scene_dir = config.output.scenes_dir / scene_entry.name

        if args.skip_blender and not (scene_dir / "manifest.json").exists():
            log.warning(
                "skip-blender set and no scene manifest for %s; skipping",
                scene_entry.name,
            )
            continue

        if not (scene_dir / "manifest.json").exists():
            ensure_scene(
                spec, scene_dir, scene_entry.densities, config.seed,
                blender_bin=args.blender_bin,
            )
        scene_manifest_path = scene_dir / "manifest.json"
        counters.scenes += 1

        capture_root = config.output.captures_dir / scene_entry.name
        if args.skip_blender:
            cap_manifests = {
                d: capture_root / d / "captures.json"
                for d in scene_entry.densities
                if (capture_root / d / "captures.json").exists()
            }
        else:
            cap_manifests = ensure_captures(
                scene_manifest_path, capture_root, scene_entry.densities,
                blender_bin=args.blender_bin,
            )

        for density in scene_entry.densities:
            cap_manifest = cap_manifests.get(density)
            if cap_manifest is None or not cap_manifest.exists():
                log.warning(
                    "no captures for %s/%s, skipping density",
                    scene_entry.name, density,
                )
                continue
            captures = load_capture(cap_manifest)
            counters.captures += 1
            train, held = split_holdout(captures, n_holdout=1)
            gt = build_ground_truth(scene_manifest_path, held)

            for method_name in config.methods:
                _run_one_method(
                    db=db,
                    run_id=run_id,
                    config=config,
                    scene_name=scene_entry.name,
                    density=density,
                    method_name=method_name,
                    captures_train=train,
                    gt=gt,
                    counters=counters,
                )

    log.info(
        "done. scenes=%d captures=%d fits=%d skipped=%d "
        "metrics_written=%d metric_errors=%d",
        counters.scenes, counters.captures, counters.fits,
        counters.fit_skipped, counters.metric_writes,
        counters.metric_errors,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
