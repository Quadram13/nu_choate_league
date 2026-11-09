(function () {
    enableNav();
    enableSeasonPicker();
    enableSeasonTabs();
    enableAwardTabs();
    scrollH2hNow();
    document.querySelectorAll("table.js-sort").forEach(enableSort);
    enableFilters();
    enableRankMode();
    document.querySelectorAll(".bracket-tree").forEach(enableBracket);
})();

function enableNav() {
    const button = document.querySelector(".nav-toggle");
    const nav = document.querySelector("#site-nav");
    if (!button || !nav) {
        return;
    }
    button.addEventListener("click", () => {
        const open = nav.classList.toggle("is-open");
        button.setAttribute("aria-expanded", open ? "true" : "false");
    });
}

function scrollH2hNow() {
    const now = document.querySelector(".h2h-meet.now");
    const scroller = document.querySelector(".h2h");
    if (!now || !scroller) {
        return;
    }
    const nowBox = now.getBoundingClientRect();
    const box = scroller.getBoundingClientRect();
    scroller.scrollLeft += nowBox.left - box.left - (box.width - nowBox.width) / 2;
}

function enableSeasonPicker() {
    const select = document.querySelector(".js-season-pick");
    if (!select) {
        return;
    }
    const suffix = select.dataset.suffix || "";
    select.addEventListener("change", () => {
        window.location.href = `/seasons/${select.value}${suffix}`;
    });
}

