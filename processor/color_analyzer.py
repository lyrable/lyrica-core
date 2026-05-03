from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from colorthief import ColorThief
import base64
from PIL import Image
import io

RgbColor = Tuple[int, int, int]


def _rgb_to_hex(color: RgbColor) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)

def _image_to_base64(path: str, size: tuple = (300, 300)) -> str:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img = img.resize(size, Image.LANCZOS)
        
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


def analyze_cover(cover_path: str | Path) -> Path:
    cover_file = Path(cover_path)
    if not cover_file.exists():
        raise FileNotFoundError(f"Cover image not found.")

    color_thief = ColorThief(str(cover_file))
    palette = color_thief.get_palette(color_count=3, quality=1)

    if len(palette) < 3:
        dominant = color_thief.get_color(quality=1)
        while len(palette) < 3:
            palette.append(dominant)

    primary, secondary, accent = palette[0], palette[1], palette[2]

    theme_data: Dict[str, str] = {
        "color_pallete": {
            "primary": _rgb_to_hex(primary),
            "secondary": _rgb_to_hex(secondary),
            "accent": _rgb_to_hex(accent),
        },
        "image_base64": _image_to_base64(cover_file),
    }

    output_path = cover_file.parent / "theme.json"
    output_path.write_text(
        json.dumps(theme_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
