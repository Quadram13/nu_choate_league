"""One skin name per document. Templates do not branch on it.

The catalog below is the only theme list. Each name has one file,
``hub/static/skins/<name>.css``. ``spine.css`` is not a theme: every page
loads it, and it holds the shared document contract (one pane visible, era-only
pieces hidden until a skin opts in).

``resolve_theme`` is the boundary. Callers pass the raw query string and get
back a catalog name. Inside the templates the name is already valid.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..paths import project_root

# Order is the switcher order. Labels are the only user-facing names.
THEMES: tuple[tuple[str, str], ...] = (
    ("era90", "1998"),
    ("era2010", "2010"),
    ("modern", "Today"),
)

# Season panes, document order. season.html and spine.css must match this
# tuple or the process refuses to import. First id is the no-hash pane.
PANE_IDS: tuple[str, ...] = (
    "standings",
    "weeks",
    "playoffs",
    "moves",
    "draft",
    "lineups",
    "stacks",
)

_THEME_NAME = re.compile(r"[a-z][a-z0-9]{0,31}")
_PANE_OPEN = re.compile(r"<section\b[^>]*\bjs-season-pane\b[^>]*>")


def skins_dir() -> Path:
    return project_root() / "hub" / "static" / "skins"


def theme_names() -> tuple[str, ...]:
    return tuple(name for name, _label in THEMES)


def resolve_theme(raw: str | None) -> str:
    """Return a catalog theme. Anything else is modern."""
    if raw and _THEME_NAME.fullmatch(raw) and raw in theme_names():
        return raw
    return "modern"


def theme_query(raw: str | None) -> str:
    """``?theme=...`` when the request asked for a real skin, else empty.

    Stamping the name onto every href would make the body differ per theme,
    so redirects are the only place this string is written.
    """
    if raw and resolve_theme(raw) == raw:
        return f"?theme={raw}"
    return ""


def assert_theme_contract() -> None:
    """Fail import when the catalog, the skin files, and the pane list disagree."""
    root = project_root()
    directory = skins_dir()
    missing = [name for name in theme_names() if not (directory / f"{name}.css").is_file()]
    if missing:
        raise RuntimeError(f"missing skin stylesheet(s): {', '.join(missing)}")
    spine = directory / "spine.css"
    if not spine.is_file():
        raise RuntimeError(f"missing {spine}")
    spine_text = spine.read_text(encoding="utf-8")
    for pane in PANE_IDS:
        token = f"#{pane}:target"
        if token not in spine_text:
            raise RuntimeError(f"spine.css has no {token} rule; pane list drifted")
    if PANE_IDS[0] != "standings":
        raise RuntimeError("the no-hash pane is standings; PANE_IDS[0] must stay standings")
    template = (root / "hub" / "templates" / "season.html").read_text(encoding="utf-8")
    found: list[str] = []
    for tag in _PANE_OPEN.findall(template):
        match = re.search(r'\bid="([^"]+)"', tag)
        if match is None:
            raise RuntimeError(f"js-season-pane section has no id: {tag}")
        found.append(match.group(1))
    if tuple(found) != PANE_IDS:
        raise RuntimeError(f"season panes {found} != catalog {list(PANE_IDS)}")
