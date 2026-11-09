# A1 grounding package — theme architecture spike (#95)

Shared grounding for the arena candidates. Read this end to end, plus `docs/ui/research-digest.md` (the era evidence base; its reachability table is authoritative — cite only reached sources), plus ticket #95 on GitHub.

## The decision

How do three first-class themes (modern / 1990s / ~2010) share one hub's data and content? This is the wave's one-way door: every later ticket (theme infra A2, loading mechanism A3, the C-lane era builds, IA restructures B1–B3) keys off the split-line chosen here.

## System facts (verified against the wave worktree at 68324dd)

- FastAPI + Jinja2. One `Jinja2Templates(directory=hub/templates)`. Static files at `hub/static` mounted `/static`.
- 20 GET routes in `src/nu_choate_league/web/app.py`, all rendering through one helper:

```python
def page(request: Request, name: str, *, nav: str, title: str, **context) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"nav": nav, "title": title, **context})
```

- 27 templates, flat: `base.html` (shell every page extends), 19 page templates, 7 `*_macros.html` libraries (acquisition, draft, plaque, scoring, trade, week_card, wire) that render nearly every stat table hub-wide.
- ONE stylesheet `hub/static/hub.css` (2121 lines), ONE script `hub/static/hub.js` (509 lines, dependency-free, no build step).
- The season page (`season.html`, 1227 lines) is ALREADY a tabbed mega-page: panes standings/weeks/playoffs/moves/draft/lineups/stacks with hash aliases, JS-only tab switching today.
- `/players` ships a 5,243,355-byte document (career 518 rows + season 1,370 rows + wire boards + counting boards). Perf-wave time 0.90s. The wave splits it PFR-style (ticket #105) — the architecture must make deferred fragments natural.
- The hub already has a disclosure vocabulary: client-side top-20 `js-fold`, column sort, year/pos filters. Loading lane extends this; it does not invent a second mechanism.
- DB: shared Docker Postgres on :5433 (read-only for this spike; NO schema changes, NO loads).

## Product constraints (locked — from #45, the go message, and the digest)

1. Three themes are first-class and selectable: **modern** (current hub, byte-near), **1990s** (dense table portals, blue links, ticker/link-farm grammar), **~2010** (fixed-width glossy shell, tabbed league home, logos, matchup cards). Switch persists; works WITHOUT JavaScript (link/form + cookie or equivalent).
2. No-JS spine everywhere: theme switching, tabs, pagination, deferred sections must all work as plain links; JS is an upgrade layer only.
3. Light stat surfaces in EVERY theme (Yahoo 2013 dark-UI failure: numbers on black were unreadable, no revert).
4. Leader emphasis = bold/gold/italic text + footnotes; never cell fills (PFR pattern).
5. Era grammar is real, not costume: 1998 portal = 3-column borderless (left rail league tasks in fixed order, right-rail labeled link box, commissioner header band #660000); standings as small bordered grids W-L-T/PF/PA with `-` ties, no zebra striping, no header fills; numeral-row pagination (`Results 1 … 16`, each numeral a link). ~2010 = tabbed league home mapped onto the EXISTING season panes (do NOT fabricate an ESPN 2010 tab order — it was not captured), matchup cards, top-10 modules with View All links, MFL dense standings row.
6. A theme ships only when every page family uses it (no half-migration — the Yahoo 2013 lesson). The architecture decides how this is enforced mechanically.
7. Modern stays byte-near identical to today until #107 (C3 polish). Theme machinery must not regress the perf-wave numbers (statement-level cost per render matters; no per-theme double-querying).

## The three hardest surfaces (prototype targets — same task for every candidate)

1. **/players rankings table** (one board, e.g. career top-50): the heaviest table macro in the hub, must render in all three era grammars.
2. **Season page shell**: the existing tabbed mega-page must become (a) modern-as-today, (b) 1998 numeral-row linked pages, (c) ~2010 tabbed league home — one content source.
3. **One stat macro ×3 grammars**: pick one `*_macros.html` table (e.g. scoring) and render it in all three themes.

## Candidate seeds (structurally distinct; diverge further if you find a better shape — differences are signal)

- **C1 — Per-theme template sets.** Each theme owns a template directory (`themes/era90/`, `themes/era2010/`, `themes/modern/`) with full freedom over markup; shared pieces live as class-only include fragments. Loader resolves theme-first with fallback. Era fidelity is total; the risk is drift between three copies of every board.
- **C2 — Hybrid: per-theme shells + shared class-only fragments.** ONE content template set renders theme-agnostic, class-only stat markup; themes own only the shell (layout, rails, header, chrome) + one stylesheet each. Structural era differences must fit in shells; content never forks.
- **C3 — CSS-skin as far as it goes.** Single DOM for all themes; theme = stylesheet + `data-theme` attribute; era structure (portal columns, tabs-as-rows) expressed via CSS reordering and conditional classes only where CSS genuinely cannot.

## Rubric (what the synthesis scores)

1. **Era-fidelity headroom** — can the 1998 portal AND the ~2010 tabbed shell both be expressed without hacks on the hardest surfaces?
2. **Content single-source** — a stat board is written once; adding a 4th theme or changing a board touches how many files?
3. **No-JS spine** — switch/tabs/pagination as real links with JS disabled.
4. **Blast radius on existing code** — how many of the 27 templates / 7 macro libs must change; does modern stay byte-near?
5. **Agent-maintainability** (design-red-flags screen) — one obvious way to add a page; no hand-synced lists; copying the nearest example yields the right thing; no shallow modules or split ownership.
6. **Perf/payload** — no per-theme double-render; deferred-fragment loading (#99/#105) stays natural.

## Deliverable per candidate

A working THROWAWAY prototype in your own worktree + branch, demonstrating your architecture on the three hardest surfaces, served live on your assigned port for Marcus to click, plus a candidate rationale (`docs/ui/a1/candidate-<n>.md` on your branch) naming the alternatives you considered and rejected. Prototype quality bar: real data from the shared DB (read-only), real routes, all three themes switchable via `?theme=` links with no JS. Polish is NOT the bar — the split-line is. Do not modify shared files outside your worktree; do not touch the DB; do not open PRs.