function enableSeasonTabs() {
    const tabs = document.querySelector(".js-season-tabs");
    if (!tabs) {
        return;
    }
    const panes = [...document.querySelectorAll(".js-season-pane")];
    const buttons = [...tabs.querySelectorAll("[data-tab]")];
    if (!panes.length) {
        return;
    }
    const aliases = {
        scoring: "standings",
        "scoring-env": "standings",
        share: "standings",
        universes: "standings",
        "universe-ranks": "standings",
        "universe-brackets": "standings",
        "universe-replay": "standings",
        luck: "standings",
        allpro: "standings",
        allbench: "standings",
        power: "standings",
        heat: "standings",
        race: "standings",
        desk: "standings",
        "median-tax": "standings",
        matchups: "weeks",
        trades: "moves",
        wire: "moves",
    };
    function paneId(hash) {
        const raw = (hash || "").replace(/^#/, "");
        if (!raw) {
            return panes[0].id;
        }
        if (panes.some((pane) => pane.id === raw)) {
            return raw;
        }
        return aliases[raw] || panes[0].id;
    }
    function show(hash) {
        const target = paneId(hash);
        buttons.forEach((button) => {
            button.classList.toggle("on", button.dataset.tab === target);
        });
        panes.forEach((pane) => {
            pane.hidden = pane.id !== target;
        });
        window.dispatchEvent(new Event("resize"));
    }
    window.addEventListener("hashchange", () => show(location.hash));
    show(location.hash);
}

function enableAwardTabs() {
    const tabs = document.querySelector(".js-award-tabs");
    if (!tabs) {
        return;
    }
    const panes = [...document.querySelectorAll(".js-award-pane")];
    const buttons = [...tabs.querySelectorAll("[data-tab]")];
    if (!panes.length) {
        return;
    }
    const title = document.querySelector(".js-award-title");
    function show(target) {
        buttons.forEach((button) => {
            const on = button.dataset.tab === target;
            button.classList.toggle("on", on);
            button.setAttribute("aria-pressed", on ? "true" : "false");
            if (on && title && button.dataset.title) {
                title.textContent = button.dataset.title;
            }
        });
        panes.forEach((pane) => {
            pane.hidden = pane.id !== target;
        });
    }
    tabs.addEventListener("click", (event) => {
        const button = event.target.closest("[data-tab]");
        if (!button || !tabs.contains(button)) {
            return;
        }
        show(button.dataset.tab);
    });
}

function enableSort(table) {
    const headers = [...table.tHead.querySelectorAll("th")];
    headers.forEach((header, index) => {
        header.classList.add("sortable");
        header.addEventListener("click", () => {
            const type = header.dataset.type || (header.classList.contains("num") ? "num" : "text");
            const nextDesc = header.classList.contains("sorted")
                ? !header.classList.contains("desc")
                : type === "num";
            headers.forEach((other) => other.classList.remove("sorted", "desc"));
            header.classList.add("sorted");
            if (nextDesc) {
                header.classList.add("desc");
            }
            sortBody(table.tBodies[0], index, type, nextDesc);
        });
    });
}

function sortBody(body, index, type, desc) {
    const rows = [...body.rows];
    rows.sort((left, right) => {
        const cmp = compareValues(
            cellValue(left.cells[index], type),
            cellValue(right.cells[index], type),
        );
        return desc ? -cmp : cmp;
    });
    rows.forEach((row) => body.append(row));
    paintFolds();
}

function cellValue(cell, type) {
    if (!cell) {
        return null;
    }
    if (cell.dataset.value !== undefined) {
        if (cell.dataset.value === "") {
            return null;
        }
        return type === "num" ? Number(cell.dataset.value) : cell.dataset.value.toLowerCase();
    }
    const text = cell.innerText.trim();
    if (text === "" || text === "—") {
        return null;
    }
    if (type === "num") {
        const n = Number(text.replace(/,/g, ""));
        return Number.isNaN(n) ? null : n;
    }
    return text.toLowerCase();
}

function compareValues(left, right) {
    if (left == null && right == null) {
        return 0;
    }
    if (left == null) {
        return 1;
    }
    if (right == null) {
        return -1;
    }
    if (left < right) {
        return -1;
    }
    if (left > right) {
        return 1;
    }
    return 0;
}

const filterState = { year: "all", pos: "all" };

function enableFilters() {
    const rows = [...document.querySelectorAll("[data-year], [data-year-start], [data-pos]")];
    const yearSlots = [...document.querySelectorAll(".js-year-filter")];
    const posSlots = [...document.querySelectorAll(".js-pos-filter")];
    if (!rows.length || (!yearSlots.length && !posSlots.length)) {
        paintFolds();
        return;
    }
    const urlSlot = yearSlots.find((slot) => slot.dataset.url);
    const yearBlocks = [...document.querySelectorAll(".js-year-block")];
    const years = [...new Set([
        ...rows.flatMap(rowYears),
        ...yearBlocks.map((block) => Number(block.dataset.year)),
    ].filter((year) => !Number.isNaN(year)))].sort((a, b) => b - a);
    const positions = [...new Set(rows.map((row) => row.dataset.pos).filter(Boolean))];
    positions.sort((left, right) => posRank(left) - posRank(right) || left.localeCompare(right));
    const yearButtons = new Map();
    const posButtons = new Map();
    function paint() {
        yearButtons.forEach((button, key) => {
            button.classList.toggle("on", key === filterState.year);
        });
        posButtons.forEach((button, key) => {
            button.classList.toggle("on", key === filterState.pos);
        });
        rows.forEach((row) => {
            row.hidden = !rowIsMatched(row);
        });
        yearBlocks.forEach((block) => {
            const year = Number(block.dataset.year);
            block.hidden = filterState.year !== "all" && year !== filterState.year;
        });
        document.querySelectorAll("[data-grain='career']").forEach((el) => {
            el.hidden = filterState.year !== "all";
        });
        document.querySelectorAll("table.js-fold").forEach((table) => {
            table.classList.remove("is-open");
        });
        paintFolds();
        syncYearUrl(urlSlot);
    }
    yearSlots.forEach((slot) => {
        if (!years.length) {
            return;
        }
        slot.hidden = false;
        addChip(slot, yearButtons, "all", "All years", () => {
            filterState.year = "all";
            paint();
        });
        years.forEach((year) => {
            addChip(slot, yearButtons, year, String(year), () => {
                filterState.year = year;
                paint();
            });
        });
        if (slot.dataset.default === "latest" && years.length) {
            filterState.year = years[0];
        }
    });
    posSlots.forEach((slot) => {
        if (!positions.length) {
            return;
        }
        slot.hidden = false;
        addChip(slot, posButtons, "all", "All pos", () => {
            filterState.pos = "all";
            paint();
        });
        positions.forEach((pos) => {
            addChip(slot, posButtons, pos, pos, () => {
                filterState.pos = pos;
                paint();
            });
        });
    });
    const requested = new URLSearchParams(location.search).get("year");
    if (requested === "all") {
        filterState.year = "all";
    } else if (requested && !Number.isNaN(Number(requested))) {
        filterState.year = Number(requested);
    } else if (urlSlot && urlSlot.dataset.year) {
        filterState.year = Number(urlSlot.dataset.year);
    }
    paint();
}

function syncYearUrl(slot) {
    if (!slot || !slot.dataset.url) {
        return;
    }
    const url = new URL(location.href);
    if (filterState.year === "all") {
        url.searchParams.delete("year");
    } else {
        url.searchParams.set("year", String(filterState.year));
    }
    history.replaceState(null, "", url);
}

function rowIsMatched(row) {
    return rowMatchesYear(row, filterState.year) && rowMatchesPos(row, filterState.pos);
}

function paintFolds() {
    document.querySelectorAll("table.js-fold").forEach(foldTable);
}

function foldTable(table) {
    const open = table.classList.contains("is-open");
    const limit = Number(table.dataset.fold) || 20;
    const matched = [...table.tBodies[0].rows].filter(rowIsMatched);
    matched.forEach((row, index) => {
        row.hidden = !open && index >= limit;
    });
    let more = table.nextElementSibling;
    if (!more || !more.classList.contains("js-fold-more")) {
        more = document.createElement("p");
        more.className = "note js-fold-more";
        table.after(more);
    }
    if (matched.length <= limit) {
        more.hidden = true;
        more.replaceChildren();
        return;
    }
    more.hidden = false;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = open ? `Show top ${limit}` : `Show all ${matched.length}`;
    button.addEventListener("click", () => {
        table.classList.toggle("is-open");
        foldTable(table);
    });
    more.replaceChildren(button);
}

function enableRankMode() {
    const slot = document.querySelector(".js-rank-mode");
    const panels = [...document.querySelectorAll(".js-rank")];
    if (!slot || !panels.length) {
        return;
    }
    const buttons = [...slot.querySelectorAll("button[data-mode]")];
    function show(mode) {
        buttons.forEach((button) => {
            button.classList.toggle("on", button.dataset.mode === mode);
        });
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.mode !== mode;
        });
        document.querySelectorAll("table.js-fold").forEach((table) => {
            table.classList.remove("is-open");
        });
        paintFolds();
    }
    buttons.forEach((button) => {
        button.addEventListener("click", () => show(button.dataset.mode));
    });
    show("career");
}

