# B2 record book chapters (#97)

`/records` is an index. Each chapter is `/records/<slug>`. The old 2,061-line `hub/templates/records.html` is gone. Board markup was copied into chapter templates; the route loads one chapter at a time.

## Templates

| File | Role |
|---|---|
| `hub/templates/records/index.html` | Table of contents, holders, and the legacy-anchor forwarder |
| `hub/templates/records/chapter.html` | Shell: index / prev / next, in-chapter jump, `?year=` filter, then the boards |
| `hub/templates/records/_nav.html` | Index, previous chapter, next chapter |
| `hub/templates/records/chapters/<slug>.html` | That chapter's boards, with the original macro imports |
| `hub/templates/records/chapters/_holders.html` | "Who owns the book" |

Markup added for navigation uses existing classes only (`lede`, `note`, `jump`, `jump-label`, `sticky-jump`, `js-year-filter`). No inline styles.

`queries.records_page()` is now the composition of the chapter loaders plus `marks_page()`. New loaders are appended at the end of `queries.py`. The `/records/{chapter}` route is the delimited block at the end of `app.py`.

## Chapter list

The grouping is the one in `ia-inventory.md`. Order follows that list, which follows the old scroll except for three pulls the inventory already makes: trade partners join trades, lineup counting joins bench, and positional finishes plus season and career counting join counting stats. No board was added.

Titles on grouped chapters name the boards they carry. They are not extra sections.

| Slug | Title | H2 ids |
|---|---|---|
| (index) | Record book | `holders` |
| `awards` | Season awards | `awards` |
| `season` | Season | `season` |
| `clutch` | Consistency and clutch | `clutch` |
| `playoff` | Playoff | `playoff` |
| `chairs` | Weekly honors | `chairs` |
| `environment` | Weeks and scoring environment | `median`, `platform`, `eras`, `high`, `low`, `league-high`, `environment` |
| `games` | Blowouts and closest games | `blowouts`, `closest` |
| `trades` | Trades | `trades`, `traded`, `journeymen`, `partners` |
| `rings` | Rings | `rings` |
| `draft` | Draft | `draft`, `draft-capital` |
| `roster` | Waivers and roster shape | `waiver-roi`, `roster-shape` |
| `wire` | Wire | `wire` |
| `lineups` | Bench and lineup counting | `lineups`, `lineup-counting` |
| `counting` | Counting stats | `counting`, `finishes`, `counting-season`, `counting-career` |
| `coach` | Coaching | `coach` |
| `streaks` | Streaks | `wins`, `losses`, `current`, `drought` |
| `stacks` | Stacks | `stacks` |
| `playoff-history` | Playoff history | `playoff-history` |
| `universe-replay` | Universe brackets | `universe-replay` |

H3 ids, same pages: `consistency`, `pythagorean`, `one-score`, `blowout-record` on clutch; `league-low`, `league-mean` on environment; `wire-left` on wire. "Most FA adds in a season" has no id and stays under `eras`.

`?year=` still filters on the chapter. The shell keeps the old `js-year-filter` node (`data-url="records"`). Checked on `/records/season?year=2024`: the filter carries `data-year="2024"`, and Index / Prev / Next keep the query string (`/records/awards?year=2024`, `/records/clutch?year=2024`).

## Board mapping

Baseline is `parity-main/r17.html` (the pre-split `/records` body, 854,055 bytes). Headings were parsed from that file and from the index plus all 19 chapter pages.

Result: 39 `h2` ids on each side, none dropped, none invented, each id on exactly one new page. The multiset of `h2`/`h3`/`h4` headings is 160 = 160. Every `h2` block's table rows (including the dynamic `h3`s under it) match the baseline. 0 row mismatches.

