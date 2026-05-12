"""Refresh `site/` from the latest run and push to gh-pages.

    python -m spiral_sandbox.publish [--blender-bin PATH] [--push]

Steps:
1. Pick the latest run from `results/spiral.db`.
2. Copy the spiral.db + a JSON summary into `site/data/`.
3. Copy the rendered RGB views from each density into `site/figures/<density>/`.
4. Convert each scene's `ground_truth.obj` and any reconstructed mesh
   (`results/artifacts/.../mesh.obj`) into GLB via Blender headless,
   into `site/models/`.
5. Regenerate `site/index.html` from the SQLite results.
6. If `--push`, commit `site/` to main and `git subtree push` it to gh-pages.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="publish")
    p.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--blender-bin", type=str, default="blender")
    p.add_argument("--push", action="store_true",
                   help="Commit site/ and git subtree push to gh-pages.")
    return p.parse_args()


def _latest_run(db_path: Path) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    c = sqlite3.connect(db_path)
    rid = c.execute("SELECT MAX(run_id) FROM runs").fetchone()[0]
    rows = [
        dict(zip(["scene", "density", "method", "metric", "value", "extra"], r))
        for r in c.execute(
            "SELECT scene, density, method, metric, value, extra "
            "FROM metrics WHERE run_id=?",
            (rid,),
        )
    ]
    recons = [
        dict(zip(["scene", "density", "method", "artifact_dir", "metadata"], r))
        for r in c.execute(
            "SELECT scene, density, method, artifact_dir, metadata "
            "FROM reconstructions WHERE run_id=?",
            (rid,),
        )
    ]
    return int(rid), rows, recons


def _copy_renders(captures_dir: Path, site_figures: Path) -> dict[str, list[str]]:
    """Copy each density's RGB views into site/figures/<density>/."""
    out: dict[str, list[str]] = {}
    for scene_dir in captures_dir.iterdir():
        if not scene_dir.is_dir():
            continue
        for density_dir in scene_dir.iterdir():
            rgb = density_dir / "rgb"
            if not rgb.is_dir():
                continue
            dst = site_figures / scene_dir.name / density_dir.name
            dst.mkdir(parents=True, exist_ok=True)
            names = []
            for img in sorted(rgb.glob("*.png")):
                shutil.copy2(img, dst / img.name)
                names.append(f"{scene_dir.name}/{density_dir.name}/{img.name}")
            out[f"{scene_dir.name}/{density_dir.name}"] = names
    return out


