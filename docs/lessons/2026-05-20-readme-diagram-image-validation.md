# README Diagram Image Validation

## Context

The dependency BOM README diagram was regenerated from the original Mermaid
history into the shared pastel infographic PNG/SVG style.

## Decision

Use PNG for README embeds and keep SVG beside it for reuse. Preserve the
English-only diagram text and avoid fixed canvas sizing so the dependency graph
can use the space it needs.

## Outcome

- 2 rendered artifacts
- 1 PNG file
- 1 SVG source file
- no missing README image links
- no local SVG image embeds in README files
- no remaining Mermaid code blocks

## Verification

- `node /Users/debop/work/bluetape4k/.omx/scripts/refine-readme-diagrams.mjs .`
- README image link and Mermaid residue checker
- PNG/SVG shape checker
- Visual image review
- `git diff --check`

## Future Guidance

For dense dependency diagrams, prioritize readable labels and valid arrow
geometry over forcing a uniform grid or repo-wide fixed image size.
