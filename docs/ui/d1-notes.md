# D1 /players progressive split (#105)

`/players` is a summary. Each full table is an A3 board: `/boards/<name>` is the document and `/fragments/<name>` is the same template with no shell. The old 5.2 MB page is gone. Era themes inherit the boards through the existing envelope. No second route table was added.

## N

Rankings and both counting boards show the first **50** rows of the order the old page already used. Wire boards show the first **5**.

50 is the number the ticket names and the number `fragments.DEFAULT_PAGE_SIZE` already uses for a career log of about 520. Disclosure picked it as one short printed page (518 careers is ten pages of 50 and a last page of 18). A 50-row career slice was already measured at about 68 KB on `/fragments/players-career`. Four slices of 50 plus three wire strips of 5 rendered here at **239,843 bytes**, under the 1 MB cap (1,048,576). The existing fold is 20, so 50 is the next screen of the same table, not a second ranking.

Wire boards are already a SQL `LIMIT 15`. A 50-row teaser would be the whole board. Five is the leader strip; the other ten stay on the board URL. No row past those 15 was added.

The index does not embed the rest of any table, and it does not hide a full table with `hidden`, `<details>`, or `display:none`. The fold only shortens rows that are already in that document.

## Route map

| URL | What it ships |
|---|---|
| `/players` | Summary. First 50 career, first 50 season, first 5 of each wire board, first 50 of each counting board. Real "View all" links. Legacy ids `rankings`, `wire`, `counting`. |
| `/boards/players-career-rankings` | All 518 career rows. Position chips, fold 20, sort, sticky header, rank column. |
| `/fragments/players-career-rankings` | That section, no document shell. |
| `/boards/players-season-rankings` | All 1,370 season rows. Year and position chips, fold 20, sort, sticky header. Years link to `/seasons/<year>`. |
| `/fragments/players-season-rankings` | Same section. |
| `/boards/players-wire-season` | The published season wire board, 15 rows, sort. |
| `/fragments/players-wire-season` | Same section. |
| `/boards/players-wire-career` | The published career wire board, 15 rows, sort. |
| `/fragments/players-wire-career` | Same section. |
| `/boards/players-wire-unowned` | The published never-rostered board, 15 rows, sort. |
| `/fragments/players-wire-unowned` | Same section. |
| `/boards/players-counting-career` | All 1,082 counting career rows. Position chips, fold 20, sort. Wide table stays in `standings-wrap`. |
| `/fragments/players-counting-career` | Same section. |
| `/boards/players-counting-season` | All 2,560 counting season rows. Year and position chips, fold 20, sort. |
| `/fragments/players-counting-season` | Same section. |
| `/boards/players-career` | Unchanged A3 log, 50 rows a page. Linked from the full career page as "Pages of 50". |

`/players/<id>` is still the player page (B1). These routes do not touch it.

A section on the index carries `data-fragment` and `data-board`. "View all" is an `<a href>` to that board, so the A3 click handler can inline `/fragments/<name>`. Without script the link navigates. Each full board has a "Players" link back to `/players#rankings`, `#wire`, or `#counting`, plus links to the other six boards.

## Templates with a raw `<table>`

A2's `stat_table` is not on this branch. These new files contain a `<table>` and need to be absorbed on the A2 merge:

- `hub/templates/players/career.html`
- `hub/templates/players/season.html`
- `hub/templates/players/wire_season.html`
- `hub/templates/players/wire_career.html`
- `hub/templates/players/wire_unowned.html`
- `hub/templates/players/counting_career.html`
- `hub/templates/players/counting_season.html`

`hub/templates/players.html` has no `<table>`. The board templates do not `{% extends %}`, do not put `theme=` in an href, and do not set an inline style. They are class-only. Season rows still call `person_link` for the manager, the same macro the old season table used. On this database the rendered season board had no `style=` and no `onerror=`.

`fragments._register_boards` registers the seven boards after the three A3 boards. `paginate`, the page size, and the existing loaders are unchanged. `page=12` on `/boards/players-career` is still 404. Page 2 of that log does not contain Josh Allen.

## Content

Old `/players` saved before the edit (5,243,355 bytes) against the new boards. Cell text matches once the new rank column is ignored. 0 mismatches.

