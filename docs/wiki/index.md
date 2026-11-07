# Nu Choate League wiki

Historical record for agents and humans working on this repo. Every claim is dated; code claims cite the commit they were true at. Pages describe what was decided and learned, never what "is" — check the code for that.

## Decisions

- [2026-11-07 Wiki location](decisions/2026-11-07-wiki-location.md) — docs live in-repo under `docs/`; pattern ported selectively from hanlun_tools.
- [2026-11-07 Orchestration](decisions/2026-11-07-orchestration.md) — Kimi K3 chief-of-staff + grok-4.7-high-fast implementers; worktree-per-ticket; Refs-only on parent issues.

## Subsystems

- [Hub](subsystems/hub.md) — FastAPI/Jinja2 local web app: serve workflow, layers, known quirks.
- [Data](subsystems/data.md) — dumps → fact tables → analysis views → materialized snapshots; the Docker Postgres.

## Problems

- [WatchFiles hang](problems/watchfiles-hang.md) — hub auto-reload hangs after `queries.py` edits (tracked as issue #11).
