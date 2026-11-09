# UI/IA wave plan (#45 board, implement go 2026-11-09)

Framing per the figure-it-out skill. The board: 13 sub-issues of #45 (#95–#107) with native blocked-by edges. This file is the phase list the human reviews.

## Definition of done (falsifiable predicate)

All of the following hold at wave end:

1. All 13 sub-issues closed with evidence comments; the "do not start" line removed from each as it was picked up.
2. One draft wave PR (branch `cursor/ui-wave-45-bf5b` → `main`) contains the whole wave: three selectable themes (modern / 1990s / ~2010) with persisted no-JS-safe switching, the IA restructure (player pages, records chapters, hub cross-linking), and the loading splits (/players PFR-style split, hub-wide deferred boards).
3. Every route verified on the real hub (Docker Postgres :5433, serve from the wave worktree on :8100), not self-report.
4. Content parity: no landed stat removed. Where a ticket restructures a page, the ticket's evidence shows old-vs-new content audits (`scripts/ui/parity.ps1` where byte-parity is required, explicit content checklists where layout changes by design).
5. Perf guardrails: no route regresses beyond noise vs the 68324dd baselines (perf wave: / 0.29s, /players 0.90s, /records 1.81s, /seasons/2025 0.75s, scoring 0.16s; median/range, n≥5, `scripts/perf/baseline.ps1`), and the loading tickets post before→after payload tables.
6. Decision trail `.audit/uiwave.tsv` committed in the PR.
7. PR stays DRAFT. No merge to main without a separate Marcus go.

## Scope

13 tickets across 4 lanes (foundation, IA, themes, loading). Hot blast-radius surfaces: `hub/templates/base.html` (every page extends it), the 7 `*_macros.html` libraries (every stat table), `page()` in `src/nu_choate_league/web/app.py` (every route renders through it), `hub/static/hub.css` (2121 lines, single stylesheet), `hub/static/hub.js` (509 lines, dependency-free). 20 GET routes, 27 templates, no build step.

## Rigor

- HIGH: #95 A1 (one-way-door architecture) — architect skill, arena of 3 candidates, cross-judge, synthesis doc, Marcus checkpoint before downstream lanes start.
- HIGH: #105 D1 / #106 D2 (loading + perf guardrails) — benchmark discipline: before→after bytes and seconds, median/range, named limiters.
- MEDIUM: #98 A2, #99 A3 (infra, sketch contract from A1), #96 B1 / #97 B2 / #102 B3 (IA, content-parity gates).
- STANDARD: C-lane era skins (#100/#103/#101/#104/#107) — screenshot evidence + parity gates, experience-first polish.

## Phases (respect blocked-by)

0. Setup: wave worktree, serve :8100, parity baseline vs main — DONE (see decisions.tsv).
1. #95 A1 spike: arena → decision doc + fragment contract + clickable throwaway prototypes. Checkpoint to Marcus.
2. #98 A2 + #99 A3 + #96 B1 + #97 B2 (parallel after A1).
3. #102 B3 (needs B1+B2), #100 C1a + #101 C2a (need A2), #105 D1 (needs A3).
4. #103 C1b + #104 C2b (need core + A3), #106 D2 (needs A3 + B2).
5. #107 C3 (needs B3 + A2), final guardrail sweep, wave ready-for-review report.

## Verification gates (per ticket, in addition to its acceptance criteria)

- Parity: `scripts/ui/parity.ps1 -Mode check` against the captured main baseline until a ticket intentionally changes a page; intentional changes get before/after evidence in the ticket.
- Perf: `scripts/perf/baseline.ps1` on the five perf-wave pages after any ticket touching shared templates/macros/queries.
- No-JS sweep on any ticket adding interaction.
- Each unit lands green before the next starts (sequence-verifiable-units); one wave branch, per-ticket feature branches merged in after verification.

## Hard holds

No ESPN load. #71–#73 parked. #8/#27/#29 not this wave. No merge to main. Draft PR only; undraft when Marcus reviews.