| Table | Old rows | New rows | Index prefix |
|---|---:|---:|---:|
| Career rankings | 518 | 518 | 50, equal to the full board's first 50 |
| Season rankings | 1,370 | 1,370 | 50 |
| Wire season | 15 | 15 | 5 |
| Wire career | 15 | 15 | 5 |
| Never rostered | 15 | 15 | 5 |
| Counting career | 1,082 | 1,082 | 50 |
| Counting season | 2,560 | 2,560 | 50 |

Player-href multisets match the old tables (518, 1,370, 15, 15, 15, 1,082, 2,560). Member hrefs on the season table match (1,370). Year hrefs are new: 1,370 season rows, 15 wire-season rows, 15 never-rostered rows, 2,560 counting-season rows, each `/seasons/<year>`. The gap sentence is the same text, including 1,685 excluded season rows and 600 excluded players.

Checked against Postgres (`v_players_index_career`, `v_players_index_season`, `v_fa_season`, `v_player_counting_career`, `v_player_counting_season`):

| Board | Row | Value |
|---|---|---|
| Career | 1 | Josh Allen `4984`, QB, 5 years, 71 starts, 1673.6 PF, 341.4 VORP |
| Season | 1 | 2026 Jaxon Smith-Njigba `9488`, WR, 8 starts, 220.0. Links `/seasons/2026` and `/players/9488` |
| Wire season | 1 | 2024 Jauan Jennings `7049`, FA VORP +30.1 |
| Counting career | 1 | Patrick Mahomes `4046`, 18,743 pass yards, −2 receiving yards |
| Counting season | 1 | 2026 Jordan Love, 2,256 rush+receiving+pass yards |
| Career, last | 518 | Jaylin Noel `12536`. On the full board. Not on the index. |

Counting counts exclude `TEAM_*` rows (32 team totals on the career view). 1,082 and 2,560 match `count(*)` with that exclusion.

## No-JS

Each new document was fetched with curl. No script ran.

- Fragments start at `<section` and contain no `<html>`. The fragment text is a substring of the matching `/boards/<name>` document.
- Tbody rows are not `hidden`. Fold and chips are script. Without script the full row set is in the HTML.
- "View all N" is an `<a href="/boards/...">` inside the summary section.
- "Players" on a full board is an `<a href="/players#...">`. The index still has `id="rankings"`, `id="wire"`, and `id="counting"`.
- The old season rankings wrapper was `<div class="js-rank" data-mode="season" hidden>`. That toggle is gone. Both summaries are in the index, and each full table is its own URL, so the season table is reachable with script off.
- Year and position chips are the existing `.js-year-filter` / `.js-pos-filter` buttons. They are on the full pages that hold the rows they filter: season rankings and counting-by-season get both; career rankings and counting-career get position only. They are not on the index. A year chip there would filter a 50-row prefix, and the season prefix is the newest year, so 2024 would show an empty teaser.

## Perf

Same machine, one request at a time, `curl.exe --noproxy '*' http://127.0.0.1:8116`. One warmup round, then 7 rounds, round-robin. Median is the middle sorted sample, the same rule as `scripts/perf/baseline.ps1`. Bytes are `size_download` and did not vary. Every sample was 200.

Before, this machine, the unsplit `/players` (the wave tip, before this edit), n=7: median **0.969 s**, range 0.900–1.134 s, TTFB median 0.962 s (0.894–1.111), **5,243,355 bytes**. The published baseline is 0.90 s and the same byte count.

After, n=7:

| Page | Bytes | TTFB median | TTFB range | Total median | Total range |
|---|---:|---:|---|---:|---|
| `/players` | 239,843 | 0.207 s | 0.194–0.232 | 0.208 s | 0.194–0.233 |
| `/boards/players-career-rankings` | 693,390 | 0.223 s | 0.218–0.255 | 0.224 s | 0.218–0.277 |
| `/boards/players-season-rankings` | 1,647,485 | 0.352 s | 0.345–0.383 | 0.358 s | 0.347–0.391 |
| `/boards/players-wire-season` | 11,309 | 0.205 s | 0.181–0.213 | 0.205 s | 0.182–0.213 |
| `/boards/players-wire-career` | 10,494 | 0.194 s | 0.163–0.198 | 0.194 s | 0.163–0.198 |
| `/boards/players-wire-unowned` | 10,879 | 0.183 s | 0.172–0.212 | 0.183 s | 0.172–0.212 |
| `/boards/players-counting-career` | 938,045 | 0.338 s | 0.327–0.493 | 0.343 s | 0.328–0.494 |
| `/boards/players-counting-season` | 2,321,561 | 0.531 s | 0.522–0.560 | 0.534 s | 0.524–0.563 |

