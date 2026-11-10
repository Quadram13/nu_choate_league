# IA map — B3 (#102)

Hub-wide information architecture after B1 (player pages) and B2 (record chapters). This file is the map. It does not restyle a theme and it does not change a metric. Era shells, fragment templates, `themes.py`, and the players index stay with their owners. Modern templates gained links only.

The research bar used here is the one in `docs/ui/research-digest.md`: the league is one click from home, there is one way into a destination, and a page is not pushed further away without a named reason. Weekly surfaces stay on the mast. Rare surfaces stay one click from a mast item, or one click from the entity they describe.

## 1. Cross-link discipline

An entity cell is a player, a manager or franchise, a season year, a week, a matchup, or a record citation. The cell's text is an `<a href>`. Script is not required to follow it.

| Entity | Destination |
|---|---|
| Player name | `/players/<id>` |
| Manager | `/members/<id>` |
| Franchise jersey for a season | `/seasons/<year>#m-<manager_id>` (the standings row). The manager name beside it is the member link. |
| Year | `/seasons/<year>`, plus the pane hash when the number is about that pane (`#standings`, `#wire`, `#draft`, `#stacks`, `#scoring-env`, `#median-tax`, `#luck`) |
| Week | `/seasons/<year>/week/<week>` |
| Matchup | `/seasons/<year>/week/<week>/<matchup_id>` |
| Trade | `/seasons/<year>/trades/<transaction_id>` |
| Wire claim | `/seasons/<year>/wire/<transaction_id>` |
| Record citation (`/records#anchor`, or a "Nth-highest" label) | `/records/<chapter>#<anchor>` |

`hub/templates/link_macros.html` is the rewrite. `records_chapter` maps a legacy `/records#anchor` onto the B2 chapter. An anchor that is not in that map is left unchanged, so the index forwarder still has it. `season_years` is the no-JS year row.

### Exceptions

- A figure that is one game or one week keeps the event URL the query already stored (gamecenter or week slate). The record-book link is the citation next to it (`alltime_label`), not a replacement of the event link. Pair-page margins ("The inch", "The rout") are that pair's game: the figure opens the matchup, and the year-week meta opens the week slate.
- On a records chapter, the value is already the chapter. The when-cell opens the season, week, or matchup. The number is not a link back to itself.
- SVG axis numbers on the scoring chart and the points race link to the week. League-aggregate circles (average, median, high, low) do too. A counterfactual bracket round is a span (`W15–W16` or similar), not one slate, so the span stays text.
- Column abbreviations on Versus and the schedule desk are the manager. They link to the member page. The `title` is the full name. `person_link` is not used there, because the avatar does not fit the header cell.
- "Even" is not a manager. A player or manager with no id stays text.
- Busiest-pair "got" cells on `/records/trades` are one SQL string (`left_received` / `right_received`) with no player id on the row. Linking them needs a query change. Left as text. See Handoff.
- Live standings cells (record, PF, luck) are this season's row, not a record-book citation. The manager is linked. The season page is the parent link.
- `/seasons` with data in the warehouse is a 302 to the latest scored year. It is not an archive document. The archive is the champion rail on home and the year row on each season page.

## 2. Top-level grammar — the six stay

Modern mast, unchanged, in `hub/templates/base.html`:

Home, Seasons, Members, Versus, Records, Players.

A2's boot gate locks this order to `NAV_ORDER["modern"]` in `themes.py`. B3 does not edit that file. Demoting any of the six would also desync the gate. The traffic argument below is why the lock is the right grammar, not only a constraint.

| Item | Traffic | Why it stays top-level |
|---|---|---|
| Home | Weekly | Current desk: champion rail, this season's standings, this week's slate. It is also the no-JS seasons archive, because `/seasons` redirects. |
| Seasons | Weekly | The redirect lands on the latest season. That season is the weekly document (standings, weeks, moves). Sibling years are one click from the year row. |
| Members | Rare, but it is the manager destination | Every manager cell in the hub points here. A career page is not a section of Versus or of one season. One way in. |
| Versus | Rare | The matrix has two subjects. It is not a tab of one member. Home already teases the top rivalries, so the matrix is one click either from the mast or from that tease. Demoting it would not shorten a weekly path. |
| Records | Rare | The book is one destination. Nineteen chapters are sections of it (B2), not mast items. Home links the index. A citation links the chapter. |
| Players | Weekly when a name is on screen, rare as a browse | Player-name cells point here. The log and the splits are sections of one player (B1), not mast items. |

