# The Spiral Framework: Project Outline, Vocabulary, and Bootstrap Prompt

**Working title:** *Perspective as Trade: A Comparative Topology of Dimensional Transmutation in 3D Reconstruction Methods*

**Author:** Zach Sundown
**Stance:** Theoretical framework + empirical synthetic sandbox + comparative analysis. Not inventing — naming and systematizing what humanity is already doing.

---

## 1. Conceptual Framework & Vocabulary

The paper begins with vocabulary. Naming the operation changes how it can be reasoned about. The reader needs precise terms before any results make sense.

### 1.1 Core Terms

**Source state.** The starting condition: physical reality with three spatial axes and one temporal axis (3+1). Tangible matter, continuous, infinite information density at every point.

**Compression mechanism.** The operation that abstracts the source state into a lower-information representation. In the clockwise direction (physical → digital), the compression mechanism is *perspective* — a viewpoint-anchored projection that collapses 3+1 onto a 2D plane plus an implicit camera pose.

**Abstraction.** The output of compression. A still photograph is the canonical abstraction: 3+1 reduced to a frozen 2D rectangle, with perspective doing the dimensional bookkeeping.

**Trade.** What is gained for what is lost during compression. In the clockwise direction: time and one spatial axis are surrendered; perspective is acquired. This is not a loss-only operation — it is an exchange. Naming it as a trade rather than a loss is critical to the framework.

**Reconstruction.** The inverse-direction operation that takes high-precision abstractions and rebuilds a higher-dimensional representation. Photogrammetry, NeRF training, Gaussian splat fitting, point cloud accumulation are all reconstruction operations.

**Transmutation.** The end state of the round trip. The reconstructed object is *not* the source object. It occupies a different ontological category — it has spatial geometry but no matter, infinite reproducibility but no singularity, downstream editability but no temporal continuity. The geometry may be correct; the essence is changed. This is the headline claim: the spiral does not return to its origin.

**Spiral.** The full operation viewed as a path in conceptual space. From above (top-down view) it looks like a closed circle: 3D → 2D → 3D. From the side it is a helix — the endpoint sits on a different plane than the origin. The spiral metaphor is what makes the transmutation visible.

**Path.** A specific method through the spiral. Photogrammetry to textured mesh is one path. Multi-view stereo to point cloud is another. NeRF is another. Gaussian splatting is another. Each path traverses the same conceptual spiral but produces non-equivalent reconstructions.

**Error topology.** The shape of where each path fails. Not a scalar (this method is X% accurate) but a *surface* over the trade-off space. Point clouds fail differently than NeRF, which fails differently than Gaussian splatting. The error topology of a method is its signature.

**Downstream affordance.** What the reconstruction lets the next person do. A point cloud affords editing and decimation. A NeRF affords novel-view synthesis but resists manipulation. A textured mesh affords standard 3D pipeline integration but loses sub-mesh detail. Affordance is non-visual and often more important than visual fidelity.

**Authorial intent / composition agency.** Following the conversation thread on Leonardo's Paragone: the painter exercises authorial intent at capture; reality capture aims to *neutralize* authorial intent so that downstream consumers can apply their own composition. The choice of reconstruction method directly affects how much composition agency transfers downstream.

**Parameter vs. dimension.** A deliberate vocabulary distinction. *Dimensions* are independent measurable axes treated as ontologically primary (x, y, z, t). *Parameters* are measurable properties treated as derivative or chosen (color, texture, material, behavior). The paper uses *parameter* when discussing what can be optionally captured and *dimension* when discussing what is structurally required.

### 1.2 The Counter-clockwise Conjecture

If clockwise compression trades (time + 1 spatial axis) for perspective, then a counter-clockwise abstraction would trade *perspective* for some other organizing principle, while preserving or even adding parameters.

This is **not** a solved problem. The paper proposes the conjecture and outlines what such an abstraction might look like — possibly state-space representations, behavioral models, causal graphs, or possibility trees — without claiming to have found it. This is the speculative section of the paper.

---

## 2. Research Hypotheses

