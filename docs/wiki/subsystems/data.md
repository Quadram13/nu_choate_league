# Data

As of `@74d6fb0` (2026-11-07):

- Pipeline: dumpers (`espn-dumper`, `sleeper-dumper`) → gitignored `data/` JSON → `uv run nu-choate-league load` → Postgres fact tables (`sql/facts.sql`) → analysis views (`sql/analysis/`, applied in numeric order: 10 games, 20 standings, 30 records, 40 luck, 50 draft/moves, 60 players, 65 management, 70 universes, 80 assets, 90 waivers, 95 marks — the last five are materialized and refreshed by `load`).
- Docker Postgres 17 container `nu-choate-postgres` on `localhost:5433` (host port from `compose.yaml`; credentials in `.env` / `DATABASE_URL`). DB name `nu_choate`.
- On 2026-11-07 the DB held ~5 seasons (ESPN 2022–23, Sleeper 2024–26), ~1200 players, 558 matchups, 1762 transactions, 24883 player_week_scores.
- `maps/` holds identity: `managers.yaml`, `seasons.yaml` (FAAB starts 2026), D/ST mapping. `inspect-managers` must pass before `load`.
- Read-only introspection for agents: `docker exec nu-choate-postgres psql -U <user> -d nu_choate -c "..."`. Agents never run `load` and never write to the DB unless a ticket explicitly says so.
- CLI reading of the same views: `uv run nu-choate-league query <name>` (career, h2h, record-weeks, draft, moves, universes, luck, trades, draft-value, waivers, vorp, management).

## Players catalog rule (agents)

README ("Dumping" section) is the human source of truth; this note is the agent-facing pointer, added 2026-11-07 after Marcus's sanction.

- `data/sleeper/players/nfl.json` (~12k players, ~15 MB) is **required for ingest** — `load` fails fast with `FileNotFoundError` without it.
- Default cadence: at most once per day. `sleeper-dumper --fetch-players` downloads it **only if missing** (the guard), per Sleeper API etiquette.
- Force-refresh with `--refresh-players` when dumps are weeks/months stale, when player ids or roster metadata look wrong, or whenever the catalog might have been lost — do not skip the refresh just because `nfl.json` exists. On 2026-11-07 a catalog from 2026-09-11 was force-refreshed on Marcus's instruction before the wave's full `load`.
- Refresh ordering: players refresh and season dumps must finish **before** `load` starts, and never run a dumper concurrently with `load` (the dumper rewrites season directories in place).

## Dump/load coordination for agents

- `data/` is gitignored: fresh worktrees lack it. Bridging with a directory junction works for `load` runs but is dangerous at cleanup time — see [the worktree-remove wipe](../problems/data-junction-worktree-remove.md). As of 2026-11-07 the rule is: junctions only in the long-lived integration worktree, and always `cmd /c rmdir` the junction before any `git worktree remove`.
- One `load` at a time, announced (the hub serves from the same views `load` rebuilds). Per-season runs use `load --year <yyyy>`; a full run needs both platforms' dumps present: `data/espn/{2022,2023}` and `data/sleeper/{2024,2025,2026}` plus `data/sleeper/players/nfl.json`.