Not top-level, and why:

| Surface | Home | Clicks from home | Reason |
|---|---|---|---|
| Scoring sheet | Season subpage, and an era90 rail task | 1, after the desk promotion below | Reference, not a weekly check. It does not earn a seventh mast item. |
| Desk, distinctions, moves log, draft board | Season subpages | 1 from the home desk row (desk, marks, moves) or 2 (draft, via the season) | They are panes or logs of one year. |
| Week slate, gamecenter, trade, wire claim | Season children | 2 (home slate is 1 for the current week) | The current week is already on the home aside. Older weeks hang off the season. |
| Record chapter | Section of Records | 2 from home, 1 from a citation | B2's split. The index is the mast target. |
| Player log, player splits | Sections of one player | 2 | B1. The profile is the mast target. |
| Champions | Section of Home (`#champions`), not a route | 0 | Five seasons fit on the desk. There is no champions route, and adding one would be a Python change. |
| Era theme | Switcher on every modern page, one click, no script | 0 | A2. Not a mast item. |

Nothing in this pass moved a page further from home. Scoring moved closer (see the modern map).

## 3. Home content maps

C lanes draw these. This ticket records what each home is, and it applies only the modern link promotions that do not remove a stat.

### Modern — current desk

What is on `/` today, and the decision:

| Block | Decision | Why |
|---|---|---|
| Champion rail (`#champions`) | Keep | It is the champions list and the no-JS archive. Each year and each manager is already a link. Jerseys already open `#m-<id>` on that season. |
| "Weekly newsletter" and "Main wiki page" cards | Cut when C3 skins modern | Both say they are not in the hub. They are two empty promo slots. The digest allows one promo, and not above the work. This pass does not delete them: that would drop copy, and C3 owns the modern skin. |
| Current-year standings | Keep | Weekly. The table is `fragments/home_standings.html` (not edited here). Managers are linked. |
| Desk row | Keep, and promote Scoring onto it | Full season, desk, distinctions, and moves were already one click. Scoring was two (home, season, sheet). It is now on the same row, still off the mast. |
| Season highlights and all-time plaques | Keep | Figures keep the event URL the query stored. The all-time note links Members, Versus, Records, and Players. |
| Top rivalries | Keep | The pair is one click to Versus. |

The two stub cards are the only cut. No stat block moves off the desk.

### 1990s — portal

Eagle's home is a portal, not a stat sheet. Left rail, top to bottom, adapted to this league and already locked by A2's era90 nav (do not add an item; the boot gate checks the tuple):

1. Home
2. Current season — the Seasons task. `/seasons` redirects to the latest year. The small standings grid is the only data table on the era season pilot.
3. Record book — `/records`
4. Leaders — `/players`. Eagle's "TOP 10" is this list, not a second mast. A ten-row teaser with View All is the 2010 module, not this rail.
5. Rules and scoring — the current season's scoring sheet (`/seasons/<year>/scoring`). A2 already points the scoring task there.
6. Members
7. Versus

Champions are not an eighth rail item. They are the `#champions` section of the portal (the modern rail, which the era home should reuse as content). A separate champions URL was not added.

Seasons archive is the same year row as modern: one link per year, on the home portal and on the season page. It is not a new route.

Right rail: one labeled link box. A2 already ships that box, with the Eagle off-site names as text (`dead-label`), not as invented hrefs. Do not add a second box or turn those labels into links.

Header band: "Email the commissioner", the maroon `#660000` band A2 already paints. No commissioner route.

### ~2010 — module home

The home is four modules, in this order. The first module is the week or the standings, not a poll and not a house ad.

1. Current-week card. The matchup opens gamecenter. The week title opens the slate. Summary in the card, the full week one click away.
2. Standings card. The small grid, with a link to the season standings pane.
3. Top 10, with a real View All to `/players`. Ten rows, not the index embedded in the card. The link is `<a href>`, not a script-only expand.
4. At most one promo slot. The two modern "coming soon" cards do not both survive. Zero is allowed. The slot sits after the three modules above.

era2010's mast reuses the modern six (A2: no 2010 source captured a tab order). Season panes stay the seven real links A2 already renders as tabs. This ticket does not draw the module chrome.

## 4. Season sub-IA

The seven panes are the boot-checked catalog. Hash aliases in `hub.js` (not edited) open the parent pane. No-JS shows every pane, because `hidden` is set by script only.

