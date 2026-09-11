from __future__ import annotations

import time
from typing import Any

import requests
from requests.exceptions import RequestException

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"


class EspnClient:
    def __init__(self, year: int, league_id: int, espn_s2: str, swid: str) -> None:
        self.year = year
        self.league_id = league_id
        self.cookies = {"espn_s2": espn_s2, "SWID": swid}
        self.session = requests.Session()
        if year < 2018:
            self.league_url = f"{BASE}/leagueHistory/{league_id}"
            self.league_params: dict[str, Any] = {"seasonId": year}
        else:
            self.league_url = f"{BASE}/seasons/{year}/segments/0/leagues/{league_id}"
            self.league_params = {}
        self.season_url = f"{BASE}/seasons/{year}"

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            started = time.perf_counter()
            print(f"  GET {url}", flush=True)
            try:
                response = self.session.get(
                    url,
                    params=params or None,
                    headers=headers,
                    cookies=self.cookies,
                    timeout=(3, 60),
                )
            except RequestException as exc:
                last_error = exc
                print(f"    failed after {time.perf_counter() - started:.1f}s: {exc}", flush=True)
                if attempt < 3:
                    time.sleep(2 * attempt)
                continue

            elapsed = time.perf_counter() - started
            print(
                f"    {response.status_code} in {elapsed:.1f}s ({len(response.content)} bytes)",
                flush=True,
            )
            try:
                payload: Any = response.json()
            except ValueError:
                payload = {"_dump_text": response.text}

            if response.status_code != 200:
                return {
                    "_dump_error": {
                        "status": response.status_code,
                        "url": response.url,
                    },
                    "body": payload,
                }
            return payload

        return {
            "_dump_error": {
                "status": None,
                "url": url,
                "message": str(last_error),
            }
        }

    def league(
        self,
        *,
        views: list[str] | str | None = None,
        scoring_period: int | None = None,
        headers: dict[str, str] | None = None,
        extend: str = "",
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = dict(self.league_params)
        if extra_params:
            params.update(extra_params)
        if views is not None:
            params["view"] = views
        if scoring_period is not None:
            params["scoringPeriodId"] = scoring_period
        payload = self.get(self.league_url + extend, params=params, headers=headers)
        # Pre-2018 leagueHistory returns a one-element list.
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        return payload

    def season(
        self,
        *,
        views: list[str] | str | None = None,
        headers: dict[str, str] | None = None,
        extend: str = "",
        extra_params: dict[str, Any] | None = None,
    ) -> Any:
        params: dict[str, Any] = dict(extra_params or {})
        if views is not None:
            params["view"] = views
        return self.get(self.season_url + extend, params=params or None, headers=headers)