**H1 (descriptive).** The set of methods commonly used for 3D reconstruction (point cloud, textured mesh, NeRF, Gaussian splatting, signed distance function, volumetric occupancy) all instantiate the same abstract operation: compression via perspective, then reconstruction with non-equivalent error topology.

**H2 (comparative).** When run on identical synthetic source data, these methods produce reconstructions whose differences are best characterized as *trade-off profiles* across geometric fidelity, visual fidelity, storage cost, render cost, editability, and failure-mode signature — not as a single ordering of "better" to "worse."

**H3 (perceptual–structural divergence).** Methods can be visually near-identical at the rendered output while differing radically in underlying representation and downstream affordance. NeRF vs. Gaussian splatting is the canonical test case.

**H4 (visual divergence with shared substrate).** Methods can produce visually divergent output from identical input data. Point cloud vs. textured mesh is the canonical test case here — same source images, different reconstructions, different visual character.

**H5 (speculative).** A counter-clockwise abstraction operation exists conceptually. It would trade perspective for a different organizing principle and add dimensions or parameters rather than removing them. The form of such an abstraction is an open question worth naming.

---

## 3. Project Architecture

### 3.1 Stages

**Stage A — Synthetic scene generation.** Programmatic construction of ground-truth 3D scenes in Blender via the Python API. Scenes designed to stress different methods in different ways.

**Stage B — Capture simulation.** From each scene, generate the inputs each method requires: rendered images from known camera poses, depth maps, point samples. All capture parameters logged to JSON.

**Stage C — Reconstruction pipeline.** Run each method on the synthetic captures. Output reconstructions to a standardized directory with manifest files.

**Stage D — Metric collection.** Run a battery of metrics on each reconstruction against ground truth. Output to a structured results database (SQLite or Parquet).

**Stage E — Analysis & visualization.** Generate the trade-off space plots, error topology surfaces, and per-method signatures. Produce figures suitable for the paper.

**Stage F — Insight extraction.** Human-in-the-loop review of results, looking for patterns the framework predicts and surprises it doesn't.

**Stage G — Paper drafting.** Write the conceptual framework, methods, results, and discussion sections. The conjecture section is hand-written; the comparative results are largely generated from Stage E outputs.

### 3.2 What Runs Hands-Off

Stages A through E should run end-to-end with a single command. The sandbox is the deliverable here. Stage F is where Zach engages — reading results, arguing with them, generating insights. Stage G is collaborative writing.

### 3.3 Synthetic Scene Catalog

Every scene must have known ground truth: meshes with vertices, materials with measurable properties, lighting with known parameters. The catalog stresses the methods at known weak points.

| Scene | Stress test for |
|-------|----------------|
| Stanford bunny + textured floor | Baseline; well-conditioned input |
| Mirrored sphere | Specular surface (NeRF strong, photogrammetry weak) |
| Featureless white wall + edge | Featureless region (photogrammetry weak, NeRF passable) |
| Thin foliage / grass blades | Sub-pixel geometry (point cloud weak, NeRF strong) |
| Glass vase | Transparency (all methods weak, characterizes failure mode) |
| Heavily occluded interior | Visibility constraints |
| Repeating pattern (checkerboard tower) | Aliasing, correspondence ambiguity |
| Animated object across frames | Tests temporal collapse (this is the trade — what is lost) |
| Blue-morpho-style structural color | Material-geometry entanglement (theoretical edge case) |

Each scene is rendered at multiple camera densities (sparse / medium / dense) to also study how each method's error topology shifts with input density.

### 3.4 Methods Under Test

| Method | Library |
|--------|---------|
| Point cloud (depth + camera fusion) | Open3D |
| Photogrammetric textured mesh | COLMAP + Open3D meshing |
| Multi-view stereo dense cloud | OpenMVS or COLMAP dense |
| NeRF | nerfstudio (nerfacto) |
| Gaussian splatting | gsplat or original 3DGS reference |
| Signed distance function (neural) | nerfstudio (neus-facto) or instant-NGP variant |

All methods consume the same synthetic capture set. All output a reconstruction in a standardized format.

### 3.5 Metrics

**Geometric fidelity (vs. ground-truth mesh):**
- Chamfer distance
- Hausdorff distance
- Normal consistency
- F-score at multiple thresholds

