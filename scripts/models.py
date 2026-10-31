"""Domain models and telemetry value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WakaStat:
    """Represents programming metrics for a specific language."""
    name: str
    time_text: str
    percent: float


@dataclass(frozen=True)
class PhotoMetadata:
    """Represents Unsplash photo attribution and asset URLs."""
    image_url: str
    page_url: str
    author_name: str
    author_url: str
    dominant_color: str | None
    alt_description: str


@dataclass(frozen=True)
class PlacementMetrics:
    """Stores smart corner analysis, luminance scores, and algorithmic decision rationale."""
    wakatime_box_luminance: dict[str, float]
    attribution_strip_luminance: dict[str, float]
    primary_corner: str
    secondary_corner: str | None
    merged_attribution: bool
    adaptive_dim_percent: int
    wakatime_reasoning: str
    attribution_reasoning: str


@dataclass(frozen=True)
class PerformanceMetrics:
    """Stores execution timing and resource metrics in milliseconds."""
    unsplash_api_ms: float
    image_download_ms: float
    wakatime_fetch_ms: float
    render_ms: float
    total_execution_ms: float
    banner_size_kb: float
