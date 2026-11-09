"""Shell contract for the theme spike.

A page author calls ``render_panes`` and never names a theme. The function
resolves ``?theme=`` and ``?pane=``, runs only the active pane's loader, and
returns one shell document. Shells may place slots and the active fragment.
They may not name a content template, link a second stylesheet, or branch
into ``fragments/``.

Slots the shells place, in an order each shell chooses:

- ``lead`` — one line of page identity
- ``aside`` — the page's related links

The active pane template is mounted once, through ``shells/_fragment.html``.
Content templates are class-only. They do not read ``frame.theme`` and do not
emit ``?theme=``. Theme carried on a content link is a redirect from the
Referer of a shell link, so the fragment bytes stay free of the theme token.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse

from jinja2 import TemplateNotFound
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates

from ..paths import project_root

THEMES: tuple[str, ...] = ("modern", "era90", "era2010")

THEME_LABELS: dict[str, str] = {
    "modern": "Modern",
    "era90": "1998",
    "era2010": "2010",
}

# One destination table. A None path is filled with the season year at render.
NAV: dict[str, tuple[str | None, str]] = {
    "home": ("/", "Home"),
    "seasons": ("/seasons", "Seasons"),
    "members": ("/members", "Members"),
    "versus": ("/versus", "Versus"),
    "records": ("/records", "Records"),
    "players": ("/players", "Players"),
    "scoring": (None, "Scoring"),
}

_SITE_NAV: tuple[str, ...] = ("home", "seasons", "members", "versus", "records", "players")

# Era90 rail follows the Eagle task shape: record book, top 10, rules, then
# the rest of the league. It is not the modern mast order. Era2010 reuses the
# site nav; no reached source captured an ESPN 2010 league-tab order.
NAV_ORDER: dict[str, tuple[str, ...]] = {
    "modern": _SITE_NAV,
    "era2010": _SITE_NAV,
    "era90": ("home", "seasons", "records", "players", "scoring", "members", "versus"),
}

_FRAGMENT_FORBIDDEN: tuple[str, ...] = (
    "frame.theme",
    "query_params",
    "{% extends",
    "{%extends",
    "theme=",
    "?theme",
)

_templates: Jinja2Templates | None = None


@dataclass(frozen=True)
class FragmentView:
    name: str
    label: str
    template: str


@dataclass(frozen=True)
class Pane:
    """One entry in a page's fragment catalog. The loader runs only when active."""

    name: str
    label: str
    template: str
    load: Callable[[], Mapping[str, object]]


@dataclass(frozen=True)
class Slot:
    name: str
    template: str


@dataclass(frozen=True)
class NavLink:
    key: str
    href: str
    label: str


@dataclass(frozen=True)
class ThemeChoice:
    id: str
    label: str


@dataclass(frozen=True)
class Frame:
    theme: str
    title: str
    nav: str
    pager: str
    fragments: tuple[FragmentView, ...]
    active: FragmentView
    slots: Mapping[str, str]
    path: str
    nav_links: tuple[NavLink, ...]
    theme_choices: tuple[ThemeChoice, ...]

    @property
    def paged(self) -> bool:
        """Pane chrome exists only when the catalog has somewhere to go."""
        return len(self.fragments) > 1

    def slot(self, name: str) -> str | None:
        return self.slots.get(name)

    def pane_href(self, name: str) -> str:
        return self.path + "?" + urlencode((("pane", name), ("theme", self.theme)))

    def theme_href(self, theme: str) -> str:
        chosen = canonical_theme(theme) or "modern"
        return self.path + "?" + urlencode((("pane", self.active.name), ("theme", chosen)))

    def carry(self, href: str) -> str:
        """Append the current theme to a shell link. Fragments do not call this."""
        if not href.startswith("/") or href.startswith("//"):
            return href
        join = "&" if "?" in href else "?"
        return f"{href}{join}theme={self.theme}"


def canonical_theme(value: object) -> str | None:
    if isinstance(value, str) and value in THEMES:
        return value
    return None


def carry_redirect(request: Request) -> RedirectResponse | None:
    """Keep a theme on a content link that deliberately omits ``?theme=``.

    Fragment HTML stays byte-identical. The browser's Referer still has the
    theme from the shell link that opened the page. Direct visits with no
    theme render modern.
    """
    if request.method != "GET":
        return None
    path = request.url.path
    if not path.startswith("/") or path.startswith("//") or path.startswith("/static"):
        return None
    if canonical_theme(request.query_params.get("theme")) is not None:
        return None
    referer = request.headers.get("referer")
    if not referer:
        return None
    carried = canonical_theme(dict(parse_qsl(urlparse(referer).query)).get("theme"))
    if carried is None:
        return None
    pairs = [
        (key, item)
        for key, item in parse_qsl(request.url.query, keep_blank_values=True)
        if key != "theme"
    ]
    pairs.append(("theme", carried))
    return RedirectResponse(path + "?" + urlencode(pairs), status_code=302)


def bind(templates: Jinja2Templates) -> None:
    global _templates
    _templates = templates
    _check_contract()


