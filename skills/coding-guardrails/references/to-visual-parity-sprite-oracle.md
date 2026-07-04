# TO-style visual parity: inspect sprites, recreate pixels, verify by oracle

Use when rebuilding or cloning a legacy UI whose fidelity depends on tiny sprites / 1px guide-lines / tree gutters. Screenshots and vision models are not enough; the original DOM/CSS/assets are the source of truth.

## Workflow

1. **Inspect the original implementation, not just its appearance.**
   - Read the extension/app CSS for the exact selectors, background images, offsets, repeat mode, padding, and z-order.
   - Measure the live DOM with `getComputedStyle()` + `getBoundingClientRect()` so source CSS and runtime reality agree.
   - Extract the relevant sprite/image assets and dump their alpha masks / logical pixel maps.

2. **Separate visual contract from architecture.**
   - Copy the *visual contract* exactly: pixel geometry, line color, offsets, pitch, sprite dimensions, masking behavior.
   - Do **not** blindly copy a legacy architecture if it conflicts with the new product architecture. Example: keep virtualization, but draw long rails with a separate structural overlay.

3. **Recreate proprietary sprites product-safely.**
   - Do not embed/copy third-party PNGs directly unless licensing permits it.
   - Recreate the pixel geometry with CSS/Canvas/SVG you own. CSS `box-shadow` maps are viable for tiny monochrome sprites.
   - Preserve antialias/opacity when it materially affects the look.

4. **Model every line system separately.**
   - Tree gutters often have multiple strands: parent/sibling rails, child rails, node-anchor glyphs, elbows, last-child terminators.
   - A single “continuous rail” abstraction can test green while visually wrong if the original deliberately masks the rail under the node box.

5. **Respect stacking contexts.**
   - Transformed virtual rows (`transform: translateY(...)`) create stacking contexts.
   - A child `z-index` cannot rise above a sibling overlay with a higher parent stacking order. If the row’s sprite/mask must cover an overlay rail, place the overlay behind the row (or lift the entire row layer), not just the child glyph.

6. **Verify with a deterministic pixel oracle.**
   - After rendering the new UI, crop the glyph/gutter from a live screenshot.
   - Downsample to logical pixels when DPR > 1.
   - Compare rendered pixel coordinates against the original sprite mask: report `missing=[]` and `extra=[]` for exact parity.
   - Use band-scans for 1px anti-aliased fractional-DPR vertical lines; single-column scans can false-fail.

## Session-derived example

Tabs Outliner’s tree gutter used CSS backgrounds:

- `.nodeTitleAndSubnodesContainer`: `lineto_subnode_s1.png` + `line_vertical_s1.png` repeated vertically.
- `.nodeTitleContainer`: `node_anchor_expanded_s1.png`, `node_anchor_colapsed_s1.png`, `node_anchor_no_subnodes_s1.png`.

Measured visual contract:

- depth pitch: `17px`
- anchor sprite: `15x16`
- rail color: `rgb(79,104,130)` / `#4f6882`
- important correction: the rail **does not** show through the node box interior; the 15x16 anchor sprite masks that area and paints only its own pixels.

The rebuild kept the modern virtualized architecture but recreated the TO anchor sprites as product-safe CSS pixel maps. The final live screenshot oracle matched the original expanded anchor sprite exactly: `missing=[]`, `extra=[]`.

## Pitfalls

- **Vision can confidently lie on 1px detail.** Treat it as a human-style sanity check, not an oracle.
- **“Continuous” is not always correct.** If the original sprite masks a rail under a box, matching that intentional discontinuity is parity.
- **Rounded CSS boxes are not pixel-art sprites.** A 13px rounded border can feel “close” but still fail the legacy UI’s visual language.
- **Z-order comments are not proof.** Inspect actual stacking contexts created by transforms and positioned elements.
