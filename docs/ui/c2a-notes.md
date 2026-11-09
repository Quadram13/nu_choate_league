# C2a era2010 core (#101)

Late-2000s/early-2010s shell on `cursor/ui-c2a-era2010-bf5b`. Measured against `http://127.0.0.1:8120` from this worktree after merging `origin/cursor/ui-wave-45-bf5b` (A3 reconcile, D1, then C1a). The boot gate is green. Fragment templates were not edited.

Era pages for this theme live in `hub/templates/era2010/`. The shell stays `hub/templates/shells/era2010.html`, which is the one file the gate checks. Dispatch is an append-only middleware in `app.py`. It handles `/`, `/members`, `/members/{id}`, and the week and gamecenter paths when the theme is era2010. Season pages stay on `season_document`. The C1a `era90` home check and `page()` wrapper are untouched.

## Palette

ESPN-ish black and red chrome on white panels. The theme is the ESPN Fantasy 2010 product. The only nearby color sentence in the digest is the 30 Jun 2010 ESPN.com home (a red page with a top menu), and that page is ESPN.com, not the fantasy product. No hex was reached. Yahoo purple is the other allowed choice, and the Yahoo page that was actually reached is the 2013 dark-table complaint, which is the stat-surface anti-pattern.

Chrome, not sampled from a stylesheet:

- Header gradient `#2b2b2b` to `#111`, 4px `#cc0000` top border.
- Glossy primary button `#ff5a5a` to `#cc0000`.
- Page wash `#e4e4e4`. Panels, stat tables, and matchup cards `#fff` with `#1a1a1a` text.
- Links `#0645ad`. That blue is the boot-gate token, not a sampled ESPN link color. Table links and player-cell links stay `#0645ad` when visited. Winner emphasis is the score color `#9e0e18` and a 3px `#cc0000` inset bar, not a dark cell fill.
- Type is Arial/Helvetica 13px, cells `3px 6px`. Denser than the modern 14px body, larger than the 1990s size-2 glossary.

## Placeholders

A2's steel-blue gloss is replaced by the black/red gloss above. `width: 960px` stays. No reached ESPN, CBS, or MFL page measured a width. 960px is the late-2000s fixed grid (960.gs, March 2008) and the boot-gate token. It is not a claim that ESPN was 960px. Gold `#6b4f00` stays and is still unattested. No PFR hex was captured.

## What shipped against the acceptance list

- Fixed 960px centered shell, global header, hub nav, one promo. The promo is the record-book button on the home and on the season shell only. Week, gamecenter, League, and My Team have none. No Flash, plugin, share, or stacked ad rail.
- Season page is the existing pane strip, in our order: Standings, Weeks, Playoffs, Moves, Draft, Lineups, Stacks. Tabs are real `?pane=` links. The page has no `<script>`. Hash aliases from `hub.js` are real anchors in an "Also" row and link to the pane that script already opened. They are not positioned offscreen.
- Week slate and gamecenter are side-by-side franchise cards. Starters use initial-and-surname (`B. Purdy`), a catalog club badge (`SF`), and a position badge. Defenses keep the stored name (`SF D/ST`). `players.nfl_team` is the catalog abbreviation, and the page says so. The week slate is starters only. Gamecenter adds the bench. Avatars use `avatar_url`. Live scoring is not drawn.
- Dense standings where the warehouse has the numbers. See the column list below. Nothing invented. No division column.
- Two top-10 modules on the home and on the season standings pane. Position tabs are real links. View all is a real link. Columns are landed stats.
- Member pages are My Team: avatar, franchise name, owner, career line, and a season table. League (`/members`) is the all-time franchise board.
- Stat surfaces in the screenshots are white, including the matchup cards.

The season Weeks tab stays the shared games fragment. The matchup cards are the week URL and the gamecenter URL. Putting cards into that fragment would have been a fragment edit.

## Dense standings

Projection `franchise, record, win_pct, games_back, streak, points_for, avg_pf, points_against, avg_pa`.

