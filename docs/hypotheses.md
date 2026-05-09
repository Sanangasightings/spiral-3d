# Research hypotheses

**H1 (descriptive).** The set of methods commonly used for 3D reconstruction (point cloud, textured mesh, NeRF, Gaussian splatting, signed distance function, volumetric occupancy) all instantiate the same abstract operation: compression via perspective, then reconstruction with non-equivalent error topology.

**H2 (comparative).** When run on identical synthetic source data, these methods produce reconstructions whose differences are best characterized as *trade-off profiles* across geometric fidelity, visual fidelity, storage cost, render cost, editability, and failure-mode signature — not as a single ordering of "better" to "worse."

**H3 (perceptual–structural divergence).** Methods can be visually near-identical at the rendered output while differing radically in underlying representation and downstream affordance. NeRF vs. Gaussian splatting is the canonical test case.

**H4 (visual divergence with shared substrate).** Methods can produce visually divergent output from identical input data. Point cloud vs. textured mesh is the canonical test case here — same source images, different reconstructions, different visual character.

**H5 (speculative).** A counter-clockwise abstraction operation exists conceptually. It would trade perspective for a different organizing principle and add dimensions or parameters rather than removing them. The form of such an abstraction is an open question worth naming.
