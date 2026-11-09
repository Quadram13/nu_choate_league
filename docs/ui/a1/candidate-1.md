# Candidate 1 — per-theme template sets

## Problem

Ticket #95 needs three first-class presentations of one league: today's hub, a 1998 portal, and a ~2010 league home. The pages that make this hard already exist. `season.html` is one JavaScript hash-tab document of about 1,200 lines. `players.html` is a 5 MB index. Seven `*_macros.html` libraries paint nearly every stat table, and `scoring_macros.html` is imported by the season page, the scoring page, and `records.html`. Query functions already return the rows (`players_index`, `season_page`, `scoring_sheet`). Theme must not query twice and must not change those rows.

The era split is a markup split. Reeve's standings (REACHED) are `<td>` cells, `border=2 cellpadding=5`, a blank 220px franchise header, ties as `-`, and no header fill. LFFL's week control (REACHED, Lame FFL 1998) is a row of numeral links labeled Results. Eagle's home (REACHED) is a borderless three-column table, a `#660000` commissioner band, and a FANTASY LINKS rail, with no stylesheet. CBS on 17 Sep 2009 (REACHED) is a ten-row module of `A. Rodgers` names with a View All escape, and the archive text contains no pixel width and no hex. The modern page has to stay byte-near, including its dark `hub.css`, until #107. A class string cannot emit those three trees. The design question is how three markup copies stay one set of numbers.

## Usage (caller's view)

A route does not learn themes. `page()` already builds the context; it hands that context to `render_page`, which binds `?theme=` for the render and resets it before returning. An unknown value is modern. There is no cookie.

```python
def page(request, name, *, nav, title, **context):
    return render_page(templates, request, name, {"nav": nav, "title": title, **context})
```

A board author includes one file and walks `present()`. The theme directory supplies the tags. `present("standings", standings)` returns columns, cells (`text`, `raw`, `href`, `emphasis`), and an optional glossary. It does not sort and does not query. The 1998 standings file is the whole era decision: a `border="2"` table of `<td>`, leader emphasis as `<b>`, glossary at `font size="3"`.

```jinja
{% set board = present("standings", standings) %}
<table border="2" cellpadding="5">
{% for row in board.rows %}
<tr>{% for cell in row %}<td data-cell="{{ cell.key }}" data-raw="{{ cell.raw }}">…{{ cell.text }}…</td>{% endfor %}</tr>
{% endfor %}
</table>
```

A season shell asks for the pane list, then includes one pane. `season_panes(year)` reads the `data-tab` order already in legacy `season.html` (Standings, Weeks, Playoffs, Moves, Draft, Lineups, Stacks). Era templates link `pane.href`. Modern does not override `season.html`, so the hash tabs stay the file that ships today.

```jinja
{% set panes = season_panes(current.year) %}
{% set active = active_pane(panes) %}
{% for pane in panes %}
{% if pane.id == active %}<b>{{ pane.label }}</b>{% else %}<a href="{{ pane.href }}">{{ pane.label }}</a>{% endif %}
{% endfor %}
{% include "panes/" ~ active ~ ".html" %}
```

A macro that must change shape does not get a second copy of the library. `distribution(season)` is one line: `theme_include("boards/scoring_distribution.html", season=season)`. The include renders in the active environment, so era90, era2010, and modern each own the table while `week_links`, `environment_table`, `marks_table`, `share_table`, and `league_week_board` stay the legacy macros `records.html` already imports.

## Shape

```
hub/templates/                     legacy documents and the 7 macro libraries
hub/templates/themes/modern/       overrides only (players.html, two boards)
hub/templates/themes/era90/        base, players, season, scoring, boards, two panes
hub/templates/themes/era2010/      the same file set as era90
hub/templates/themes/_shared/      panes and boards a theme did not override
src/nu_choate_league/web/themes.py install, render_page, present, theme_include
src/nu_choate_league/web/app.py    page() and the error handler call render_page
```

