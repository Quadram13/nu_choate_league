# Windows shell gotchas (parallel agent work)

Learned 2026-11-07 while running six agents plus integrator shells on WIN11PC-Choate.

## Temp ps-script lock races

The Cursor shell wrapper writes each command to a `Temp\ps-script-*.ps1` file. With many parallel sessions, creation of that file intermittently fails ("being used by another process" / "access denied"). Retrying sometimes works; the reliable pattern is to write long commands to a `.ps1` file with the Write tool and run `powershell -NoProfile -ExecutionPolicy Bypass -File <path>`. As of 2026-11-07 all maintenance scripts on this machine use that pattern.

## `$home` is a reserved automatic variable

On 2026-11-07 a cleanup script did `$home = '<worktree path>'`. The assignment failed (`HOME` is read-only), leaving `$home` pointing at the user profile, and the following `Remove-Item $home -Recurse -Force` ran against `C:\Users\marcusdu`. **No damage** — the profile root cannot be deleted while in use, and a full sweep (repos, `.cursor`, `.env`, data dumps, agent store, configs) verified everything intact. Rules since:

- `Set-StrictMode -Version Latest` at the top of every maintenance script (makes the failed assignment fatal before the dangerous line).
- Never name script variables `$home`, `$pwd`, `$host`, `$PID` or other automatic names; use `$wtHome` style.

## Start-Process orphans

`Start-Process uv ... -PassThru` then `Stop-Process -Id $p.Id` kills the `uv` shim but not its python (uvicorn) child. On 2026-11-07 two orphaned hub serves survived smoke tests this way, holding file locks on worktrees. Kill the tree instead: `taskkill /PID $p.Id /T /F`, or find the listener by port and stop that PID.
