from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import IdentityIndex, load_managers, load_seasons
from .dumps import DumpError, dump_owners, season_dir
from .models import DumpOwner, Manager, Season


@dataclass
class InspectReport:
    seasons: list[tuple[Season, int, int]] = field(default_factory=list)
    unmapped: list[DumpOwner] = field(default_factory=list)
    unused: list[Manager] = field(default_factory=list)
    missing_dumps: list[Season] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unmapped and not self.missing_dumps


def inspect_managers() -> InspectReport:
    seasons = load_seasons()
    managers = load_managers()
    index = IdentityIndex(managers)
    seen_manager_ids: set[str] = set()
    report = InspectReport()

    for season in seasons:
        try:
            owners = dump_owners(season)
        except DumpError:
            report.missing_dumps.append(season)
            continue
        mapped = 0
        for owner in owners:
            manager = index.resolve(owner.platform, owner.platform_id)
            if manager is None:
                report.unmapped.append(owner)
            else:
                mapped += 1
                seen_manager_ids.add(manager.id)
        report.seasons.append((season, mapped, len(owners)))

    report.unused = [manager for manager in managers if manager.id not in seen_manager_ids]
    return report


def format_report(report: InspectReport) -> str:
    lines: list[str] = []
    if report.missing_dumps:
        lines.append("Missing dumps:")
        for season in report.missing_dumps:
            lines.append(f"  {season.year} {season.platform.value}  {season_dir(season)}")
        lines.append("")

    lines.append("Seasons:")
    for season, mapped, total in report.seasons:
        flag = "median" if season.vs_median else "h2h"
        status = "OK" if mapped == total else "GAP"
        lines.append(
            f"  {status:3} {season.year} {season.platform.value:7} {mapped}/{total} owners  ({flag})"
        )

    if report.unmapped:
        lines.append("")
        lines.append("Unmapped owners:")
        for owner in report.unmapped:
            lines.append(
                f"  {owner.year} {owner.platform.value}  {owner.label}  id={owner.platform_id}"
            )

    if report.unused:
        lines.append("")
        lines.append("Managers in the map but not in any dump:")
        for manager in report.unused:
            lines.append(f"  {manager.id}  {manager.display_name}")

    if report.ok and not report.unused:
        lines.append("")
        lines.append("All dump owners resolve to a manager.")
    elif report.ok:
        lines.append("")
        lines.append("All dump owners resolve. Unused map rows are leftover identities.")
    return "\n".join(lines) + "\n"
