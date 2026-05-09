# Open questions

Revisited every analysis pass. Append; don't rewrite.

- Is there an existing mathematical formalism that already names the spiral? Likely candidates to investigate: Radon transform / inverse problems, plenoptic function (Adelson & Bergen 1991), light field theory, projective geometry literature.
- Does any method's error topology cluster into discrete failure classes, or is it continuous?
- For the perceptual–structural divergence test (NeRF vs. GS): can we quantify "downstream affordance" in a principled way, or does it stay heuristic?
- The blue morpho case: does any method preserve structural color, or is material-geometry entanglement universally lost? This may be a sub-paper of its own.
- Counter-clockwise: is there any working formalism in physics or systems theory that does what's described — adding dimensions while changing the organizing principle? State-space representations? Category-theoretic constructions?
- Mobile-viewable output stack: which hosting + viewer combination delivers every artifact (3D reconstructions, figures, results tables, draft documents) as a phone-openable link with the least operational overhead? Candidates: GitHub Pages + a static-site renderer for the wiki/figures + `model-viewer` for glTF + Datasette or a static HTML export for the results DB; alternatively a single deploy target like Cloudflare Pages or Vercel hosting all four. Decision point arrives at Phase 10 (analysis layer); pick before we accumulate format debt.
