# 2026-11-07: Agent orchestration model

Decided by Marcus on 2026-11-07 (mirrors the Mac hanlun port sanction):

- **Chief-of-staff (admin / DRI):** Kimi K3 at max. Coordinates, files tickets, comments on issues, merges.
- **All Task / implementer sub-agents:** `grok-4.7-high-fast` only. DeepSeek is not on the allowlist and is not probed. No Claude slugs.
- **Implement pattern:** two-ticket `implement` + `implement-spec` combo — each ticket gets a fresh implementer in its own git worktree on a `cursor/<slug>-bf5b` branch based on the integration branch; a merger lands it back.
- **Issue conventions:** parent/umbrella issues carry sub-issues; child PRs and commits use `Refs #N` on parents — never `Closes`/`Fixes` on an umbrella without Marcus's explicit say-so.
- **Verification norm:** there is no test suite (as of `@74d6fb0`). Verification = `serve` smoke against the local Docker DB + `query` CLI checks + browser click-through checklists where the ticket is visual.

Probed on 2026-11-07: a throwaway `grok-4.7-high-fast` Task responded correctly, confirming the slug is accepted on the WIN11PC-Choate worker.
