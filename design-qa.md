# Frontend design QA — 2026-10-07

Scope: polish the existing research workspace, retaining React, Lucide, ECharts, the navy/teal palette and existing analysis services. This is an intentional product refinement, not a pixel-identical reproduction.

## Visual evidence

- Source visual truth: `artifacts/design-review/02-before-theory.jpg`.
- Implementation: `artifacts/design-review/04-after-theory.jpg`.
- Full-view comparison: `artifacts/design-review/06-theory-comparison.jpg`.
- Focused header/navigation comparison: `artifacts/design-review/07-header-comparison.jpg`.
- Matrix: `artifacts/design-review/03-after-matrix.jpg`.
- Mobile: `artifacts/design-review/05-mobile-theory.jpg`.
- Evidence files are local, ignored review artifacts and are not included in the public source archive.

Baseline and implementation use the same 1006 × 658 CSS viewport, the same GAN analysis (one paper, three theory nodes, two dependencies), no selected learning goal and no assistant panel. Full-page captures are 991 × 2718 and 991 × 2063 pixels respectively; the browser scrollbar accounts for the viewport/capture width difference. Comparison preserves the captures' pixel scale, without stretching. The shortened page reflects intentionally collapsed conditions and proof explanations; their complete content remains available through disclosure controls.

Responsive checks also used 390 × 844 and 1440 × 900 CSS viewports. The mobile page fits the document client width, with horizontal scrolling confined to tabs and the comparison table.

## Findings and comparison history

- [P2, fixed] Navigation and hierarchy: the former long tab label crowded medium widths, and the header did not identify the selected view. Added compact tab labels, view titles/descriptions, selected sidebar shortcuts and keyboard tab navigation. Evidence: focused comparison.
- [P2, fixed] Theory reading flow: dependency graph followed long condition lists. Moved the graph next to the learning goal, made conditions and proof descriptions expandable, and grouped the learning path with its assistant action. Evidence: full-view comparison and successful expansion of Theorem 1's conditions.
- [P2, fixed] Graph framing: smaller containers could clip the bottom node label, while repeated edge labels competed with node text. Added chart margins and aspect preservation, and hid repeated dependency labels in layered mode; the arrow semantics remain in the graph description and accessible relation list. Verified fresh loading, layout switching and full-screen entry/exit. Intermediate hot-reload captures with stale chart transforms were rejected; final captures use a fresh page.
- [P2, fixed] Narrow-screen persistent controls: prior mobile styling hid report export and the sidebar contained the only history entry. Restored report export and added a mobile history button. Opened history and upload dialogs without submitting files.
- [P2, fixed] Assistant and wide-screen theory layout: the two-column theory layout became too compressed when the assistant occupied the right side. Use a stacked theory layout while the assistant is active.
- [P3, accepted] Tab and matrix horizontal scrolling remains on narrow screens; it preserves the complete labels and comparison content. Matrix paper cells stay pinned while other columns scroll.

## Required fidelity surfaces

- Typography: retained the existing system/CJK fallback and KaTeX fonts. Strengthened workspace/view/paper/node heading hierarchy; formulas and complete statements remain readable. Long content wraps or uses its existing local scroll container.
- Spacing: compact header and statistics, consistent card padding/radii, grouped search controls, graph placed near its learning context. Wide and narrow layouts were inspected.
- Colors: retained navy and teal tokens, with navy navigation, light selected states, and more legible secondary copy. This visual check is not a comprehensive accessibility certification.
- Assets: retained existing Lucide icons and data-rendered ECharts graphs. No new decorative raster assets, fabricated logos or custom substitute illustrations were introduced.
- Copy: added actionable view descriptions, learning hints, evidence counts and a recovery instruction for empty search results. Actual analysis data and original evidence references are preserved.

## Verification

- Search with no matches, then reset: passed.
- Learning goal selection and prerequisite path: passed.
- Native condition disclosure and original evidence dialog: passed.
- Graph layered/force switching and full-screen Escape: passed.
- Keyboard tab navigation: passed.
- Mobile history and upload dialog opening/closing: passed.
- Assistant opening and existing controls: passed; no model answer was generated as part of this visual check.
- Browser console error entries: none observed in the checked local session.
- Production frontend build: passed.
- Graph, evidence rendering and packaging checks: 10 passed.

No actionable P0/P1/P2 findings remain in the checked states. Remaining coverage gap: this pass does not replace testing every possible paper batch or a full screen-reader audit.

final result: passed
