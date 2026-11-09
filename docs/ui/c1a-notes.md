# C1a 1990s theme, core slice (#100)

Branch `cursor/ui-c1a-era90-bf5b`. Era pages are a skin on the landed fragments. The shell owns the portal, the rails, the band, the type, and the week numerals. `hub/templates/fragments/` is unchanged.

Content templates live in `hub/templates/era90/`. They are mounted by `shells/era90.html` the same way a season pane is mounted. They are not under `shells/`, so the shell file stays the one layout `<table` the boot gate counts.

## What the pages are

`/?theme=era90` is the portal. It does not call `queries.home_desk()`. The left rail, only on this page, is the Eagle task order adapted to routes that exist:

1. `{latest scored year} season` → `/seasons/{year}`
2. `Past seasons`, then each other year (newest first)
3. Record book → `/records`
4. Top 10 → `/players`
5. Rules and scoring → `/seasons/{year}/scoring`
6. Champions → `/records/awards`
7. `Last updated {day Mon year}`

The right rail is one box labeled "Fantasy links". The only anchors in it are `https://www.nfl.com/` and `https://www.espn.com/nfl/`. Both returned HTTP 200 on 9 Nov 2026. The Eagle farm (Nando, SportsZone, USA Today, CBS SportsLine, CNN/SI, Injury Report) is not printed and is not linked. `ERA90_DEAD_LABELS` is empty. The shell still loops that tuple, and the gate still requires any label that remains to render as `<p class="dead-label">` with no href. Contract §3.5 forbids invented hrefs for dead names. It does not require the dead names to stay on the page. The ticket calls a dead farm the anti-pattern.

The header band is `Nu Choate League`, then `Email the COMMISSIONER`, then the theme switcher. There is no commissioner mailbox in the warehouse, so the line is text. No mailto was invented.

The center is the current season's standings on the shared `stat_table` (Manager, W, L, T, PF, PA), a one-sentence glossary under it, a red cheer above it, and a static CommWire line. The cheer is `Congratulations` plus the champion when `list_seasons` has one, and `Leader` plus the rank-1 manager when the current season has no champion. 2026 has no champion.

Interior season pages keep the A2 left rail (home, seasons, records, players, scoring, members, versus). The boot gate locks that order. Replacing it on every page would fail the fixture that renders the season shell.

These routes render inside the era shell when `?theme=era90` (or the cookie) is set:

| Route | Template |
|---|---|
| `/` | `era90/home.html` |
| `/seasons/{year}` and each pane | existing `render_panes` path |
| `/seasons/{year}/week/{week}` | `era90/week.html` |
| `/seasons/{year}/week/{week}/{matchup}` | `era90/gamecenter.html` |
| `/seasons/{year}/moves` | `era90/moves.html` |
| `/seasons/{year}/draft` | `era90/draft.html` |
| `/seasons/{year}/marks` | `era90/marks.html` |
| `/seasons/{year}/desk` | `era90/desk.html` |
| `/seasons/{year}/scoring` | `era90/scoring.html` |
| `/records` | `era90/records.html` |

`app.py` checks the theme at the start of `home()` and, at the bottom of the module, wraps `page()` so only an era90 request for one of those template names leaves the legacy renderer. Every other call is the original `page()`.

Trade, wire, players, members, versus, and `/records/{chapter}` stay on the legacy template. Chapter templates belong to #97. The players list belongs to #105. The records index is skinned because the screenshot set includes it. A chapter link leaves the shell.

Week numerals are `Results` plus one `<a>` per scored week, href `/seasons/{year}/week/{n}?theme=era90`. They are the weeks `scored_weeks` returns, not a padded 1–16. A season with 14 scored weeks shows 14 numbers. 2026 includes week 9 because `seasons.through_week` is 9 and that week has nonzero points. The shared `_week_nav.html` does not mark the current number. That include is shared with era2010, so it was left alone.