function addChip(slot, buttons, key, label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", onClick);
    slot.append(button);
    buttons.set(key, button);
}

function posRank(pos) {
    const order = ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF"];
    const index = order.indexOf(pos);
    return index === -1 ? order.length : index;
}

function rowMatchesPos(row, selected) {
    if (selected === "all") {
        return true;
    }
    return (row.dataset.pos || "") === selected;
}

function rowYears(row) {
    if (row.dataset.year) {
        return [Number(row.dataset.year)];
    }
    const start = Number(row.dataset.yearStart);
    if (Number.isNaN(start)) {
        return [];
    }
    const end = row.dataset.yearEnd ? Number(row.dataset.yearEnd) : start;
    const years = [];
    for (let year = start; year <= end; year += 1) {
        years.push(year);
    }
    return years;
}

function rowMatchesYear(row, selected) {
    if (selected === "all") {
        return true;
    }
    if (row.dataset.year) {
        return Number(row.dataset.year) === selected;
    }
    const start = Number(row.dataset.yearStart);
    if (Number.isNaN(start)) {
        return true;
    }
    if (!row.dataset.yearEnd) {
        return selected >= start;
    }
    return selected >= start && selected <= Number(row.dataset.yearEnd);
}

function matchIds(match) {
    return [match.dataset.homeId, match.dataset.awayId].filter(Boolean);
}

