# Nu Choate League

This project keeps fantasy football history in one place after the league moved from ESPN (2022–2023) to Sleeper (2024 onward).

You do **not** need to know how to code to get a working copy on your computer. Ctrl-C and Ctrl-V are all you need to get something out of this.

**What you end up with**

1. Raw season files on your machine (`data/`, not stored in GitHub).
2. A local database (Postgres, running in Docker).
3. Commands that load those files into the database and print standings, career records, drafts, and trades.

The public website / wiki / newsletters are later. This branch is the data warehouse.

## What to install first

Install these three things, then restart your computer if Docker asks you to.

| Tool | What it is | Where |
| --- | --- | --- |
| [Git](https://git-scm.com/downloads) | Downloads this project | Any default installer is fine |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Runs the database in a container | Use the default settings; wait until it says it is running |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Installs Python and this project's libraries | Follow the uv install page for your OS |

You need **Python 3.14**. You do not have to install Python by hand. After `uv` works, the setup commands below will fetch 3.14 for you.

Open a terminal:

- Windows: PowerShell
- Mac: Terminal

## First-time setup

**1. Download the project** (this overhaul lives on the `feat/complete-overhaul` branch):

```text
git clone -b feat/complete-overhaul https://github.com/Quadram13/nu_choate_league.git
cd nu_choate_league
```

If you already cloned the old site, run this inside the folder instead:

```text
git fetch
git checkout feat/complete-overhaul
git pull
```

**2. Create your private settings file**

Copy the example file to `.env`. Git ignores `.env` so your password and ESPN cookies never go to GitHub.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Mac / Linux:

```bash
cp .env.example .env
```

Open `.env` in a text editor. You can leave the database password as `change-me` for local use. If you change it, change it in **both** `POSTGRES_PASSWORD` and `DATABASE_URL`.

League ids are already filled in. ESPN cookies can stay blank until you dump 2022–2023.

**3. Start the database**

Docker Desktop must be running.

```text
docker compose up -d
```

The first time this downloads Postgres. The database is on your machine at port **5433** (not the usual 5432, so it does not fight a Windows Postgres install).

**4. Install this project's Python tools**

```text
uv python install 3.14
uv sync
```

That creates a local `.venv` folder. You never have to activate it by hand if you start commands with `uv run`.

## Get the league data

The dumps are **not** in GitHub. Each person either downloads them again or copies a `data/` folder from someone who already dumped.

Sleeper needs no login. ESPN needs cookies from a browser that can still open those old leagues.

**Sleeper (2024, 2025, 2026)** — do this first; it is enough to try `load` if someone else already has ESPN files to share:

```text
uv run sleeper-dumper --fetch-players
```

`--fetch-players` also downloads the NFL player catalog (`data/sleeper/players/nfl.json`). That file is required for ingest.

**ESPN (2022, 2023)**

1. In Chrome, open [espn.com](https://www.espn.com) while logged into the account that can see the old leagues.
2. Press `F12` (or right-click → Inspect).
3. Open the **Application** tab → **Cookies** → `https://www.espn.com`.
4. Copy `espn_s2` into `ESPN_S2` in `.env` (keep the `%` encoding if it is there).
5. Copy `SWID` into `ESPN_SWID` and **keep the curly braces**.
6. Run:

```text
uv run espn-dumper
```

That writes `data/espn/2022/` and `data/espn/2023/`. You will see a **404** for league communication (`COMMUNICATION_GROUP_NOT_FOUND`). ESPN does not keep a message board for these leagues. The rest of the dump is still good — ignore that one error.

If you already have a complete `data/` folder from someone else, skip dumping. Put it in this project as `data/espn/...` and `data/sleeper/...`.

## Load and look around

```text
uv run nu-choate-league inspect-managers
uv run nu-choate-league load
uv run nu-choate-league query career
uv run nu-choate-league query h2h --manager marcus-du
uv run nu-choate-league query draft --year 2025
uv run nu-choate-league query moves --year 2024
uv run nu-choate-league query record-weeks
```

`load` reads `data/`, writes fact tables, then creates the analysis views. Re-run it after a new dump.

`inspect-managers` should say every owner in the dumps is mapped. If it fails, a new Sleeper user is missing from `maps/managers.yaml`.

Other useful commands:

```text
uv run nu-choate-league standings 2023
uv run nu-choate-league standings 2025
uv run nu-choate-league load --year 2025
```

## If something breaks

| What you see | Likely cause |
| --- | --- |
| `Missing DATABASE_URL` | No `.env`. Copy `.env.example` to `.env`. |
| `role "nu_choate" does not exist` | Talking to a different Postgres on 5432. This project uses **5433**. Check `DATABASE_URL`. |
| `docker compose` cannot start | Docker Desktop is not running, or port 5433 is already in use. |
| `No seasons to load` / missing dump directory | `data/` is empty. Run the dumpers or copy dumps from a teammate. |
| ESPN dump 401 / 403 | Cookies expired. Copy `espn_s2` and `SWID` again. |
| ESPN dump 404 for communication / `COMMUNICATION_GROUP_NOT_FOUND` | Expected. There is no league chat to download. Keep going. |
| `inspect-managers` fails | New league member. Add them to `maps/managers.yaml`. |
| Python version error | Run `uv python install 3.14` then `uv sync` again. |

To stop the database later: `docker compose down`. Data stays in a Docker volume until you delete it on purpose.

## What not to commit

Never add these to git:

- `.env` (passwords and ESPN cookies)
- `data/` (raw dumps)
- `.venv/` (local Python install)

`uv.lock`, `.env.example`, `maps/`, and `sql/` **should** be committed.

## Layout (for people who want to change code)

```text
maps/          identity: managers, seasons, D/ST
data/          gitignored dumps: espn/{year}/, sleeper/{year}/
sql/facts.sql  tables
sql/analysis.sql  views (career, H2H, draft, trades, …)
src/nu_choate_league/  dump, ingest, load, query
compose.yaml   Postgres 17 on localhost:5433
```

Dumps stay raw JSON. Python ingest turns them into rows. Analysis is SQL views, not a second copy of `career.json`.
