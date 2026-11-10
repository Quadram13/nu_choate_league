# C2b era2010 completion (#104)

Era2010 pages for the routes C2a left on the modern shell. Measured on `http://127.0.0.1:8132` from this worktree. The boot gate stayed green (the server imports). Fragment templates, the seven pre-contract player tables, `base.html`, `hub.css`, and `hub.js` were not edited.

Dispatch is `era2010_c2b.c2b_response`, called at the top of `themes.era2010_dispatch` when the request theme is era2010. A path this module does not own returns None, and the existing route answers. A path it owns whose row is missing returns the era shell with status 404 (`era2010/missing.html`). `/fragments/` stays a bare fragment. That is the A3 document, not a themed page.

## What shipped

- `/players`: the C2a top-10 modules (position tabs and View all are links), then seven deferred boards. Each board link is an `<a href>` to `/boards/<name>` inside a `[data-fragment]` box. A short page script fetches the bare fragment on an unmodified click, the same swap A3 uses. The fragment link and a modified click navigate. Career pages of 50 stay `/boards/players-career`. Below that, one card per career teaser row: short name, position, latest stored season (starts, starter points, owner), and four most recent stored weeks. No projections.
- Player, game log, and splits use `stat_table`. The profile career row uses `player_anatomy` summary marks: gold `is-record`, italic `is-active-leader`, and season rows use bold `is-leader`. J. Allen (`4984`) renders `is-record` on starts, starter points, and fantasy points.
- `/records` is a holder grid plus a chapter card per chapter. All 19 chapter slugs return the era shell. Chapter tables come from the loader context through `stat_table`. Bold is the first row when the board has a lead number. Gold is that lead number, including ties. Italic is `is_current`. No cell fill.
- `/members` keeps the career table and turns the franchise strip into cards (avatar, owner, W-L-T) when `franchise_cards` is set. Home does not set that flag, so the home strip stays a strip.
- `/versus` is a CSS grid. A winning record is bold. `/versus/{left}/{right}` is one score card per stored game.
- Season moves, draft, marks, desk, scoring, trade, and wire, plus `/boards/<name>`, render the era shell. Moves keeps the era trade board and adds the stored add/drop log. Draft uses the era draft board, so player names are initial and surname.

## First payload

`/players?theme=era2010` was 61,549 bytes. Modern `/players` on the same port was 240,496. Main's `/players` on this VM was 5,500,422 (`/cursor/stores/self/internal/baselines/parity-main-68324dd`). The seven full boards are not in the first document. `/fragments/players-career-rankings` was 694,628 bytes and contains no `era2010.css`.

## Perf

n=7, 0 errors, after one warmup, same port. Median (min–max) seconds.

| Route | Modern | era2010 |
| --- | --- | --- |
| `/` | 0.172 (0.170–0.194) | 0.059 (0.057–0.065) |
| `/players` | 0.116 (0.106–0.149) | 0.249 (0.241–0.276) |
| `/records` | 0.678 (0.674–0.721) | 0.698 (0.678–0.811) |
| `/seasons/2025` | 1.213 (1.165–1.341) | 0.060 (0.056–0.071) |
| `/seasons/2025/scoring` | 0.099 (0.098–0.104) | 0.110 (0.105–0.115) |
| `/members` | 0.067 (0.064–0.079) | 0.070 (0.066–0.087) |
| `/versus` | 0.027 (0.026–0.029) | 0.027 (0.025–0.030) |
| `/players/4984` | 0.416 (0.399–0.448) | 0.397 (0.388–0.484) |
| `/fragments/players-career-rankings` | 0.123 (0.121–0.178) | |
| `/boards/players-career-rankings?theme=era2010` | | 0.126 (0.123–0.154) |

Era `/players` is slower than modern `/players` on this run. The extra work is the top-10 modules plus one query for the 50 cards' latest season and four weeks. The ranges do not overlap. The other paired routes overlap or the era page is faster. These medians are from this 4-core VM after the warehouse was warm. The cold `/records` median in `/cursor/stores/self/internal/baselines/perf-main-68324dd.csv` was 4.827. Do not compare that cold number with this warm one.

## Modern bytes

Before the D2 rebase, unthemed responses on 8132 matched the wave serve on 8100 for all 20 `scripts/ui/parity.ps1` routes (status, location, sha256). That serve was wave tip `0d051359`. After rebasing onto `06fa98a`, the same 20 unthemed routes on 8132 matched a serve of that tip on 8133 (status, location, sha256). D2's own cuts are in both: `/seasons/2025` is 104,335 bytes and `/members/alex-coletti` is 11,172. `8133/players?theme=era2010` stays `hub.css`, so that serve is not running this dispatch.

## No-JS

Curl does not run script. Every board link, fragment link, position tab, View all, chapter anchor, and theme choice is an `<a href>`. The players index is the only new page with a `<script>`, and it only upgrades an unmodified click. `/players/no-such-player?theme=era2010` is 404 with `era2010.css` and the sentence "That page is not in the book." `/seasons?theme=era2010` is 302 to `/seasons/2026`; the cookie brings the next document back as era2010.

## Screenshots

`docs/ui/shots/c2b/`: home, players, player, player-log, records, records-streaks, members, versus, versus-pair, season, week, game, moves, draft, scoring.
