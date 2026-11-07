#!/usr/bin/env python3
"""Подготовка логотипа для шаблона.

- обрезает поля;
- делает прозрачный фон (если логотип на белом);
- собирает монохромную версию для тёмных слайдов;
- сохраняет logo.png и logo_dark.png в templates/default/assets/.

Пример:
    python3 scripts/prepare_logo.py ~/Downloads/logo.png
    python3 scripts/prepare_logo.py logo.png --mode keep
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "templates" / "default" / "assets"


def _dominant_color(pixels: list[tuple[int, int, int, int]]) -> tuple[tuple[int, int, int], float]:
    """Самый частый непрозрачный цвет (без почти белого) и его доля."""
    counter: Counter[tuple[int, int, int]] = Counter()
    for r, g, b, a in pixels:
        if a < 20:
            continue
        if r > 245 and g > 245 and b > 245:
            continue
        counter[(r // 8 * 8, g // 8 * 8, b // 8 * 8)] += 1
    if not counter:
        return (0, 0, 0), 0.0
    color, count = counter.most_common(1)[0]
    total = sum(counter.values())
    return color, count / total


def prepare(source: Path, out_dir: Path, name: str = "logo", mode: str = "auto") -> tuple[Path, Path, str]:
    img = Image.open(source).convert("RGBA")
    img.load()

    # Прозрачный фон: белый -> альфа 0, цвет -> один фирменный цвет.
    pixels = list(img.getdata())
    brand, share = _dominant_color(pixels)
    monochrome = mode == "yes" or (mode == "auto" and share >= 0.55)

    prepared: list[tuple[int, int, int, int]] = []
    if monochrome:
        br, bg, bb = brand
        denom = (max(1, 255 - br), max(1, 255 - bg), max(1, 255 - bb))
        for r, g, b, a in pixels:
            if a < 10:
                prepared.append((br, bg, bb, 0))
                continue
            alpha = max((255 - r) / denom[0], (255 - g) / denom[1], (255 - b) / denom[2])
            alpha = int(max(0.0, min(1.0, alpha)) * a)
            prepared.append((br, bg, bb, alpha))
    else:
        for r, g, b, a in pixels:
            if r > 248 and g > 248 and b > 248:
                prepared.append((0, 0, 0, 0))
            else:
                prepared.append((r, g, b, a))

    img.putdata(prepared)
    bbox = img.getbbox()
    if bbox:
        pad = max(4, int(max(img.size) * 0.015))
        bbox = (
            max(0, bbox[0] - pad), max(0, bbox[1] - pad),
            min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad),
        )
        img = img.crop(bbox)

    # Размер: не больше 1200 px по большей стороне.
    if max(img.size) > 1200:
        scale = 1200 / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)

    out_dir.mkdir(parents=True, exist_ok=True)
    light_path = out_dir / f"{name}.png"
    img.save(light_path, optimize=True)

    dark = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dark.putdata([(255, 255, 255, a) for _, _, _, a in img.getdata()])
    dark_path = out_dir / f"{name}_dark.png"
    dark.save(dark_path, optimize=True)

    hex_color = "#{:02X}{:02X}{:02X}".format(*brand) if monochrome else ""
    return light_path, dark_path, hex_color


def main() -> int:
    parser = argparse.ArgumentParser(description="Подготовить логотип для шаблона")
    parser.add_argument("source", help="Исходный файл логотипа (PNG/JPG)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--name", default="logo")
    parser.add_argument("--mode", choices=["auto", "yes", "no"], default="auto",
                        help="yes — монохром, no — сохранить цвета, auto — определить")
    args = parser.parse_args()

    source = Path(args.source).expanduser()
    if not source.exists():
        raise SystemExit(f"Файл не найден: {source}")

    light, dark, color = prepare(source, Path(args.out_dir), args.name, args.mode)
    print(f"Светлая версия: {light}")
    print(f"Тёмная версия:  {dark}")
    if color:
        print(f"Основной цвет:  {color}")
        print("При желании поставьте его в theme.yaml → colors.accent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
