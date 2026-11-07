#!/usr/bin/env python3
"""Фоны презентации: светлая и тёмная точечная сетка с мягким свечением."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "templates" / "default" / "assets"
W, H = 1920, 1080


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def gradient(top: str, bottom: str) -> Image.Image:
    image = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(image)
    a, b = rgb(top), rgb(bottom)
    for y in range(H):
        t = y / max(1, H - 1)
        color = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=color)
    return image.convert("RGBA")


def glow(image: Image.Image, cx: int, cy: int, radius: int, color: str, alpha: int) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*rgb(color), alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 3))
    image.alpha_composite(layer)


def dots(image: Image.Image, color: str, major: str, step: int = 30, r: float = 1.15) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    base, strong = rgb(color), rgb(major)
    for i, x in enumerate(range(step // 2, W, step)):
        for j, y in enumerate(range(step // 2, H, step)):
            is_major = i % 5 == 0 and j % 5 == 0
            c = strong if is_major else base
            rr = r + (0.35 if is_major else 0)
            draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(*c, 255))
    image.alpha_composite(layer)


def build_light() -> Image.Image:
    image = gradient("#F7FAFD", "#EDF3F9")
    glow(image, W - 120, 80, 620, "#0AB2A9", 20)
    glow(image, 80, H - 80, 560, "#4C7DFF", 16)
    glow(image, W - 260, H - 200, 420, "#8B7CF6", 10)
    dots(image, "#D4E1EE", "#BFD2E3")
    return image


def build_dark() -> Image.Image:
    image = gradient("#08111F", "#0B1A2B")
    glow(image, W - 160, 60, 700, "#0AB2A9", 32)
    glow(image, 60, H - 60, 620, "#8B7CF6", 26)
    glow(image, W - 220, H - 240, 460, "#4C7DFF", 16)
    dots(image, "#1B324B", "#2A4A6B")
    return image


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    light = build_light().convert("RGB")
    dark = build_dark().convert("RGB")
    light.save(OUT / "bg-light.png", optimize=True)
    dark.save(OUT / "bg-dark.png", optimize=True)
    print("backgrounds:", OUT / "bg-light.png", OUT / "bg-dark.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
