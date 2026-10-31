"""Profile Orchestrator with 2K Lossless WebP rendering, performance benchmarking, and telemetry export."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from scripts.models import PerformanceMetrics, PhotoMetadata, PlacementMetrics
from scripts.unsplash_client import UnsplashClient
from scripts.wakatime_client import WakaTimeClient
from scripts.renderer import BannerRenderer


class ProfileOrchestrator:
    """Orchestrates pipeline execution, 2K Lossless WebP asset generation, telemetry export, and README sync."""

    README_FILE = "README.md"
    BANNER_ASSET_PATH = "assets/profile-banner.webp"
    TELEMETRY_PATH = "metrics/banner_telemetry.json"
    START_MARKER = "<!-- UNSPLASH:START -->"
    END_MARKER = "<!-- UNSPLASH:END -->"
    MAX_RECENT_HISTORY = 5

    def __init__(
        self,
        unsplash_token: str,
        wakatime_key: str | None = None,
        collections_input: str | None = None,
        query_input: str | None = None,
    ) -> None:
        self._unsplash = UnsplashClient(unsplash_token)
        self._wakatime = WakaTimeClient(wakatime_key)
        self._renderer = BannerRenderer()
        self._collections = self._parse_collections(collections_input) if collections_input else None
        self._query = query_input

    @staticmethod
    def _parse_collections(raw_str: str) -> list[str]:
        ids: list[str] = []
        for item in raw_str.split(","):
            token = item.strip()
            if not token:
                continue
            m = re.search(r"collections/([a-zA-Z0-9_-]+)", token)
            ids.append(m.group(1) if m else token)
        return ids

    def _load_recent_photos(self) -> list[str]:
        if not os.path.exists(self.TELEMETRY_PATH):
            return []
        try:
            with open(self.TELEMETRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            history = list(data.get("recent_photos", []))
            last_url = data.get("photo", {}).get("page_url")
            if last_url and last_url not in history:
                history.insert(0, last_url)
            return history[: self.MAX_RECENT_HISTORY]
        except Exception:
            return []

    def run(self) -> None:
        t_total_start = time.perf_counter()
        recent_history = self._load_recent_photos()

        # 1. Fetch Photo Metadata (Raw Stream with Deduplication)
        t0 = time.perf_counter()
        photo = self._unsplash.fetch_photo_metadata(
            self._collections,
            self._query,
            exclude_urls=set(recent_history),
        )
        dim = self._unsplash.calculate_adaptive_dim(photo.dominant_color)
        unsplash_api_ms = round((time.perf_counter() - t0) * 1000, 2)
        print(f"Photo retrieved by {photo.author_name} in {unsplash_api_ms}ms (Color: {photo.dominant_color}, Dim: {dim}%)")

        # 2. Download Uncompressed 2K Source Image
        t0 = time.perf_counter()
        raw_img = self._unsplash.download_image(photo.image_url, width=2400)
        image_download_ms = round((time.perf_counter() - t0) * 1000, 2)

        # 3. Retrieve WakaTime metrics
        t0 = time.perf_counter()
        stats = self._wakatime.get_stats(limit=5)
        wakatime_fetch_ms = round((time.perf_counter() - t0) * 1000, 2)
        print(f"Retrieved {len(stats)} language metrics from WakaTime in {wakatime_fetch_ms}ms.")

        # 4. Render 2K Retina Composite Banner
        t0 = time.perf_counter()
        composite_banner, placement_metrics = self._renderer.render(raw_img, photo, stats, dim)
        render_ms = round((time.perf_counter() - t0) * 1000, 2)

        # 5. Save Generated Banner Asset as 100% Lossless WebP (Zero Compression Artifacts)
        os.makedirs(os.path.dirname(self.BANNER_ASSET_PATH), exist_ok=True)
        composite_banner.save(self.BANNER_ASSET_PATH, format="WEBP", lossless=True, quality=100, method=4)
        banner_size_kb = round(os.path.getsize(self.BANNER_ASSET_PATH) / 1024, 2)
        print(f"Saved 2K Lossless WebP composite banner ({banner_size_kb} KB) to {self.BANNER_ASSET_PATH}")

        # 6. Synchronize README.md Reference
        self._update_readme(photo)

        total_execution_ms = round((time.perf_counter() - t_total_start) * 1000, 2)

        # 7. Export Telemetry & Performance Report
        perf_metrics = PerformanceMetrics(
            unsplash_api_ms=unsplash_api_ms,
            image_download_ms=image_download_ms,
            wakatime_fetch_ms=wakatime_fetch_ms,
            render_ms=render_ms,
            total_execution_ms=total_execution_ms,
            banner_size_kb=banner_size_kb,
        )
        self._export_telemetry(photo, placement_metrics, perf_metrics, recent_history)
        self._write_step_summary(photo, placement_metrics, perf_metrics)
        print(f"Exported telemetry to {self.TELEMETRY_PATH} (Total time: {total_execution_ms}ms).")

    def _export_telemetry(
        self,
        photo: PhotoMetadata,
        placement: PlacementMetrics,
        perf: PerformanceMetrics,
        recent_history: list[str],
    ) -> None:
        os.makedirs(os.path.dirname(self.TELEMETRY_PATH), exist_ok=True)
        updated_history = [photo.page_url] + [u for u in recent_history if u != photo.page_url]
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "photo": asdict(photo),
            "placement": asdict(placement),
            "performance": asdict(perf),
            "recent_photos": updated_history[: self.MAX_RECENT_HISTORY],
        }
        with open(self.TELEMETRY_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _write_step_summary(
        photo: PhotoMetadata,
        placement: PlacementMetrics,
        perf: PerformanceMetrics,
    ) -> None:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return

        waka_scores = ", ".join(f"`{k}: {v}`" for k, v in placement.wakatime_box_luminance.items())
        attr_scores = ", ".join(f"`{k}: {v}`" for k, v in placement.attribution_strip_luminance.items())

        summary_md = (
            "## Daily Profile Banner Telemetry\n\n"
            "| Metric | Value |\n"
            "| :--- | :--- |\n"
            f"| **Photographer** | [{photo.author_name}]({photo.author_url}) ([Unsplash]({photo.page_url})) |\n"
            f"| **Dominant Color / Dimming** | `{photo.dominant_color}` / `{placement.adaptive_dim_percent}%` |\n"
            f"| **WakaTime Corner** | `{placement.primary_corner}` ({waka_scores}) |\n"
            f"| **Attribution Corner** | `{placement.secondary_corner}` (Merged: `{placement.merged_attribution}`, {attr_scores}) |\n"
            f"| **Asset Size (2K WebP)** | `{perf.banner_size_kb} KB` |\n"
            f"| **Execution Time** | `{perf.total_execution_ms} ms` (API: `{perf.unsplash_api_ms} ms`, DL: `{perf.image_download_ms} ms`, Render: `{perf.render_ms} ms`) |\n\n"
            "### Algorithmic Placement Rationale\n"
            f"- **WakaTime Block:** {placement.wakatime_reasoning}\n"
            f"- **Photo Attribution:** {placement.attribution_reasoning}\n"
        )
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(summary_md)

    def _update_readme(self, photo: PhotoMetadata) -> None:
        if not os.path.exists(self.README_FILE):
            raise FileNotFoundError(f"{self.README_FILE} not found.")

        with open(self.README_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        version_tag = int(datetime.now(timezone.utc).timestamp())
        asset_url = f"{self.BANNER_ASSET_PATH}?v={version_tag}"

        new_block = (
            f"{self.START_MARKER}\n"
            f'  <a href="{photo.page_url}">\n'
            f'    <img src="{asset_url}" alt="{photo.alt_description}" width="100%" style="border-radius: 8px;" />\n'
            f"  </a>\n"
            f"  {self.END_MARKER}"
        )

        pattern = re.compile(f"{re.escape(self.START_MARKER)}.*?{re.escape(self.END_MARKER)}", re.DOTALL)
        if not pattern.search(content):
            raise ValueError(f"Markers not found in {self.README_FILE}")

        updated_content = pattern.sub(new_block, content)
        with open(self.README_FILE, "w", encoding="utf-8") as f:
            f.write(updated_content)


def main() -> None:
    unsplash_token = os.environ.get("UNSPLASH_TOKEN")
    if not unsplash_token:
        print("Error: 'UNSPLASH_TOKEN' environment variable is required.", file=sys.stderr)
        sys.exit(1)

    wakatime_key = os.environ.get("WAKATIME_API_KEY")
    collections_input = os.environ.get("UNSPLASH_COLLECTIONS")
    query_input = os.environ.get("UNSPLASH_QUERY")

    try:
        orchestrator = ProfileOrchestrator(
            unsplash_token=unsplash_token,
            wakatime_key=wakatime_key,
            collections_input=collections_input,
            query_input=query_input,
        )
        orchestrator.run()
    except Exception as err:
        print(f"Fatal error during banner generation: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
