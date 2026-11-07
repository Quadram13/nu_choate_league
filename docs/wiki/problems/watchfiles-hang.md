# WatchFiles hang after queries.py edits

Tracked as issue [#11](https://github.com/Quadram13/nu_choate_league/issues/11) (parent #8).

- First noted on the `feat/ui-planning` branch around 2026-11-06 (per issue #8 body): hub auto-reload via WatchFiles hangs after edits to `src/nu_choate_league/web/queries.py`, forcing a full process restart during UI work.
- As of `@7dcb214`, `serve.py` runs uvicorn with `reload=True` and `reload_dirs=[src, hub]`; the app reuses one DB connection (perf commit `931f61c`).
- Unproven hypotheses at filing: (a) the old uvicorn worker never exits because an open psycopg connection blocks shutdown on Windows; (b) watchfiles scanning cost in `hub/` (fonts/static); (c) large `queries.py` re-import cost.
- Workaround until fixed: `serve --no-reload` and restart manually per edit.
- 2026-11-07: implementer dispatched on `cursor/issue-11-watchfiles-bf5b`. Update this page with the confirmed root cause when it lands.
