# IA inventory — current section maps for B1 (#96) and B2 (#97)

Groundwork for the IA lane, captured from the wave branch at 68324dd so implementers start from facts. B2's acceptance bar is "zero boards dropped, zero invented" — the chapter checklist below is the drop-list. B1's is the current player-page anatomy to restructure.

## Player page (`player.html`, 514 lines) — current anatomy vs PFR target (#96 B1)

Current (single URL, top to bottom):

| # | Block | Lines | PFR-anatomy target |
|---|---|---|---|
| 0 | Header/identity block (`{% block body %}` start) | 15–106 | Identity header in PFR order (name, position, hand, h/w, team, born, college, career value, draft; no jersey #), then season-vs-career summary strip incl. FantPt-like column |
| 1 | `<h2 id="own">` Ownership | 107–149 | Stays on profile (roster history is PFR "Teams" grammar) |
| 2 | `<h2 id="seasons">` By season | 150–205 | The summary strip's season table; stays on profile |
| 3 | `<h2 id="weeks">` Weeks | 206–274 | PFR: CURRENT season's game log on profile; career log on its own URL with year list |
| 4 | box-score macros | 275–381 | Shared by weeks/career-log renders |
| 5 | `<h2 id="splits">` Splits (vs opponent, home/away) | 382–472 | Own URL; one repeating table with group-name rows (PFR), more groups can ride the landed data |
| 6 | `<h2 id="counting">` Counting (career, by season) | 473–514 | Stays on profile (PFR keeps counting on the fantasy tab — decide placement, justify) |

Also required by the ticket: leader marks as bold/gold/italic text + footnote (no cell fills); Inactive weeks as the word, not zero-rows; 1-game season = same table one row; cross-links (player ↔ season/week/member); theme-contract clean markup.

## Record book (`records.html`, 2,019 lines) — 40 H2 sections, chapter map (#97 B2)

Proposed chapter grouping (implementer refines; nothing dropped, nothing invented). "Boards" counts include H3 sub-boards.

| Chapter | H2 sections (ids) | Approx boards |
|---|---|---|
| (index teasers) | `holders` | 1 |
| awards | `awards` | 1 |
| season | `season` | 8 |
| clutch | `clutch` (consistency ×2, pythagorean ×2, one-score ×2, blowout-record ×2) | 8 |
| playoff | `playoff` | 3 |
| chairs | `chairs` | 3 |
| environment | `median`, `platform`, `eras` (+1), `high`, `low`, `league-high` (×4), `environment` (×2) | ~13 |
| games | `blowouts`, `closest` | 2 |
| trades | `trades`, `traded`, `journeymen`, `partners` (+pair detail) | ~5 |
| rings | `rings` | 1 |
| draft | `draft` (×3), `draft-capital` | 4 |
| roster | `waiver-roi` (×2), `roster-shape` (×2) | 4 |
| wire | `wire` (×3 incl. wire-left ×3) | ~6 |
| lineups | `lineups` (×2), `lineup-counting` (boards) | ~3 |
| counting | `counting` (boards), `finishes` (boards), `counting-season` (boards), `counting-career` (boards) | many (board loops) |
| coach | `coach` | 1 |
| streaks | `wins`, `losses`, `current`, `drought` | 4 |
| stacks | `stacks` (×5) | 5 |
| playoff-history | `playoff-history` (per-season loop) | 1 loop |
| universe-replay | `universe-replay` (per-season loop) | 1 loop |

Legacy anchors to keep resolving: every `id` above (`/records#season` etc.), plus `/luck` → currently 302 to `/seasons/2026#luck` (leave that redirect alone — it does not point at records).

## Cross-link opportunities the B3 audit should catch

- `playoff-history` and `universe-replay` already link into `/seasons/{year}#…` — the pattern to extend.
- Records boards name managers, seasons, players constantly; B3's entity-link discipline applies here first.
- `holders` ("Who owns the book") is the natural index-page content for the chapterized records home.
