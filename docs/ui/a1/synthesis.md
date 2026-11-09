# A1 synthesis — theme architecture decision (#95)

Base: **Candidate 2 — per-theme shells + shared class-only fragments**, with grafts from C1 and C3. Cross-judge (grok-4.7-xhigh-fast, independent read) picked C2 as well; agreement confirms the pick. Candidate packages: `docs/ui/a1/candidate-{1,2,3}.md` on branches `cursor/proto-a1-c{1,2,3}-bf5b`. Prototypes remain clickable on ports 8121/8122/8123 while this wave runs.

## Problem

Three first-class themes (modern / 1990s / ~2010) must share one hub's data and content. The binding constraints (grounding doc): no-JS spine for switch/tabs/pagination; era grammar is structural (1998 portal columns and numeral rows, ~2010 tab strip and cards), not just color; modern stays byte-near until #107; light stat surfaces in era themes; leader marks as text, not fills; and the loading lane (#105/#106) must stay natural — the digest's central verdict is that hidden rows are not a savings, so panes and boards need real URLs.

## Usage (caller's view)

A page author lists panes and slots and calls `render_panes`. They never read the theme, never write a second copy of a table, and never name a shell. From C2's prototype (`theme_pages.py`):

```python
return render_panes(
    request, title=f"{year} season", nav="seasons", pager="Season",
    panes=tuple(Pane(name, label, template, loader) for name, label in _SEASON_LABELS),
    slots=(Slot("lead", "fragments/season_lead.html"), Slot("aside", "fragments/season_aside.html")),
    context={"year": year, "current": current},
)
```

Adding a pane = one `Pane` row. Adding a theme = registry entry + `shells/<id>.html` + `static/themes/<id>.css`; the boot gate fails loudly if they disagree. Only the active pane's loader runs — deferred loading is the shape, not an add-on.

## Shape (the split-line)

**Fragments own facts. Shells own grammar.**