**Loader.** `install()` builds one Jinja environment per theme. `ChoiceLoader` order is `themes/<theme>/`, then `themes/_shared/`, then the legacy template directory. `templates.get_template` dispatches on a contextvar. The cache is per environment, so the same name can be three documents. `auto_reload` is on. Starlette renders inside `TemplateResponse` before the response returns, and `BaseHTTPMiddleware` runs the app in a child task, so the contextvar is set inside `render_page`, not in middleware.

**What forks.** Documents fork: `base.html`, `players.html`, `season.html`, `scoring.html`. Boards that cannot share tags fork: career rankings, standings, matchups, scoring distribution. Era90 and era2010 also fork `panes/standings.html` and `panes/weeks.html` because the 1998 center column is a heading plus a Results numeral row, and the 2010 center is a module heading plus matchup cards. Modern forks only `players.html` (top 50, so the spike is not the 5 MB index) and the two boards whose markup is the current hub table. Deleting `themes/modern/players.html` restores the full index with no route change.

**What stays shared.** Playoff path, and the moves, draft, lineups, and stacks panes, live in `_shared` and read the route context (`trades`, `draft`, `lineups`, `stacks`). They are summaries, not three copies of `season.html`. `playoff_path` is one neutral board. Navigation chrome (`theme_switch.html`, `week_nav.html`) is shared and emits real `<a href>` links. `qhref()` appends `?theme=` only when the theme is not modern, so modern in-page links stay byte-near. `theme_href()` always sets the theme and keeps `pane`, `week`, and `rows`.

**Values.** `present(board_id, rows)` is the only formatter. Projections pick column keys per theme. Career modern is Player, Pos, Yrs, Starts, PF, Avg, VORP. Era90 drops Yrs and VORP and leaves the franchise header blank, matching Reeve. Era2010 career is Player, Pos, PF, Avg, capped at 10 unless `?rows=all` (still capped at 50 in the spike), with `more_href` for View All. Names on that board are initial-plus-last (`A. Rodgers`; a particle stays, so `Amon-Ra St. Brown` is `A. St. Brown`). Standings era90 is W, L, T, PF, PA with a zero tie as `-`. Era2010 standings is Franchise, W-L-T, Pct, PF, PA, and the record is always three numbers. Scoring distribution is the same eight columns in every theme: Mgr-weeks, Teams, Avg, Median, Std dev, Min, Max, League PF. The decile strip stays on the modern board only, behind `{% if season.deciles %}`. Leader and higher-score emphasis is a cell flag; templates turn it into `<b>`, not a fill. Raw values on shared keys are required to be equal across themes.

**Drift mechanism, enforced at import.** `install()` raises `ThemeContractError` and the process does not serve.

1. Era90 and era2010 must both contain `REQUIRED_THEME_FILES`, and their html sets must match. A board added to one era fails the other.
2. Every `data-tab` pane in legacy `season.html` must resolve in the theme directory or `_shared`.
3. Theme templates may not read query fields (`starter_points`, `points_for`, `home_points`, and the rest of that list). Cells come from `present()`.
4. Era90 boards must carry `border="2"` and `cellpadding="5"`, must call `present(`, and must not contain `bgcolor`, `<th`, `class=`, a stylesheet, `hub.css`, or `hub.js`. Era2010 `base.html` links `era2010.css` and not `hub.css`. Modern career keeps `js-sort` and `<th>`. Era2010 career must reference `board.more_href`.
5. The macro library stays one file. If an era later drops in `scoring_macros.html`, its macro names must equal the legacy file. Era templates may import only `distribution` and `environment_block`. Any other import would paint legacy markup that the era shell has no stylesheet for, or would hide a macro `records.html` still needs.
6. A fixture render of career, standings, distribution, and a week must echo `present()` in `data-cell` / `data-raw` / visible text. The 10-vs-all cap is part of that render. A copied board that hard-codes a digit fails closed.

