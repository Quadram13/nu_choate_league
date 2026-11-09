# B1 player pages (#96)

Profile stays at `/players/{id}`. Career weeks moved to `/players/{id}/log`. Splits moved to `/players/{id}/splits`. Ownership and counting stay on the profile. Markup is class-only on the modern pages: no inline style, no cell fill, no `theme=` links. A2 owns the shared `stat_table` macro, so these pages keep ordinary tables.

## Identity

Landed header, in order: name, position, height, weight, NFL club (text; there is no club page), current manager, birth date, college (text; no college-stats URL is stored). Second line is the career value the old lede already showed: starts, starter PF, VORP, own%, year span. League draft (`v_draft`) sits under that.

Not stored, so not shown: nicknames, throwing hand, birth city, weighted career AV, an NFL draft. Jersey, age, high school, rookie year, years of experience, and the Sleeper catalog note are in a “More bio” disclosure. Jersey is not in the header block.

## Where each old section went

| Section | Now |
| --- | --- |
| By season | Summary on the profile: the same season rows, a FantPt column, and a career footer |
| Weeks | Latest stored season stays on the profile. Every stored week is `/players/{id}/log`, with numeral `?year=` links |
| Splits, opponent, home/road | One table on `/players/{id}/splits`. Group rows: Phase, Half, Home/Road, Opponent |
| Ownership, counting, chairs, rings, volatility | Profile |

FantPt is `v_players_index_season.points` (every stored week, bench included). An FA-only season is not in that matview, so its FantPt cell is blank. That column did not exist on the old page.

The profile’s `#splits` anchor is a pointer plus year links, so `/players/{id}#splits` still resolves.

## Content parity, Patrick Mahomes (4046)

Baseline is `parity-main/r20.html` (163,683 bytes). Compared with the served profile, `/log`, and `/splits` by header-aligned table cells.

| Surface | Baseline rows | Where it is now | Cell diffs |
| --- | ---: | --- | ---: |
| Season | 5 | Profile summary, plus a career footer | 0 on every shared column. New column is FantPt only |
| Ownership | 5 | Profile | 0. Headers equal |
| Weeks | 76 | `/players/4046/log` | 0 on full rows. See the six quiet weeks below |
| 2026 weeks | 9 of those 76 | Profile | Same rows as the log’s 2026 slice, in the same order |
| Counting career | 1 | Profile | 0. Headers equal |
| Counting season | 5 | Profile | 0. Headers equal |
| Phase and half | 19 | Splits, full counting rows | 0 on every shared column |
| Opponent | 27 | Splits, short rows | 0 on games, PF, PF/G |
| Home/road | 4 | Splits, short rows | 0 on games, PF, PF/G |

Visible-number scan of the baseline against the three new pages: 644 unique numbers, and the only one absent is `0.00`. Those zeros are the six quiet weeks, which the page now spells out:

| Week | Role | NFL | Was | Now |
| --- | --- | --- | --- | --- |
| 2022 W8 | bench | BYE | 0.00 | bye |
| 2023 W10 | bench | BYE | 0.00 | bye |
| 2024 W6 | bench | — | 0.00 | Inactive |
| 2025 W10 | bench | — | 0.00 | Inactive |
| 2026 W5 | bench | — | 0.00 | Inactive |
| 2026 W9 | start | — | 0.00 | Inactive |

Identity columns on those rows are unchanged. A week with a counting line, a non-zero score, or a Sleeper games-played/snap flag stays numeric. Christian Watson (8167) 2024 W2 is still `0.00` because `gp` is set; 2024 W17 is Inactive.

`75 of 77 posted lineup weeks` is a `title` on the own% cells, not a text node. It is still in the profile HTML (lede and career row). Bio phrases checked in the combined text and all present: `6'2"`, `#15`, age 31, 225 lb, Texas Tech, Whitehouse (TX), rookie 2017, 9 yr NFL, 54 starts, 1105.2 starter PF, +116.5 VORP, 97%, catalog 2026-11-07, Status Active, depth chart QB #1, chairs, rings, title points 97.0, volatility line, `R4 (39)`.

No season, week, split, counting, or ownership number was invented. The career footer uses index totals for starts, starter PF, VORP, and own%, and the sum of the season rows for the other columns.

## Leader marks

`player_anatomy` (appended in `queries.py`; nothing above it was edited):

- Bold: the player’s value equals the maximum on a finished season (`v_finished_seasons.regular_season_complete`). 2022–2025 are finished. 2026 is not marked.
- Gold: the value equals the all-time maximum.
- Italic: the value equals the maximum among players whose `last_year` is the latest year on `v_players_index_career`, and the player does not also hold the all-time mark. Gold wins the tie.
- A tie with the maximum is a mark. Floats compare at the displayed precision (2 places on the summary, 4 on rate boards, exact integers on counting totals and starts).
- Summary columns: starts, starter PF, FantPt, VORP, from `v_players_index_season` / `v_players_index_career`. FantPt’s career total is the sum of season `points`. VORP may be negative and can still lead. Starts of 17 in 2022 are a real multi-player tie and are marked.
- Counting columns and gates are `_COUNTING_SUMMARY_BOARDS`. `TEAM_*` rows are excluded. Season counting marks use finished years only. Career counting includes 2026 because the career view sums every stored year. Rate boards (PA/G, YA/G) are DEF-only, games ≥ 4, and both the high and the low can mark. A sum marks only when the maximum is greater than 0.

