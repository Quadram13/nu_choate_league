# WatchFiles hang after queries.py edits

Tracked as issue [#11](https://github.com/Quadram13/nu_choate_league/issues/11) (parent #8). **Resolved 2026-11-07** on `feat/ui-planning` (`a5a20ad`, fix commit `dcaa64d`); rides to main with PR #13.

- First noted on the `feat/ui-planning` branch around 2026-11-06: hub auto-reload via WatchFiles hung after edits to `src/nu_choate_league/web/queries.py`, forcing a full process restart during UI work.
- **Root cause (confirmed 2026-11-07):** uvicorn 0.52.4 on Windows reloads by sending `CTRL_C_EVENT` to the worker and then `process.join()`. The worker never exits on that event, so the reloader blocked in `join()` after logging `Reloading...` and the old process kept serving. Ruled out with evidence: an open psycopg connection (`pg_stat_activity` was clean at shutdown) and watch scope (a minimal no-database FastAPI app hung identically).
- **Fix:** as of `dcaa64d`, `serve.py` (Windows + reload only) replaces `BaseReload.restart` with `Process.terminate()` + `join()` + respawn via `get_subprocess`; the reloader keeps the listening socket. Unix behavior unchanged. The monkeypatch can come out if a future uvicorn stops using `CTRL_C_EVENT` for Windows reload.
- **Verification:** implementer ran three consecutive clean reloads after `queries.py` edits plus `query career` exit 0; integrator reproduced one clean reload post-merge (`Started server process` + 200 on `/`).
- Superseded hypotheses (2026-11-07 filing): DB-connection-on-shutdown, `hub/` watch scope, large-file re-import cost. None were the cause.