`numeral_hrefs` appends `/week/N` to the request path. That is correct on `/seasons/{year}` and wrong on `/` and on a week URL. The home and the family renderer set the hrefs themselves. `render_panes` remains the season-document entry. This is the reading of contract §5.1 used here. It is not a fragment change.

Every era90 season pane also gets a Results row. Weeks and playoffs already returned their own numbers. The other panes now add `scored_weeks` when the loader did not. era2010 loaders are not wrapped.

## Standings grammar

The era90 projection was already Manager, W, L, T, PF, PA. Zero ties render as `-` through `tie_dash`. The grid's border, 5px cell padding, transparent header, and lack of a stripe are `era90.css` against `stat_table.html`. The fragment markup is untouched. No `border=` or `cellpadding=` was added to a fragment. The shell keeps the layout-table attributes A2 already shipped (`cellpadding`, `cellspacing`, column `width`, `valign`).

The warehouse has no division column. Home and the week page group on `row["division"]` when a future row carries one, and otherwise render one table. The season standings pane is the shared `fragments/board.html`, which renders one board. Splitting that pane needs a fragment change. Nothing in the current data needs it.

The era90 standings note is one sentence, at 16px:

> W, L, and T are wins, losses, and ties; PF is points for and PA is points against, and a zero tie is shown as -.

That replaces the shared gold footnote on this board only. Moves, lineups, stacks, and draft keep the shared footnote. The boot fixture requires the first three to be byte-identical across themes, and the era90 draft to match the modern draft. Changing those notes would fail the gate.

## CommWire and the load stamp

There is no `load_ledger` relation. `players.catalog_as_of` is the catalog file date `load` writes on every player row. The maximum is that stamp. On this database every player row is 2026-11-07, so the line reads `Last updated 7 Nov 2026`. Autovacuum times and `transactions.at` are not a load. Dump manifests are not in Postgres.

The CommWire is a `<p class="commwire">` of real anchors: every regular, playoff, or consolation game in the latest `v_posted_weeks` week for the current season, then `high_weeks(1)`, then `closest_games(1)`. For 2026 the posted week is 8 (six games). Week 9 is inside `through_week` but is not posted (scores top out at 22.5), so it is not on the wire. The items are in the HTML. There is no `<script>` on an era page. Motion is an opacity pulse, and only under `prefers-reduced-motion: no-preference`. `prefers-reduced-motion: reduce` sets `animation: none`. The text is not clipped.

## Palette

Page gray and the white card are the acceptance surface (LFFL), not the tan Reeve page. Tan `#c8bfb6` stays attested and unused. The center column is 468px because that is LFFL's white card, not Eagle's 211px image column. The left rail is Eagle's measured 178px. The right rail stays 196px, the narrow outside column A2 already used. 178 + 468 + 196 = 842, centered, border 0. Body type is Times / "Times New Roman" / serif at 16px. The title is 20px navy, not `SIZE=+4`. Rails are not all caps. `COMMISSIONER` is the one attested capital word.

| Token | Value | Where it is used | Attestation |
|---|---|---|---|
| Page | `#eeeeee` | `body`, both rails | LFFL `BGCOLOR`, digest line 54 and the token list at line 122 |
| Card | `#ffffff` | `.portal-main`, `.link-box`, `table.stat` | LFFL `TABLE BGCOLOR="#FFFFFF"` at 468px, digest line 54 |
| Navy | `#000066` | `h1`, `h2`, caption, CommWire, band's bottom edge | Eagle title `FONT COLOR`, digest line 82 |
| Green | `#003300` | kicker, week group label | Eagle "FANTASY FOOTBALL", digest line 82 |
| Green | `#006600` | the year in the kicker, last-updated | Eagle draft-times color, digest line 82 |
| Link | `#0000ff` | default anchors (rails, the link box) | LFFL `LINK`, digest line 86 |
| Link | `#0000af` | anchors in the center column | Eagle body `FONT COLOR`, digest line 82 |
| Visited | `#990099` | `a:visited`, including the center | LFFL `VLINK`, digest line 86 |
| Maroon band | `#660000` background, white text | header band | Boot gate requires `background:#660000`. Digest line 120 puts the commissioner line in the header in this maroon. Eagle used the same hex as a font color (digest line 82), so the Fantasy links label is `#660000` text on white |
| Cheer | `red` | the line above the grid | Reeve named the color red, digest line 84. Not a hex |
| Record cell | bold, no second color | `.is-record` | Reeve grids have no leader-cell color, digest line 72 and line 117. No gold hex was reached |

