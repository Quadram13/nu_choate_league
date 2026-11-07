# 2026-11-07: Wiki and agent docs live in-repo under `docs/`

On 2026-11-07 Marcus sanctioned porting a selective subset of the `hanlun_tools` docs structure (`docs/adr`, `docs/agents`, `docs/runbooks`, `docs/wiki`) into this repo.

Decided:

- The chief-of-staff wiki lives at `docs/wiki/` in this repo, following the hanlun `wiki/` convention (index + decisions / problems / subsystems / open).
- Agent-orchestration conventions live at `docs/agents/`.
- **Not ported:** hanlun ADRs 0002–0004 (Tcl/Tk, macOS GUI, update delivery), the macOS workstation runbook, and all hanlun domain content. No ADR directory yet — Choate decisions are wiki decision pages until one needs immutable numbering.
- Sources are cited, never copied. Hanlun pages remain the record for hanlun.

Reason: this repo has no docs beyond README (as of `Quadram13/nu_choate_league@74d6fb0`), and agent sessions need durable memory that survives context compaction. In-repo means the wiki versions with the code it describes.