**Visual fidelity (vs. ground-truth renders from held-out poses):**
- PSNR
- SSIM
- LPIPS (perceptual)

**Resource cost:**
- File size on disk
- Peak memory during reconstruction
- Wall-clock training/fitting time
- Render time per novel view at fixed resolution

**Affordance proxies:**
- Number of independently addressable primitives (proxy for editability)
- Whether the representation supports relighting (yes/no, with caveats)
- Whether the representation is differentiable end-to-end (yes/no)
- Topology export quality (does mesh extraction produce a usable mesh?)

**Failure-mode signature:**
- Per-region error decomposition: project the geometric error back onto the ground truth mesh and tag which scene region (specular / featureless / thin / occluded / etc.) the error concentrates in.

The output of the metric stage is a long-format table: one row per (scene, density, method, metric) tuple. This table is what every chart in the paper plots.

### 3.6 Analysis Outputs

- **Trade-off radar charts** per method showing all metric axes simultaneously.
- **Error topology heatmaps** projected onto ground-truth meshes per scene per method.
- **Pareto frontier plots** for selected metric pairs (e.g. visual fidelity vs. file size).
- **Method-divergence matrix:** pairwise difference between methods on the same scene, separating perceptual divergence from structural divergence. This is the H3/H4 test.
- **Density-sensitivity curves** showing how each method's metrics shift as input view density changes.

---

## 4. Bootstrap Prompt for Claude Code

The bootstrap prompt below is what was dropped into a fresh Claude Code session to scaffold this repo. Kept here verbatim as a record of the original instructions.

> **Project: Spiral Sandbox**
>
> You are bootstrapping an analytical sandbox for a research paper comparing 3D reconstruction methods (point cloud, textured mesh, NeRF, Gaussian splatting, SDF, dense MVS) on identical synthetic input data. The paper's framing is dimensional trade-off and error-topology analysis, not method invention.
>
> **Operating principles:**
> - Synthetic-first. No real-world capture in this codebase. All inputs are generated from Blender scenes with known ground truth.
> - One command runs the whole pipeline end-to-end: `python -m spiral_sandbox.run --config configs/full_run.yaml`.
> - Every artifact is reproducible from the config plus a fixed random seed.
> - Results land in a structured SQLite database plus a per-run directory of artifacts.
> - Methods are pluggable. Adding a new reconstruction method should be a single file implementing a defined interface.
>
> **Phase 1 — Scaffolding (do this first):** Create the repo structure (see README for layout). Write the README to describe the project at a high level and list every method, scene, and metric the sandbox is designed to support.
>
> **Phase 2 — Method interface.** Define `Method` as a base class with `fit(captures, config) -> Reconstruction` and `render(reconstruction, camera) -> Image`. Define `Reconstruction` as a typed object with `geometry_export() -> Mesh | PointCloud | None` and `metadata: dict`. Stub each of the six methods as a class inheriting from `Method`, with a `NotImplementedError` body and a docstring explaining what it will do. Wire them into a method registry keyed by name.
>
> **Phase 3 — Scene generation.** Implement a Blender scene generator for the simplest scene first: Stanford bunny on a textured plane with a single area light. Generation runs in headless Blender (`blender --background --python`). Output: a `.blend` file plus a manifest JSON listing camera poses, light parameters, and ground-truth mesh path.
>
> **Phase 4 — Capture simulation.** From a scene manifest, render N views at specified resolutions, plus depth maps and (where applicable) sparse point samples. Save to a capture directory with a manifest.
>
> **Phase 5 — One real method end-to-end.** Implement the point cloud method (depth + camera fusion via Open3D) fully. Run it on the bunny scene. Verify the reconstruction loads and renders. This is the smoke test for the entire pipeline.
>
> **Phase 6 — Metrics infrastructure.** Implement Chamfer distance and PSNR as the first two metrics. Wire results into the SQLite database. Generate a single placeholder bar chart of those two metrics.
>
> **Phase 7 — Expand methods one at a time.** Photogrammetry next (COLMAP wrapper). Then Gaussian splatting via gsplat. Then NeRF via nerfstudio. Then SDF. Then dense MVS. Each method gets an integration test that runs it on the bunny scene and asserts the reconstruction loads.
>
> **Phase 8 — Expand scenes.** Add scenes from the catalog one at a time, with a stress-test annotation describing what failure mode each is designed to expose.
>
> **Phase 9 — Expand metrics.** Add Hausdorff, normal consistency, F-score, SSIM, LPIPS, and the resource metrics. Add the affordance proxy metrics last; some are heuristic.
>
> **Phase 10 — Analysis layer.** Implement the radar chart, error topology heatmap, Pareto frontier plot, and method-divergence matrix as standalone scripts that read from the results DB and write figures to `results/figures/`.
>
> **Important constraints:**
> - Use `uv` for dependency management. NeRF and Gaussian splatting libraries have heavy GPU dependencies — isolate them in optional dependency groups so the rest of the sandbox installs cleanly without them.
> - Every long-running operation logs progress and is resumable.
> - Configs are YAML, parsed into typed dataclasses with pydantic.
> - No hardcoded paths. Everything flows from config.
>
> When you reach the end of a phase, stop and summarize what was built and what's next, so I can review before you continue.