| H2 id | Heading | Page |
|---|---|---|
| `holders` | Who owns the book | `/records` |
| `awards` | Season awards | `/records/awards` |
| `season` | Season | `/records/season` |
| `clutch` | Consistency and clutch | `/records/clutch` |
| `playoff` | Playoff | `/records/playoff` |
| `chairs` | Weekly honors | `/records/chairs` |
| `median` | Median tax | `/records/environment` |
| `platform` | Platform split | `/records/environment` |
| `eras` | Waiver era vs FAAB era | `/records/environment` |
| `high` | Highest weeks | `/records/environment` |
| `low` | Lowest weeks | `/records/environment` |
| `league-high` | League weeks | `/records/environment` |
| `environment` | Scoring environment | `/records/environment` |
| `blowouts` | Biggest blowouts | `/records/games` |
| `closest` | Closest games | `/records/games` |
| `trades` | Most lopsided trades | `/records/trades` |
| `traded` | Most traded | `/records/trades` |
| `journeymen` | Journeymen | `/records/trades` |
| `partners` | Trade partners | `/records/trades` |
| `rings` | Rings | `/records/rings` |
| `draft` | Draft | `/records/draft` |
| `draft-capital` | Career draft capital | `/records/draft` |
| `waiver-roi` | Waiver priority | `/records/roster` |
| `roster-shape` | Roster shape | `/records/roster` |
| `wire` | Wire | `/records/wire` |
| `lineups` | Bench | `/records/lineups` |
| `lineup-counting` | Lineup counting | `/records/lineups` |
| `counting` | Counting stats | `/records/counting` |
| `finishes` | Weekly positional finishes | `/records/counting` |
| `counting-season` | Season counting | `/records/counting` |
| `counting-career` | Career counting | `/records/counting` |
| `coach` | Coaching | `/records/coach` |
| `wins` | Longest win streaks | `/records/streaks` |
| `losses` | Longest loss streaks | `/records/streaks` |
| `current` | Current streaks | `/records/streaks` |
| `drought` | Title droughts | `/records/streaks` |
| `stacks` | Stacks | `/records/stacks` |
| `playoff-history` | Playoff history | `/records/playoff-history` |
| `universe-replay` | Universe brackets | `/records/universe-replay` |

## Content audit

Cell text under all 39 `h2` blocks matches `r17.html`. Five boards across five chapters, first data row, baseline and the new page:

| Board | Page | Value |
|---|---|---|
| Most PF | `/records/season` | Nate White, 2024, 2016.8 |
| Highest weeks | `/records/environment` | Andrew Howey, 2025 W7, 201.36 |
| Biggest blowouts | `/records/games` | Jack Miley 170.6, Nate White 75.9, 2024 W3, margin 94.7 |
| Season awards | `/records/awards` | 2022: Hilal Zoberi, Marcus Du, Hilal Zoberi, Hilal Zoberi, Sam Curtis |
| Best stack week | `/records/stacks` | Fenn Suter, 2025 W1, BAL, Lamar Jackson 29.36, Derrick Henry RB 29.20, Zay Flowers WR 28.10, combined 86.66 |

The stack row's `86.66` cell is the same markup as the baseline (`<td class="num">86.66</td>`). The index taste is "Best week: Fenn Suter 2025 W1 · 86.66".

Saquon Barkley, 2005 rush yards, on `/records/counting`: the baseline and the chapter page both contain `<a href="/players/4866">Saquon Barkley</a>`, `RB`, 16 games, and `<td class="num">2005</td>`.

Links that were already in the boards are still in the copied markup (`/members/…`, `/players/…`, `/seasons/…`, week and trade and wire urls). The Barkley cell still points at `/players/4866`.

## Legacy anchors

The fragment never reaches the server, so `/records#season` cannot be a 302. The index returns 200 and contains every legacy id (45 anchors, plus `holders`, plus `site-nav` from the shell). An inline script on the index does `location.replace("/records/<chapter>" + location.search + "#" + id)`. Without the script, the id is a link to that chapter.

Checked in headless Chrome: `http://127.0.0.1:8115/records#high` rendered the environment chapter (`<title>Weeks and scoring environment · Record book</title>`, `<h2 id="high">`).

Referrers left as `/records#…` (other templates and `queries.py` were not edited). Each target id is on the chapter page:

| Referrer | Target |
|---|---|
| `season.html` `#high`, `queries.py` high/low | `/records/environment#high` or `#low` |
| `season.html` `#stacks` | `/records/stacks#stacks` |
| `players.html` `#wire-left` | `/records/wire#wire-left` |
| `members.html` `#current` | `/records/streaks#current` |
| `member.html` `#clutch` | `/records/clutch#clutch` |
| `queries.py` closest/blowouts | `/records/games#closest` or `#blowouts` |
| `queries.py` wins/losses | `/records/streaks#wins` or `#losses` |
| `app.py` `/luck` fallback `#season` (only when no scored year) | `/records/season#season` |

`/luck` was not changed. It is 302 to `/seasons/2026#luck`.

## Loading

Same machine, one request at a time, Intel i5-8500 (6 logical processors). The monolith was timed before the edit (1 warmup, then 7). Chapters were timed after (7 straight passes, 0 non-200). The two sides were not interleaved. The index gap is larger than the monolith's run-to-run range.

