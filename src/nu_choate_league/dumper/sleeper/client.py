from __future__ import annotations

import time
from typing import Any

import requests
from requests.exceptions import RequestException

BASE = "https://api.sleeper.app/v1"


class SleeperClient:
    def get(self, path: str) -> Any:
        url = path if path.startswith("http") else f"{BASE}{path}"
        last_error: Exception | None = None
        for attempt in range(1, 4):
            started = time.perf_counter()
            print(f"  GET {url}", flush=True)
            try:
                response = requests.get(url, timeout=(3, 120))
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
