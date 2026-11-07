# Data

As of `@74d6fb0` (2026-11-07):

- Pipeline: dumpers (`espn-dumper`, `sleeper-dumper`) → gitignored `data/` JSON → `uv run nu-choate-league load` → Postgres fact tables (`sql/facts.sql`) → analysis views (`sql/analysis/`, applied in numeric order: 10 games, 20 standings, 30 records, 40 luck, 50 draft/moves, 60 players, 65 management, 70 universes, 80 assets, 90 waivers, 95 marks — the last five are materialized and refreshed by `load`).
- Docker Postgres 17 container `nu-choate-postgres` on `localhost:5433` (host port from `compose.yaml`; credentials in `.env` / `DATABASE_URL`). DB name `nu_choate`.
- On 2026-11-07 the DB held ~5 seasons (ESPN 2022–23, Sleeper 2024–26), ~1200 players, 558 matchups, 1762 transactions, 24883 player_week_scores.
- `maps/` holds identity: `managers.yaml`, `seasons.yaml` (FAAB starts 2026), D/ST mapping. `inspect-managers` must pass before `load`.
- Read-only introspection for agents: `docker exec nu-choate-postgres psql -U <user> -d nu_choate -c "..."`. Agents never run `load` and never write to the DB unless a ticket explicitly says so.
- CLI reading of the same views: `uv run nu-choate-league query <name>` (career, h2h, record-weeks, draft, moves, universes, luck, trades, draft-value, waivers, vorp, management).
