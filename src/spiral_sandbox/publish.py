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


def _render_gallery(figures: dict[str, list[str]]) -> str:
    """HTML <figure> blocks per (scene, density)."""
    out = []
    for k in sorted(figures):
        names = figures[k]
        if not names:
            continue
        scene, density = k.split("/", 1)
        out.append(f'<h3 style="margin-bottom: .25rem;">{scene} / {density} '
                   f'<span class="pill">{len(names)} views</span></h3>')
        out.append('<div class="gallery">')
        for n in names:
            out.append(f'  <img src="figures/{n}" alt="{n}" loading="lazy">')
        out.append("</div>")
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
    padding: 1rem; max-width: 880px; margin: 0 auto;
  }}
  h1 {{ font-size: 1.5rem; margin: 0 0 .25rem 0; }}
  h2 {{ font-size: 1.1rem; margin: 1.5rem 0 .5rem 0; }}
  p {{ color: var(--muted); margin: 0 0 1rem 0; }}
  .pill {{ display: inline-block; padding: 2px 8px; font-size: 12px; background: #eee; border-radius: 999px; color: #333; }}
  model-viewer {{ width: 100%; height: 56vh; max-height: 480px; background: var(--card); border: 1px solid var(--line); border-radius: 8px; }}
  .gallery {{ display: grid; gap: 6px; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }}
  .gallery img {{ width: 100%; aspect-ratio: 4/3; object-fit: cover; border-radius: 6px; background: #ddd; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); font-size: 14px; }}
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
  <span class="pill">run #{run_id}</span>
</p>

<h2>Ground-truth scene</h2>
<p>The synthetic baseline. Pinch to zoom, drag to rotate.</p>
<model-viewer src="models/bunny_baseline_gt.glb"
  alt="Ground-truth bunny baseline scene"
  camera-controls auto-rotate shadow-intensity="0.6" exposure="1.0"
  ar ar-modes="webxr scene-viewer quick-look"></model-viewer>

<h2>Captures</h2>
{gallery_html}

<h2>Metrics</h2>
<table>
  <thead>
    <tr><th>Scene</th><th>Density</th><th>Method</th><th>Metric</th><th class="num">Value</th></tr>
  </thead>
  <tbody>
{metric_rows}
  </tbody>
</table>

<details style="margin-top: 8px;">
  <summary>Reading the comparative table</summary>
  <p style="margin-top: 8px;">
    Lower chamfer is better (units = scene meters); higher PSNR is better (dB).
    Photogrammetry on the noCUDA COLMAP build skips dense MVS — the
    Poisson mesh is built from only the sparse SfM cloud, so its surface
    quality is bounded by SfM cloud density. The asymmetric chamfer
    (pred→GT vs GT→pred) reflects predicted-coverage gaps; see
    <code>docs/open_questions.md</code>.
  </p>
</details>

<h2>Browse the results database</h2>
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
    for scene_dir in scenes_dir.iterdir():
        if not scene_dir.is_dir():
            continue
        gt_obj = scene_dir / "ground_truth.obj"
        if gt_obj.exists():
            try:
                _convert_obj_to_glb(
                    args.blender_bin, gt_obj,
                    site / "models" / f"{scene_dir.name}_gt.glb",
                )
            except subprocess.CalledProcessError as exc:
                print(f"GLB convert failed for {gt_obj}: {exc.stderr}",
                      file=sys.stderr)

    (site / "index.html").write_text(
        INDEX_TEMPLATE.format(
            run_id=rid,
            gallery_html=_render_gallery(figures),
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
