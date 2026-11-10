# C1b 1990s theme completion (#103)

Branch `cursor/ui-c1b-bf5b`. This finishes the era90 skin on the page families C1a left on the legacy template: players, record chapters, members, versus, and the trade and wire documents those families link to.

Modern documents are unchanged. `page()` and `board_document` take the new path only when `resolve_theme` is `era90`. A request with no theme cookie and no `?theme=` is the same bytes as the wave tip.

## What the pages are

| Route | Era document |
|---|---|
| `/players` | `era90/players.html`. Ten rows of each published board, or the whole list when it is shorter. A numeral row under each board. |
| `/boards/players-*` | `era90/ranking.html`. One page of that board. |
| `/players/{id}`, `/log`, `/splits` | The modern body, mounted. Year numerals sit above it. |
| `/records` | The C1a link farm, plus one glossary sentence. |
| `/records/{chapter}` | The modern chapter body, mounted, plus the same glossary. |
| `/members` | `era90/members.html`. One career line. |
| `/members/{id}` | The modern member body, mounted. |
| `/versus` | `era90/versus.html`. W-L-T from the row manager's side. No heat fill. |
| `/versus/{a}/{b}` | The modern pair body, mounted. |
| `/seasons/{year}/trades/{id}`, `/wire/{id}` | The modern body, mounted, so those links stay inside the theme. |

The modern template is not copied. `{% extends "base.html" %}` is answered by an empty shell, so the body block is the same source the legacy page renders. The week-table macro's click handler is removed from that mount. It only renumbers rows after a sort, and era pages do not load that sort. The rows stay in the HTML.

## Page size and sort

The page size is `fragments.DEFAULT_PAGE_SIZE`, 50. Digest §4 and the D1 comment already justify 50: one printed page of the career list, not 25. The index does not repeat that page. The portal rail says Top 10, so the index shows ten (`ERA90_TOP`). A shorter teaser, such as the wire list of five, shows every row it has.

The order is the order `players_summary` and `players_board_payload` already publish. Nothing is sorted again.

| Board | Order |
|---|---|
| Career rankings, and `/boards/players-career` | Starter points, then VORP, then name |
| Season rankings | Newest year, then points on starts |
| Wire season and wire career | FA VORP |
| Never rostered | Points while unowned |
| Counting career | Rush yards plus receiving yards plus pass yards, then name |
| Counting season | Newest year, then that yard sum |

Rank on a full page is `(page - 1) * 50 + row`. Page 2 starts at 51. The numeral for the current page is `<strong>`, not a link. An out-of-range page is the existing 404 from `paginate`.

The index numerals all link, including page 1, because the index is not itself page 1. Each numeral is its own `<a>`. The href carries `theme=era90`, so the first click does not depend on the cookie. A later click can omit the query: the middleware sets the `theme` cookie when the request has `?theme=`.

The small grid keeps the person and the sort keys (year when the order uses one, PF and VORP, or the yard sum, or FA VORP). The other columns stay on the player page and on Modern. The theme switcher is the way to that full table.

A rankings page is the shell plus fifty rows. On this database the career page is about 17 KB. The old `/players` document in the main baseline is 5,500,422 bytes.

## Leader marks

C1a already paints `.is-leader` and `.is-record` as bold type, and `.is-active-leader` as italic. No cell fill. This slice uses those classes and does not add a color.

- Rank 1 of a player board is `.is-leader`. Page 1 also prints `Leader` and the name in red, which is the cheer C1a already uses.
- The member with the most titles is `.is-leader` on the name. The member with the most points for is `.is-record` on PF.
- Record chapters keep the modern body's own marks. The glossary under the chapter says a leader is bold and a record is bold type, not a filled cell.

The versus grid does not copy `style="--win"`. A cell is the W-L-T figure. A number after the dot is how many times that pair has traded.

## Identity and year numerals

Player, log, and splits print one line in the era order: last name, first name, team, position. `Patrick Mahomes` with team `KC` and position `QB` is `Mahomes, Patrick KC QB`. A defense, or a name with no space, is left as stored.

The year numerals are the player's `log_years`. On the profile they link to `/players/{id}/log?year=N`. On the log and the splits, the selected year is `<strong>` and the rest are links, including `All`.

## What stayed put

`queries.py`, `hub.css`, `hub.js`, `base.html`, the fragment templates, and the era2010 files are untouched. `BOARDS` did not gain a player board. The seven pre-contract tables inside `hub/templates/players/` are still the modern body. They render inside the era shell. They were not rewritten.