The public surface is `render_page`, `present`, `theme_include`, `season_panes`, `active_pane`, `week_slice`, `theme_href`, and `qhref`. Routes, queries, and macro callers stay on the other side of it. `themes.py` hides loader order, projections, and the ship gate.

**Era chrome that is citation versus prototype.** Era90 uses the Eagle/LFFL bytes: HTML 4.01 Transitional, `bgcolor="#EEEEEE"`, `link="#0000FF"`, `vlink="#990099"`, white columns, left rail from the existing league tasks (Home, Seasons, Members, Versus, Records, Players), right rail labeled FANTASY LINKS. ESPN is the one off-site link with a reached host (`http://espnet.sportszone.com/`). NANDO, USA TODAY, CBS SPORTSLINE, CNN/SI, and INJURY REPORT are labels without invented URLs. The commissioner line links to `/members`. No counter, no `size="+4"`. The center column is fluid because Eagle's 211px center was an image. Era2010 is a 960px shell, a blue gradient bar, and the same task list as a sport bar. That width and that hex are not in any REACHED source. Tabs are the existing pane order, not the MFL 2020 printer-view list (REACHED, and explicitly not a 2009 default). Stat tables on both era shells are light, which is the Yahoo Aug 2013 lesson (REACHED) and LFFL's white card. Modern stays on dark `hub.css` because byte-near outranks that lesson until #107.

## Synthesis decision

Filled by the arena after the three candidates.

## Tradeoffs accepted

- We accept three markup copies of each forked board in exchange for era tags a shared fragment cannot emit: Reeve's border and `<td>` header, a 2010 matchup card, and the current `<thead>` plus `js-sort`.
- We accept a boot-time fixture render, and a hard error if it fails, in exchange for drift failing closed instead of shipping a board that formatted its own number.
- We accept one shared summary for moves, draft, lineups, stacks, and the playoff path in exchange for not copying `season.html` three times. Those panes are the first place a later era override would go; the coverage gate already requires the file in both eras once either era adds it.
- We accept the legacy macro library, with `distribution` delegating through `theme_include`, in exchange for `/records?theme=era90` still rendering the records tables. A per-theme `scoring_macros.html` would replace the whole file and blank every macro the era did not reimplement.
- We accept a top-50 shadow of `/players` for the spike in exchange for a page that can be compared across themes. Removing `themes/modern/players.html` is the rollback.
- We accept modern hash tabs, which need JavaScript to switch panes, in exchange for leaving `season.html` byte-near. Era panes are query links and work with JavaScript disabled. The theme switcher is a link on every shell.
- We accept an unlabeled 960px gradient as 2010 chrome in exchange for a shell that is recognizably not the 1998 table and not today's dark hub. It is marked as prototype chrome in `era2010.css`.

## Alternatives considered

- **C2, shells plus class-only fragments.** One content template would call `present()` and emit one tree. Shells could still be era documents, and the interface for a page author would be smaller. It loses on the boards that are the ticket: a fragment cannot be a `border=2` table of `<td>`, a `<div class="matchup">`, and a sortable `<thead>` unless the fragment grows `{% if theme %}` branches. Those branches are a third copy with worse locality, and they put era grammar back in the shared file this shape exists to keep dumb.
- **C3, one DOM plus a stylesheet.** `data-theme` and CSS can recolor the modern page. They cannot turn the season document into seven addressable pages, cannot make the 1998 response omit `hub.css` and the script, and cannot turn a 5 MB index into a ten-row module without still sending the hidden rows. Hiding panes fails the no-JavaScript requirement and the payload constraint. The interface looks deep (one template) and is shallow where it matters, because era structure leaks into conditional classes on the single tree.
- **Three full copies of `season.html` and of `scoring_macros.html`, with no `present()`.** Maximum fidelity, and the drift risk the seed named with nothing mechanical behind it. `records.html` imports five scoring macros; a stub library made those pages empty inside the era shell. That variant was implemented, seen, and removed.
- **Per-theme macro files that `{% include %}` the legacy library and override `distribution` only.** Jinja replaces the template name. An include inside the macro does not see the macro's `season` argument. `theme_include` is the smaller seam: one function, explicit arguments, markup returned as `Markup`.

