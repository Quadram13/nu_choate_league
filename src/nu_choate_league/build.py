from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

import json

from .alternate import alternate_season
from .catalog import load_managers, load_seasons
from .history import career_records, head_to_head
from .ingest import ingest_all
from .models import DraftPick, Player, SeasonBundle, TeamSeason, Transaction
from .paths import site_data_dir
from .records import sort_standings


def build_data(*, year: int | None = None) -> list[str]:
    dest = site_data_dir()
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "seasons").mkdir(exist_ok=True)
    (dest / "matchups").mkdir(exist_ok=True)
    (dest / "drafts").mkdir(exist_ok=True)
    (dest / "transactions").mkdir(exist_ok=True)
    (dest / "scores").mkdir(exist_ok=True)
    (dest / "alternate").mkdir(exist_ok=True)
    seen_players: dict[str, Player] = {}
    season_summaries = []
    lines: list[str] = []
    bundles = ingest_all(year=year)
    for bundle in bundles:
        season = bundle.season
        _write_json(dest / "seasons" / f"{season.year}.json", _season_payload(bundle))
        _write_json(
            dest / "matchups" / f"{season.year}.json",
            [matchup.model_dump() for matchup in bundle.matchups],
        )
        _write_json(
            dest / "drafts" / f"{season.year}.json",
            [pick.model_dump() for pick in bundle.draft_picks],
        )
        _write_json(
            dest / "transactions" / f"{season.year}.json",
            [txn.model_dump() for txn in bundle.transactions],
        )
        _write_json(
            dest / "scores" / f"{season.year}.json",
            [row.model_dump() for row in bundle.week_scores],
        )
        alt = alternate_season(bundle)
        if alt is not None:
            _write_json(dest / "alternate" / f"{season.year}.json", alt.model_dump())
        _collect_players(bundle, seen_players)
        outcome = bundle.outcome
        season_summaries.append(
            {
                "year": season.year,
                "platform": season.platform.value,
                "league_id": season.league_id,
                "name": season.name,
                "vs_median": season.vs_median,
                "teams": len(bundle.teams),
                "matchups": len(bundle.matchups),
                "draft_picks": len(bundle.draft_picks),
                "transactions": len(bundle.transactions),
                "champion": outcome.champion if outcome else None,
                "runner_up": outcome.runner_up if outcome else None,
                "regular_season_champion": outcome.regular_season_champion if outcome else None,
                "most_points": outcome.most_points if outcome else None,
                "playoff_teams": (
                    outcome.playoff_format.teams if outcome and outcome.playoff_format else None
                ),
                "playoff_byes": (
                    outcome.playoff_format.byes if outcome and outcome.playoff_format else None
                ),
            }
        )
        lines.extend(_compare(bundle))
    if year is None:
        _write_json(
            dest / "league.json",
            {
                "name": "Nu Choate League",
                "seasons": season_summaries,
            },
        )
        _write_json(
            dest / "managers.json",
            [manager.model_dump() for manager in load_managers()],
        )
        _write_json(
            dest / "players.json",
            [player.model_dump() for player in sorted(seen_players.values(), key=lambda item: item.id)],
        )
        leftover = {season.year for season in load_seasons()} - {row["year"] for row in season_summaries}
        for old in leftover:
            (dest / "seasons" / f"{old}.json").unlink(missing_ok=True)
            (dest / "matchups" / f"{old}.json").unlink(missing_ok=True)
            (dest / "drafts" / f"{old}.json").unlink(missing_ok=True)
            (dest / "transactions" / f"{old}.json").unlink(missing_ok=True)
            (dest / "scores" / f"{old}.json").unlink(missing_ok=True)
            (dest / "alternate" / f"{old}.json").unlink(missing_ok=True)
        _write_json(dest / "career.json", [row.model_dump() for row in career_records(bundles)])
        _write_json(dest / "h2h.json", [row.model_dump() for row in head_to_head(bundles)])
    return lines


def format_standings(teams: Iterable[TeamSeason]) -> str:
    names = {manager.id: manager.display_name for manager in load_managers()}
    rows = ["Rk  Sd  Manager              Team                             W-L-T   PF      PA"]
    for team in sort_standings(list(teams)):
        record = f"{team.wins}-{team.losses}-{team.ties}"
        label = names.get(team.manager_id, team.manager_id)
        seed = team.playoff_seed or "-"
        rows.append(
            f"{team.final_rank or 0:2}  {seed!s:>2}  {label:20} {team.team_name:32} "
            f"{record:7} {team.points_for:7.2f} {team.points_against:7.2f}"
        )
    return "\n".join(rows) + "\n"


def format_draft(picks: Iterable[DraftPick]) -> str:
    names = {manager.id: manager.display_name for manager in load_managers()}
    rows = ["Rd  Ovr  Manager              Player                         K"]
    for pick in picks:
        keeper = "K" if pick.keeper else ""
        label = names.get(pick.manager_id, pick.manager_id)
        rows.append(
            f"{pick.round:2}  {pick.overall:3}  {label:20} {pick.player_name:28} {keeper}"
        )
    return "\n".join(rows) + "\n"


