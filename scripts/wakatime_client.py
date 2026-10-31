"""WakaTime REST API client with local cache stored in metrics/ directory."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

import httpx

from .models import WakaStat


class WakaTimeClient:
    """Fetches user metrics from WakaTime API with fallback cache in metrics/."""

    API_URL = "https://wakatime.com/api/v1/users/current/stats/last_7_days"
    CACHE_PATH = "metrics/wakatime_cache.json"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def get_stats(self, limit: int = 5) -> list[WakaStat]:
        if self._api_key:
            try:
                stats = self._fetch_from_api(limit)
                if stats:
                    self._save_cache(stats)
                    return stats
            except Exception as err:
                print(f"Warning: WakaTime API request failed ({err}); falling back to cache.", file=sys.stderr)

        return self._fetch_from_cache(limit)

    def _fetch_from_api(self, limit: int) -> list[WakaStat]:
        res = httpx.get(
            self.API_URL,
            auth=(self._api_key or "", ""),
            timeout=15.0,
        )
        res.raise_for_status()
        data = res.json()

        raw_languages = data.get("data", {}).get("languages", [])
        return [
            WakaStat(
                name=item["name"],
                time_text=item["text"],
                percent=float(item["percent"]),
            )
            for item in raw_languages[:limit]
        ]

    def _save_cache(self, stats: list[WakaStat]) -> None:
        try:
            os.makedirs(os.path.dirname(self.CACHE_PATH), exist_ok=True)
            with open(self.CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump([asdict(s) for s in stats], f, indent=2)
        except Exception as err:
            print(f"Warning: Could not save wakatime cache: {err}", file=sys.stderr)

    def _fetch_from_cache(self, limit: int) -> list[WakaStat]:
        if os.path.exists(self.CACHE_PATH):
            try:
                with open(self.CACHE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return [WakaStat(**item) for item in data[:limit]]
            except Exception as err:
                print(f"Warning: Could not read wakatime cache ({err}).", file=sys.stderr)

        print("Warning: No WakaTime stats available from API or cache; degrading gracefully.", file=sys.stderr)
        return []
