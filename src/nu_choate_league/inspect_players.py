from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .catalog import load_seasons
from .dumps import DumpError, dump_players, season_dir
from .models import DumpPlayer, Player, Season
from .players import PlayerIndex


@dataclass
class PlayerInspectReport:
    seasons: list[tuple[Season, int, int, Counter[str]]] = field(default_factory=list)
    espn_only: list[tuple[DumpPlayer, Player]] = field(default_factory=list)
    missing_sleeper: list[DumpPlayer] = field(default_factory=list)
    missing_dumps: list[Season] = field(default_factory=list)
    duplicate_espn_ids: dict[int, list[str]] = field(default_factory=dict)
    catalog_size: int = 0
    catalog_with_espn_id: int = 0

    @property
    def ok(self) -> bool:
        return not self.espn_only and not self.missing_sleeper and not self.missing_dumps


def inspect_players() -> PlayerInspectReport:
    seasons = load_seasons()
    index = PlayerIndex()
    report = PlayerInspectReport(
        duplicate_espn_ids=index.duplicate_espn_ids,
        catalog_size=len(index.catalog),
        catalog_with_espn_id=len(index.espn_ids),
    )
    for season in seasons:
        try:
            dumps = dump_players(season)
        except DumpError:
            report.missing_dumps.append(season)
            continue
        sources: Counter[str] = Counter()
        mapped = 0
        for dump in dumps:
            player = index.resolve(dump)
            sources[player.source] += 1
            if player.source == "espn_only":
                report.espn_only.append((dump, player))
            elif player.source == "missing":
                report.missing_sleeper.append(dump)
            else:
                mapped += 1
        report.seasons.append((season, mapped, len(dumps), sources))
    return report


def format_player_report(report: PlayerInspectReport) -> str:
    lines = [
        f"Sleeper catalog: {report.catalog_size} players, "
        f"{report.catalog_with_espn_id} with espn_id, "
        f"{len(report.duplicate_espn_ids)} duplicate espn_ids",
        "",
    ]
    if report.missing_dumps:
        lines.append("Missing dumps:")
        for season in report.missing_dumps:
            lines.append(f"  {season.year} {season.platform.value}  {season_dir(season)}")
        lines.append("")

    lines.append("Seasons:")
    for season, mapped, total, sources in report.seasons:
        status = "OK" if mapped == total else "GAP"
        detail = ", ".join(f"{key}={sources[key]}" for key in sorted(sources) if sources[key])
        lines.append(
            f"  {status:3} {season.year} {season.platform.value:7} {mapped}/{total} players  ({detail})"
        )

    if report.duplicate_espn_ids:
        lines.append("")
        lines.append("Duplicate espn_ids in catalog (highest score kept):")
        for espn_id, sleeper_ids in sorted(report.duplicate_espn_ids.items()):
            lines.append(f"  espn {espn_id}: {', '.join(sleeper_ids)}")

    if report.espn_only:
        lines.append("")
        lines.append("ESPN-only (no Sleeper match; canonical id espn:{id}):")
        for dump, player in report.espn_only:
            years = ",".join(str(year) for year in dump.years) or str(dump.years)
            lines.append(
                f"  {dump.platform_id}  {player.display_name or '(unnamed)'}  "
                f"pos={dump.position or '-'}  years={years}"
            )

    if report.missing_sleeper:
        lines.append("")
        lines.append("Sleeper ids used in dumps but missing from nfl.json:")
        for dump in report.missing_sleeper:
            lines.append(f"  {dump.platform_id}  {dump.display_name or '-'}")

    if report.ok:
        lines.append("")
        lines.append("All dump players resolve to a Sleeper id.")
    return "\n".join(lines) + "\n"