## Open questions and risks

- Should the required-file list grow by scanning every `page()` template name, or stay the three surfaces until a theme claims the rest of the hub?
- Does byte-near keep the modern stat surface dark until #107, given the Yahoo 2013 note that numbers want a light table?
- Is the unlabeled 2010 width acceptable until a capture actually contains a pixel width?
- Should the unthemed scoring macros eventually pass through `present()`, or is a legacy table inside an era shell acceptable for `/records` during the spike?
- Does `?rows=all` stay capped at 50, or does the full career index return as its own URL once modern stops shadowing `players.html`?

## Next implementation step

Point the remaining `page()` templates at the loader as they are claimed, and add each new forked board to `REQUIRED_THEME_FILES` plus one fixture row in `collect_contract_problems()` before writing the second era's tags.

## Click list

Served from this worktree on port 8121. Latest scored season is 2026. Switcher links work with JavaScript disabled.

- http://localhost:8121/players?theme=modern
- http://localhost:8121/players?theme=era90
- http://localhost:8121/players?theme=era2010
- http://localhost:8121/players?theme=era2010&rows=all
- http://localhost:8121/seasons/2026?theme=modern
- http://localhost:8121/seasons/2026?theme=era90
- http://localhost:8121/seasons/2026?theme=era90&pane=standings
- http://localhost:8121/seasons/2026?theme=era90&pane=weeks
- http://localhost:8121/seasons/2026?theme=era90&pane=weeks&week=1
- http://localhost:8121/seasons/2026?theme=era90&pane=playoffs
- http://localhost:8121/seasons/2026?theme=era90&pane=moves
- http://localhost:8121/seasons/2026?theme=era90&pane=draft
- http://localhost:8121/seasons/2026?theme=era90&pane=lineups
- http://localhost:8121/seasons/2026?theme=era90&pane=stacks
- http://localhost:8121/seasons/2026?theme=era2010
- http://localhost:8121/seasons/2026?theme=era2010&pane=standings
- http://localhost:8121/seasons/2026?theme=era2010&pane=weeks
- http://localhost:8121/seasons/2026?theme=era2010&pane=weeks&week=1
- http://localhost:8121/seasons/2026?theme=era2010&pane=playoffs
- http://localhost:8121/seasons/2026?theme=era2010&pane=moves
- http://localhost:8121/seasons/2026?theme=era2010&pane=draft
- http://localhost:8121/seasons/2026?theme=era2010&pane=lineups
- http://localhost:8121/seasons/2026?theme=era2010&pane=stacks
- http://localhost:8121/seasons/2026/scoring?theme=modern
- http://localhost:8121/seasons/2026/scoring?theme=era90
- http://localhost:8121/seasons/2026/scoring?theme=era2010

Verified live against the read-only database: each URL returned 200. Career PF text matched across modern, era90, and era2010 `rows=all` (first five: 1673.6, 1380.5, 1320.5, 1293.7, 1290.9). Era2010 default showed 10 rows; `rows=all` showed 50. Scoring Avg was 125.24 and League PF was 12022.94 on all three themes. Era90 standings ties rendered `-`; era2010 records rendered `12-4-0` form. Era90 responses carried `bgcolor="#660000"`, FANTASY LINKS, `border="2"`, and no `hub.css`. Era2010 responses carried `era2010.css`, `league-tabs`, and `class="matchup"`, and no `hub.css`. Modern season kept `js-season-tabs` and all seven `data-tab` panes. `/records?theme=era90` rendered the records tables inside the 1998 shell. Week 1 era90 used a bold `1` and linked the other numerals. A 2010 matchup bolded the higher score (163.7 vs 83.8).
