# Candidate 2 — per-theme shells, one content catalog

## Problem

Three themes have to share one warehouse and one set of boards, and the season page is the split that makes the shape non-obvious. Today every route goes through `page()` into `base.html` plus `hub.css`, and `season.html` is one document whose panes (standings, weeks, playoffs, moves, draft, lineups, stacks) switch with script. The 1998 grammar, from Eagle and LFFL, is a borderless three-column portal and a numeral row of real links. The ~2010 grammar, from the CBS bar and the MFL module home, is a fixed shell whose league tabs are real links. No reached source captured an ESPN 2010 tab order, so the tabs have to be this league's panes. Modern has to keep today's mast. The boards themselves (Reeve's W-L-T grid, the rankings table, the scoring totals) are the same facts in every era. A theme that forks those facts will drift, and a theme that only restyles one DOM cannot put the champion line in a header band in one era and in the right-hand link box's neighbor in another.

## Usage (caller's view)

A page author adds a page by listing panes and slots, then calling `render_panes`. They do not name a shell, read `?theme=`, or write a second copy of a table. The first pane is the document when `?pane=` is absent or unknown. Only that pane's loader runs.

Rankings, two windows of one board (`theme_pages.players_response`):

```python
return render_panes(
    request,
    title="Players",
    nav="players",
    pager="Rankings",
    panes=(
        Pane("top", f"Top {TOP_N}", "fragments/board.html", top),
        Pane("career", "Career", "fragments/board.html", career),
    ),
    slots=(
        Slot("lead", "fragments/players_lead.html"),
        Slot("aside", "fragments/players_aside.html"),
    ),
)
```

`top` and `career` close over one `LIMIT 50` read of `v_players_index_career`. Each returns `{"board": ...}` for `fragments/board.html`, which only calls the stat macro.

Season, seven panes, two of them the same games template (`theme_pages.season_response`):

```python
panes = tuple(
    Pane(
        name,
        label,
        "fragments/games.html" if name in ("weeks", "playoffs") else "fragments/board.html",
        loaders[name],
    )
    for name, label in _SEASON_LABELS
)
return render_panes(
    request,
    title=f"{year} season",
    nav="seasons",
    pager="Season",
    panes=panes,
    slots=(
        Slot("lead", "fragments/season_lead.html"),
        Slot("aside", "fragments/season_aside.html"),
    ),
    context={"year": year, "current": current},
)
```

`_SEASON_LABELS` is the order already in `season.html`: Standings, Weeks, Playoffs, Moves, Draft, Lineups, Stacks. Weeks and playoffs both mount `fragments/games.html`. The other five mount `fragments/board.html`. The route checks `season_row` and returns 404 before this call.

Scoring, a one-pane page so the shell draws no tab strip and no numeral row (`theme_pages.scoring_response`):

```python
return render_panes(
    request,
    title=f"{year} scoring",
    nav="seasons",
    pager="Sheet",
    panes=(Pane("sheet", "Scoring", "fragments/board.html", sheet),),
    slots=(
        Slot("lead", "fragments/scoring_lead.html"),
        Slot("aside", "fragments/scoring_aside.html"),
    ),
    context={"year": year, "current": current},
)
```

`sheet` builds the week-total board (Week, Low, Avg, High) through the same macro as standings and the rankings.

To add a pane, add one `Pane` to that tuple: name, label, template, loader. Shells pick it up because they loop `frame.fragments`. To add a fourth theme, add its id to `THEMES`, a label, a nav order, `shells/<id>.html`, and `static/themes/<id>.css`. Importing the app fails if any of those disagree.

## Shape

The catalog is the data structure. A `Pane` is a name, a label, a template path, and a zero-arg loader. A `Slot` is a name and a template path. `render_panes` resolves the theme, picks the active pane, runs that loader, and builds a frozen `Frame`: theme, title, nav key, pager label, fragment views, the active view, the slot map, shell nav links, and theme choices. The shell is `shells/{theme}.html`. It reads the frame and mounts content only through two includes, `shells/_fragment.html` and `shells/_slot.html`.

The stat board is the other structure. One builder, `_board`, returns a caption, columns (`label`, `numeric`), rows of cells (`text`, `numeric`, `href`, `mark`), and a note. `fragments/stat_table.html` is the only template allowed to contain `<table`. Cell marks are `is-leader` (bold), `is-record` (gold text), and `is-active-leader` (italic). The spike emits the first two. A zero tie is the character `-` from `_tie`, in every theme. Leader color is a stylesheet rule on the class. No cell fill.

What each shell does with the same frame:

| Frame field | 1998 shell | 2010 shell | Modern shell |
| --- | --- | --- | --- |
| `nav_links` | Left rail, Eagle task order, 178px. Scoring is included when the page has a year. | Sport bar, same six links as today's mast. | Mast, same six links, `class="on"`. |
| `theme_choices` | In the `#660000` commissioner band. | Utility line on the gloss header. | Link row under the mast. |
| `lead` slot | Center column, above the numeral row. | Inside the gloss header, under the wordmark. | Under the h1, `class="lede"`. |
| `paged` + `fragments` | Numeral row `1 2 3 …`, each a link, plus a key line derived from the same loop. Label is `frame.pager`. | Tab strip. Labels and order are the catalog. | `p.jump` of the same labels. |
| active fragment | Center column, once. | White panel under the tabs, once. | Body, once. |
| `aside` slot | Right rail, inside the box headed "Fantasy links". | "Related" module under the panel. | Link list under the board. |

A shell that names `fragments/` or a content `.template`, links a second stylesheet, or drops the lead/aside mount fails at import. `era90.css` fails the import if it contains flex, grid, or `hub.css`. `modern.css` is required to `@import` `hub.css`, so today's sheet stays the modern base instead of a fork of its 2121 lines. Era sheets do not import it, because that sheet paints the dark page.

Invariants, checked rather than commented: theme ids, labels, nav orders, shell files, and stylesheets are one set; pane names and slot names are unique; a loader cannot overwrite a context key; an unknown theme renders modern; an unknown pane renders the first pane; a fragment template that mentions `frame.theme`, `theme=`, or `{% extends` fails the import; a second `<table` outside the macro fails the import. Theme on a content href is rejected by that last check. Shell links call `frame.carry` and `frame.pane_href`. A content link is a plain path. `carry_redirect` appends `?theme=` from the Referer when the query has none, so the next document keeps the theme without the fragment bytes changing. Direct visits with no theme are modern.

The public surface is `render_panes`, `Pane`, and `Slot`. Hidden behind it: theme parsing, pane fallback, running one loader, shell choice, href shape, nav-order selection, and the asset contract. Exposed on purpose: the fragment catalog and the two slot names, because placement is the shell's job and offering the block is the page's job. The call chain is the route, the catalog function, `render_panes`, then the shell. Query code is unchanged. The spike reads existing helpers (`standings`, `draft_page`, `_season_trades`, `_season_lineups`) and four small SELECTs (career top 50, matchups, stacks, week totals) so a theme switch does not call `players_index` or `season_page`.

This shape does not persist a cookie, render inactive panes, or give a theme its own columns. `is-active-leader` is reserved in the stylesheets for the PFR italic and is not emitted, because this data has no active-leader flag.

## Synthesis decision

Left for synthesis.

## Tradeoffs accepted

- We accept one column set per board in exchange for a fragment that is byte-identical across themes. The standings grid is `#`, Manager, W, L, T, PF, PA. Era 2010 density is padding, a header bar, and a full-width table, not the MFL extra columns (Pct, GB, Strk, averages). The rankings board is Rk, Player, Pos, Yrs, Starts, PF, Avg. Adding a modern-only column would be a second fragment, and the shells would be choosing content.
- We accept the tie glyph `-` on the modern rendering of this grid in exchange for keeping the glyph in one function. CSS cannot swap `-` and `0`. Reeve's dash is the shared policy.
- We accept that a content link opened with no Referer renders modern, in exchange for fragment bytes that contain no theme token. Shell chrome does not depend on Referer. Cookie persistence is A2.
- We accept empty panes in the catalog (a season with no draft still shows Draft) in exchange for one list that does not shrink per theme. Hiding a pane would be a second, data-dependent nav.
- We accept that drill-in routes (week, player, member, desk, marks) still use `page()` and `base.html`. The Referer redirect adds `?theme=` and those templates ignore it. The spike themes the three surfaces only.
- We accept today's dark stat surface on the modern shell, because `modern.css` imports `hub.css` unchanged. Era shells paint light grids (white cells, black text, blue links) on their own sheets. The Yahoo 2013 lesson is applied to the era themes here.
- We accept a real layout table in the 1998 shell, and color in the stylesheet, in exchange for one place to recolor. Inline `FONT`/`BGCOLOR` in the fragment would be unstyleable by the other two themes. The portal is a `border="0"` table at 178px, not a grid. The 2010 sheet may use flex; the 1998 sheet is refused at import if it does.

## Alternatives considered

Per-theme template directories (the C1 seed). Each era would own `season.html` and the stat markup, with a loader that falls back to a shared fragment. That hides almost nothing: the page author, or the next agent, copies the nearest board and the other two copies go stale. Interface depth is the opposite of this shape. The capability (era structure) is real, and the cost is three owners for every cell. This spike's import check, which rejects a second `<table>`, exists because that copy is the failure mode.

One DOM and a `data-theme` stylesheet (the C3 seed). The page author has the smallest surface, a single template, and the stylesheet is asked to become the shell. A numeral row and a tab strip are different elements and different hrefs; a left rail and a header band are different parents for the same lead and aside. CSS can restyle the shared board, and this candidate already does that. It cannot move the lead into the gloss header in one theme and into the center column in another unless both parents exist in the document. Shipping both and hiding one reintroduces the payload problem the grounding states for `display:none` tabs, and it gives the agent two structures to edit. The games list shows the boundary this shape does keep in CSS: the same `li.matchup` is a card in `era2010.css`, a ruled line in `era90.css`, and a hub row in `modern.css`.

Theme-only extra slots for a wider standings grid. The mount already lets a shell skip a slot the page offered. Using that to attach MFL columns in 2010 only would make the visible board depend on the theme. The standings fragment would stay identical and the page would not. That is a content fork with a cleaner diff. Rejected. Placement of `lead` and `aside` is the difference the slots are for, and every shell is required to mount both.

Encoding `?theme=` inside the fragment with a helper. Links would survive a stripped Referer, and the byte diff would be the token in every href. The mount check forbids `theme=` in fragments so that helper cannot grow there.

Child templates that `{% extends shells/{{ theme }}.html %}` and fill blocks. Same placement power, with the content template able to override a shell block. The mount includes make the shell the only caller. A content file that extends anything fails the import.

## Open questions and risks

- Should modern's stat grids stay on the dark `hub.css` surface until #107, or does the light-stat rule repaint `.stat` on the modern sheet in the same pass as the eras?
- If modern must show a zero tie as `0` while 1998 shows `-`, is that a shared-policy change (everyone gets one glyph) or a reason to leave this shape?
- Is Referer carry enough until A2, or should the theme move to a path prefix so relative fragment links stay byte-identical and survive a new tab?
- The import check covers shells, stylesheets, the macro, and fragment hygiene. Which page-family list should fail the build while a route is still on `page()`? This spike leaves every page template except the three routes above on `base.html`.
- Should a loader be allowed to drop an empty pane from the catalog for every theme at once? Doing it per theme would desync the numeral row and the tab strip.
- Where does the PFR italic (`is-active-leader`) get its flag, and which boards have an active leader worth marking?

## Next implementation step

Move the next page family onto `render_panes` and decide whether the shared standings grid grows extra columns before any era build forks a board.

## What the spike serves

`nu-choate-league serve --port 8122` from this worktree. Theme switches are ordinary links. Script is not required. `/seasons` with `?theme=` redirects to the latest scored year and keeps the theme; today that year is 2026. The clicks below use 2024, which has a full draft, trades, playoffs, and a champion (Will Flamm, bold) distinct from the high points-for (Nate White, gold).

Players, top 10 and the career top 50:

- http://localhost:8122/players?theme=era90
- http://localhost:8122/players?theme=era90&pane=career
- http://localhost:8122/players?theme=era2010
- http://localhost:8122/players?theme=era2010&pane=career
- http://localhost:8122/players?theme=modern
- http://localhost:8122/players?theme=modern&pane=career

Season panes. Replace `{pane}` with `standings`, `weeks`, `playoffs`, `moves`, `draft`, `lineups`, or `stacks`:

- http://localhost:8122/seasons/2024?theme=era90&pane=standings
- http://localhost:8122/seasons/2024?theme=era2010&pane=standings
- http://localhost:8122/seasons/2024?theme=modern&pane=standings
- http://localhost:8122/seasons/2024?theme=era90&pane=weeks
- http://localhost:8122/seasons/2024?theme=era2010&pane=weeks
- http://localhost:8122/seasons/2024?theme=modern&pane=weeks
- http://localhost:8122/seasons/2024?theme=era90&pane=playoffs
- http://localhost:8122/seasons/2024?theme=era2010&pane=playoffs
- http://localhost:8122/seasons/2024?theme=modern&pane=playoffs
- http://localhost:8122/seasons/2024?theme=era90&pane=moves
- http://localhost:8122/seasons/2024?theme=era2010&pane=moves
- http://localhost:8122/seasons/2024?theme=modern&pane=moves
- http://localhost:8122/seasons/2024?theme=era90&pane=draft
- http://localhost:8122/seasons/2024?theme=era2010&pane=draft
- http://localhost:8122/seasons/2024?theme=modern&pane=draft
- http://localhost:8122/seasons/2024?theme=era90&pane=lineups
- http://localhost:8122/seasons/2024?theme=era2010&pane=lineups
- http://localhost:8122/seasons/2024?theme=modern&pane=lineups
- http://localhost:8122/seasons/2024?theme=era90&pane=stacks
- http://localhost:8122/seasons/2024?theme=era2010&pane=stacks
- http://localhost:8122/seasons/2024?theme=modern&pane=stacks

Scoring macro, same `stat_table` as the standings grid and the rankings:

- http://localhost:8122/seasons/2024/scoring?theme=era90
- http://localhost:8122/seasons/2024/scoring?theme=era2010
- http://localhost:8122/seasons/2024/scoring?theme=modern

Latest season, 1998 shell: http://localhost:8122/seasons/2026?theme=era90&pane=standings

## Fragment byte-identity

Markers `<!--a1-fragment-->`, `<!--a1-slot:lead-->`, and `<!--a1-slot:aside-->` wrap the three mounts. A sweep of 33 documents (the URLs above, all HTTP 200, zero failures) compared each marker across `era90`, `era2010`, and `modern`. Zero mismatches. None of the extracted regions contain `theme=`.

SHA-256 prefixes of the active fragment, identical on all three themes:

| Surface | Prefix | UTF-8 bytes |
| --- | --- | --- |
| 2024 standings (the stat macro) | `D874BADD1700` | 3619 |
| 2024 weeks (the games list, `Results 1 … 14`) | `A5BA3AAABF46` | 17999 |
| 2024 playoffs | `587D0D7BF0EF` | 3478 |
| 2024 draft | `01B466897F65` | 38941 |
| 2024 scoring | `CE062CDDB803` | 3953 |
| Players top 10 | `E12FBE3BBD60` | 3416 |

The standings lead is 113 bytes and the aside is 252 bytes on every theme. Placement is the shell. On 1998 the lead sits in the center column and the aside sits in the Fantasy links box. On 2010 the lead sits in the gloss header and the aside sits under Related. On modern the lead sits under the h1 and the aside sits under the table.

Week and player anchors inside those fragments are plain paths (`/seasons/2024/week/1`, `/players/4984`). A request for `/players/4984` with Referer `http://localhost:8122/players?theme=era90` returns `302` to `/players/4984?theme=era90`. `?theme=costume` renders `modern.css`. `?pane=roster` renders the standings pane.
