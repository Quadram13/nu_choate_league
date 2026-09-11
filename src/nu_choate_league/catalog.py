from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import TypeAdapter

from .models import Manager, Platform, Season
from .paths import maps_dir


class DuplicateIdentityError(ValueError):
    pass


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a mapping")
    return payload


def load_seasons(path: Path | None = None) -> list[Season]:
    data = load_yaml(path or maps_dir() / "seasons.yaml")
    return TypeAdapter(list[Season]).validate_python(data.get("seasons") or [])


def load_managers(path: Path | None = None) -> list[Manager]:
    data = load_yaml(path or maps_dir() / "managers.yaml")
    managers = TypeAdapter(list[Manager]).validate_python(data.get("managers") or [])
    _assert_unique_ids(managers)
    return managers


def _assert_unique_ids(managers: list[Manager]) -> None:
    seen_manager: set[str] = set()
    seen_espn: dict[str, str] = {}
    seen_sleeper: dict[str, str] = {}
    for manager in managers:
        if manager.id in seen_manager:
            raise DuplicateIdentityError(f"Duplicate manager id {manager.id!r}")
        seen_manager.add(manager.id)
        for espn_id in manager.espn_member_ids:
            key = _espn_key(espn_id)
            if key in seen_espn:
                raise DuplicateIdentityError(
                    f"ESPN member {espn_id} mapped to {seen_espn[key]!r} and {manager.id!r}"
                )
            seen_espn[key] = manager.id
        for sleeper_id in manager.sleeper_user_ids:
            key = str(sleeper_id)
            if key in seen_sleeper:
                raise DuplicateIdentityError(
                    f"Sleeper user {sleeper_id} mapped to {seen_sleeper[key]!r} and {manager.id!r}"
                )
            seen_sleeper[key] = manager.id


def _espn_key(member_id: str) -> str:
    return member_id.strip().upper()


class IdentityIndex:
    def __init__(self, managers: list[Manager]) -> None:
        self.managers = managers
        self._by_id = {manager.id: manager for manager in managers}
        self._espn = {_espn_key(espn_id): manager for manager in managers for espn_id in manager.espn_member_ids}
        self._sleeper = {str(sleeper_id): manager for manager in managers for sleeper_id in manager.sleeper_user_ids}

    def by_id(self, manager_id: str) -> Manager | None:
        return self._by_id.get(manager_id)

    def resolve(self, platform: Platform, platform_id: str) -> Manager | None:
        if platform is Platform.ESPN:
            return self._espn.get(_espn_key(platform_id))
        return self._sleeper.get(str(platform_id))