| Column | Source |
| --- | --- |
| Franchise | `flavor_team(display_name, team_name)`, else the display name. Link to `/members/{id}`. |
| W-L-T | Official wins, losses, ties, including a played median game. |
| Pct | Official `win_pct`. |
| GB | `(best wins-minus-losses − this wins-minus-losses) / 2`, official W and L. Ties are not in the formula. |
| Strk | Trailing run of `v_games` for that season, `regular` and `vs_median`, ties included, median after the head-to-head game in the same week. Not `v_streaks.is_current` (that view is career-long and skips ties). |
| PF | Official `points_for`. |
| Avg PF | Official points for ÷ head-to-head games. Median games are not in the denominator, because they do not add points. |
| PA | Head-to-head `points_against`. |
| Avg PA | That points-against ÷ the same head-to-head games. |

A missing points value or zero head-to-head games renders the average as —. Div W-L-T is omitted. This league has no division rows. The sentence under the table says so.

2025 check: Andrew Howey is rank 1 and not the champion, so the franchise is italic (`is-active-leader`): 20-8-0, 0.714, GB 0.0, L2, PF 1974.98 in gold, Avg PF 141.07 (1974.98 / 14). Nate White is the champion (`is-leader`), also 20-8-0 and GB 0.0. A 12-4 against an 11-5 is GB 1.0. A 9-7 against a 12-4 is GB 3.0.

era90 still projects Manager, W, L, T, PF, PA. The extra keys are on the row and are not in that projection.

## Top-10 modules

Both boards sit outside `BOARDS`. The boot gate equates that registry with the season pane catalog, and these modules are not panes. They still render through the `stat_table` macro. That is not a fragment amendment.

Position tabs are QB, RB, WR, TE, K, DEF. The label is DEF, which is our code, not CBS's DST. Default position is QB. A position tab drops that module's `rows=all` and keeps the other module's position and rows flag.

1. **Stat line** (`#mod-counting`). Season fantasy points on posted weeks that have a `player_week_scores` row. Counting columns sum `player_week_counting_stats` on those weeks. A scored week with no counting row adds zero.
   - QB: Player, YDS (pass yards), TD-INT, PTS
   - RB: Player, RUSH, REC, TD (rush plus receiving)
   - WR/TE: Player, REC, YDS (receiving), TD
   - K: Player, FG and XP as makes-attempts, PTS
   - DEF: Team (stored name), YDS (yards allowed), PA (points allowed), SCK, TO (interceptions plus fumble recoveries), PTS
2. **Week highs** (`#mod-weeks`). One posted week per row. Player or Team, Wk (link to that week), PTS. Skill names are initial and surname. Defenses keep the stored name.

Bold marks the points leader. 2025 QB leaders start J. Allen 364.62. 2025 K starts J. Myers 39-44, 47-47, 189.00. 2026 DEF starts TB D/ST with yards allowed, points allowed, sacks, and turnovers from the counting rows. View all on the 2026 QB boards returned 200: 61 counting rows and 300 week rows.

Home uses the latest scored year (2026 when this was measured). The season page uses that season. Both modules are on each.

## Modern and era90

`git diff origin/cursor/ui-wave-45-bf5b` is the era2010 shell, CSS, and `hub/templates/era2010/*`, plus append-only tails in `app.py`, `queries.py`, and `themes.py`. The queries and app diffs have no deletions. Modern templates, `hub.css`, `hub.js`, and the era90 shell and CSS are the wave tip.

Unthemed `/`, `/?theme=modern`, and `/?theme=nope` are the same document (39,542 UTF-8 bytes) and link `hub.css`. They do not link an era stylesheet.

`/seasons/2025?theme=era90&pane=standings` is 7,924 UTF-8 bytes. That is the figure C1a recorded for this URL on the wave tip. Headers are Manager, W, L, T, PF, PA. The era90 glossary is present. The page links `era90.css`.

`scripts/ui/parity.ps1 -Mode check` against `parity-main`, switcher stripped at the expected 194 bytes:

