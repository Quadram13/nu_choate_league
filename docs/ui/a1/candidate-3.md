# Candidate 3 — one document, three skins

## Problem

Three themes have to share one hub's data and pages, and the choice is a one-way door for every later theme ticket. The hub is one Jinja environment, one `page()` helper, one `hub.css`, and a season page that is already seven panes in one template. Modern has to stay today's markup. 1998 wants a borderless three-column portal and a numeral row. ~2010 wants a fixed glossy shell and a tab strip over those same panes. A template fork makes era fidelity easy and makes every later board edit a three-way merge. This candidate pushes the other way: one rendered body, and the era is a stylesheet.

Constraints that bind the shape: no per-theme queries, no JavaScript required for the switch or the pane links, light stat grids in the era skins (Yahoo 2013; modern stays today's dark sheet until #107), leader emphasis as bold or italic text (PFR; no cell fill, and no gold hex was in the reached extract), and the ~2010 tab labels are this hub's panes in document order (no ESPN 2010 tab order was captured). Era bytes cited below are from `docs/ui/research-digest.md` sources marked REACHED.

## Usage (caller's view)

A page author extends `base.html` and writes the body once. They never read `theme`. The shell stamps `data-theme` and the skin stylesheet. A new theme is a file `hub/static/skins/<name>.css` plus one row in `THEMES` in `theme.py`. Import fails if the file, the tuple, and the season pane ids disagree.

A plain stat table needs no hook. `scoring_macros.html` is unchanged; `distribution` and `environment_table` pick up borders, type, and header treatment from the skin.

```jinja
{{ distribution(environment.season) }}
{{ environment_table(environment.seasons, current.year) }}
```

A table with a dense modern column set marks the columns 1998 drops:

```jinja
<th class="num">PF</th>
<th class="num col-opt">VORP</th>
```

The players board also carries the 2010 escape hatch, same bytes in every theme:

```jinja
<div class="js-rank" id="rank-board" data-mode="career">
  <table class="js-sort">...</table>
  <p class="view-all"><a href="#rank-board">View all</a></p>
</div>
```

A combined record string cannot be split by CSS, so the standings table always emits both shapes. Skins choose a set:

```jinja
<th class="col-record" data-type="num">Record</th>
<th class="num col-w" data-type="num">W</th>
<th class="num col-l" data-type="num">L</th>
<th class="num col-t" data-type="num">T</th>
...
<td class="num col-t">{% if row.ties %}{{ row.ties }}{% else %}-{% endif %}</td>
<p class="wlt-glossary">W, L, and T are wins, losses, and ties. A tie is -, not 0. ...</p>
```

Pane links keep their names and gain a span so a skin can hide the word without dropping the accessible name:

```jinja
<a href="#weeks" data-tab="weeks"><span class="tab-label">Weeks</span></a>
```

`href="#weeks"` keeps `?theme=` on the query string. Content links stay root-relative and do not carry the theme.

## Shape

Theme is a catalog name, validated once at the request boundary (`resolve_theme`). Inside the templates it is already one of `era90`, `era2010`, `modern`. `page()` and the error handler are the only TemplateResponse call sites, and both merge `_shell(request)` last so a route cannot override the name. Unknown query values render modern.

The document contract, identical for every theme:

- `<html data-theme>` plus `hub.css`, then `skins/<theme>.css`, then `skins/spine.css`.
- Shell landmarks: band (wordmark + commissioner line), theme switcher, existing site nav, `main.portal-main`, Fantasy links aside.
- Season panes are `section.js-season-pane` in the order `PANE_IDS`. The no-hash pane is the first of those sections. Links use `href="#<id>"`.
- `spine.css` hides era-only pieces at low specificity (`.commish`, `.fantasy-links`, `.col-w`, `.col-l`, `.col-t`, `.wlt-glossary`, `.view-all`) and shows one pane: `:target`, with the first pane shown when nothing is targeted. `:has()` hides that first pane when another pane is targeted. Active-tab color, weight, and background are custom properties set by the skin and applied by one selector list in `spine.css`.
- `era90.css` places the landmarks in a 178px / center / 210px grid (Eagle's left-rail width), paints the band `#660000`, the page `#eeeeee`, links `#0000ff` / visited `#990099`, and tables `border: 2px solid #000` with no header fill (Reeve, LFFL). Pane links become `League 1 2 3 …` via `counter()`.
- `era2010.css` is a 960px white card on a blue gradient, Verdana, a horizontal bar, glossy tabs in document order, light grids with a header gradient, and ten ranking rows until `#rank-board` is the target.
- `modern.css` only restates today's tab-highlight tokens. The dark sheet stays `hub.css`.

Invariants: one query pass per request; skins do not branch markup; column visibility is by class, never by `nth-child` (the standings table inserts H2H and Median only in some seasons); the pane id list has one owner and import checks `season.html` and `spine.css` against it; zero ties render as the character `-` in the T cell for every theme, and modern hides the cell.

Interface depth: a page author learns a handful of classes, not the era rules. The skins own portal geometry, type, color, which columns show, whether the pane nav is numerals or tabs, and the ten-row cutoff. What stays exposed is deliberate: `col-opt` means "1998 drops this column," and the W/L/T cells exist because a record string is not a layout.

`display: contents` on `.mast` is era90-only, so the band, switcher, and nav become grid items of `.wrap` without a second header. Source order is band, switcher, nav, main, aside, which matches left rail, then page, then the link box.

### Single-DOM exceptions

These elements are in every theme's body. The diff does not show them, because the bytes match. A skin shows one by overriding `display`.

| Hook | Why CSS could not do it alone |
| --- | --- |
| `p.commish` | The commissioner line is content. era90 shows it in the `#660000` band. The warehouse has no commissioner address, so the spike links to `/members`. |
| `aside.fantasy-links` | Eagle's right rail is a labeled box of outside names. The site nav is the left rail, reused. Nando and CNN/SI are text; those URLs are dead. |
| `nav.theme-switch` | The spike's `?theme=` control. Href text is identical across themes (`?theme=era90` and so on). CSS bolds the current one. |
| `main.portal-main` | One grid item for the center column. |
| `col-w` / `col-l` / `col-t` next to `col-record` | CSS cannot split `20-8` into three cells. |
| `col-rank`, `col-opt` | Named columns so a skin can drop them. `nth-child` is wrong once H2H and Median appear. |
| `p.wlt-glossary` | The glossary sentence under the grid. Readable size, not HTML `size=2`. |
| `p.view-all` → `#rank-board` | CBS-style escape hatch. era2010 hides `tbody tr:nth-child(n + 11)` until the board is `:target`. |
| `span.tab-label` | era90 clips the word and shows `counter()`. The accessible name stays "Weeks". |
| `tr.leader` on rank 1 | Data class. era90 bolds it. Modern has no rule, so the row looks as it does today. |

Visibility rules on elements that already existed: era skins hide `.js-season-tabs a:not([data-tab])` (All-pro, All-bench), so the numeral row and the tab strip enumerate panes. Modern still shows those links.

### Prototype evidence

Body bytes, compared after extracting `<body>…</body>` from the three themes of each URL. Identical in every case.

| URL | Body bytes | Full-document delta |
| --- | --- | --- |
| `/players?theme=` | 79,844 | theme name only |
| `/seasons/2026?theme=` | 275,710 | theme name only |
| `/seasons/2025?theme=` | 374,154 | theme name only |
| `/seasons/2026/scoring?theme=` | 67,755 | theme name only |
| `/?theme=` | 34,716 | theme name only |

The full document differs by the length of the theme token in two head spots: `data-theme="…"` and `href="/static/skins/….css"`. `era90` vs `era2010` is 4 bytes (2 + 2). `hub.css` and `spine.css` are the same hrefs. No body exception showed up in the diff. Players renders 50 career rows. 2025 emits all seven pane links. 2026 omits the Playoffs link because the existing template condition is false; the playoffs section is still in the document. A 2026 standings leader cell rendered `12-4` beside W `12`, L `4`, T `-`.

Checked in Chrome on the live server: 1998 is a gray page, maroon band, left task rail, Fantasy links box, `League 1 2 3 4 5 6 7`, and a small W-L-T/PF/PA grid. 2010 is a 960px card, blue bar, tab strip in pane order, dense Official/H2H/PF row, ten ranking rows, and a View all link. Modern is today's dark sheet plus the switcher row. With the script tag removed, `/seasons/2025?theme=era90` still showed the portal and the numeral row, and `#draft` showed the draft pane. Headless Chrome crashed when launched with script disabled, so that check was done by serving the page without `hub.js` and then restoring the tag.

Click these:

- http://localhost:8123/players?theme=era90
- http://localhost:8123/players?theme=era2010
- http://localhost:8123/players?theme=modern
- http://localhost:8123/players?theme=era2010#rank-board
- http://localhost:8123/seasons/2025?theme=era90
- http://localhost:8123/seasons/2025?theme=era2010
- http://localhost:8123/seasons/2025?theme=modern
- http://localhost:8123/seasons/2025?theme=era90#weeks
- http://localhost:8123/seasons/2025?theme=era2010#playoffs
- http://localhost:8123/seasons/2025/scoring?theme=era90
- http://localhost:8123/seasons/2025/scoring?theme=era2010
- http://localhost:8123/seasons/2025/scoring?theme=modern

`/seasons?theme=era90` redirects to `/seasons/2026?theme=era90`. The season dropdown keeps `location.search`, so a year change keeps the skin. Other root-relative links do not.

## Synthesis decision

Left for the synthesizer. This file is candidate 3 only.

## Tradeoffs accepted

- We accept a fidelity ceiling in exchange for one body. Numerals are counters on the same links, not separate week-style URLs. The 1998 page is CSS grid reproducing a borderless table, which the digest names as a costume tell. The 960px shell and the glossy tab chrome are not a measured ESPN league page; no reached capture had a width or a tab order.
- We accept hidden columns and hidden panes in the HTML in exchange for one render. `display: none` does not shrink the season document. Deferred fragments stay natural later, because the pane link is already an `href` a fragment URL can replace.
- We accept `display: contents` on the mast in era90 in exchange for placing the existing nav in the left column without a second nav list. Browsers that drop `display: contents` boxes from the accessibility tree lose the header landmark; the links remain.
- We accept a closed class vocabulary (`col-opt`, `col-w`, `tab-label`, `view-all`) in exchange for skins that do not need `nth-child` or a template branch. An author who forgets `col-opt` on a new column shows that column in 1998.
- We accept that the theme is not written into content hrefs, in exchange for a body diff that stays empty. Hash links and the season dropdown keep the query. A click on `/players` from a themed page returns to modern until A2 persists the choice outside the document.
- We accept `:has()` for the single-pane rule. Without it, the first pane stays visible beside the targeted pane. The links still work.
- The spike drops `js-fold` on the career board and slices that board to 50 rows with the other players boards omitted. The `hidden` attribute is `display: none !important` in the UA sheet, so a fold that sets it cannot be reinterpreted as a ten-row module. The query is unchanged. This cut is the prototype, not the production page.
- Modern grows a theme-switcher row and the era-only nodes, hidden or quiet. The dark tables, type, and pane set stay `hub.css`.

## Alternatives considered

- Per-theme template directories (C1). Each theme owns full markup; a loader falls back to a shared fragment. Fidelity is total, including a real 1998 `<table>` skeleton and a hand-built tab strip. The caller has to know which directory they are editing, and a board change is three files that drift. The public surface is the whole template tree. That hides nothing and duplicates the stat macros. Rejected: the maintenance cost is the thing ticket #95 cannot afford, and modern's byte-near copy would rot on the first shared fix.
- Per-theme shells plus shared class-only fragments (C2). Content templates stay theme-blind; each theme owns a shell and a stylesheet. Deeper than C1 for stat boards, shallower at the shell seam. The season pane nav is the seam: numerals versus tabs is structural, so the shell would still fork that control, and "which pane is showing" would live in three shell templates plus the shared sections. The caller would have to know what is shell and what is fragment. Rejected for this candidate because the same DOM already expresses that seam with counters, tabs, and `:target`, and a second template family is a second way to add a page.
- Rendering a different body per theme from one template (`{% if theme %}`). The smallest fork, and the one an agent will copy. It makes the body diff the product, splits ownership of every section, and fails the "one obvious way" test. Rejected. The hook classes are the escape hatch, and they are the same string in every theme.
- Stamping `?theme=` onto every href so navigation keeps the skin. That preserves the query without a cookie and makes every href differ across themes, which throws away the single-DOM evidence. Rejected. Persistence belongs outside the document.

## Open questions and risks

- Is a counter on an in-page link enough for the 1998 numeral row, or do those links need to be real document URLs so each pane is a small payload? Separate URLs keep one template and still one body per URL; they change which pane's markup is in the response, which is a payload win and a different contract than "all panes always present."
- Where should A2 store the choice so content hrefs stay theme-free? A cookie read in `resolve_theme` keeps this module the only boundary. Writing the name into hrefs forks the body.
- Should a new column be `col-opt` unless someone opts it into the 1998 grid? The dangerous default today is "visible in 1998," because forgetting the class shows the column.
- Can the production fold and the season script keep setting `hidden`, or does every disclosure a skin must reinterpret have to be an `href`? The career board dropped `js-fold` so the ten-row rule could work.
- `display: contents` on the mast is the accessibility risk to weigh before this leaves the spike. A nested grid that duplicates the column tracks inside the header avoids it and also duplicates the 178px / 210px tracks.
- 960px, the blue gradient, and the tab shape are costume relative to the reached 2010 sources. Which of those are acceptable until a real league capture exists?
- JS-injected chips (the position filter on `/players`) are not in the server HTML, so skins can only style whatever classes the script happens to use. Is that chip row in scope for era fidelity?

## Next implementation step

Keep `theme.py` as the only theme boundary, point `resolve_theme` at a cookie when A2 adds one, and leave every content template on the hook classes above.
