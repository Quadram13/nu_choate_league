from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

from .catalog import load_yaml
from .models import DumpPlayer, Platform, Player
from .paths import data_dir, maps_dir

ESPN_DST_OFFSET = 16000
FIRST_NAME_ALIASES = {
    "kenneth": "kenny",
    "kenny": "kenneth",
    "chigoziem": "chig",
    "chig": "chigoziem",
    "joshua": "josh",
    "josh": "joshua",
    "michael": "mike",
    "mike": "michael",
}
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$", re.I)
NON_ALNUM = re.compile(r"[^a-z0-9]+")


def norm_name(name: str) -> str:
    cleaned = name.lower().replace("'", "").replace("’", "")
    parts = [part for part in cleaned.split() if part]
    if parts:
        parts[-1] = SUFFIX.sub("", parts[-1]).strip()
        parts = [part for part in parts if part]
    return NON_ALNUM.sub("", " ".join(parts))


def last_name_key(name: str) -> str:
    cleaned = name.lower().replace("'", "").replace("’", "")
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return ""
    return NON_ALNUM.sub("", SUFFIX.sub("", parts[-1]).strip())


def alias_names(name: str) -> list[str]:
    parts = name.split()
    if not parts:
        return [name]
    first = parts[0].lower().strip(".,")
    alias = FIRST_NAME_ALIASES.get(first)
    if not alias:
        return [name]
    return [name, " ".join([alias.title(), *parts[1:]])]


def espn_dst_team_id(espn_id: int) -> int | None:
    if espn_id >= 0:
        return None
    team_id = -espn_id - ESPN_DST_OFFSET
    return team_id if team_id > 0 else None


@lru_cache(maxsize=1)
def load_sleeper_catalog() -> dict[str, dict[str, Any]]:
    path = data_dir() / "sleeper" / "players" / "nfl.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be an object")
    return {key: value for key, value in payload.items() if isinstance(value, dict)}


# Catalog height is either total inches ("74") or feet and inches (6 feet 2).
_FEET_INCHES = re.compile(r"""^(\d+)'(\d{1,2})"?$""")


class CatalogIdentity(NamedTuple):
    """Fields copied off one Sleeper catalog record.

    Static facts stay historically safe. Snapshot fields are whatever the
    catalog says right now; the load stamps catalog_as_of beside them.
    The catalog's integer `age` is intentionally absent.
    """

    birth_date: date | None
    height_in: int | None
    weight_lb: int | None
    high_school: str | None
    rookie_year: int | None
    nfl_status: str | None
    injury_status: str | None
    injury_body_part: str | None
    injury_notes: str | None
    depth_chart_position: str | None
    depth_chart_order: int | None


def sleeper_catalog_path() -> Path:
    return data_dir() / "sleeper" / "players" / "nfl.json"


def sleeper_catalog_as_of(path: Path | None = None) -> date:
    """Local calendar date of nfl.json's mtime.

    The catalog JSON has no refresh field. Snapshot columns mean this date,
    which is the file modification date, not a league week.
    """
    catalog_path = path or sleeper_catalog_path()
    return datetime.fromtimestamp(catalog_path.stat().st_mtime).date()


def format_height(inches: int | None) -> str | None:
    if inches is None:
        return None
    feet, rest = divmod(int(inches), 12)
    return f"{feet}'{rest}\""