| Pane | What lives here | Also reachable |
|---|---|---|
| Standings | Official table, weekly scoring chart, scoring environment, universe line and counterfactual brackets, all-pro, all-bench, all-play, week ranks, points race, schedule desk, median tax | In-pane jump for the blocks that were not in the tab row: `#scoring`, `#scoring-env`, `#universes`, `#universe-brackets`, `#universe-replay`, `#power`, `#heat`, `#race`, `#desk`, `#median-tax`. All-pro and all-bench stay on the tab row. |
| Weeks | Week grid. Each week opens the slate. Each game has a lineups link to gamecenter. | `#matchups` (notable games) from the tab row when any notable exists. |
| Playoffs | Path table, winners and consolation brackets. Bracket "week N" opens the slate. | `/records/playoff`, `/records/playoff-history` |
| Moves | Trades and wire for the year. Week cells open the trade or the wire claim. | `/seasons/<year>/moves`, `/records/trades`, `/records/wire` |
| Draft | Manager grades, hits, misses. | `/seasons/<year>/draft` (pick ids `p<overall>`), `/records/draft` |
| Lineups | Coach table. Week numbers open the slate. | `/records/lineups`, `/records/coach` |
| Stacks | Season stack boards. | `/records/stacks#stacks` |

Subpages and the parent they name:

| Page | Links back |
|---|---|
| `/seasons/<year>/moves` | Season `#moves`, trades chapter, wire chapter, plus a year row |
| `/seasons/<year>/draft` | Season `#draft`, draft chapter, year row |
| `/seasons/<year>/marks` | Season `#weeks`, chairs chapter, year row |
| `/seasons/<year>/desk` | Season `#desk`, year row. Header abbreviations link to the member. |
| `/seasons/<year>/scoring` | Season, `#scoring`, environment chapter, year row. In-page jumps for distribution, spread, seasons, positions, scarcity, sheet, rule diff were already there. |
| `/seasons/<year>/week/<week>` | Season, `#weeks`, previous and next week, in-page standings, matchups, card, transactions. Matchups open gamecenter. |
| Gamecenter | Season, the week, previous and next matchup, a week numeral row, sibling matchups. Names in the title link to the member. Jerseys link to `#m-<id>`. |
| Trade detail | Season `#trades`, the week slate, previous and next trade. The two managers in the title link to the member. A jersey links to `#m-<id>`. |
| Wire detail | Season `#wire`, the week `#transactions`, previous and next claim. The player and the manager were already linked. |

The `<select class="js-season-pick">` is still the compact control. It needs script. The year row under it is the same destination with no script. Both are on the season page and on moves, draft, marks, desk, and scoring.

## 5. Cross-link audit

"Linked" means the rendered cell is an `<a>`. "Exception" is a row in section 1. "Handoff" is a real gap in a file this ticket does not own.

