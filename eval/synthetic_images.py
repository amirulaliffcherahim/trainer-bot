"""Pillow-based synthetic Strava-style screenshots — privacy-safe eval images.

No real user data: every value is injected per test. Renders a dark-theme
activity card the OCR pipeline can read, plus the ground-truth text a
perfect OCR would produce.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

BG = (24, 24, 28)
FG = (240, 240, 245)
MUTED = (150, 150, 155)
ACCENT = (252, 76, 2)


@dataclass(frozen=True)
class SyntheticRun:
    title: str
    distance_km: float
    moving_time_min: float
    pace_text: str  # "6:58"
    avg_hr: int | None = None
    elevation_m: int | None = None
    date: str | None = None


def render(run: SyntheticRun) -> bytes:
    """Render a Strava-style activity card to PNG bytes."""
    width, height = 900, 800
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    big = ImageFont.load_default(size=72)
    med = ImageFont.load_default(size=36)
    small = ImageFont.load_default(size=28)

    y = 60
    draw.text((60, y), run.title, font=med, fill=FG)
    y += 90

    draw.text((60, y), f"{run.distance_km:.2f}", font=big, fill=FG)
    draw.text((60, y + 84), "km", font=small, fill=MUTED)

    minutes = int(run.moving_time_min)
    seconds = int(round((run.moving_time_min - minutes) * 60))
    draw.text((340, y), f"{minutes}:{seconds:02d}", font=big, fill=FG)
    draw.text((340, y + 84), "min", font=small, fill=MUTED)

    draw.text((620, y), run.pace_text, font=big, fill=ACCENT)
    draw.text((620, y + 84), "/km", font=small, fill=MUTED)
    y += 240

    if run.avg_hr is not None:
        draw.text((60, y), str(run.avg_hr), font=med, fill=FG)
        draw.text((150, y), "bpm", font=small, fill=MUTED)
    if run.elevation_m is not None:
        draw.text((340, y), str(run.elevation_m), font=med, fill=FG)
        draw.text((440, y), "m", font=small, fill=MUTED)
    if run.date:
        draw.text((620, y), run.date, font=small, fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ground_truth_text(run: SyntheticRun) -> str:
    """The text a perfect OCR would emit (parses back into the same values)."""
    minutes = int(run.moving_time_min)
    seconds = int(round((run.moving_time_min - minutes) * 60))
    lines = [
        run.title,
        f"{run.distance_km:.2f} km",
        f"{minutes}:{seconds:02d} min",
        f"{run.pace_text} /km",
    ]
    if run.avg_hr is not None:
        lines.append(f"{run.avg_hr} bpm")
    if run.elevation_m is not None:
        lines.append(f"{run.elevation_m} m")
    if run.date:
        lines.append(run.date)
    return "\n".join(lines)