def format_transactions(transactions: Iterable[Transaction]) -> str:
    names = {manager.id: manager.display_name for manager in load_managers()}
    rows = ["Wk  Type          Status    Moves"]
    for txn in transactions:
        moves = _move_text(txn, names)
        rows.append(f"{txn.week:2}  {txn.type:13} {txn.status:9} {moves}")
    return "\n".join(rows) + "\n"


def _move_text(txn: Transaction, names: dict[str, str]) -> str:
    parts: list[str] = []
    for move in txn.adds:
        label = names.get(move.manager_id, move.manager_id)
        parts.append(f"+{move.player_name} ({label})")
    for move in txn.drops:
        label = names.get(move.manager_id, move.manager_id)
        parts.append(f"-{move.player_name} ({label})")
    return ", ".join(parts)


def _season_payload(bundle: SeasonBundle) -> dict:
    season = bundle.season
    outcome = bundle.outcome
    payload = {
        "year": season.year,
        "platform": season.platform.value,
        "league_id": season.league_id,
        "name": season.name,
        "vs_median": season.vs_median,
        "champion": outcome.champion if outcome else None,
        "runner_up": outcome.runner_up if outcome else None,
        "regular_season_champion": outcome.regular_season_champion if outcome else None,
        "most_points": outcome.most_points if outcome else None,
        "playoff_managers": outcome.playoff_managers if outcome else [],
        "playoff_format": outcome.playoff_format.model_dump() if outcome and outcome.playoff_format else None,
        "teams": [team.model_dump() for team in bundle.teams],
    }
    return payload


def _collect_players(bundle: SeasonBundle, seen: dict[str, Player]) -> None:
    def add(player_id: str, player_name: str, slot: str | None = None) -> None:
        if player_id in seen:
            return
        seen[player_id] = Player(
            id=player_id,
            display_name=player_name,
            sleeper_id=None if player_id.startswith("espn:") else player_id,
            position=slot if slot not in {None, "BN", "IR", "FLEX"} else None,
            source="lineup" if slot else "roster",
        )

    for matchup in bundle.matchups:
        for side in (matchup.home, matchup.away):
            for slot in side.lineup:
                add(slot.player_id, slot.player_name, slot.slot)
    for pick in bundle.draft_picks:
        add(pick.player_id, pick.player_name)
    for txn in bundle.transactions:
        for move in (*txn.adds, *txn.drops):
            add(move.player_id, move.player_name)


def _compare(bundle: SeasonBundle) -> list[str]:
    season = bundle.season
    by_id = {team.manager_id: team for team in bundle.teams}
    lines = [f"{season.year} {season.platform.value}:"]
    mismatches = 0
    for row in bundle.official:
        team = by_id[row.manager_id]
        record_ok = (team.wins, team.losses, team.ties) == (row.wins, row.losses, row.ties)
        pf_ok = abs(team.points_for - row.points_for) <= 0.05
        status = "OK" if record_ok and pf_ok else "DIFF"
        if status == "DIFF":
            mismatches += 1
        lines.append(
            f"  {status:4} {row.manager_id:20} ours {team.wins}-{team.losses}-{team.ties} {team.points_for:.2f}  "
            f"platform {row.wins}-{row.losses}-{row.ties} {row.points_for:.2f}"
        )
    if mismatches == 0:
        lines.append("  all records match the platform.")
    keepers = sum(1 for pick in bundle.draft_picks if pick.keeper)
    lines.append(f"  draft {len(bundle.draft_picks)} picks ({keepers} keepers)")
    kinds = Counter(txn.type for txn in bundle.transactions)
    kind_text = ", ".join(f"{name} {count}" for name, count in sorted(kinds.items())) or "none"
    lines.append(f"  transactions {len(bundle.transactions)} ({kind_text})")
    outcome = bundle.outcome
    if outcome and outcome.champion:
        playoff = ", ".join(outcome.playoff_managers) or "none"
        lines.append(
            f"  champion {outcome.champion}  runner-up {outcome.runner_up}  "
            f"RS {outcome.regular_season_champion}  PF {outcome.most_points}"
        )
        lines.append(f"  playoffs {playoff}")
        fmt = outcome.playoff_format
        if fmt:
            rounds = ", ".join(f"{round.name} w{round.week}" for round in fmt.rounds)
            lines.append(f"  bracket {fmt.teams} teams, {fmt.byes} byes ({rounds})")
    elif outcome:
        lines.append("  no champion yet")
        fmt = outcome.playoff_format
        if fmt:
            rounds = ", ".join(f"{round.name} w{round.week}" for round in fmt.rounds)
            lines.append(f"  bracket {fmt.teams} teams, {fmt.byes} byes ({rounds})")
    unpaired = sum(1 for row in bundle.week_scores if not row.paired)
    if bundle.week_scores:
        lines.append(f"  weekly scores {len(bundle.week_scores)} ({unpaired} unpaired)")
    alt = alternate_season(bundle)
    if alt is not None:
        for universe in alt.universes:
            status = "MATCH official" if universe.matches_official else "alt"
            lines.append(
                f"  {universe.id:14} {status:14} RS {universe.regular_season_champion}  "
                f"champ {universe.champion}  runner-up {universe.runner_up}"
            )
            for note in universe.notes:
                lines.append(f"    note {note}")
    return lines


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