- Fragments (stat boards, game lists, week cards) are theme-agnostic, class-only, semantic markup. One `stat_table` macro owns `<table`. Fragments never read the theme, never carry `?theme=` in hrefs, never `{% extends %}`.
- Shells (one per theme) own layout: portal columns vs fixed-width gloss vs modern fluid, numeral row vs tab strip, rails, bands, typography, color. Shells mount fragments and slots; they contain no stat facts.
- Boards declare **column projections per era** (graft from C1): the default projection is the full modern column set; `era90` projects the digest's small grid (W-L-T/PF/PA etc.). Projections select which shared facts render — rows and raw values are identical across eras, and the boot gate checks value parity on a fixture render. This resolves C2's one-column-set tension without forking fragments: era density is a presentation choice, content stays single-source.
- Leader marks are text classes (`is-leader` bold, `is-record` gold, `is-active-leader` italic) with a glossary footnote. No cell fills. Exact gold hex is fixed in the C-lane tickets against the reached PFR pages (C2's `#6b4f00` is a placeholder).
- Zero ties render as `-` in era themes from one shared function. Modern keeps today's exact rendering (byte-near — see below).
- **Modern is the legacy path** (graft from C3): modern keeps `base.html`, the existing templates, `hub.css`, and `hub.js` byte-near, with the theme switcher as the only injected chrome. Era themes render through `render_panes` + shells. Two render paths exist during the wave by design; migrating modern onto `render_panes` is a named non-goal with a revisit trigger (all era shells shipped + #107 landed).
- Theme state: `?theme=` links now; A2 (#98) adds cookie persistence. Fragments stay theme-free, so carry happens at the chrome layer (cookie primary; C2's Referer-302 was spike-only). Unknown theme → modern.

## Synthesis decision

**Base C2.** It is the only candidate where each board is written once (byte-identical fragments, verified: standings `D874BADD1700` across themes), every pane is a real no-JS document in every era, and deferred loading falls out of the shape (only the active pane loads). Its interface (`render_panes`/`Pane`/`Slot`) is the deepest of the three: the page author's surface is a catalog row.

**Grafts:**

1. **From C1: boot-time fail-closed contract gate.** C1's `install()` refuses to serve on violation (era file-set parity, `border="2"` presence, fixture echo of `present()` values). A2 adopts this posture for the whole contract: registry ↔ shell files ↔ stylesheets ↔ pane ids ↔ season-template sections must agree at boot, plus C2's import checks (fragment hygiene: no `{% extends %}`, no `theme=`, no second `<table`; era90 stylesheet: no flex/grid; modern skin: must import `hub.css`). The gate fires on a fixture render including value parity across era projections. Judge's C3-graft (`assert_theme_contract` on pane ids) folds into this gate.
2. **From C1: era column projections with raw-value parity** (described in Shape above). Also C1's `A. Rodgers` initial-plus-surname formatter and `?rows=all` View All pattern for the ~2010 top-10 modules (CBS grammar).
3. **From C1: week navigation is shell grammar.** C2's `/week/N` currently 302s onto unthemed `week.html`; the contract states week numeral rows live in the era shells (C1's `week_slice` + `week_nav` pattern) and week content is a fragment.
4. **From C3: modern = legacy documents + thin skin** (above), and the **single-DOM diff discipline** — A2's verification harness diffs rendered bodies across themes the way C3 proved byte-identity (374,167-byte body, exact match), adapted to prove fragment identity and modern byte-nearness.
5. **From C3: theme registry minimalism** — one tuple + one shell + one stylesheet per theme, nothing else to add a theme.

**Rejected:** C1's split board ownership (three markup copies per forked board; the drift gate catches values, not structure; judge: "the next board is three files plus a projection beside the old macros"). C3's all-panes-in-every-document (374KB season page in every theme; the digest's named anti-pattern and a direct fight with #106), counter-numeral #anchors (not real URLs), CSS-grid-as-1998-table (the costume tell), `display:contents` mast (accessibility risk), invented off-site hrefs (dead labels stay text, per digest discipline — C1 got this right).

## Tradeoffs accepted

- We accept **two render paths during the wave** (modern legacy, eras on `render_panes`) in exchange for modern byte-nearness without a 20-route rebuild. Revisit trigger is named above.
- We accept **one stat-table macro and a closed class vocabulary** in exchange for fragments that never fork; a genuinely new board shape is a new fragment, added deliberately.
- We accept that **C2's prototype replaces three routes' render paths** while week/player/member stay on `page()` during the spike; A2 scopes the full route migration per family.
- We accept that **era90's small-grid projection hides shared facts** (e.g. VORP) from era90 renders; the facts remain one click away (player pages, modern theme), and projections are declared in one registry, not scattered.

## Alternatives considered

- **C1 per-theme template sets** — lost on ownership: every board edit becomes three files with structural drift the value-gate cannot catch. Its grafts (fail-closed gate, projections, week-nav grammar, name formatter) are the parts that survived.
- **C3 CSS-skin single DOM** — lost on payload and fidelity ceiling: hidden panes are not a savings (digest), and the era structures it cannot reach are precisely the structural ones the product constraints demand.
- **Per-theme `{% if theme %}` branches in one template** (considered by all three candidates, rejected by all three): the smallest fork and the one an agent would copy; splits ownership of every section.

## Open questions (flagged for Marcus, not blocking)

1. **Modern's stat surface.** Today it is dark; the digest rule "light stat field in every theme" was written against era-accuracy + the Yahoo 2013 failure. Conservative reading applied: era themes ship light grids; modern stays byte-near until #107, where a light-table repaint is the named decision. Override welcome.
2. **2010 chrome width/gradient** (960px, blue gloss) is unattested — no reached capture measured one. Prototypes mark it as such; C2a will either justify or strip.
3. **Theme-carry before cookies**: A2 decides cookie semantics; fragments never carry theme regardless.

## Next implementation step

#98 A2 builds `web/themes.py` (registry, `render_panes`, `Pane`/`Slot`, frozen `Frame`, cookie, boot gate) + the three shells, against `docs/ui/a1/fragment-contract.md`, modern on the legacy path, with the parity harness and C3's body-diff discipline as gates.