Checked on the served HTML: Mahomes has 8 bold cells (2022 starts, PF, FantPt, plus 2022 pass yards, pass TD, total TD, 300-yard games, 2-TD games) and 3 gold cells (career pass yards, pass TD, 300-yard games). No italic. PIT D/ST career defensive interceptions 63 is italic; BUF D/ST 65 is gold and last played 2025.

Classes are `is-leader`, `is-record`, `is-active-leader` on the `td`. The appended `hub.css` block sets bold, gold text (`#e0c36a`), and italic. No background.

The footnote under the summary and under counting: bold means led that finished season, including a tie; gold is an all-time record; italic is the active leader; a linked number has a leaderboard; the in-progress season is not marked.

### Marks and links that were left off

- Own%, FA VORP, and the volatility columns are not marked. They are not record-book boards.
- Counting columns that are not on those boards are not marked.
- Splits are not marked. A split is not a league-wide total.
- Season starts, PF, VORP, and FantPt are marked and not linked. `/records#season` is manager PF, and the players-index season mode is a script button, so there is no no-JS season board to point at.
- Career starter PF links to `/players#rankings` (the index is ordered by starter points).
- Counting board columns link to `/records#counting-season` or `/records#counting-career`. PA/G and YA/G link only when the row is DEF.
- Most career maxima in this database are held by someone still active in 2026, so gold swallows italic. That is the data, not a missing class.

## Other players

All of these returned 200:

| Player | What was checked |
| --- | --- |
| 4046 Mahomes | Long career. Profile, log, splits, `log?year=2025`, `splits?year=2024`, `log?year=1999` |
| 2309 Amari Cooper | Summary years 2024, 2023, 2022, and a career row |
| 3969 Leonard Fournette | One index season (2022) plus the FA-only 2023 row `player_page` already adds. The profile week log is the latest stored week-year, so it shows the 2023 week. 2022 is on the log |
| 9510 Lew Nichols | One stored week (2026 W5, FA, 0.60) on the profile and on the log |
| 4018 Joe Mixon | 17 Inactive cells, plus the glossary line that uses the same word |
| 8167 Christian Watson | 2024 W2 stays 0.00; 2024 W17 is Inactive |
| PIT, BUF | Italic 63 vs gold 65 on career defensive interceptions |

`/players/no-such-player` is 404. An unknown year is 200 with “No stored weeks in 1999.” `splits?year=2024` has group rows Phase and Half only, and no `/seasons/2022` link. Year navigation is an `<a href>` with a query string. These pages do not use the script year filter.

## Time

Median of 7 samples on this machine (4th of the sorted seven). Baseline was `/players/4046` before this change.

| Route | Median | Min | Max | Bytes |
| --- | ---: | ---: | ---: | ---: |
| `/players/4046` before | 0.577s | 0.548s | 0.966s | 163,683 |
| `/players/4046` | 0.692s | 0.665s | 0.820s | 51,105 |
| `/players/4046/log` | 0.673s | 0.599s | 0.827s | 88,703 |
| `/players/4046/splits` | 0.629s | 0.597s | 0.986s | 49,093 |
| `/players/4046/log?year=2025` | 0.608s | 0.544s | 0.665s | 21,384 |

The profile is about 0.11s slower than the measured baseline and about 0.09s slower than the ticket’s ~0.6s figure. `player_anatomy` is ~0.07–0.09s of that, and almost all of it is the two counting-view scans that find the league maxima. The HTML is smaller because the career log and the splits left the profile. Log and splits call `player_page` and skip the anatomy query.

## Parity harness

`scripts/ui/parity.ps1 -Mode check` against `http://127.0.0.1:8114`, run with Windows PowerShell 5.1: 19 routes PASS. `/players/4046` FAIL, which is this change. The same check under PowerShell 7 also reported `/seasons` and `/luck` as FAIL because that host’s redirect response does not yield `Headers['Location']` to the harness. The headers themselves are still `/seasons/2026` and `/seasons/2026#luck`.

## Deviations

- `player()` was edited so the profile receives anatomy and the current-season weeks. The two new routes are appended in the B1 block. `queries.py` is append-only. The three leader classes are an appended block at the end of `hub.css`.
- Splits are one table and are not `js-sort`. The existing sorter would reorder the group-name rows, and `hub.js` was left alone.
- Rank on the game log is recomputed by a small script in the week-table macro: the click listener is on the table, so it runs after `hub.js` sorts. It was not clicked in a browser. With scripts off, rank is the row order.
- Home/road and opponent rows have no counting stats in the landed views, so those cells are an em dash across the counting columns rather than a row of zeros.
- There is no League, Result, or Margin split family in the landed views, so those group names are not on the page.
- High school is in More bio. The header order requested for this ticket did not include it, and the value is still on the page.

## Open

- The profile median is outside the noise around 0.6s. Cutting the counting-leader scans would land it, and would also remove the counting bold/gold/italic marks.
- No browser was available. Sort-recompute, the gold color, and the footnote were checked in the HTML and CSS, not by a click.
