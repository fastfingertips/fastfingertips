"""Unsplash REST API client and high-resolution raw asset downloader."""

from __future__ import annotations

from io import BytesIO

import httpx
from PIL import Image, ImageColor

from .models import PhotoMetadata


class UnsplashClient:
    """Client for querying Unsplash REST API and downloading pristine raw assets."""

    API_ENDPOINT = "https://api.unsplash.com/photos/random"
    DEFAULT_QUERY = "nature,minimal,landscape,architecture"
    APP_NAME = "fastfingertips_profile_readme"

    def __init__(self, token: str) -> None:
        self._token = token

    @staticmethod
    def append_utm(url: str) -> str:
        return str(
            httpx.URL(url).copy_merge_params({
                "utm_source": UnsplashClient.APP_NAME,
                "utm_medium": "referral",
            })
        )

    def fetch_photo_metadata(
        self,
        collections: list[str] | None = None,
        query: str | None = None,
        exclude_urls: set[str] | None = None,
    ) -> PhotoMetadata:
        params: dict[str, str | int] = {
            "orientation": "landscape",
            "content_filter": "high",
            "count": 5,
        }
        if collections:
            params["collections"] = ",".join(collections)
        elif query:
            params["query"] = query or self.DEFAULT_QUERY

        res = httpx.get(
            self.API_ENDPOINT,
            params=params,
            headers={
                "Authorization": f"Client-ID {self._token}",
                "Accept-Version": "v1",
                "User-Agent": self.APP_NAME,
            },
            timeout=15.0,
        )
        res.raise_for_status()
        raw_payload = res.json()

        candidates = raw_payload if isinstance(raw_payload, list) else [raw_payload]
        excluded = exclude_urls or set()
        data = next(
            (item for item in candidates if self.append_utm(item["links"]["html"]) not in excluded),
            candidates[0],
        )

        # Use 'raw' URL instead of pre-compressed 1080p 'regular' URL to avoid double compression
        return PhotoMetadata(
            image_url=data["urls"]["raw"],
            page_url=self.append_utm(data["links"]["html"]),
            author_name=data["user"]["name"],
            author_url=self.append_utm(data["user"]["links"]["html"]),
            dominant_color=data.get("color"),
            alt_description=data.get("alt_description") or "Unsplash photo",
        )

    def download_image(self, image_url: str, width: int = 2400) -> Image.Image:
        """Downloads the uncompressed 2K Retina source image from Unsplash raw stream."""
        res = httpx.get(
            image_url,
            params={"w": width, "q": 100, "fm": "png", "fit": "max"},
            headers={"User-Agent": self.APP_NAME},
            follow_redirects=True,
            timeout=30.0,
        )
        res.raise_for_status()
        return Image.open(BytesIO(res.content)).convert("RGBA")

    @staticmethod
    def calculate_adaptive_dim(hex_color: str | None) -> int:
        """Calculates perceived luminance (ITU-R BT.709) and maps to 0% - 40% dimming."""
        if not hex_color:
            return 20
        try:
            r, g, b = ImageColor.getrgb(hex_color if hex_color.startswith("#") else f"#{hex_color}")[:3]
        except ValueError:
            return 20
        luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        if luminance <= 0.15:
            return 0
        return min(40, max(0, round((luminance - 0.15) * 50)))