Index versus the unsplit page on this machine: **0.969 s → 0.208 s**, **5,243,355 → 239,843 bytes**. Against the published 0.90 s the index is also under that line. The slowest full table is counting-by-season at 0.534 s, under 0.90 s. `scripts/perf/baseline.ps1` now times these seven board URLs along with `/players`.

Every board loader calls `players_index()` and then keeps one list. That is why a 15-row wire page still takes about 0.2 s, and why the cell text can match the old page with zero mismatches. The counting scans are in that call. A limit-only summary query would drop them from the index. It was not worth a second copy of the SQL while the index is at 0.208 s.

## Parity

`scripts/ui/parity.ps1 -Mode check -BaseUrl http://127.0.0.1:8116 -CheckDir C:\Users\marcusdu\AppData\Local\Temp\uiwave\parity-main`

```
/                                                FAIL status 200->200 bytes 34444->34873
/seasons                                         PASS status 302->302 bytes 0->0
/seasons/2025                                    PASS status 200->200 bytes 369120->369120
/seasons/2025/trades/1269432330255081472         PASS status 200->200 bytes 24638->24638
/seasons/2025/moves                              PASS status 200->200 bytes 311846->311846
/seasons/2025/draft                              PASS status 200->200 bytes 78098->78098
/seasons/2025/wire/1266620574830952448           PASS status 200->200 bytes 6425->6425
/seasons/2025/week/1                             PASS status 200->200 bytes 73852->73852
/seasons/2025/week/1/2025-w01-1                  PASS status 200->200 bytes 18123->18123
/seasons/2025/marks                              PASS status 200->200 bytes 93107->93107
/seasons/2025/desk                               PASS status 200->200 bytes 21573->21573
/seasons/2025/scoring                            PASS status 200->200 bytes 79761->79761
/versus                                          PASS status 200->200 bytes 48610->48610
/versus/alex-coletti/andrew-howey                PASS status 200->200 bytes 4349->4349
/members                                         PASS status 200->200 bytes 24197->24197
/members/alex-coletti                            PASS status 200->200 bytes 62644->62644
/records                                         FAIL status 200->200 bytes 854055->34916
/luck                                            PASS status 302->302 bytes 0->0
/players                                         FAIL status 200->200 bytes 5243355->239843
/players/4046                                    PASS status 200->200 bytes 163683->163683
PARITY FAIL: 3 route(s) differ
```

The three failures are the ones the wave already expects: `/` is A3 (+429 bytes, 34,444 → 34,873), `/records` is B2, `/players` is this split. `/players/4046` is unchanged.

## Deviations

- The view-all target for career is the full sortable table, not the A3 paged log. A client sort on one page of 50 would not be the old sort. The paged log remains at `/boards/players-career` and the full career page links to it.
- No `/players/<board>` aliases. A second path would fork the envelope. The comment at the end of `app.py` records that.
- Rank is a new column. The old tables had no Rk. The server writes 1..n in the current order. `hub.js` rewrites `td.rk` after a header click on `table.js-rk`. Fold and the year/position chips do not renumber; a hidden row keeps its place.
- The Career/Season buttons are gone. They were script-only, and the season table was `hidden` without script.
- Year cells link to `/seasons/<year>`. They were plain text. The cell has `data-value` set to the year so a partial-season asterisk still sorts as that year.
- The wire note's Records link is `/records/wire#wire-left`. `/records#wire-left` only reaches the chapter when the index script runs.
- The counting note no longer says career rows hide when a year is selected. That was true because both tables shared a page. Career counting is now its own URL.
- The inline upgrade swaps in the full fragment and A3 rebinds sort. It does not rebuild the year/position chips or the fold. Those run on the board URL itself. The rank listener is on `document`, so a sort after an inline swap still renumbers.
- Clicking the Rk header sorts by the current numbers and then rewrites them as 1..n, so one click reverses the list and a second click does not reverse it back.

## Open

- The index and every board still run `players_index()`, including the counting scans the page does not render.
- Counting-by-season is the slow full table (0.534 s, 2.3 MB). It is under 0.90 s.
- Rank recompute was not clicked in a browser in this run. The ranks in the HTML are 1..n, and the listener is the block at the end of `hub.js`.
