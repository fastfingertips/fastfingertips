"""Banner rendering engine at 2K Retina (2400px) resolution with algorithmic rationale generation."""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont, ImageStat

from .models import PhotoMetadata, PlacementMetrics, WakaStat


class BannerRenderer:
    """Renders 2K (2400px) ultra-crisp composite banner with dual-ROI luminance ranking and decision notes."""

    FONT_DIR = "assets/fonts"
    LIGHT_FONT_PATH = os.path.join(FONT_DIR, "Roboto-Light.ttf")

    BRIGHTNESS_MERGE_THRESHOLD = 115.0
    VERTICAL_BALANCE_BONUS = 18.0
    SCALE = 2  # 2x Retina HiDPI scale (2400px width)

    CORNER_NAMES = {
        "TL": "Top-Left",
        "TR": "Top-Right",
        "BL": "Bottom-Left",
        "BR": "Bottom-Right",
    }

    @classmethod
    def _load_font(cls, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        scaled_size = size * cls.SCALE
        if os.path.exists(cls.LIGHT_FONT_PATH):
            try:
                return ImageFont.truetype(cls.LIGHT_FONT_PATH, scaled_size)
            except Exception:
                pass

        candidates = [
            "segoeui.ttf",
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, scaled_size)
            except Exception:
                continue
        return ImageFont.load_default()

    def rank_wakatime_corners(self, image: Image.Image) -> tuple[list[tuple[str, float]], tuple[int, int]]:
        """Measures average brightness in the WakaTime occupation box across 4 corners."""
        w, h = image.size
        roi_w = min(320 * self.SCALE, int(w * 0.27))
        roi_h = min(185 * self.SCALE, int(h * 0.28))

        corners = {
            "TL": image.crop((0, 0, roi_w, roi_h)),
            "TR": image.crop((w - roi_w, 0, w, roi_h)),
            "BL": image.crop((0, h - roi_h, roi_w, h)),
            "BR": image.crop((w - roi_w, h - roi_h, w, h)),
        }

        brightness = {name: round(ImageStat.Stat(crop.convert("L")).mean[0], 2) for name, crop in corners.items()}
        ranked = sorted(brightness.items(), key=lambda item: item[1])
        print(f"WakaTime Block ROI Ranking (Darkest -> Brightest): {dict(ranked)}")
        return ranked, (roi_w, roi_h)

    def rank_attribution_corners(
        self,
        image: Image.Image,
        exclude_corner: str,
    ) -> tuple[list[tuple[str, float]], dict[str, float], tuple[int, int]]:
        """Measures average brightness specifically in the thin 1-line strip for 'Photo by'."""
        w, h = image.size
        strip_w = min(260 * self.SCALE, int(w * 0.22))
        strip_h = 48 * self.SCALE

        strips = {
            "BL": image.crop((0, h - strip_h, strip_w, h)),
            "BR": image.crop((w - strip_w, h - strip_h, w, h)),
            "TL": image.crop((0, 0, strip_w, strip_h)),
            "TR": image.crop((w - strip_w, 0, w, strip_h)),
        }

        raw_scores: dict[str, float] = {}
        for name, crop in strips.items():
            if name == exclude_corner:
                continue
            raw_scores[name] = round(ImageStat.Stat(crop.convert("L")).mean[0], 2)

        waka_is_top = "T" in exclude_corner
        ranked = sorted(
            raw_scores.items(),
            key=lambda item: item[1] - (self.VERTICAL_BALANCE_BONUS if (("B" in item[0]) == waka_is_top) else 0.0),
        )
        print(f"Attribution Strip ROI Scores: {raw_scores} -> Best balanced choice: '{ranked[0][0]}'")
        return ranked, raw_scores, (strip_w, strip_h)

    @classmethod
    def _build_wakatime_rationale(
        cls,
        ranked: list[tuple[str, float]],
        roi_size: tuple[int, int],
    ) -> str:
        best_code, best_lum = ranked[0]
        runner_code, runner_lum = ranked[1]
        brightest_code, brightest_lum = ranked[-1]
        diff = round(runner_lum - best_lum, 2)
        roi_w, roi_h = roi_size

        return (
            f"Scanned {roi_w}x{roi_h}px ROI boxes across all 4 corners to fit the 6-line WakaTime block. "
            f"{cls.CORNER_NAMES[best_code]} ({best_code}) recorded the lowest mean luminance ({best_lum}/255) "
            f"— {diff} pts darker than the runner-up {cls.CORNER_NAMES[runner_code]} ({runner_lum}) and "
            f"{round(brightest_lum - best_lum, 2)} pts darker than the brightest corner {cls.CORNER_NAMES[brightest_code]} ({brightest_lum}) "
            f"— providing maximum contrast for crisp white typography."
        )

    @classmethod
    def _build_attribution_rationale(
        cls,
        primary_corner: str,
        secondary_corner: str,
        secondary_lum: float,
        raw_scores: dict[str, float],
        strip_size: tuple[int, int],
        merged: bool,
    ) -> str:
        strip_w, strip_h = strip_size
        scores_str = ", ".join(f"{k}: {v}" for k, v in raw_scores.items())

        if merged:
            return (
                f"Scanned {strip_w}x{strip_h}px horizontal strips across the 3 remaining corners for the 1-line 'Photo by' attribution ({scores_str}). "
                f"Even the darkest alternative, {cls.CORNER_NAMES[secondary_corner]} ({secondary_lum}/255), exceeded the brightness safety threshold "
                f"({cls.BRIGHTNESS_MERGE_THRESHOLD}/255). To prevent text washout against bright backgrounds, the attribution was stacked directly "
                f"beneath the WakaTime block in {cls.CORNER_NAMES[primary_corner]} ({primary_corner})."
            )

        waka_is_top = "T" in primary_corner
        sec_is_bottom = "B" in secondary_corner
        balance_note = (
            f"Additionally, because WakaTime occupies the upper region ({primary_corner}), the lower strip ({secondary_corner}) was prioritized "
            f"with a -{cls.VERTICAL_BALANCE_BONUS} luminance weight bonus to preserve vertical visual balance."
            if (waka_is_top and sec_is_bottom)
            else f"{cls.CORNER_NAMES[secondary_corner]} ({secondary_corner}) offered the optimal balance of visual composition and dark-ground contrast."
        )

        return (
            f"Scanned {strip_w}x{strip_h}px horizontal strips across the 3 remaining corners for the 1-line 'Photo by' attribution ({scores_str}). "
            f"The {cls.CORNER_NAMES[secondary_corner]} ({secondary_corner}) strip provided sufficient darkness ({secondary_lum}/255) for clean legibility. "
            f"{balance_note}"
        )

    @classmethod
    def _draw_clean_text(
        cls,
        draw: ImageDraw.ImageDraw,
        pos: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        fill: tuple[int, int, int, int],
    ) -> None:
        """Draws 2K Retina crisp text with a delicate micro-shadow."""
        x, y = pos
        s = cls.SCALE
        draw.text((x + s, y + s), text, font=font, fill=(0, 0, 0, 175))
        draw.text((x, y + s), text, font=font, fill=(0, 0, 0, 130))
        draw.text((x, y), text, font=font, fill=fill)

    def render(
        self,
        base_image: Image.Image,
        metadata: PhotoMetadata,
        stats: list[WakaStat],
        dim_percent: int,
    ) -> tuple[Image.Image, PlacementMetrics]:
        target_width = 1200 * self.SCALE  # 2400px 2K Retina
        aspect_ratio = base_image.height / base_image.width
        target_height = int(target_width * aspect_ratio)

        max_h = 650 * self.SCALE
        min_h = 450 * self.SCALE
        if target_height > max_h:
            target_height = max_h
        elif target_height < min_h:
            target_height = min_h

        image = base_image.resize((target_width, target_height), Image.Resampling.LANCZOS)

        if dim_percent > 0:
            alpha = int((dim_percent / 100.0) * 255)
            overlay = Image.new("RGBA", image.size, (0, 0, 0, alpha))
            image = Image.alpha_composite(image, overlay)

        waka_ranked, waka_roi_size = self.rank_wakatime_corners(image)
        primary_corner, _ = waka_ranked[0]

        attr_ranked, attr_raw_scores, attr_strip_size = self.rank_attribution_corners(
            image, exclude_corner=primary_corner
        )
        secondary_corner, secondary_lum = attr_ranked[0]

        merge_attribution = secondary_lum > self.BRIGHTNESS_MERGE_THRESHOLD

        waka_rationale = self._build_wakatime_rationale(waka_ranked, waka_roi_size)
        attr_rationale = self._build_attribution_rationale(
            primary_corner=primary_corner,
            secondary_corner=secondary_corner,
            secondary_lum=secondary_lum,
            raw_scores=attr_raw_scores,
            strip_size=attr_strip_size,
            merged=merge_attribution,
        )

        print(f"WakaTime Rationale: {waka_rationale}")
        print(f"Attribution Rationale: {attr_rationale}")

        text_canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_canvas)

        if stats:
            self._draw_stats_and_attribution(
                draw=draw,
                image_size=image.size,
                stats=stats,
                author_name=metadata.author_name,
                primary_corner=primary_corner,
                secondary_corner=None if merge_attribution else secondary_corner,
            )
        else:
            self._draw_single_attribution(draw, image.size, metadata.author_name, primary_corner)

        final_composite = Image.alpha_composite(image, text_canvas).convert("RGB")

        placement_metrics = PlacementMetrics(
            wakatime_box_luminance={k: v for k, v in waka_ranked},
            attribution_strip_luminance=attr_raw_scores,
            primary_corner=primary_corner,
            secondary_corner=None if merge_attribution else secondary_corner,
            merged_attribution=merge_attribution,
            adaptive_dim_percent=dim_percent,
            wakatime_reasoning=waka_rationale,
            attribution_reasoning=attr_rationale,
        )
        return final_composite, placement_metrics

    def _draw_stats_and_attribution(
        self,
        draw: ImageDraw.ImageDraw,
        image_size: tuple[int, int],
        stats: list[WakaStat],
        author_name: str,
        primary_corner: str,
        secondary_corner: str | None,
    ) -> None:
        width, height = image_size
        s = self.SCALE
        font_body = self._load_font(13)
        font_header = self._load_font(12)
        font_attr = self._load_font(11)

        margin_x = 36 * s
        margin_y = 30 * s
        line_height = 24 * s

        merged = secondary_corner is None
        total_lines = len(stats) + 1 + (1 if merged else 0)
        extra_gap = (8 * s) if merged else 0

        is_top = "T" in primary_corner
        is_left = "L" in primary_corner

        if is_top:
            start_y = margin_y
        else:
            start_y = height - margin_y - (total_lines * line_height) - extra_gap

        # 1. Header
        header_text = "WAKATIME · LAST 7 DAYS"
        header_bbox = draw.textbbox((0, 0), header_text, font=font_header)
        header_w = header_bbox[2] - header_bbox[0]
        header_x = margin_x if is_left else (width - margin_x - header_w)

        self._draw_clean_text(draw, (header_x, start_y), header_text, font=font_header, fill=(220, 230, 240, 220))
        curr_y = start_y + line_height + (2 * s)

        # 2. Language Stats
        for stat in stats:
            line_str = f"{stat.name} · {stat.time_text} ({stat.percent:.1f}%)"
            bbox = draw.textbbox((0, 0), line_str, font=font_body)
            line_w = bbox[2] - bbox[0]
            line_x = margin_x if is_left else (width - margin_x - line_w)

            self._draw_clean_text(draw, (line_x, curr_y), line_str, font=font_body, fill=(255, 255, 255, 250))
            curr_y += line_height

        # 3. Attribution
        attr_text = f"Photo by {author_name} on Unsplash"
        attr_bbox = draw.textbbox((0, 0), attr_text, font=font_attr)
        attr_w = attr_bbox[2] - attr_bbox[0]

        if merged:
            curr_y += (6 * s)
            attr_x = margin_x if is_left else (width - margin_x - attr_w)
            self._draw_clean_text(draw, (attr_x, curr_y), attr_text, font=font_attr, fill=(210, 215, 220, 200))
        else:
            self._draw_single_attribution(draw, image_size, author_name, secondary_corner)

    def _draw_single_attribution(
        self,
        draw: ImageDraw.ImageDraw,
        image_size: tuple[int, int],
        author_name: str,
        corner: str,
    ) -> None:
        width, height = image_size
        s = self.SCALE
        font_attr = self._load_font(11)
        text = f"Photo by {author_name} on Unsplash"
        bbox = draw.textbbox((0, 0), text, font=font_attr)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        margin_x = 36 * s
        margin_y = 26 * s

        is_top = "T" in corner
        is_left = "L" in corner

        attr_x = margin_x if is_left else (width - margin_x - text_w)
        attr_y = margin_y if is_top else (height - margin_y - text_h)

        self._draw_clean_text(draw, (attr_x, attr_y), text, font=font_attr, fill=(225, 230, 235, 215))