---

## 5. Paper Output Structure

Final paper sections:

1. **Introduction.** The Paragone framing — Leonardo's painter-vs-poet argument — opening to the modern problem of reality capture and the question of where authorial intent lives in a captured-then-reconstructed scene.
2. **Vocabulary & Framework.** The spiral, the trade, transmutation, error topology, downstream affordance. This is the section that gives readers the language.
3. **Hypotheses.**
4. **Methods.** Synthetic sandbox design, scene catalog, method roster, metric battery.
5. **Results.** Trade-off profiles per method, error topology maps, perceptual–structural divergence analysis (NeRF vs. GS), visual divergence analysis (point cloud vs. mesh).
6. **Discussion.** What the trade-off space implies for downstream agency. Why no method dominates. Why "best method" is the wrong question.
7. **The Counter-clockwise Conjecture.** Speculative section. What an abstraction in the opposite direction might look like. Open invitation to the field.
8. **Conclusion.**

Target venue: open question. Possibly a computer graphics / computer vision conference (SIGGRAPH, CVPR, ECCV) for the empirical work; possibly a Leonardo journal or arts-and-technology venue for the conceptual framing. A pre-print on arXiv is the no-regret first move.

---

## 6. Open Questions to Track

Maintained as `docs/open_questions.md` in the repo and revisited every analysis pass.

- Is there an existing mathematical formalism that already names the spiral? Likely candidates to investigate: Radon transform / inverse problems, plenoptic function (Adelson & Bergen 1991), light field theory, projective geometry literature.
- Does any method's error topology cluster into discrete failure classes, or is it continuous?
- For the perceptual–structural divergence test (NeRF vs. GS): can we quantify "downstream affordance" in a principled way, or does it stay heuristic?
- The blue morpho case: does any method preserve structural color, or is material-geometry entanglement universally lost? This may be a sub-paper of its own.
- Counter-clockwise: is there any working formalism in physics or systems theory that does what's described — adding dimensions while changing the organizing principle? State-space representations? Category-theoretic constructions?

---

## 7. What Lives Where

| Artifact | Location |
|----------|----------|
| This document | `docs/project.md` |
| Vocabulary | `docs/vocabulary.md` (extracted from §1) |
| Hypotheses | `docs/hypotheses.md` (extracted from §2) |
| Open questions | `docs/open_questions.md` |
| Code | `src/spiral_sandbox/` |
| Scene configs | `configs/scenes/` |
| Run configs | `configs/` |
| Results database | `results/spiral.db` (gitignored) |
| Figures | `results/figures/` |
| Paper draft | `paper/` (LaTeX or Quarto) |

---

## 8. The Vocabulary Move

Worth re-stating because it is the meta-point of the whole project: changing one word — *dimension* to *parameter* — shifted the entire conceptual space of this conversation. The paper's contribution is not the sandbox results. It is the vocabulary that lets people see the operation. The sandbox provides the empirical backbone so the vocabulary is grounded, not floating.

The deliverable to the field is: *here is a name for what we are doing, here is how the methods compare under that name, and here is a direction the name suggests we have not yet explored.*