def _convert_obj_to_glb(blender_bin: str, obj_path: Path, glb_path: Path) -> None:
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).parent / "scenes" / "to_glb.py"
    cmd = [
        blender_bin, "--background", "--python", str(script), "--",
        "--input", str(obj_path), "--output", str(glb_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _render_metric_table(rows: list[dict[str, Any]]) -> str:
    """HTML <tbody> rows for the metrics table."""
    out = []
    for r in sorted(rows, key=lambda r: (r["scene"], r["density"], r["method"], r["metric"])):
        v = r["value"]
        v_fmt = "—" if v is None else f"{v:.4f}"
        out.append(
            f'<tr><td>{r["scene"]}</td><td>{r["density"]}</td>'
            f'<td>{r["method"]}</td><td>{r["metric"]}</td>'
            f'<td class="num">{v_fmt}</td></tr>'
        )
    return "\n".join(out)


def _render_scene_sections(
    scenes: list[str],
    figures: dict[str, list[str]],
    method_models: dict[str, list[tuple[str, str, str]]],
    rows: list[dict[str, Any]],
) -> str:
    """One card per scene: GT viewer, reconstruction viewers (one per
    available method/density mesh), four sample captures, scene metrics
    sub-table. `method_models[scene]` is a list of (density, method,
    glb_relpath) for reconstructed-method meshes published in this run."""
    out = []
    for scene in scenes:
        out.append(f'<section class="scene-card"><h2>{scene}</h2>')
        # 3D viewers row
        out.append('<div class="viewers">')
        out.append(
            f'<figure><figcaption>Ground truth</figcaption>'
            f'<model-viewer src="models/{scene}_gt.glb" '
            f'alt="{scene} GT" camera-controls auto-rotate '
            f'shadow-intensity="0.4" exposure="1.0"></model-viewer></figure>'
        )
        for density, method, glb in method_models.get(scene, []):
            out.append(
                f'<figure><figcaption>{method} / {density}</figcaption>'
                f'<model-viewer src="models/{glb}" '
                f'alt="{scene} {method} {density}" camera-controls '
                f'auto-rotate shadow-intensity="0.4" '
                f'exposure="1.0"></model-viewer></figure>'
            )
        out.append('</div>')
        # Sample captures: pick 4 indexes spread across the trajectory
        # so the preview spans the elevation sweep (low → high), not the
        # first four near-low-elevation views.
        for k in sorted(k for k in figures if k.startswith(f"{scene}/")):
            density = k.split("/", 1)[1]
            all_names = figures[k]
            if not all_names:
                continue
            n_total = len(all_names)
            if n_total <= 4:
                picks = all_names
            else:
                picks = [
                    all_names[int(round(i * (n_total - 1) / 3))]
                    for i in range(4)
                ]
            out.append(
                f'<p style="font-size: 13px; margin: 8px 0 4px;">'
                f'{density} captures '
                f'<span class="pill">{n_total} total</span></p>'
            )
            out.append('<div class="gallery sample">')
            for n in picks:
                out.append(
                    f'  <img src="figures/{n}" alt="{n}" loading="lazy">'
                )
            out.append('</div>')
        # Scene-specific metric mini-table
        scene_rows = [r for r in rows if r["scene"] == scene]
        if scene_rows:
            out.append('<table>')
            out.append(
                '<thead><tr><th>Density</th><th>Method</th>'
                '<th>Metric</th><th class="num">Value</th></tr></thead>'
            )
            out.append('<tbody>')
            for r in sorted(scene_rows,
                            key=lambda r: (r["density"], r["method"], r["metric"])):
                v = r["value"]
                v_fmt = "—" if v is None else f"{v:.4f}"
                out.append(
                    f'<tr><td>{r["density"]}</td><td>{r["method"]}</td>'
                    f'<td>{r["metric"]}</td>'
                    f'<td class="num">{v_fmt}</td></tr>'
                )
            out.append('</tbody></table>')
        out.append('</section>')
    return "\n".join(out)


INDEX_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Spiral Sandbox — run {run_id}</title>
<script type="module" src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js"></script>
<style>
  :root {{ --fg:#1a1a1a; --muted:#666; --bg:#fafaf7; --card:#fff; --line:#e5e5e0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    color: var(--fg); background: var(--bg);
    padding: 1rem; max-width: 980px; margin: 0 auto;
  }}
  h1 {{ font-size: 1.5rem; margin: 0 0 .25rem 0; }}
  h2 {{ font-size: 1.2rem; margin: 0 0 .5rem 0; }}
  p {{ color: var(--muted); margin: 0 0 1rem 0; }}
  .pill {{ display: inline-block; padding: 2px 8px; font-size: 12px; background: #eee; border-radius: 999px; color: #333; }}
  .scene-card {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; margin: 16px 0; }}
  .viewers {{ display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); margin-bottom: 8px; }}
  .viewers figure {{ margin: 0; }}
  .viewers figcaption {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
  model-viewer {{ width: 100%; height: 38vh; max-height: 360px; background: #f7f7f1; border: 1px solid var(--line); border-radius: 6px; }}
  .gallery {{ display: grid; gap: 6px; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }}
  .gallery.sample {{ grid-template-columns: repeat(4, 1fr); }}
  .gallery img {{ width: 100%; aspect-ratio: 4/3; object-fit: cover; border-radius: 6px; background: #ddd; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; margin-top: 10px; }}
  th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--line); font-size: 13px; }}
  th {{ background: #f5f5ef; font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  td.num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  a {{ color: #0a66c2; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  details {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  code {{ background: #f0f0e8; padding: 1px 5px; border-radius: 3px; font-size: 13px; }}
</style>
</head>
<body>

<h1>Spiral Sandbox</h1>
<p>
  Comparative 3D reconstruction sandbox for the <em>Perspective as Trade</em> paper.
  One card per scene: ground truth, reconstructions, sample captures, scene-local metric table.
  <span class="pill">run #{run_id}</span>
</p>

{scene_sections}

<h2>Full comparative table</h2>
<table>
  <thead>
    <tr><th>Scene</th><th>Density</th><th>Method</th><th>Metric</th><th class="num">Value</th></tr>
  </thead>
  <tbody>
{metric_rows}
  </tbody>
</table>

<details style="margin-top: 12px;">
  <summary>Reading the comparative table</summary>
  <p style="margin-top: 8px;">
    Lower chamfer is better (units = scene meters); higher PSNR is better (dB).
    Photogrammetry on the noCUDA COLMAP build skips dense MVS — the
    Poisson mesh is built from only the sparse SfM cloud, so its surface
    quality is bounded by SfM cloud density. The asymmetric chamfer
    (pred→GT vs GT→pred) reflects predicted-coverage gaps; see
    <code>docs/open_questions.md</code>. Photogrammetry coordinates are
    aligned to GT via Umeyama similarity using paired camera centers.
  </p>
</details>

<h2 style="margin-top: 14px;">Browse the results database</h2>
<p>
  <a href="https://lite.datasette.io/?url=https://sanangasightings.github.io/spiral-3d/data/spiral.db" target="_blank">
    Open spiral.db in Datasette-Lite ↗
  </a> — runs entirely in your browser; no server.
  Or: <a href="data/spiral.db">spiral.db</a> ·
  <a href="data/latest_run.json">latest_run.json</a>
</p>

</body>
</html>
"""


def main() -> int:
    args = _parse()
    repo_root: Path = args.repo_root
    site = repo_root / "site"
    db_path = repo_root / "results" / "spiral.db"
    if not db_path.exists():
        print(f"no results DB at {db_path}; nothing to publish")
        return 1

    rid, rows, recons = _latest_run(db_path)
    print(f"publishing run {rid} ({len(rows)} metric rows)")

    site.mkdir(exist_ok=True)
    (site / "data").mkdir(exist_ok=True)
    (site / "figures").mkdir(exist_ok=True)
    (site / "models").mkdir(exist_ok=True)

    shutil.copy2(db_path, site / "data" / "spiral.db")
    (site / "data" / "latest_run.json").write_text(
        json.dumps({"run_id": rid, "rows": rows, "recons": recons}, indent=2),
        encoding="utf-8",
    )

    # Wipe any stale per-density figure trees and rebuild.
    for d in (site / "figures").iterdir():
        if d.is_dir():
            shutil.rmtree(d)
        else:
            d.unlink()
    figures = _copy_renders(repo_root / "results" / "captures", site / "figures")

    # Ground-truth GLB per scene.
    scenes_dir = repo_root / "scenes"
    scenes_found: list[str] = []
    for scene_dir in sorted(scenes_dir.iterdir()):
        if not scene_dir.is_dir():
            continue
        gt_obj = scene_dir / "ground_truth.obj"
        if gt_obj.exists():
            try:
                _convert_obj_to_glb(
                    args.blender_bin, gt_obj,
                    site / "models" / f"{scene_dir.name}_gt.glb",
                )
                scenes_found.append(scene_dir.name)
            except subprocess.CalledProcessError as exc:
                print(f"GLB convert failed for {gt_obj}: {exc.stderr}",
                      file=sys.stderr)

    # Reconstructed-method meshes (currently only photogrammetry).
    method_models: dict[str, list[tuple[str, str, str]]] = {}
    artifacts_dir = repo_root / "results" / "artifacts"
    if artifacts_dir.exists():
        for scene_dir in sorted(artifacts_dir.iterdir()):
            for density_dir in sorted(scene_dir.iterdir()):
                for method_dir in sorted(density_dir.iterdir()):
                    mesh_obj = method_dir / "mesh.obj"
                    if not mesh_obj.exists():
                        continue
                    glb_name = (
                        f"{scene_dir.name}_{density_dir.name}_"
                        f"{method_dir.name}.glb"
                    )
                    try:
                        _convert_obj_to_glb(
                            args.blender_bin, mesh_obj,
                            site / "models" / glb_name,
                        )
                        method_models.setdefault(scene_dir.name, []).append(
                            (density_dir.name, method_dir.name, glb_name)
                        )
                    except subprocess.CalledProcessError as exc:
                        print(
                            f"GLB convert failed for {mesh_obj}: "
                            f"{exc.stderr}",
                            file=sys.stderr,
                        )

    (site / "index.html").write_text(
        INDEX_TEMPLATE.format(
            run_id=rid,
            scene_sections=_render_scene_sections(
                scenes_found, figures, method_models, rows
            ),
            metric_rows=_render_metric_table(rows),
        ),
        encoding="utf-8",
    )
    print(f"wrote {site / 'index.html'}")

    if args.push:
        subprocess.run(
            ["git", "-c", "user.email=zacharykiser@gmail.com",
             "-c", "user.name=Zach Sundown",
             "add", "site"],
            cwd=repo_root, check=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=zacharykiser@gmail.com",
             "-c", "user.name=Zach Sundown",
             "commit", "-m", f"Publish run #{rid}"],
            cwd=repo_root, check=False,  # OK if nothing to commit
        )
        subprocess.run(
            ["git", "-c", "user.email=zacharykiser@gmail.com",
             "-c", "user.name=Zach Sundown",
             "subtree", "push", "--prefix", "site", "origin", "gh-pages"],
            cwd=repo_root, check=True,
        )
        print("pushed gh-pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
