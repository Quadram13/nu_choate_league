# A2 theme infrastructure (#98)

Branch `cursor/ui-a2-themes-bf5b`. Served on port 8112. Database was read only.

## Files

- `src/nu_choate_league/web/themes.py` — registry (`modern`, `era90`, `era2010`), resolution (`?theme=` then cookie then modern; unknown becomes modern), `render_panes`, `Pane` / `Slot` / frozen `Frame`, cookie persistence, board registry, boot gate.
- `hub/templates/shells/era90.html`, `era2010.html`, `_fragment.html`, `_slot.html`, `_week_nav.html`.
- `hub/templates/fragments/stat_table.html` (the only fragment `<table>`), `board.html`, `games.html`, `season_lead.html`, `season_aside.html`.
- `hub/static/themes/era90.css`, `era2010.css`.
- `hub/templates/base.html` — one switcher row, the only edit.
- `src/nu_choate_league/web/app.py` — `themes.install` before routes, cookie middleware, `theme` on `page()`, era dispatch at the start of the season route.

Modern is the legacy `page()` path. There is no modern shell and no `themes/modern.css`. The gate rejects both.

## Parity

`scripts/ui/parity.ps1` was not modified. It reports FAIL on all 20 routes. The bodies do not.

Stripping this one line from each live 200 body makes the bytes equal the baseline file in `parity-main`. The line is 194 bytes including its leading newline:

```html
        <nav class="theme-switch" aria-label="Theme"><a href="?theme=modern" class="is-on" aria-current="page">Modern</a> <a href="?theme=era90">1998</a> <a href="?theme=era2010">2010</a></nav>
```

Switcher-delta routes (status stayed 200, delta +194, nothing else): `/`, `/seasons/2025`, `/seasons/2025/trades/1269432330255081472`, `/seasons/2025/moves`, `/seasons/2025/draft`, `/seasons/2025/wire/1266620574830952448`, `/seasons/2025/week/1`, `/seasons/2025/week/1/2025-w01-1`, `/seasons/2025/marks`, `/seasons/2025/desk`, `/seasons/2025/scoring`, `/versus`, `/versus/alex-coletti/andrew-howey`, `/members`, `/members/alex-coletti`, `/records`, `/players`, `/players/4046`.

`/seasons` and `/luck` stay 302 with empty bodies. `http.client` reads `Location: /seasons/2026` and `Location: /seasons/2026#luck`, matching the manifest. The harness reads `$r.Headers['Location']` on the PowerShell 5.1 `HttpResponseException` path and gets an empty string, so those two rows FAIL inside the harness. The product redirect is unchanged.

`/seasons/2025`, `/seasons/2025?theme=modern&pane=standings`, and `/seasons/2025?theme=nope` are the same 369314-byte document. `?theme=nope` sets `theme=modern`.

## Era season panes

All 7 panes × `era90` and `era2010` returned 200. Fragment sha256 prefixes (12 hex), region between `<!--a2-fragment-->` markers:

| pane | bytes | era90 | era2010 | same |
| --- | --- | --- | --- | --- |
| standings | 3856 / 3516 | c12e9eb8845f | e51b9c488d81 | no |
| weeks | 20442 | 61210b4dd094 | 61210b4dd094 | yes |
| playoffs | 3606 | 21cb13ab58ef | 21cb13ab58ef | yes |
| moves | 3500 | 66bf04ea42c5 | 66bf04ea42c5 | yes |
| draft | 46757 / 46078 | 0b2c0c7398f0 | 857d7b221e85 | no |
| lineups | 3424 | cb3a76ac96ec | cb3a76ac96ec | yes |
| stacks | 3453 | 2326b02b2fc2 | 2326b02b2fc2 | yes |

Lead slot `91dac4d395ab` and aside slot `27e799e27e64` match across the two shells. No fragment region contains `theme=`.

Standings differ because the projections differ (era90: manager, W, L, T, PF, PA; era2010: manager, record, pct, PF, PA). Draft differs because the player formatter shortens names on era2010.

## Selective loaders

`NU_CHOATE_PERF=1`. `season_row` runs for the page, then only the active loader.