function enableBracket(tree) {
    const svg = tree.querySelector("svg.bracket-lines");
    let frame = 0;
    const paint = () => {
        if (frame) {
            return;
        }
        frame = requestAnimationFrame(() => {
            frame = 0;
            if (svg && tree.classList.contains("tree")) {
                paintBracketLines(tree, svg);
            }
            highlightBracket(tree, tree.dataset.activeManager || "");
        });
    };
    paint();
    new ResizeObserver(paint).observe(tree);
    tree.addEventListener("scroll", paint);
    window.addEventListener("resize", paint);
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(paint);
    }
    tree.addEventListener("mouseover", (event) => {
        const seed = event.target.closest(".seed");
        if (!seed || !tree.contains(seed)) {
            return;
        }
        tree.dataset.activeManager = seed.dataset.managerId || "";
        highlightBracket(tree, tree.dataset.activeManager);
    });
    tree.addEventListener("mouseleave", () => {
        delete tree.dataset.activeManager;
        highlightBracket(tree, "");
    });
}

function paintBracketLines(tree, svg) {
    const width = Math.max(tree.scrollWidth, 1);
    const height = Math.max(tree.scrollHeight, 1);
    svg.setAttribute("width", String(width));
    svg.setAttribute("height", String(height));
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.replaceChildren();
    const rounds = [...tree.querySelectorAll(":scope > .bracket-round")];
    for (let index = 0; index < rounds.length - 1; index += 1) {
        const targets = [...rounds[index + 1].querySelectorAll(".bracket-match")];
        rounds[index].querySelectorAll(".bracket-match").forEach((source) => {
            const target = nextBracketMatch(source, targets);
            if (!target) {
                return;
            }
            svg.append(bracketElbow(tree, source, target));
        });
    }
}

function nextBracketMatch(source, targets) {
    const winner = source.dataset.winnerId;
    if (winner) {
        const hit = targets.find((target) => matchIds(target).includes(winner));
        if (hit) {
            return hit;
        }
    }
    const ids = matchIds(source);
    const hits = targets.filter((target) => matchIds(target).some((id) => ids.includes(id)));
    return hits.length === 1 ? hits[0] : null;
}