- Pass: `/seasons` 302, `/luck` 302, `/seasons/2025/scoring` 79,761 bytes unchanged.
- The structural misses the wave already documented against that baseline are `/` (A3), `/records` (B2), and `/players` (D1).
- Other data pages also differ from that older capture (season, week, members, `/players/4046`, and the rest of the harness). Those templates and their query functions match the wave tip, so the movement is the live warehouse against the capture, not an era2010 leak into the modern shell. `/players/4046` still renders the modern anatomy (Summary, season, Ownership, Splits, Counting) at 55,615 UTF-8 bytes.

## Performance

Same commit, `Invoke-WebRequest` to `127.0.0.1`, one warmup dropped, n=5. Milliseconds.

| Page | Modern median (min–max) | era2010 median (min–max) |
| --- | --- | --- |
| `/` | 329.2 (275.8–419.2) | 97.7 (89.9–107.3) |
| `/seasons/2025` standings | 689.5 (677.9–706.2) | 87.2 (86.3–112.4) |
| `/seasons/2025/week/1` | 102.9 (84.2–106.7) | 45.5 (43.1–77.3) |
| `.../week/1/2025-w01-1` | 97.7 (91.8–101.8) | 52.6 (35.4–250.1) |

Medians are under the modern page. The gamecenter max of 250.1 was one sample. A second n=5 on that era URL was 49.8 median, 45.6–58.5. The era week and gamecenter paths do not call `week_slate` or `gamecenter`, so they skip luck, coach, and history.

## No JS

Era2010 home, season panes, week, gamecenter, League, and My Team contain zero `<script>` tags. Tabs, alias anchors, matchup cards, player cells, position tabs, and View all are in the HTML. Confirmed by fetching the documents, not by disabling a script that was present.

## Hash aliases

On `/seasons/2025?theme=era2010` the tab anchors are `standings`, `weeks`, `playoffs`, `moves`, `draft`, `lineups`, `stacks`. The Also row adds the `hub.js` map: `scoring`, `scoring-env`, `share`, `universes`, `universe-ranks`, `universe-brackets`, `universe-replay`, `luck`, `allpro`, `allbench`, `power`, `heat`, `race`, `desk`, `median-tax` → standings; `matchups` → weeks; `trades` and `wire` → moves. Each alias is an `id` and a link to that pane.

Modern also has in-pane ids (`#m-{manager}`, `#highlights`, week headings inside a pane). Those are not on the era fragment. `stat_table` has no row-id hook, and the luck plaques are modern content. The alias names themselves resolve.

## Screenshots

`docs/ui/shots/c2a/`

| File | URL |
| --- | --- |
| `home.png` | `/?theme=era2010` |
| `season.png` | `/seasons/2025?theme=era2010&pane=standings` |
| `week.png` | `/seasons/2025/week/1?theme=era2010` |
| `gamecenter.png` | `/seasons/2025/week/1/2025-w01-1?theme=era2010` |
| `my-team.png` | `/members/andrew-howey?theme=era2010` |
| `top10.png` | `/?theme=era2010` tall window, stat line and week highs |

Headless Chrome, 127.0.0.1. Avatars loaded from the sleeper CDN. The home shot includes both modules. `top10.png` is the same home, taller, so the boards are the subject.

## Contract

No fragment amendment. The grammar that needed a table uses `stat_table`. Top-10 boards stay out of `BOARDS` so the pane-equality gate still holds.

## Files

- `hub/static/themes/era2010.css`
- `hub/templates/shells/era2010.html`
- `hub/templates/era2010/` (home, week, gamecenter, score card, player cell, modules, franchises, My Team, leads and asides)
- `src/nu_choate_league/web/themes.py` (era2010 projection, standings derivation, dispatch, module boards)
- `src/nu_choate_league/web/queries.py` (streaks, roster, counting leaders, week highs)
- `src/nu_choate_league/web/app.py` (alias global and middleware, after the C1a `page()` wrapper)
- `docs/ui/c2a-notes.md`
- `docs/ui/shots/c2a/*.png`
