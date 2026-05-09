# Decision 0001 — Hosting stack for mobile-viewable outputs

**Date:** 2026-05-08
**Status:** Accepted
**Driver:** Mobile-viewability constraint (README → Constraints). Every figure,
3D reconstruction, results table, and draft document must be reachable from a
phone via a shareable link.

## Decision

**GitHub Pages + `model-viewer` + Datasette-Lite**, served from a `gh-pages`
branch (or `/docs` on `main`) of the project repository. One repo, one deploy
target, one URL space. No additional accounts, no per-artifact decisions.

| Output                | Format                          | Viewer on phone                                                         |
|-----------------------|---------------------------------|-------------------------------------------------------------------------|
| Static figures        | PNG / SVG in `site/figures/`    | direct image fetch                                                      |
| 3D reconstructions    | glTF / GLB in `site/models/`    | Google `<model-viewer>` web component (touch rotate, AR on supported phones) |
| Point clouds          | PLY → glTF point primitives     | same `<model-viewer>` page                                              |
| NeRF / Gaussian splat | converted to glTF preview where possible; otherwise a 360° turntable MP4 | `<model-viewer>` or native `<video>`                  |
| Results database      | `results/spiral.db` published as `site/data/spiral.db` | [Datasette-Lite](https://lite.datasette.io/) — SQLite in the browser via WASM, no server |
| Tabular extracts      | CSV / Parquet in `site/data/`   | same Datasette-Lite frontend; raw download links                        |
| Paper draft           | PDF + HTML in `site/paper/`     | direct fetch                                                            |

## Why

- **Already authed.** `gh` CLI is installed and authed (per CLAUDE.md). No new
  account or paid tier needed.
- **Static-first, free-tier-forever.** GitHub Pages is free for public repos,
  has a CDN, and cannot accidentally rack up usage charges.
- **Datasette-Lite collapses the database problem.** Publishing the SQLite file
  as a static asset and pointing Datasette-Lite at it gives a phone-usable
  query/filter UI for free, with no backend to keep alive. The same `.db` file
  is what the desktop pipeline writes to — zero translation.
- **`<model-viewer>` is mobile-native.** Touch gestures, AR on iOS/Android,
  drag-drop substitutes for "open in Blender."
- **One URL space** keeps the cross-linking story simple: a figure links to
  the model that produced it, which links to the results-DB rows it summarizes.

## Tradeoffs accepted

- **NeRF / Gaussian splat fidelity is reduced for the phone view.** Native
  formats don't render in `<model-viewer>`. The phone gets a turntable preview
  or a baked mesh; the full reconstruction stays viewable on desktop. The paper
  H3 test is desktop-side; phone is for review and discussion.
- **No realtime / no auth.** Acceptable — this is a research artifact, not a
  product.
- **SQLite size cap.** Datasette-Lite loads the whole DB into the browser. Fine
  while the results table is small (one row per `(scene, density, method,
  metric)`); if it grows past ~50 MB we revisit (chunk by scene, or move to a
  hosted Datasette).

## Alternatives considered

- **Cloudflare Pages / Vercel** — more polished, but adds an account and a
  deploy pipeline for no marginal capability.
- **Firebase Hosting** — Zach's Firebase auth is bound to `hoa-approved-plants`;
  setting up a second project is friction we don't need.
- **A hosted Datasette / Streamlit app** — buys interactivity but needs a
  running server and an auth boundary. Defer until research warrants it.

## Implementation hooks

- `results/figures/` and `results/artifacts/` get a `publish.py` step that
  copies into `site/` and commits to the `gh-pages` branch.
- Reconstruction methods that produce non-mesh representations include a
  `preview_glb_path` field in their `Reconstruction.metadata` for the publisher
  to pick up.
- The publisher runs at the end of `python -m spiral_sandbox.run` when
  `output.publish: true` is set in the run config.
