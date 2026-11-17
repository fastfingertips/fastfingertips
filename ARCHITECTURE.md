# Architecture

This document outlines the pipeline, data sources, and tools used to build and update the daily 2K profile banner.

---

## How It Works

Every day at 06:00 UTC, a GitHub Actions workflow executes the following pipeline:

```
[Unsplash] ───> Random Photo ──────────┐
                                       ├──> [Pillow] Contrast Placement ──> [2K WebP Banner]
[WakaTime] ───> 7-Day Coding Stats ────┘            │
                                                    └──> [Telemetry JSON]
                                                                │
                                                                ▼
                                                        [Bash & jq Script]
                                                                ├──> Update README.md
                                                                └──> Git Commit Amend (Zero Bloat)
```

1. **Photo Acquisition**: Fetches a landscape image from an Unsplash collection. A 5-entry history log prevents consecutive repeats.
2. **Stats Retrieval**: Queries the top 5 languages and hours coded in the last 7 days from WakaTime.
3. **Contrast-Aware Placement**:
   - Analyzes corner brightness across four regions.
   - Places the 6-line WakaTime block in the darkest corner for natural readability without artificial dark backdrops.
   - Places the photographer attribution in a separate dark corner, or stacks it under WakaTime if remaining corners are too bright.
4. **2K Lossless Export**: Renders at 2400px width and saves directly to `assets/profile-banner.webp` in WebP format (`quality=100, lossless=True`).
5. **Telemetry Logging**: Writes luminance values, placement rationale, and execution times to `metrics/banner_telemetry.json`.
6. **Repository Update**: Updates `README.md` with a timestamp query parameter (`?v=...`) to invalidate GitHub CDN caching, then amends the previous bot commit to prevent repository size bloat.

---

## Technologies

- **Python 3.12**: Core banner orchestration and rendering.
- **Pillow**: Image resizing, corner luminance calculation, and typography drawing.
- **HTTPX**: API requests with connection pooling and automatic retries.
- **Bash & jq**: README marker replacement and zero-bloat Git synchronization.
- **GitHub Actions**: Scheduled daily cron workflow with a 5-minute timeout.
- **Dependabot**: Monthly grouped updates for GitHub Actions.

---

## Services & Data Sources

- **Unsplash API**: Random photo endpoint filtered by collection [PRzhB2kfOhc](https://unsplash.com/collections/PRzhB2kfOhc).
- **WakaTime API**: Weekly coding statistics endpoint for [@fastfingertips](https://wakatime.com/@fastfingertips).
