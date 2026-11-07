# Hub

Local FastAPI + Jinja2 app serving the league yearbook. As of `@74d6fb0` (main) and `@7dcb214` (feat/ui-planning tip, 2026-11-07):

- Entry: `uv run nu-choate-league serve --port <p>` → `src/nu_choate_league/web/serve.py` runs uvicorn with `reload_dirs=[src, hub]`. `--no-reload` disables.
- Layers: routes in `web/app.py` → SQL in `web/queries.py` → templates in `hub/templates/` → static in `hub/static/`. Templates/macros: plaque, wire, trade, week_card.
- Routes include `/`, `/seasons/{y}`, `/seasons/{y}/week/{w}`, matchup/trade/wire detail, `/moves`, `/draft`, `/marks`, `/desk`, `/scoring`, `/members`, `/versus`, `/records`, `/players`. `/luck` redirects to latest-season luck plaques.
- All hub queries are read-only SELECTs over the analysis views (see [Data](data.md)). Stop `serve` before running `load`.

## Gotchas (learned 2026-11-07)

- **`.env` is per-worktree.** `git worktree add` does not bring `.env` (gitignored), so `serve` in a fresh worktree fails with `Missing DATABASE_URL`. Copy `.env` from the main checkout into the worktree first. Implementer agents must do this on every new worktree.
- First `uv run` in a worktree builds a fresh `.venv` (uv cache makes it fast).
- Auto-reload can hang after `queries.py` edits — see [WatchFiles hang](../problems/watchfiles-hang.md). Assign each parallel agent its own `--port`.
