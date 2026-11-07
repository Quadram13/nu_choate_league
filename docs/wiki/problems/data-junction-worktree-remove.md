# `git worktree remove` through a data junction deletes the real dumps

Incident of 2026-11-07 on WIN11PC-Choate, during the data-utilization wave.

## What happened

Ticket #22 needed `load` to run from a fresh worktree, but `data/` is gitignored so worktrees do not have it. The implementer bridged it with a directory junction: `<worktree>\data` → `<main checkout>\data`. When the ticket landed, the integrator ran `git worktree remove --force <worktree>` — and git's recursive delete **followed the junction and deleted the target's contents**. `data/espn/` (2022–2023 raw dumps) was lost outright; `data/sleeper/` was emptied and only reappeared because a sanctioned dump refresh rewrote it minutes later. `data/sleeper/players/nfl.json` (the NFL player catalog) was also gone, which failed the next full `load` fast with `FileNotFoundError` — the failure that surfaced the wipe.

Timeline: Marcus verified `data/espn` + `data/sleeper` present (files of 2026-09-11) at ~15:12; worktree removal ~15:14; Sleeper re-dump 15:15 (seasons only, no `--fetch-players`, so the catalog stayed missing); full `load` 15:18 failed on `players/nfl.json`; catalog force-refreshed 15:19; second full `load` then failed on missing `data/espn/2022/league.json`, exposing the rest of the wipe. Recovery: `uv run espn-dumper` re-dumped both ESPN seasons from the API (cookies in `.env`).

No database damage: the wipe only removed raw JSON on disk; Postgres already held every ingested fact.

## Rules since

- **Never `git worktree remove` a worktree that contains a junction.** Remove the junction first with `cmd /c rmdir <junction>` (rmdir on a junction removes the reparse point, not the target), verify `Test-Path <junction>` is false, then remove the worktree.
- Prefer junctions only in long-lived worktrees (the integration worktree), not in per-ticket throwaway worktrees. A per-ticket agent that needs `data/` should say so in its report so the integrator runs the `load` step itself.
- PowerShell's own `Remove-Item -Recurse` on a junction has the same target-deleting footgun on Windows PowerShell 5.1 — `cmd /c rmdir` is the only sanctioned way to drop a junction.
- After any worktree cleanup near `data/`, sanity-check the real dumps: `data/espn/{2022,2023}/league.json`, `data/sleeper/{2024,2025,2026}/manifest.json`, `data/sleeper/players/nfl.json` all present.

## Verification pattern

Cheap post-cleanup check (2026-11-07, used after the incident):

```powershell
foreach ($p in 'data\espn\2022\league.json','data\espn\2023\league.json',
               'data\sleeper\2024\manifest.json','data\sleeper\2025\manifest.json',
               'data\sleeper\2026\manifest.json','data\sleeper\players\nfl.json') {
  "$p : $(Test-Path $p)"
}
```