| Surface | Entity | Result |
|---|---|---|
| Home champion rail | Year, manager, jersey | Linked |
| Home desk | Season, desk, marks, moves, scoring | Linked. Scoring promoted. |
| Home standings fragment | Manager | Linked. PF and record are the live row (exception). |
| Home slate fragment | Week title, matchup overlay, managers | Linked. Open-week "Year WN" heading is text. Handoff. |
| Home plaques and rivalries | Manager, event figure, pair | Linked. Figure URL is the event (exception). |
| Season standings and the other panes | Manager, player, year is the page | Linked. In-pane hashes added where the tab row had no link. |
| Season bracket | Manager, week, jersey | Linked this pass. |
| Season points-race legend | Manager | Linked this pass. Chart weeks linked this pass. |
| Season desk headers | Manager abbreviation | Linked this pass. |
| Season notable rows | Week/matchup, managers, record citation | Citation rewritten to the chapter. |
| Moves, draft, marks, desk, scoring | Year row, parent season, record chapter where one exists | Linked this pass. A free-agent drop with no add opens the week slate. The wire route only serves a waiver claim or a completed free-agent add, so those drop-only rows were 404s. |
| Marks log | Manager, and the other name on the row | A hyphenated id is a manager (`managers.id` all contain a hyphen) and links to `/members/<id>`. Any other id is a player, including a defense abbreviation, and links to `/players/<id>`. |
| Week and gamecenter | Season, week, matchup, player, manager, jersey | Jersey and the gamecenter title linked this pass. |
| Trade detail | Managers, players, week, jersey | Title, week, and jersey linked this pass. |
| Wire detail | Player, manager, week | Already linked. |
| Members index | Manager, current streak | Streak now `/records/streaks#current`. |
| Member page | Seasons, draft, wire, trades, highs, clutch years, best/worst weeks | Years and best/worst weeks linked this pass. Hardware years are links. Record citations rewritten. |
| Versus matrix | Row manager, header abbreviation, cell | Header linked this pass. Cell was already the pair. |
| Versus pair | Managers, streak start, winner, margin, when | Prose names, streak, winner, and the year-week meta linked this pass. |
| Records index | Chapter anchors | Already `/records/<slug>#<id>`, including with script off. |
| Records chapters | Manager, player, year, week, matchup | Already linked, except the busiest-pair "got" string (exception) and the pair names in the busiest heading (linked this pass). |
| Players index | Player name | Linked. Year cells and `/records#wire-left` are not. 177 profile hrefs 404 because the player route has no row for that id. Handoff (#105). |
| Player profile, log, splits | Year, week, manager, opponent | Profile years and weeks are linked (B1). Volatility "best/worst in YEAR Wweek" prose, and the best/worst cells that only use `title`, are still text. Counting headers still pass `/records#counting-career` and `#counting-season`. Handoff (do not edit `player.html`). |

## 6. Gaps fixed in this branch

| Route | What changed |
|---|---|
| `/` | `#champions`. Scoring added to the desk row. |
| `/seasons/<year>` | Year row. Standings in-pane jump. Notable link. Bracket week and jersey links. Chart weeks. Race legend. Desk-header members. Record citations to chapters. Playoff, draft, lineup, and environment chapter links. |
| `/seasons/<year>/moves` | Year row. Trades and wire chapters. Drop-only free-agent weeks open the slate. |
| `/seasons/<year>/draft` | Year row. Draft chapter. |
| `/seasons/<year>/marks` | Year row. Chairs chapter. Player opponents (id has no hyphen) open `/players/<id>`. |
| `/seasons/<year>/desk` | Year row. Header members. |
| `/seasons/<year>/scoring` | Year row. Links to `#scoring` and the environment chapter. |
| `/seasons/<year>/week/<week>` | Link to the season weeks pane. |
| Gamecenter | Title names. Jerseys. |
| Trade detail | Title names. Week slate. Jerseys. |
| `/members` | Streak to `/records/streaks#current`. |
| `/members/<id>` | Hardware years, waiver and clutch and consistency years, best/worst week numbers, record citations. Season card year and jersey. |
| `/versus` | Header members. |
| `/versus/<a>/<b>` | Streak week, prose names, winner, year-week meta. |
| `/records/trades` | Busiest-pair names in the heading, the sentence, and the column headers. |

`plaque_macros.html` grew two optional arguments (`year_links`, `meta_href`). Callers that omit them render the same meta line as before.

No new class was added to `hub.css`. No script was added. `app.py` and `queries.py` were not edited. Legacy `/records#...` strings still exist in `queries.py`; the templates rewrite them at render.

## 7. Handoff

| Owner | Item |
|---|---|
| A2 reconcile / C lanes | `pager.html` mentions the word theme. `home_standings.html` and `players_career.html` contain `<table>`. The boot gate is right to refuse them. Not fixed here. |
| Fragments | Home slate, while the week is open, renders `Year WN` as a heading with no href. The closed week is linked. |
| #105 players index | Year cells in the season and wire tables are text. `/records#wire-left` should be `/records/wire#wire-left`. `/records` in the lede could name `/records/environment#high`. The career/season switch is a `<button>`, so the season board is not a link. The index also links player ids whose profile route 404s (`_load_player` returns nothing). 177 of those hrefs 404 on the 2025-era index crawl. Not edited here. |
| Player profile (`player.html`, B1) | Volatility prose "in YEAR Wweek", and best/worst cells that only put the week in `title`, are text. Counting boxes still receive `/records#counting-career` and `/records#counting-season`. |
| `queries.py` | Record citation hrefs are still `/records#high`, `#low`, `#closest`, `#blowouts`, `#wins`, `#losses`. Templates rewrite the ones they print. A later edit can store the chapter URL at the source. |
| `app.py` `/luck` | Falls back to `/records#season` only when no scored year exists. Not the live path (`/luck` redirects to the season `#luck`). |
| Records trades | `left_received` / `right_received` on the busiest-pair rows have no player id. |

## 8. Nav

Kept the six. Section 2 is the per-item reason. Scoring was promoted onto the home desk row and was not added to the mast. Era90's longer rail (scoring between players and members) stays the shell's rail, not the modern mast.
