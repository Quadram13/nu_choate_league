from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    here = Path(__file__).resolve()
    for directory in [here.parent, *here.parents]:
        if (directory / "pyproject.toml").is_file() and (directory / "src" / "nu_choate_league").is_dir():
            return directory
    return Path.cwd()


def maps_dir() -> Path:
    return project_root() / "maps"


def data_dir() -> Path:
    return project_root() / "data"


def site_data_dir() -> Path:
    return project_root() / "site" / "data"