def parse_height_in(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        total = int(text)
    else:
        match = _FEET_INCHES.fullmatch(text)
        if match is None:
            return None
        inches = int(match.group(2))
        if inches >= 12:
            return None
        total = int(match.group(1)) * 12 + inches
    if total < 60 or total > 90:
        return None
    return total


def parse_weight_lb(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        pounds = value
    else:
        text = str(value).strip()
        if not text.isdigit():
            return None
        pounds = int(text)
    if pounds <= 0 or pounds > 500:
        return None
    return pounds


def parse_birth_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        return None
    if parsed.year < 1920 or parsed.year > 2100:
        return None
    return parsed


def parse_rookie_year(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        return None
    year = int(text)
    if year < 1920 or year > 2100:
        return None
    return year


def _catalog_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _catalog_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text.isdigit():
        return None
    return int(text)


def catalog_identity(record: dict[str, Any]) -> CatalogIdentity:
    """Static bio plus the current snapshot fields this load keeps.

    practice_participation is ignored. This catalog fills it for one player,
    so storing it would look like a practice report the file does not have.
    injury_start_date and birth city/state/country are empty on every row.
    metadata injury_override_* is not a timeline and is left out.
    """
    metadata = record.get("metadata")
    rookie_raw = metadata.get("rookie_year") if isinstance(metadata, dict) else None
    return CatalogIdentity(
        birth_date=parse_birth_date(record.get("birth_date")),
        height_in=parse_height_in(record.get("height")),
        weight_lb=parse_weight_lb(record.get("weight")),
        high_school=_catalog_text(record.get("high_school")),
        rookie_year=parse_rookie_year(rookie_raw),
        nfl_status=_catalog_text(record.get("status")),
        injury_status=_catalog_text(record.get("injury_status")),
        injury_body_part=_catalog_text(record.get("injury_body_part")),
        injury_notes=_catalog_text(record.get("injury_notes")),
        depth_chart_position=_catalog_text(record.get("depth_chart_position")),
        depth_chart_order=_catalog_int(record.get("depth_chart_order")),
    )


def load_dst_map(path: Path | None = None) -> dict[int, str]:
    data = load_yaml(path or maps_dir() / "dst.yaml")
    teams = data.get("teams") or {}
    return {int(espn_id): _dst_sleeper_id(sleeper_id) for espn_id, sleeper_id in teams.items()}


def _dst_sleeper_id(value: object) -> str:
    # YAML 1.1 parses NO/YES/ON/OFF as booleans. Saints are "NO".
    if value is False:
        return "NO"
    if value is True:
        return "YES"
    return str(value)


def load_player_overrides(path: Path | None = None) -> dict[int, str]:
    data = load_yaml(path or maps_dir() / "player_overrides.yaml")
    raw = data.get("espn_to_sleeper") or {}
    return {int(espn_id): str(sleeper_id) for espn_id, sleeper_id in raw.items()}


def _record_name(record: dict[str, Any]) -> str:
    if record.get("position") == "DEF" or "DEF" in (record.get("fantasy_positions") or []):
        team = str(record.get("team") or record.get("player_id") or "")
        return f"{team} D/ST" if team else "D/ST"
    return str(record.get("full_name") or "").strip()


def _record_position(record: dict[str, Any]) -> str | None:
    if record.get("position") == "DEF" or "DEF" in (record.get("fantasy_positions") or []):
        return "DEF"
    position = record.get("position")
    return str(position) if position else None


def _score_duplicate(record: dict[str, Any]) -> tuple[int, str]:
    name = _record_name(record)
    score = 0
    if name.lower() == "duplicate player":
        score -= 100
    if record.get("active"):
        score += 10
    if str(record.get("status") or "").lower() == "active":
        score += 5
    if record.get("team"):
        score += 1
    return score, str(record.get("player_id") or "")


class PlayerIndex:
    def __init__(
        self,
        catalog: dict[str, dict[str, Any]] | None = None,
        dst: dict[int, str] | None = None,
        overrides: dict[int, str] | None = None,
    ) -> None:
        self.catalog = catalog if catalog is not None else load_sleeper_catalog()
        self.dst = dst if dst is not None else load_dst_map()
        self.overrides = overrides if overrides is not None else load_player_overrides()
        self.duplicate_espn_ids: dict[int, list[str]] = {}
        self._by_espn: dict[int, str] = {}
        self._by_name_pos: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._by_name: dict[str, list[str]] = defaultdict(list)
        self._by_last_pos: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._index_catalog()

    @property
    def espn_ids(self) -> dict[int, str]:
        return self._by_espn

    def _index_catalog(self) -> None:
        grouped: dict[int, list[str]] = defaultdict(list)
        for sleeper_id, record in self.catalog.items():
            record.setdefault("player_id", sleeper_id)
            espn_id = record.get("espn_id")
            if espn_id is not None:
                grouped[int(espn_id)].append(sleeper_id)
            name = _record_name(record)
            position = _record_position(record) or ""
            if name and name.lower() != "duplicate player":
                key = (norm_name(name), position)
                self._by_name_pos[key].append(sleeper_id)
                self._by_name[norm_name(name)].append(sleeper_id)
                last = last_name_key(name)
                if last and position:
                    self._by_last_pos[(last, position)].append(sleeper_id)
        for espn_id, sleeper_ids in grouped.items():
            if len(sleeper_ids) > 1:
                self.duplicate_espn_ids[espn_id] = sleeper_ids
            chosen = max(sleeper_ids, key=lambda sid: _score_duplicate(self.catalog[sid]))
            self._by_espn[espn_id] = chosen

    def from_sleeper(self, sleeper_id: str) -> Player | None:
        record = self.catalog.get(sleeper_id)
        if record is None:
            return None
        espn_raw = record.get("espn_id")
        return Player(
            id=sleeper_id,
            display_name=_record_name(record) or sleeper_id,
            sleeper_id=sleeper_id,
            espn_id=int(espn_raw) if espn_raw is not None else None,
            position=_record_position(record),
            source="sleeper",
        )

    def resolve(self, dump: DumpPlayer) -> Player:
        if dump.platform is Platform.SLEEPER:
            player = self.from_sleeper(dump.platform_id)
            if player is not None:
                return player
            return Player(
                id=dump.platform_id,
                display_name=dump.display_name or dump.platform_id,
                sleeper_id=dump.platform_id,
                position=dump.position,
                source="missing",
            )
        return self.resolve_espn(
            int(dump.platform_id),
            name=dump.display_name,
            position=dump.position,
        )

    def resolve_espn(self, espn_id: int, *, name: str = "", position: str | None = None) -> Player:
        override = self.overrides.get(espn_id)
        if override:
            player = self.from_sleeper(override)
            if player is not None:
                return player.model_copy(update={"espn_id": espn_id, "source": "override"})
        dst = self._resolve_dst(espn_id, position)
        if dst is not None:
            return dst
        sleeper_id = self._by_espn.get(espn_id)
        if sleeper_id:
            player = self.from_sleeper(sleeper_id)
            if player is not None:
                return player.model_copy(update={"espn_id": espn_id, "source": "espn_id"})
        matched = self._match_name(name, position)
        if matched is not None:
            return matched.model_copy(update={"espn_id": espn_id})
        return Player(
            id=f"espn:{espn_id}",
            display_name=name or f"espn:{espn_id}",
            espn_id=espn_id,
            position=position,
            source="espn_only",
        )

    def _resolve_dst(self, espn_id: int, position: str | None) -> Player | None:
        team_id = espn_dst_team_id(espn_id)
        if team_id is None and position != "DEF":
            return None
        if team_id is None:
            return None
        sleeper_id = self.dst.get(team_id)
        if not sleeper_id:
            return None
        player = self.from_sleeper(sleeper_id)
        if player is None:
            return Player(
                id=sleeper_id,
                display_name=f"{sleeper_id} D/ST",
                sleeper_id=sleeper_id,
                espn_id=espn_id,
                position="DEF",
                source="dst",
            )
        return player.model_copy(update={"espn_id": espn_id, "source": "dst"})

    def _match_name(self, name: str, position: str | None) -> Player | None:
        if not name:
            return None
        candidates: list[tuple[str, str]] = []
        for variant in alias_names(name):
            key = norm_name(variant)
            if position:
                hits = self._by_name_pos.get((key, position)) or []
                if len(hits) == 1:
                    return self._named(hits[0], "name")
                if len(hits) > 1:
                    candidates.extend((hit, "name") for hit in hits)
            hits = self._by_name.get(key) or []
            if len(hits) == 1:
                return self._named(hits[0], "name")
        if position:
            last = last_name_key(name)
            hits = self._by_last_pos.get((last, position)) or []
            if len(hits) == 1:
                return self._named(hits[0], "name")
        if len({hit for hit, _ in candidates}) == 1:
            return self._named(candidates[0][0], "name")
        return None

    def _named(self, sleeper_id: str, source: str) -> Player:
        player = self.from_sleeper(sleeper_id)
        if player is None:
            raise KeyError(sleeper_id)
        return player.model_copy(update={"source": source})