def render_panes(
    request: Request,
    *,
    title: str,
    nav: str,
    panes: Sequence[Pane],
    slots: Sequence[Slot] = (),
    context: Mapping[str, object] | None = None,
    pager: str = "",
) -> HTMLResponse:
    if _templates is None:
        raise RuntimeError("themes.bind() was not called")
    if not panes:
        raise ValueError("a themed page needs at least one pane")
    names = [pane.name for pane in panes]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate pane name on {title!r}")
    slot_map: dict[str, str] = {}
    for slot in slots:
        if slot.name in slot_map:
            raise ValueError(f"duplicate slot {slot.name}")
        slot_map[slot.name] = slot.template
    env = _templates.env
    for pane in panes:
        _require_template(env, pane.template)
    for template in slot_map.values():
        _require_template(env, template)

    base = dict(context or {})
    if "frame" in base:
        raise ValueError("context cannot include frame")
    year = base.get("year")
    if year is not None and not isinstance(year, int):
        raise ValueError("year must be int")

    theme = canonical_theme(request.query_params.get("theme")) or "modern"
    requested = request.query_params.get("pane")
    active_name = requested if isinstance(requested, str) and requested in names else names[0]
    active_pane = next(pane for pane in panes if pane.name == active_name)
    loaded = dict(active_pane.load())
    overlap = set(base) & set(loaded)
    if overlap:
        raise ValueError(f"loader overwrites context keys: {sorted(overlap)}")
    base.update(loaded)

    frame = Frame(
        theme=theme,
        title=title,
        nav=nav,
        pager=pager,
        fragments=tuple(FragmentView(pane.name, pane.label, pane.template) for pane in panes),
        active=FragmentView(active_pane.name, active_pane.label, active_pane.template),
        slots=slot_map,
        path=request.url.path,
        nav_links=_nav_links(theme, year if isinstance(year, int) else None),
        theme_choices=tuple(ThemeChoice(theme_id, THEME_LABELS[theme_id]) for theme_id in THEMES),
    )
    payload: dict[str, object] = {**base, "frame": frame, "title": title, "nav": nav}
    return _templates.TemplateResponse(request, f"shells/{theme}.html", payload)


def _require_template(env: object, name: str) -> None:
    try:
        env.get_template(name)  # type: ignore[attr-defined]
    except TemplateNotFound as exc:
        raise RuntimeError(f"missing template {name}") from exc


def _nav_links(theme: str, year: int | None) -> tuple[NavLink, ...]:
    items: list[NavLink] = []
    for key in NAV_ORDER[theme]:
        path, label = NAV[key]
        if path is None:
            if year is None:
                continue
            path = f"/seasons/{year}/scoring"
        items.append(NavLink(key, path, label))
    return tuple(items)


def _check_contract() -> None:
    if set(NAV_ORDER) != set(THEMES):
        raise RuntimeError("NAV_ORDER drifted from THEMES")
    if set(THEME_LABELS) != set(THEMES):
        raise RuntimeError("THEME_LABELS drifted from THEMES")
    for order in NAV_ORDER.values():
        missing = [key for key in order if key not in NAV]
        if missing:
            raise RuntimeError(f"nav keys missing from NAV: {missing}")

    root = project_root()
    shells = root / "hub" / "templates" / "shells"
    for name in ("_fragment.html", "_slot.html"):
        if not (shells / name).is_file():
            raise RuntimeError(f"missing shell mount {name}")
    mount = (shells / "_fragment.html").read_text(encoding="utf-8")
    if "<!--a1-fragment-->" not in mount or "<!--/a1-fragment-->" not in mount:
        raise RuntimeError("fragment mount lost its markers")
    if "frame.active.template" not in mount:
        raise RuntimeError("fragment mount does not include the active template")

    for theme in THEMES:
        path = shells / f"{theme}.html"
        if not path.is_file():
            raise RuntimeError(f"missing shell {path}")
        text = path.read_text(encoding="utf-8")
        if text.count("shells/_fragment.html") != 1:
            raise RuntimeError(f"{theme} shell must mount the fragment once")
        for snippet in ('slot_name="lead"', 'slot_name="aside"', "frame.theme_choices", "frame.nav_links", "frame.paged", "frame.pane_href"):
            if snippet not in text:
                raise RuntimeError(f"{theme} shell is missing {snippet}")
        if "fragments/" in text or ".template" in text:
            raise RuntimeError(f"{theme} shell names content; use the mount")
        if text.count('rel="stylesheet"') != 1 or f"/static/themes/{theme}.css" not in text:
            raise RuntimeError(f"{theme} shell must link exactly its own stylesheet")
        if theme == "era90" and "frame.pager" not in text:
            raise RuntimeError("era90 shell dropped the numeral label")
        css_path = root / "hub" / "static" / "themes" / f"{theme}.css"
        if not css_path.is_file():
            raise RuntimeError(f"missing stylesheet {css_path}")
        css = css_path.read_text(encoding="utf-8")
        if theme == "modern":
            if "@import" not in css or "hub.css" not in css:
                raise RuntimeError("modern.css must import hub.css")
        elif "hub.css" in css:
            raise RuntimeError(f"{theme}.css imports the modern sheet")
        if theme == "era90":
            folded = "".join(css.split()).lower()
            if "display:flex" in folded or "display:grid" in folded:
                raise RuntimeError("era90 stylesheet used flex or grid")

    fragments = root / "hub" / "templates" / "fragments"
    for path in sorted(fragments.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for token in _FRAGMENT_FORBIDDEN:
            if token in text:
                raise RuntimeError(f"{path.name} contains {token!r}")
        if "<table" in text.lower() and path.name != "stat_table.html":
            raise RuntimeError(f"{path.name} builds a table outside the stat macro")