function bracketElbow(tree, source, target) {
    const from = localRect(tree, source);
    const to = localRect(tree, target);
    const x1 = from.left + from.width;
    const y1 = from.top + from.height / 2;
    const x2 = to.left;
    const y2 = to.top + to.height / 2;
    const mid = (x1 + x2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} H ${mid} V ${y2} H ${x2}`);
    const shared = matchIds(source).filter((id) => matchIds(target).includes(id));
    path.dataset.managers = (shared.length ? shared : matchIds(source)).join(" ");
    return path;
}

function localRect(tree, el) {
    const box = el.getBoundingClientRect();
    const root = tree.getBoundingClientRect();
    return {
        left: box.left - root.left + tree.scrollLeft,
        top: box.top - root.top + tree.scrollTop,
        width: box.width,
        height: box.height,
    };
}

function highlightBracket(tree, managerId) {
    const on = Boolean(managerId);
    tree.classList.toggle("pathing", on);
    tree.querySelectorAll(".bracket-match").forEach((match) => {
        match.classList.toggle("on-path", on && matchIds(match).includes(managerId));
    });
    tree.querySelectorAll(".seed").forEach((seed) => {
        seed.classList.toggle("on-path", on && seed.dataset.managerId === managerId);
    });
    tree.querySelectorAll(".bracket-lines path").forEach((path) => {
        const ids = (path.dataset.managers || "").split(/\s+/);
        path.classList.toggle("on-path", on && ids.includes(managerId));
    });
}

/* === A3 loading: fragment inline upgrade (append-only) ===
   A [data-fragment] container's [data-board] links are real document URLs.
   With script they are fetched as the bare fragment and swapped in place.
   Modified clicks, other links, a missing fetch, and a failed response
   leave the navigation alone. The address bar follows only when the page
   is already that board, so a parent page is not rewritten into a board URL.
*/
(function () {
    if (typeof fetch !== "function" || typeof DOMParser !== "function") {
        return;
    }

    function elementTarget(event) {
        var node = event.target;
        if (node && node.nodeType !== 1) {
            node = node.parentElement;
        }
        return node;
    }

    function boardLink(container, link) {
        var board = container.getAttribute("data-board");
        var fragment = container.getAttribute("data-fragment");
        if (!board || !fragment || !link || !link.getAttribute("href")) {
            return null;
        }
        var url;
        try {
            url = new URL(link.getAttribute("href"), window.location.href);
        } catch (error) {
            return null;
        }
        if (url.origin !== window.location.origin || url.pathname !== board) {
            return null;
        }
        return { url: url, fragment: fragment, board: board };
    }

    function applyFragment(container, html, seq) {
        if (container._a3seq !== seq) {
            return "stale";
        }
        var parsed = new DOMParser().parseFromString(html, "text/html");
        var next = parsed.querySelector("[data-fragment]");
        if (!next || next.getAttribute("data-fragment") !== container.getAttribute("data-fragment")) {
            return "bad";
        }
        container.innerHTML = next.innerHTML;
        if (typeof enableSort === "function") {
            container.querySelectorAll("table.js-sort").forEach(enableSort);
        }
        return "ok";
    }

    function loadFragment(container, target, seq) {
        return fetch(target, {
            headers: { Accept: "text/html" },
            credentials: "same-origin",
        }).then(function (res) {
            if (!res.ok) {
                throw new Error(String(res.status));
            }
            return res.text();
        }).then(function (html) {
            return applyFragment(container, html, seq);
        });
    }

    document.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0) {
            return;
        }
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }
        var node = elementTarget(event);
        var link = node && node.closest ? node.closest("a") : null;
        if (!link || (link.target && link.target !== "_self")) {
            return;
        }
        var container = link.closest("[data-fragment]");
        if (!container) {
            return;
        }
        var match = boardLink(container, link);
        if (!match) {
            return;
        }
        event.preventDefault();
        var seq = (container._a3seq || 0) + 1;
        container._a3seq = seq;
        var target = match.fragment + match.url.search;
        loadFragment(container, target, seq).then(function (result) {
            if (container._a3seq !== seq || result === "stale") {
                return;
            }
            if (result !== "ok") {
                window.location.assign(link.href);
                return;
            }
            if (window.location.pathname === match.board && window.history && window.history.pushState) {
                window.history.pushState(
                    { board: match.board },
                    "",
                    match.url.pathname + match.url.search,
                );
            }
        }).catch(function () {
            if (container._a3seq === seq) {
                window.location.assign(link.href);
            }
        });
    });

    window.addEventListener("popstate", function () {
        var path = window.location.pathname;
        document.querySelectorAll("[data-fragment]").forEach(function (container) {
            if (container.getAttribute("data-board") !== path) {
                return;
            }
            var fragment = container.getAttribute("data-fragment");
            if (!fragment) {
                return;
            }
            var seq = (container._a3seq || 0) + 1;
            container._a3seq = seq;
            loadFragment(container, fragment + window.location.search, seq).catch(function () {
                return null;
            });
        });
    });
})();

/* === D1 players: rank recomputes on sort (append-only) ===
   Rk is the 1-based index in the current row order. enableSort reorders the
   body before this listener runs, because the header handler is registered
   first and this one is on document (bubble). Fold and the year/position
   chips do not renumber: a hidden row keeps its place in the full order.
   Players tables opt in with class js-rk and a td.rk per row. Other sorts
   are unchanged.
*/
document.addEventListener("click", function (event) {
    var node = event.target;
    if (node && node.nodeType !== 1) {
        node = node.parentElement;
    }
    if (!node || !node.closest) {
        return;
    }
    var header = node.closest("table.js-rk thead th");
    if (!header) {
        return;
    }
    var table = header.closest("table");
    var body = table && table.tBodies && table.tBodies[0];
    if (!body) {
        return;
    }
    Array.prototype.forEach.call(body.rows, function (row, index) {
        var cell = row.querySelector(".rk");
        if (cell) {
            cell.textContent = String(index + 1);
        }
    });
});
