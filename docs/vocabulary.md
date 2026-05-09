# Vocabulary

The paper begins with vocabulary. Naming the operation changes how it can be reasoned about. The reader needs precise terms before any results make sense.

## Core terms

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

## The counter-clockwise conjecture

If clockwise compression trades (time + 1 spatial axis) for perspective, then a counter-clockwise abstraction would trade *perspective* for some other organizing principle, while preserving or even adding parameters.

This is **not** a solved problem. The paper proposes the conjecture and outlines what such an abstraction might look like — possibly state-space representations, behavioral models, causal graphs, or possibility trees — without claiming to have found it. This is the speculative section of the paper.
