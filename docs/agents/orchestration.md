# Agent orchestration in this repo

Conventions for AI agents doing ticketed work here. Established 2026-11-07; the decision record is [../wiki/decisions/2026-11-07-orchestration.md](../wiki/decisions/2026-11-07-orchestration.md).

## Roles and models

| Role | Model |
| --- | --- |
| Chief-of-staff (coordinates, files tickets, merges) | Kimi K3 max |
| Implementers, explorers, reviewers (Task sub-agents) | `grok-4.7-high-fast` |

Do not probe DeepSeek. Do not use Claude slugs. Per-role overrides live in `~/.cursor/rules/pstack-models.mdc`.

## Working agreements

1. **Tickets first.** Work happens against GitHub issues on `Quadram13/nu_choate_league`. Umbrellas (e.g. #8) carry sub-issues; children reference parents with `Refs #N`, never `Closes`.
2. **Worktree per ticket.** `git worktree add <sibling-path> -b cursor/<slug>-bf5b <integration-branch>`. Never edit the main checkout; it stays on `main`. Copy `.env` into the worktree before serving (it is gitignored and does not follow checkouts).
3. **Integration branch.** Ticket branches merge back into the wave's integration branch (e.g. `feat/ui-planning`); one PR per wave, opened as draft until the wave's verification lands.
4. **Verification.** No test suite exists. Smoke = `uv run nu-choate-league serve --port <assigned>` + HTTP/browser checks of affected pages + `query` CLI spot checks. Visual tickets need a click-through checklist in the PR.
5. **Database.** Docker Postgres on `localhost:5433` is real data. Agents run read-only SELECTs. Never run `load` unless the ticket says so; never commit `.env` or `data/`.
6. **Parallel agents** each get an assigned serve port to avoid collisions.
7. **Sub-agent communication is by pointer:** issue numbers, commit SHAs, wiki pages — not pasted context.