`/seasons/2025?theme=era90&pane=playoffs`: `pane playoffs`, then `season_schedule` (matchups, platform, roster) and the posted-playoff select. No standings query.

`/seasons/2025?theme=era90&pane=lineups`: `pane lineups`, then the three lineup statements. No playoff select and no standings query.

## No-JS

era90 weeks page: zero `<script>`. Switcher links for modern, era90, and era2010. Pane links for all seven panes. Fourteen shell week links `/seasons/2025/week/N?theme=era90`. Fourteen fragment week links `/seasons/2025/week/N` with no theme parameter. ESPN is a `dead-label`, not an anchor. One `link-box`, six dead labels. era2010 playoffs: zero scripts, `class="tabs"`, no layout table, no dead labels.

## Cookie and missing season

`GET /?theme=era90` sets `theme=era90; HttpOnly; Max-Age=31536000; Path=/; SameSite=lax` and still renders `hub.css`. The same cookie on `/seasons/2025` renders `era90.css` and not `hub.css`. `/seasons/1999?theme=era90` is 404, body contains `No season 1999`, and the legacy error page includes the switcher.

## Boot gate

Appending `\n<table class="scratch">` to `hub/templates/fragments/games.html` and running `nu-choate-league serve --port 8112 --no-reload` exited 1:

```text
ThemeContractError: theme contract failed:
- <table is not confined to stat_table.html: ['games.html', 'stat_table.html']
```

The file was restored to its original bytes in the same step. A clean import passes the gate.

## Perf

`scripts/perf/baseline.ps1`, median of 7, warmup discarded. 68324dd baselines: `/` 0.29, `/players` 0.90, `/records` 1.81, `/seasons/2025` 0.75, `/seasons/2025/scoring` 0.16.

Modern, no theme query:

| page | median | vs 68324dd |
| --- | --- | --- |
| `/` | 0.29 | 0% |
| `/players` | 0.95 | +5.6% |
| `/records` | 1.95 | +7.7% |
| `/seasons/2025` | 0.76 | +1.3% |
| `/seasons/2025/scoring` | 0.17 | +6.3% |

Era season pages (same harness): era90 standings 0.10, weeks 0.05, draft 0.05; era2010 standings 0.08, weeks 0.06, draft 0.06. Unmigrated URLs with `?theme=` stay on the legacy template.

Interleaved round-robin of `/`, `/players`, and `/records` with and without a theme query (median of 7): home 0.29 / 0.32 / 0.28, players 0.95 / 0.98 / 0.99, records 1.96 / 1.89 / 1.80 (modern / era90 / era2010). The interleaved medians sit inside the same-run spread. `/?theme=era90` at 0.32 and `/players?theme=era2010` at 0.99 are the two that land about 10% over the old baseline, and both overlap the modern samples from that same run.

## Decisions worth a look

- Stat-grid borders are CSS. Section 2 forbids `border=` on fragments.
- era90 standings include the manager name so the grid identifies a row.
- era2010 standings are the shared facts only: record and winning percentage, plus PF/PA. Games-behind and streak are not on the board.
- Record-gold is `#6b4f00`, commented as a placeholder. era2010's 960px width and steel gradient are commented as unattested.
- The commissioner band is `background: #660000` with white text.
- `render_panes` is only the `/seasons/{year}` pilot. Other families keep the legacy template when an era cookie is set.
- Shell week numerals carry `?theme=` and open the legacy week page.
- 2025 has 14 scored playoff games and no sleeper bracket JSON, so the playoff pane lists those matchups. When a winners or consolation tree exists, that tree is what renders. The fallback still calls `season_schedule` first, then one posted-game select, and only on the playoff pane.

## For the orchestrator

- Pick the record-gold hex and whether 960px / the gloss gradient stay.
- Confirm the commissioner band (maroon bar, white text) against the digest if that note meant maroon text on the tan page.
- Modern light-stat styling is still #107.
- Week, scoring, and the other families are still legacy pages, including when the shell links into them.
- `parity.ps1` on PowerShell 5.1 will keep failing the two 302s until it reads the `Location` property. The HTML hashes fail only because of the switcher line above.
