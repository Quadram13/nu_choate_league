# 2026-11-07: Raw dump content is first-class

Decided by Marcus on 2026-11-07, as a clarification to the data-utilization goal:

- "Look at the raw data" means the `data/` folder in the local clone, not only what is loaded in Postgres.
- Dump fields that never made it into the DB are first-class opportunities: rework ingest (migrations/loaders) so they land, then surface them — not a separate later phase.

Consequences recorded:

- The 2026-11-07 schema audit (store: `schema-audit.md`) already inventoried the dumps; its "stretch" items were promoted into the ticket tree the same day: GitHub issues #23 (Sleeper counting stats), #24 (ESPN `appliedStats` backfill), #25 (ESPN market ADP/ownership/auction), #26 (NFL schedule + Sleeper roster extras), all under parent #15.
- Ingest-wave tickets run `load` to verify; as of 2026-11-07 the rule is one `load` at a time across the whole wave, announced in the PR, so parallel hub serves can restart (learned from the README: hub 503s while views rebuild).
- Verified against the dumps on 2026-11-07: ESPN boxscores carry per-week `injuryStatus` (2022 W1: 301 NORMAL / 223 ACTIVE / 53 QUESTIONABLE), so weekly injury flags exist for ESPN years only. Sleeper `players/nfl.json` is a current snapshot, not a history.

Supersedes: the "no weekly injury history in the dumps" claim in the first draft of issue #15 (corrected there the same day).
