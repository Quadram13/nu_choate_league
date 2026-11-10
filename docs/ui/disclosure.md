# Disclosure vocabulary

How the hub shows more than the first screen. The loading lane (D1, D2) and both era themes use this set. They do not add a second one.

Research source: `docs/ui/research-digest.md` §4. Contract: `docs/ui/a1/fragment-contract.md` §6. Existing client behavior on the hub is `js-fold`, `js-sort`, and the year/position filters in `hub.js`.

## The patterns

| Pattern | Use it when | Mechanism here |
| --- | --- | --- |
| Full load | The board is small enough to be the page: a standings table of about a dozen rows, a week slate, a portal home. | Render the fragment in the parent. The rows are in the HTML. |
| Numeral pagination | A log the reader scans in slices: the career ranking (518 rows), a long season log. Page size is a chosen number, 25 or 50, with a stable order. | `paginate` + `fragments/pager.html`. Each numeral is its own link. `?page=N`. |
| Fragment URL | A board has its own address. Script may swap it into the parent. The link works with script off. | `/boards/<name>` is the document. `/fragments/<name>` is the same template with no shell. |
| Separate URL | The subject changes: a player, a week, a season, the record book. | An ordinary route. Not a fragment of the index. |
| `js-fold` | A table that is already the right document still wants a shorter first view (today's top 20). The rows are in the HTML, so this saves nothing on the wire. | Existing `table.js-fold`. Leave it on those tables. |
| `js-sort` | Every row of that table is in the document, and a click may reorder them. | Existing `table.js-sort`. |
| Filters | The document already contains the rows a year or position chip would hide. | Existing `js-year-filter` / `js-pos-filter`. |
| Sticky header | A dense log stays readable while the body scrolls. It saves nothing on the wire. | Class `sticky-head`. |
| Era numeral row | Theme 1 (era90) week and page navigation. It is the pager: `Results 1 2 3 … 18`, each numeral a link. | The same `numeral_row` macro. |
| Era tabs and View All | Theme 2 (era2010) modules: a tab strip of real links, a short module (about 10 rows), View All as an `<a href>`. | A board URL or `?rows=all`. The structure is links, the same rule as the pager. |

Rules from the digest, binding here:

- Hidden rows are not a savings. A `<details>` around a full table, a `display:none` tab, and a load-more button all fail when the rows are in the first document.
- No virtual scroll. Find-in-page, print, and no-JS break, and row color stops matching the row.
- Numeral rows are the era page grammar and the pagination control. The current numeral is bold and is not a link.
- Sticky headers use an opaque background. A transparent header lets body rows show through.
- Script is an upgrade. Theme choice, pagination, View All, and every deferred section are `<a href>` first.

## Fragments

One template, one loader, two envelopes.

- `/fragments/<board>` returns the template's HTML. No `<html>`, no `base.html`.
- `/boards/<board>` returns that same string inside `page()` (`hub/templates/board.html`). The fragment bytes are a substring of the document.
- A parent may `{% include %}` the same template. Home does this for the standings and the week slate, and passes the context `queries.home_desk()` already loaded, so the desk does not run the loader again.

The template root carries the upgrade hook:

```html
<section class="board" data-fragment="/fragments/<board>" data-board="/boards/<board>">
```

`data-board` links inside that element are real document URLs. `hub.js` fetches `data-fragment` plus the link's query and swaps the section's contents. A manager link, a week link, a modified click, a missing `fetch`, or a failed response navigates normally. The address bar changes only when the page is already that board, so a parent page is not rewritten into a board URL.

Adding a board: a `Board` row in `src/nu_choate_league/web/fragments.py` (`name`, `template`, `title`, `nav`, `loader`) and a template under `hub/templates/fragments/`. The template is class-only: no `{% extends %}`, no `theme=` in an href, no inline style, no era tags. Both envelopes call `render_fragment`.

## Pagination

```python
from nu_choate_league.web.fragments import DEFAULT_PAGE_SIZE, paginate, requested_page

window = paginate(rows, page=requested_page(request), page_size=DEFAULT_PAGE_SIZE)
```

`DEFAULT_PAGE_SIZE` is 50. The digest names 25 or 50 for an index of about 520 careers. 50 is 11 addressable pages of this career list (518 rows: ten pages of 50 and a last page of 18). Each page is still a short printable table. There is no `page_size` query; the size belongs to the board. A standings table of about 12 rows stays one page, and the numeral row is omitted when `pages < 2`.

Pass `key` only when the input is not already ordered. `sorted` is stable, so a total key repeats. The career board does not pass a key: `players_index()` already orders by starter points, started VORP, then name, and that is the order `/players` renders. Sorting the float values again disagreed with the query once distinct numerics collapsed to the same float (17 positions near the bottom of the list).

```jinja
{% from "fragments/pager.html" import numeral_row %}
{{ numeral_row(pager.page, pager.pages, "/boards/<board>?page={n}") }}
```

Era week nav is the same macro:

```jinja
{{ numeral_row(week, 18, "/seasons/" ~ year ~ "/week/{n}", "Results") }}
```

`last <= 18` prints every numeral, so a season of weeks stays a full row. Longer rows keep the first, the last, and two numerals on each side of the current page. A gap of one missing numeral is filled. A wider gap is `…`, and that ellipsis is not a link. The current numeral is `<strong class="numeral" aria-current="page">`. Missing `page` is page 1. `page=0`, a non-integer, and a page past the end are 404.

A paginated board does not also carry `js-sort` or `js-fold`. A client sort would reorder one page. A fold would hide rows that pagination already removed from the document.

## Sticky headers

Append-only class in `hub.css`, marker `A3 loading`:

```css
.sticky-head thead th {
    position: sticky;
    top: 0;
    background-color: var(--sticky-head, var(--bg, #0f1419));
}
```

`#0f1419` is modern's `--bg`, `rgb(15, 20, 25)`, alpha 1. Era stylesheets set `--sticky-head` to their own opaque stat-surface color (a light grid in era90). A value with an alpha below 1 is a bug: body rows show through.

`position: sticky` sticks inside the nearest scrollport. `.standings-wrap` is `overflow-x: auto`, so a sticky header inside it sticks to that wrap. A log whose header should stick to the viewport is not wrapped in a horizontal scroller. Tables without `sticky-head` are outside this rule.

A table that is also `sticky-first` (first column sticks left) gets `top`, `left`, and `z-index: 3` on the corner cell from the combined selector, so the corner stays above both the header and the first column.

## What this ticket ships

Proving surface, on the modern `page()` path. A2's shells are not on this branch; the templates are what those shells will include.

| Board | Template | Document | Fragment |
| --- | --- | --- | --- |
| Home standings | `fragments/home_standings.html` | `/` (included) and `/boards/home-standings` | `/fragments/home-standings` |
| Home week slate | `fragments/home_slate.html` | `/` (included) and `/boards/home-slate` | `/fragments/home-slate` |
| Career rankings | `fragments/players_career.html` | `/boards/players-career?page=N` | `/fragments/players-career?page=N` |

Home still contains both boards (the include). The career board is the paginated log. `/players` is unchanged, so its fold-and-filter page stays byte-identical until D1 splits it. The career fragment is the read-only demonstration of pagination and of `sticky-head` on that log. It calls `players_index()` and renders one page of career rows.

`sticky-head` is also on the home standings table, which still sits in `.standings-wrap`.

## Verification

Port 8113, `nu-choate-league serve --port 8113`, parity baseline `parity-main`. Machine: 6 cores. The numbers below are from a quiet window (CPU load about 20%). An earlier home block while the CPU was near 60% was median 0.335s, range 0.299–0.427s; that spread is the busy machine, and it is not the number used here.

**Parity.** `scripts/ui/parity.ps1 -Mode check` over the 20 baseline routes: 19 PASS, including `/players` at 5,243,355 bytes. `/` FAIL, 34,444 → 34,873 bytes (+429).

**Home delta is a markup move.** The standings `<table>` matches the baseline once the token ` sticky-head` is removed. 48 person names, 12 score cells, and the six slate matchups match. The line diff is eight slots: a `data-fragment` section around each board, the class token, and a permalink (`Standings`, `Week slate`).

**Envelopes.** For home-standings, home-slate, career page 1, and career page 11, the fragment body is a substring of `/boards/<name>` for the same query. Fragment responses start at `<section` and contain no `<html>`. The board documents do. Unknown board, `page=abc`, `page=0`, and `page=12` return 404.

**Pagination.** 518 career rows, page counts 50 × 10 then 18. The sets are disjoint and their union is the 518. Page 1, page 2, and page 11 cell text matches the `/players` career table at those slices, in that order. Page 2's body is identical across two requests. The numeral row is `1 2 3 4 5 6 7 8 9 10 11`; the current page is a `<strong>`, and the others are `<a href="/boards/players-career?page=N">`. Those links are the no-JS path.

**Sticky header, computed in headless Chrome** against `hub.css`:

| Cell | position | top | background |
| --- | --- | --- | --- |
| `th` in `.sticky-head` | sticky | 0px | `rgb(15, 20, 25)` |
| `th` in a plain table | static | auto | `rgba(0, 0, 0, 0)` |
| corner `th` of `.sticky-head.sticky-first` | sticky | 0px (left 0px, z-index 3) | `rgb(15, 20, 25)` |

The plain cell stays static and transparent, and `/players` HTML is unchanged, so the appended rule does not move tables that lack the class.

**Inline upgrade, same Chrome run.** A page at `/static/a3-probe.html` (deleted after the run; not part of the commit) clicked the standings permalink. The server logged `GET /fragments/home-standings`. The section then held the 12 standings rows, the placeholder was gone, and the path stayed `/static/a3-probe.html`.

**Perf.** `Invoke-WebRequest` wall clock, one uncounted warmup, then 7. Zero non-200s. Each body contained its marker (home standings id, `Josh Allen` on career page 1, page-2 current numeral, and page 2 did not contain `Josh Allen`).

| URL | bytes | median | range |
| --- | --- | --- | --- |
| `/` | 34,873 | 0.289s | 0.269–0.324s |
| `/fragments/home-standings` | 10,625 | 0.076s | 0.073–0.121s |
| `/fragments/home-slate` | 7,785 | 0.082s | 0.076–0.085s |
| `/fragments/players-career` | 68,318 | 0.186s | 0.164–0.233s |
| `/fragments/players-career?page=2` | 68,513 | 0.184s | 0.164–0.216s |
| `/boards/home-standings` | 12,011 | 0.077s | 0.070–0.085s |

Home matches the 0.29s baseline: the gap is about a millisecond, inside the run range. The limiter is `home_desk` (0.230s median on a held connection, 5 runs, range 0.215–0.372s). The includes add no query. `standings()` alone is 0.031s; the slate queries are 0.028s. Career page 1 and page 2 differ by 0.002s, inside the noise, so the 50 rendered rows are not the limiter. `players_index()` is 0.128s median (range 0.126–0.150s) and still builds the season and wire boards the fragment does not render. The career fragment is 68KB against the 5,243,355-byte `/players` document.

## Open for the orchestrator

- `stat_table` does not exist on this branch (A2). The extracted standings table and the career demonstration table each contain a `<table>`. The boot gate's single-table rule will fail until those render through that macro.
- Era shells are A2's files and are not in this worktree. `--sticky-head` and `numeral_row` are the hooks. This branch demonstrates them on modern only.
- `/players` and `season.html` are not linked to the new boards. D1 and D2 own those templates. The career board is reachable at `/boards/players-career` without editing `players.html`.
- A career-only query would drop the work `players_index()` does for boards this fragment discards. That is a `queries.py` change, left alone here.
- `hub/templates/board.html` is the `page()` envelope. It extends `base.html`, so it lives outside `fragments/` (fragments must not extend a shell).
