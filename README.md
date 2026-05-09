# Spiral Sandbox

Analytical sandbox for *Perspective as Trade: A Comparative Topology of Dimensional Transmutation in 3D Reconstruction Methods* (Zach Sundown).

The sandbox runs identical synthetic input through six 3D reconstruction methods and captures the trade-off profile of each — geometric fidelity, visual fidelity, resource cost, downstream affordance, and per-region failure signature. The paper's contribution is the vocabulary that lets these results be compared on equal terms; the sandbox provides the empirical backbone.

See `docs/project.md` for the full project outline, `docs/vocabulary.md` for core terms, `docs/hypotheses.md` for the research hypotheses, and `docs/open_questions.md` for the running list of unresolved questions.

## One command

```bash
python -m spiral_sandbox.run --config configs/full_run.yaml
```

Reproducible from config plus a fixed random seed. Results land in `results/spiral.db` plus a per-run artifact directory.

## Methods under test

| Method | Library |
|--------|---------|
| Point cloud (depth + camera fusion) | Open3D |
| Photogrammetric textured mesh | COLMAP + Open3D meshing |
| Multi-view stereo dense cloud | OpenMVS or COLMAP dense |
| NeRF | nerfstudio (nerfacto) |
| Gaussian splatting | gsplat |
| Signed distance function (neural) | nerfstudio (neus-facto) |

Methods are pluggable: a new method is one file implementing the `Method` interface, registered by name.

## Scene catalog

Each scene is rendered at sparse / medium / dense camera densities so the error-topology shift with input density can be studied alongside the method comparison.

| Scene | Stress test for |
|-------|----------------|
| Stanford bunny + textured floor | Baseline; well-conditioned input |
| Mirrored sphere | Specular surface |
| Featureless white wall + edge | Featureless region |
| Thin foliage / grass blades | Sub-pixel geometry |
| Glass vase | Transparency |
| Heavily occluded interior | Visibility constraints |
| Repeating pattern (checkerboard tower) | Aliasing, correspondence ambiguity |
| Animated object across frames | Temporal collapse (the trade itself) |
| Blue-morpho structural color | Material-geometry entanglement |

## Metrics

- **Geometric fidelity** (vs. ground-truth mesh): Chamfer, Hausdorff, normal consistency, F-score at multiple thresholds
- **Visual fidelity** (vs. held-out renders): PSNR, SSIM, LPIPS
- **Resource cost:** disk size, peak memory, training/fitting time, render time per novel view
- **Affordance proxies:** independently addressable primitive count, relighting support, end-to-end differentiability, mesh-export quality
- **Failure-mode signature:** per-region error decomposition projected back onto the ground-truth mesh

Output is a long-format `(scene, density, method, metric)` table in SQLite. Every figure in the paper plots from this table.

## Repo layout

```
spiral 3d/
  configs/               run + scene configs (YAML)
    scenes/
    full_run.yaml
  scenes/                generated .blend scenes + manifests
  methods/               per-method run output
  src/spiral_sandbox/    code
    run.py               pipeline entry point
    scenes/              Blender scene generators
    capture/             camera trajectory + render
    methods/             one file per reconstruction method
    metrics/             one file per metric family
    analysis/            plots, tables, paper figures
    io/                  results DB, artifact manifest
  notebooks/
  results/               gitignored — DB + figures + artifacts
  docs/
    project.md           full project outline
    vocabulary.md
    hypotheses.md
    open_questions.md
  paper/                 LaTeX or Quarto draft
  pyproject.toml
  README.md
```

## Status

Phases 1–6 complete. Phase plan in `docs/project.md` §3.1.

- **Phase 1 — scaffolding.** Repo structure, docs, configs, package skeleton.
- **Phase 2 — method interface.** `Method`, `Reconstruction`, `MethodConfig` in `methods/base.py`; name-keyed registry; all six methods stubbed (`point_cloud`, `photogrammetry`, `mvs`, `nerf`, `gaussian_splatting`, `sdf`).
- **Phase 3 — scene generation.** `scenes/bunny.py` is a headless-Blender script that emits a `.blend`, an OBJ ground-truth, and a `SceneManifest` (camera poses per density + lights). Defaults to a subdivided UV sphere when the Stanford bunny `.ply` isn't on disk; pass `--bunny-ply` to swap it in.
- **Phase 4 — capture simulation.** `capture/render.py` is a headless-Blender script that walks a `SceneManifest`, renders RGB + Cycles depth at every pose, and writes a `CaptureManifest` per density. `capture/load_capture` reads it back into `Capture` objects with numpy arrays.
- **Phase 5 — point cloud method.** Depth-and-pose fusion in numpy (with Open3D voxel + outlier filtering when available, numpy fallback when not). Renders novel views via a numpy z-buffered point splat — visual-fidelity metrics work without a GPU.
- **Phase 6 — metrics + results store.** Symmetric Chamfer (vs. an OBJ ground truth, area-weighted surface sampling) and PSNR (vs. held-out renders). SQLite results store at `results/spiral.db` with three tables: `runs`, `metrics`, `reconstructions`. `python -m spiral_sandbox.run --config configs/full_run.yaml` is the live entry point — it gates each stage on the on-disk manifest, so re-runs resume.

Next: Phase 7 — second method end-to-end (photogrammetry via COLMAP), once Blender is installed and the bunny scene has actually been rendered locally.

### Hosting

The mobile-viewable output stack is locked in `docs/decisions/0001-hosting-stack.md`: GitHub Pages + `<model-viewer>` + Datasette-Lite, served from one `gh-pages` branch. The publisher hook fires when `output.publish: true` is set in the run config (Phase 10).

### Tests

`pytest tests` covers config loading, the SQLite results store, the methods registry, the metric math (Chamfer / PSNR / OBJ + surface sampling), the point-cloud fit/render path on synthetic depth, and the full orchestrator loop end-to-end (synthesizes a planar scene + captures, fits `point_cloud`, gracefully skips an unimplemented `nerf`, writes Chamfer + PSNR rows to a real SQLite file). 20 tests, no Blender or GPU required.

## Constraints

- `uv` for dependency management. NeRF and Gaussian splatting libraries have heavy GPU dependencies; they live in optional dependency groups so the rest installs cleanly without a GPU.
- Every long-running operation logs progress and is resumable.
- Configs are YAML, parsed into typed dataclasses with pydantic.
- No hardcoded paths. Everything flows from config.
- Synthetic-first: no real-world capture in this codebase. All inputs come from Blender scenes with known ground truth.
- Mobile-viewable outputs. Every artifact a human consumes — figures, 3D reconstructions, results tables, draft documents — must be reachable from a phone via a shareable link. The build runs on a desktop; review happens on mobile. Concrete implication: 3D reconstructions need a web viewer (or an exported video / glTF preview), figures publish to a static URL, and the results database has either a web report or a CSV/Parquet export served alongside it. No "open in Blender" or "load this .ply locally" as the only path to a result.