The commissioner words on the maroon band are white. Maroon text on a maroon band would not read. The band is the gate's reading. The label "Fantasy links" carries Eagle's maroon as type.

## Placeholders A2 left

| Placeholder | Replacement | Why |
|---|---|---|
| Record gold `#6b4f00` | Removed. `.is-record` is bold only, so a link in that cell stays blue | A2 marked the hex as a placeholder. The digest's reached pages have no gold hex and no colored leader cell. The class stays, because the fixture looks for `is-record` in the HTML and in the stylesheet |
| Commissioner reading | Band kept. Wording is now `Email the COMMISSIONER`. The gate snippet matches that casing | Eagle's bytes use that casing (digest line 82). A2 had "Email the commissioner". No address exists to link |
| 960px and the gloss gradient | Left on `era2010.css` | Those belong to #101. This slice does not edit that file |

The draft footnote still says "Gold marks a record." The fixture will not let that sentence move on a board whose era90 bytes must match modern. era90.css does not paint the gold. The standings glossary, which is the grammar this ticket specifies, does not say gold.

## Modern path

The branch merges wave tip `9e84e55` (reconcile `944af51` plus the D1 players split). `git diff origin/cursor/ui-wave-45-bf5b` after that merge is only the era90 files: `era90.css`, `shells/era90.html`, `hub/templates/era90/*`, and the era90 appends in `app.py`, `queries.py`, and `themes.py`. It does not touch `base.html`, `hub.css`, `hub.js`, `home.html`, `season.html`, the records templates, or `hub/templates/fragments/`.

`queries.py` only appends `era90_last_updated` and `era90_ticker` on top of the wave tip. `app.py` returns early from `home()` only when the theme is era90, and the wrapped `page()` calls the original function for every other request. `_note` changes text only when the theme is era90 and the projection contains `ties`. The season loader wrap and the last-updated context are inside `if theme == "era90"`.

Served on `http://127.0.0.1:8119` with the gate on. The live modern body matches an in-process render of the same templates (sha256 equal):

| Route | Bytes | sha256 prefix | era90.css | portal |
|---|---|---|---|---|
| `/` | 32923 | `8cd3b94edf455356` | no | no |
| `/seasons/2025` | 369314 | `75663cb3e9347dd7` | no | no |
| `/records` | 35110 | `9aecd45a1592611a` | no | no |

`/seasons/2025` at 369314 bytes is the figure A2 recorded for the live modern season document (`docs/ui/a2-notes.md`). The records index hash is the same one measured on this branch before the wave-tip merge, so that page did not move. `/` is smaller than the pre-reconcile home because the wave tip refactored `home_standings.html` onto `stat_table`. That delta is the reconcile, and the served bytes match the post-merge template exactly. `/?theme=modern` and `/?theme=era2010` are the same 32923-byte home. The era90 branch is the only home that leaves the modern desk.

## Boot and routes

After the wave-tip merge, `nu-choate-league serve --port 8119 --no-reload` stays up. The gate is on. Before the merge the same command exited 1 on the two pre-contract A3 fragments (`pager.html` mentions theme; extra `<table` in `home_standings.html` and `players_career.html`). Those files were not edited here. The reconcile on the wave tip is what cleared them.

Every checked route returned 200. Era pages link `era90.css`, contain one `link-box`, and contain no `hub.css` and no `<script>`.

