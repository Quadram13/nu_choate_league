# Fragment contract (A1 deliverable — binding on A2, A3, and all C-lane tickets)

The split-line in one sentence: **fragments own facts, shells own grammar.** This file is the mechanical version of `synthesis.md`. Where a ticket and this file disagree, the ticket loses or the file is amended in the same PR.

## 1. Definitions

- **Fragment**: a stat board, game list, week card, or record table. Theme-agnostic. Rendered by shared templates under `hub/templates/fragments/` (A2 creates the directory).
- **Shell**: one per theme, `hub/templates/shells/<theme>.html` + `hub/static/themes/<theme>.css`. Owns layout, nav grammar, rails, bands, type, color.
- **Pane**: one addressable section of a page (`Pane(name, label, template, loader)`). Only the active pane's loader runs per request.
- **Slot**: a named mount point a page offers (`lead`, `aside`); every shell must mount both.
- **Board registry**: the single declaration of each board's columns, with per-era **projections** (see §4).

## 2. Fragment rules (import/boot-checked)

1. Markup is semantic and class-only. No inline styles, no `bgcolor`, no `border=` attributes, no era tags.
2. `<table` appears in exactly one template: the shared `stat_table` macro. A second occurrence fails the boot gate.
3. Fragments MUST NOT read the theme, contain `theme=` in any href, or `{% extends %}`. Content hrefs are plain root-relative paths.
4. Zero-tie cells render the glyph `-` (one shared function) in era themes; modern's legacy templates keep today's exact bytes until #107.
5. Leader emphasis is a cell class — `is-leader` (bold), `is-record` (gold text), `is-active-leader` (italic) — plus a glossary footnote. No cell background fills.
6. Player-name formatters live in one module; era formats (`A. Rodgers` for era2010 boards) are projections of the same value.

## 3. Shell rules

1. A shell mounts content only through the frame's fragment/slot includes; it contains no stat facts (boot-checked: no query-field names in shell templates).
2. Pane navigation is shell grammar: numeral rows in era90, tab strip in era2010, today's jump links in modern — all real `<a href>` to pane URLs; JS never required.
3. Week numeral navigation lives in the shell layer (`week_slice` + week-nav include); week content is a fragment.
4. era90's stylesheet may not use flexbox/grid (boot-checked) and era90 markup may use a real layout table in the SHELL only; era2010's may use flex; both must render stat grids on a light surface with blue links.
5. The era90 right rail is ONE labeled link box; dead off-site labels are text, never invented hrefs.

## 4. Boards and projections

1. Every board declares its default column set once in the registry: key, label, numeric flag, formatter.
2. An era projection declares a subset/reorder of the same columns (era90 small grid) — never new values. Raw values for shared keys must be identical across eras; the boot fixture render checks this.
3. Top-N modules use real links: `?rows=all` (or a fragment URL), never client-side-only expansion. View All is an `<a href>`.
4. Pagination is a numeral row of real links (helper shared by all themes), stable sort, deliberate page size.

## 5. Theme machinery

1. `render_panes(request, title, nav, pager, panes, slots, context)` is the only era render entry. `Pane`, `Slot`, frozen `Frame` are the public types.
2. Theme resolution: `?theme=` → cookie (A2) → `modern` default. Unknown values render modern. Modern is served by the legacy `page()` path byte-near (parity-harness gated); eras are served by `render_panes`.
3. The theme switcher is a set of real links (form+GET or query links) present on every shell including modern's minimal injection; no JS required.
4. Boot gate (fail-closed, C1 graft): theme registry ↔ shell files ↔ stylesheets ↔ pane ids ↔ season sections agree; fragment rules §2 hold; era stylesheet rules §3.4 hold; fixture render echoes registry values. Violation = process refuses to serve.

## 6. Loading (A3/D1/D2 consume this)

1. A pane URL serves a full document; a **fragment URL** (`/fragments/<board>…`, A3) serves the bare fragment for JS inline upgrades. Same template, same loader, two envelopes.
2. Deferred sections are real links first; JS may inline them but is never the only path.
3. No virtual scroll, no `<details>`-wrapped full tables, no `display:none` row-hiding as a loading strategy.

## 7. Verification hooks (every C-lane PR)

- Parity harness green on modern (`scripts/ui/parity.ps1`).
- Body-diff discipline (C3 graft): rendered fragment regions identical across themes except declared projections; modern documents byte-near vs the main baseline.
- No-JS sweep: switcher, panes, pagination, View All all usable with script disabled.
- Light-surface screenshot evidence for era stat grids.