Monolith `/records`, n=7: median **1.887 s**, range 1.770–2.218 s, **854,055 bytes**. Published baseline was 1.81 s / 854 KB. Composed `records_page()` is 106 statements (99 unique SQL texts), about 2.0 s of statement time on one profile run.

After, n=7. Statement counts are from one `NU_CHOATE_PERF` profile, not from the timed runs.

| Page | Median | Range | Bytes | Statements |
|---|---:|---|---:|---:|
| `/records` | 0.237 s | 0.224–0.311 | 34,916 | 25 |
| `/records/awards` | 0.035 s | 0.027–0.047 | 6,027 | 1 |
| `/records/season` | 0.108 s | 0.098–0.121 | 35,982 | 8 |
| `/records/clutch` | 0.117 s | 0.098–0.142 | 36,407 | 9 |
| `/records/playoff` | 0.043 s | 0.033–0.106 | 12,888 | 3 |
| `/records/chairs` | 0.036 s | 0.025–0.040 | 11,597 | 3 |
| `/records/environment` | 0.115 s | 0.108–0.153 | 63,271 | 13 |
| `/records/games` | 0.045 s | 0.034–0.064 | 14,882 | 2 |
| `/records/trades` | 0.093 s | 0.079–0.126 | 102,484 | 7 |
| `/records/rings` | 0.073 s | 0.064–0.090 | 59,727 | 2 |
| `/records/draft` | 0.047 s | 0.038–0.056 | 28,502 | 4 |
| `/records/roster` | 0.133 s | 0.122–0.142 | 105,204 | 5 |
| `/records/wire` | 0.077 s | 0.061–0.083 | 28,249 | 5 |
| `/records/lineups` | 0.175 s | 0.159–0.179 | 27,523 | 8 |
| `/records/counting` | 0.414 s | 0.381–0.436 | 217,453 | 7 |
| `/records/coach` | 0.039 s | 0.037–0.056 | 8,129 | 1 |
| `/records/streaks` | 0.056 s | 0.044–0.067 | 23,649 | 3 |
| `/records/stacks` | 0.454 s | 0.431–0.566 | 26,386 | 11 |
| `/records/playoff-history` | 0.056 s | 0.052–0.064 | 26,630 | 3 |
| `/records/universe-replay` | 0.324 s | 0.314–0.377 | 31,427 | 10 |

Index versus the monolith: **1.887 s → 0.237 s**, **854 KB → 35 KB**.

Slowest chapter is **stacks** (median 0.454 s). Its 11 statements sum to 458 ms, in line with the wall time, so the page is waiting on those reads. The longest one is `v_stack_scoring_compare` at 139.8 ms (`grain, population, role, starts, points, avg_points`). Next are counting (0.414 s; top statement 82.9 ms, the season counting aggregate) and universe replay (0.324 s; the universe-games statement is 306 ms).

Every chapter's SQL, full text, is a multiset subset of `records_page()`. Checked by wrapping `_fetch_on`. The index runs 25 statements. 24 are the same SQL as the full book, with `LIMIT 1` where the existing function already took a limit. The one index-only statement is the coaching taste: `management_career(limit=1)`, the same `ORDER BY` as the coaching board plus `LIMIT 1`.

Counting, playoff history, and universe replay do not put a live number on the index. The counting scans and the universe bracket query are the expensive reads, and playoff history has no single holder.

`records_page()` still returns the old keys, including `season_pine`. That key used to be a second call of the bench-season query. It now shares the list from the lineups loader. The template never read it.

## Parity

`scripts/ui/parity.ps1 -Mode check` against `http://localhost:8115`, run under Windows PowerShell 5.1. Every route PASS except `/records` (200, 854,055 bytes → 34,916). `/luck` PASS, 302 to `/seasons/2026#luck`. `/seasons` PASS, 302 to `/seasons/2026`.

## Deviations

- The index empty note looks at holders only. The old page also looked at `high_weeks`, which the index does not load.
- `season_pine` is no longer a second query.
- Three index lines are descriptions rather than a holder and a number: counting, playoff history, universe replay.
- Grouped boards sit together on their chapter, not in the old scroll gaps (partners after draft capital, lineup counting after stacks, counting boards split around coaching and streaks).

## Open

- A browser without the index script stays on `/records#…`, on the link, and does not open the chapter. Chrome with the script does.
- Stacks is still the slow chapter, on `v_stack_scoring_compare`.
