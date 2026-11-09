# Nu Choate League wiki

Historical record for agents and humans working on this repo. Every claim is dated; code claims cite the commit they were true at. Pages describe what was decided and learned, never what "is" — check the code for that.

## Decisions

- [2026-11-07 Wiki location](decisions/2026-11-07-wiki-location.md) — docs live in-repo under `docs/`; pattern ported selectively from hanlun_tools.
- [2026-11-07 Orchestration](decisions/2026-11-07-orchestration.md) — Kimi K3 chief-of-staff + grok-4.7-xhigh-fast implementers (retargeted 2026-11-09); worktree-per-ticket; Refs-only on parent issues.
- [2026-11-07 Raw dumps first-class](decisions/2026-11-07-raw-dumps-first-class.md) — `data/` dump fields that never landed get ingest rework, then surfaces; one `load` at a time.

## Subsystems

- [Hub](subsystems/hub.md) — FastAPI/Jinja2 local web app: serve workflow, layers, known quirks.
- [Data](subsystems/data.md) — dumps → fact tables → analysis views → materialized snapshots; the Docker Postgres.

## Problems

- [WatchFiles hang](problems/watchfiles-hang.md) — hub auto-reload hangs after `queries.py` edits (tracked as issue #11).
- [Windows shell gotchas](problems/windows-shell-gotchas.md) — temp ps-script lock races, the `$home` reserved-variable near-miss, Start-Process orphans.
- [Data junction worktree-remove](problems/data-junction-worktree-remove.md) — `git worktree remove` followed a `data/` junction and deleted the real dumps; junction handling rules.