| Route | Bytes |
|---|---|
| `/?theme=era90` | 7194 |
| `/seasons/2025?theme=era90` and `pane=standings` | 7924 |
| panes weeks / playoffs / moves / draft / lineups / stacks | 24412 / 7042 / 7623 / 50880 / 7553 / 7579 |
| `/seasons/2025?theme=era2010&pane=standings` | 5980 (era2010 shell, no portal) |
| `/seasons/2025/week/1?theme=era90` | 8941 |
| `/seasons/2025/week/1/2025-w01-1?theme=era90` | 4690 |
| moves / draft / marks / desk / scoring, `?theme=era90` | 50737 / 49969 / 12977 / 14310 / 5603 |
| `/records?theme=era90` | 9005 |
| `/seasons/2026/week/8?theme=era90` and week 9 | 8557 / 8492 |

## Perf

`scripts/perf/baseline.ps1`, curl `time_total`, `http://127.0.0.1:8119`, one warmup discarded, n=5. Same commit. Era HTML is smaller on every pair. Era medians are faster on every pair. The records ranges overlap (era max 0.264, modern max 0.257); the median is still lower.

| Surface | Modern median (min–max) | era90 median (min–max) | Modern bytes | era90 bytes |
|---|---|---|---|---|
| Home | 0.302 (0.291–0.329) | 0.090 (0.085–0.118) | 32923 | 7194 |
| Standings | 0.757 (0.749–0.837) | 0.085 (0.078–0.090) | 369314 | 7924 |
| Week 1 | 0.110 (0.104–0.146) | 0.087 (0.084–0.099) | 74046 | 8941 |
| Records index | 0.255 (0.229–0.257) | 0.238 (0.234–0.264) | 35110 | 9005 |

Modern standings is the whole `/seasons/2025` document. The era figure is `?theme=era90&pane=standings`.

## No-JS

Fetched raw HTML. Era home, week, and records contain no `<script>`. The home Results row is nine separate anchors, `/seasons/2026/week/1?theme=era90` through `week/9`. The 2025 week page's Results row runs through week 17, each number its own href. The CommWire items are anchors in the HTML (posted week 8 winners, the record week, the closest game). The stylesheet's only motion is an opacity pulse inside `prefers-reduced-motion: no-preference`, and `prefers-reduced-motion: reduce` sets `animation: none`. The text is in the element either way.

## Screenshots

Headless Chrome, 1280 wide, saved in `docs/ui/shots/c1a/`.

| File | Page | Window |
|---|---|---|
| `home.png` | `/?theme=era90` | 1280×2200 |
| `standings.png` | `/seasons/2025?theme=era90&pane=standings` | 1280×2200 |
| `week.png` | `/seasons/2025/week/1?theme=era90` | 1280×2200 |
| `records.png` | `/records?theme=era90` | 1280×3400 |

The records index continues through Universe brackets, so that shot is taller than 2200. The other three fit in 2200 with gray page below the portal.

## Contract

No fragment file was edited. No amendment is required for the pages that shipped.

Two readings, if a later ticket wants them written into `fragment-contract.md`:

- §2.5 calls `is-record` gold text. No gold hex was reached, and the 1998 grids have no leader-cell color. The class stays (the fixture looks for it). era90.css paints it bold and leaves the link blue. The shared "Gold marks a record" sentence stays on moves, lineups, stacks, and draft because the fixture requires those bytes to match. The standings glossary does not say gold.
- §5.1 names `render_panes` as the era render entry. It still is, for `/seasons/{year}`. Home and the other family routes build a `Frame` and render the same shell, because `numeral_hrefs` appends `/week/N` to the request path and that is the wrong href on `/` and on a week URL.

§3.5 says a dead label is text, never an invented href. The tuple is empty. Live NFL.com and ESPN NFL are the only anchors in the one link box.

The season standings pane is `fragments/board.html`, one board. A division split of that pane would need a fragment change. The warehouse has no division column, so the page is one table. Home and the week template already group on `row["division"]` if a row ever carries one.
