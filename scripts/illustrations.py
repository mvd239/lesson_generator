#!/usr/bin/env python3
"""Генератор иллюстраций в стиле «миллиметровка + технические карточки».

Примеры:
    python3 scripts/illustrations.py assets/schema.yaml
    python3 scripts/illustrations.py docs/illustrations/specs/*.yaml
    python3 scripts/illustrations.py --types
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from theme import pil_font_path  # noqa: E402

SS = 2  # суперсэмплинг

DEFAULT_STYLE = PROJECT_ROOT / "templates" / "default" / "illustrations.yaml"

DEFAULT_COLORS = {
    "paper": "#F7FAFC", "grid": "#E1EDF6", "grid_major": "#CBDDEB",
    "card": "#FFFFFF", "ink": "#17263A", "muted": "#5F7183", "line": "#C7D6E4",
    "blue": "#2F6FED", "blue_soft": "#E8F0FE",
    "red": "#C2185B", "red_soft": "#FBE7EE",
    "orange": "#EFA33C", "orange_soft": "#FDF0DC",
    "teal": "#0AB2A9", "teal_soft": "#E1F7F5",
    "purple": "#7C5CE0", "purple_soft": "#EEE9FD",
    "shadow": "#0E2233",
}

COLOR_KEYS = {"blue", "red", "orange", "teal", "purple"}


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def rgb(value: str) -> tuple[int, int, int]:
    value = str(value).lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class Style:
    def __init__(self, data: dict[str, Any], base_dir: Path):
        self.data = data
        self.base_dir = base_dir
        self.colors = {**DEFAULT_COLORS, **(data.get("colors") or {})}
        self.grid = {"step": 26, "major_every": 5, "minor_width": 1, "major_width": 2,
                     **(data.get("grid") or {})}
        self.cards = {"radius": 16, "border": 2, "shadow_alpha": 26,
                      "shadow_offset": 5, "shadow_blur": 10, **(data.get("cards") or {})}
        self.defaults = {"size": [1600, 620], "background": "paper", "margin": 100,
                         **(data.get("defaults") or {})}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Style":
        path = Path(path) if path else DEFAULT_STYLE
        if not path.exists():
            raise SystemExit(f"Не найден файл стиля: {path}")
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(data, path.parent)

    def c(self, key: str) -> tuple[int, int, int]:
        return rgb(self.colors.get(key, DEFAULT_COLORS.get(key, "#000000")))

    def n(self, key: str, default: float) -> float:
        return float(self.grid.get(key, default))


class Scene:
    def __init__(self, spec: dict[str, Any], style: Style):
        self.spec = spec
        self.style = style
        self.w = int(spec.get("w") or (spec.get("size") or style.defaults["size"])[0])
        self.h = int(spec.get("h") or (spec.get("size") or style.defaults["size"])[1])
        self.background = spec.get("background", style.defaults.get("background", "paper"))
        self.margin = int(spec.get("margin", style.defaults.get("margin", 100)))
        self.img = Image.new("RGBA", (self.w * SS, self.h * SS), (0, 0, 0, 0))
        self.draw = ImageDraw.Draw(self.img)
        self._fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        if self.background == "paper":
            self.img.paste(self.style.c("paper"), (0, 0, self.w * SS, self.h * SS))
            self._grid()

    # ---------- геометрия ----------

    def s(self, value: float) -> int:
        return int(round(value * SS))

    def box(self, x, y, w, h) -> list[int]:
        return [self.s(x), self.s(y), self.s(x + w), self.s(y + h)]

    # ---------- фон ----------

    def _grid(self) -> None:
        step = max(6, int(self.style.n("step", 26)))
        major = max(1, int(self.style.n("major_every", 5)))
        minor_w = max(1, int(self.style.n("minor_width", 1)))
        major_w = max(1, int(self.style.n("major_width", 2)))
        dot_r = float(self.style.grid.get("dot_radius", 1.2))
        style = str(self.style.grid.get("style", "lines"))
        minor = (*self.style.c("grid"), 255)
        major_c = (*self.style.c("grid_major"), 255)
        major_line = (*self.style.c("grid_major"), 95)

        if style in {"lines", "both"}:
            for i, x in enumerate(range(0, self.w + 1, step)):
                is_major = i % major == 0
                self.draw.line([(self.s(x), 0), (self.s(x), self.h * SS)],
                               fill=major_c if is_major else minor,
                               width=(major_w if is_major else minor_w) * SS)
            for i, y in enumerate(range(0, self.h + 1, step)):
                is_major = i % major == 0
                self.draw.line([(0, self.s(y)), (self.w * SS, self.s(y))],
                               fill=major_c if is_major else minor,
                               width=(major_w if is_major else minor_w) * SS)

        if style in {"dots", "both"}:
            # точки + очень редкие линии, чтобы сохранить «миллиметровку»
            for i, x in enumerate(range(step // 2, self.w, step)):
                if i % major == 0:
                    self.draw.line([(self.s(x), 0), (self.s(x), self.h * SS)],
                                   fill=major_line, width=major_w * SS)
            for j, y in enumerate(range(step // 2, self.h, step)):
                if j % major == 0:
                    self.draw.line([(0, self.s(y)), (self.w * SS, self.s(y))],
                                   fill=major_line, width=major_w * SS)
            for i, x in enumerate(range(step // 2, self.w, step)):
                for j, y in enumerate(range(step // 2, self.h, step)):
                    is_major = i % major == 0 and j % major == 0
                    r = dot_r + (0.5 if is_major else 0)
                    self.draw.ellipse(self.box(x - r, y - r, 2 * r, 2 * r),
                                      fill=major_c if is_major else minor)

    # ---------- шрифты и текст ----------

    def font(self, kind: str, size: float) -> ImageFont.FreeTypeFont:
        key = (kind, int(size))
        if key not in self._fonts:
            mapping = {"body": "regular", "regular": "regular", "bold": "bold",
                       "mono": "mono", "mono_bold": "mono_bold"}
            path = pil_font_path(mapping.get(kind, "regular"))
            if not path:
                raise SystemExit(f"Не найден шрифт ({kind}) для иллюстраций.")
            self._fonts[key] = ImageFont.truetype(str(path), max(6, self.s(size)))
        return self._fonts[key]

    def text(self, x, y, text: str, size=24, color="ink", kind="body", anchor="la"):
        self.draw.text((self.s(x), self.s(y)), str(text), font=self.font(kind, size),
                       fill=(*self.style.c(color), 255), anchor=anchor)

    def measure(self, text: str, size: float, kind="body") -> float:
        bbox = self.draw.textbbox((0, 0), str(text), font=self.font(kind, size))
        return (bbox[2] - bbox[0]) / SS

    def wrap(self, text: str, size: float, kind: str, max_w: float) -> list[str]:
        lines: list[str] = []
        for raw in str(text).split("\n"):
            words = raw.split()
            if not words:
                lines.append("")
                continue
            current = ""
            for word in words:
                trial = f"{current} {word}".strip()
                if self.measure(trial, size, kind) <= max_w or not current:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            if current:
                lines.append(current)
        return lines

    def paragraph(self, x, y, max_w, text, size=24, kind="body", color="muted",
                  line=1.35, align="left", max_lines: int | None = None) -> float:
        lines = self.wrap(text, size, kind, max_w)
        if max_lines:
            lines = lines[:max_lines]
        for i, ln in enumerate(lines):
            dx = x
            if align == "center":
                dx = x + (max_w - self.measure(ln, size, kind)) / 2
            self.text(dx, y + i * size * line, ln, size=size, color=color, kind=kind)
        return len(lines) * size * line

    # ---------- фигуры ----------

    def _glow_rrect(self, x, y, w, h, radius, color, alpha=90, blur=16, spread=5):
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle(self.box(x - spread, y - spread, w + 2 * spread, h + 2 * spread),
                             radius=self.s(radius + spread), fill=(*self.style.c(color), alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(self.s(blur)))
        self.img.alpha_composite(layer)
        self.draw = ImageDraw.Draw(self.img)

    def _glow_ellipse(self, x, y, w, h, color, alpha=90, blur=16, spread=5):
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse(self.box(x - spread, y - spread, w + 2 * spread, h + 2 * spread),
                   fill=(*self.style.c(color), alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(self.s(blur)))
        self.img.alpha_composite(layer)
        self.draw = ImageDraw.Draw(self.img)

    def rrect(self, x, y, w, h, radius=16, fill="card", outline="line", width=2,
              dashed=False, shadow=False, glow=None, glow_alpha=80):
        box = self.box(x, y, w, h)
        if glow:
            self._glow_rrect(x, y, w, h, radius, glow, alpha=glow_alpha)
        if shadow:
            self._shadow(x, y, w, h, radius)
        if fill:
            self.draw.rounded_rectangle(box, radius=self.s(radius), fill=(*self.style.c(fill), 255))
        if outline:
            color = (*self.style.c(outline), 255)
            if dashed:
                points = self._rrect_points(x, y, w, h, radius)
                self.dashed_path(points, 12, 7, width, color)
            else:
                self.draw.rounded_rectangle(box, radius=self.s(radius), outline=color,
                                            width=max(1, self.s(width)))

    def ellipse(self, x, y, w, h, fill="card", outline=None, width=2, glow=None, glow_alpha=80):
        if glow:
            self._glow_ellipse(x, y, w, h, glow, alpha=glow_alpha)
        self.draw.ellipse(
            self.box(x, y, w, h),
            fill=(*self.style.c(fill), 255),
            outline=(*self.style.c(outline), 255) if outline else None,
            width=max(1, self.s(width)),
        )

    def _shadow(self, x, y, w, h, radius) -> None:
        alpha = int(self.style.cards.get("shadow_alpha", 26))
        if alpha <= 0:
            return
        offset = int(self.style.cards.get("shadow_offset", 5))
        blur = int(self.style.cards.get("shadow_blur", 10))
        layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle(self.box(x, y + offset, w, h), radius=self.s(radius),
                             fill=(*self.style.c("shadow"), alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(self.s(blur)))
        self.img.alpha_composite(layer)
        self.draw = ImageDraw.Draw(self.img)

    @staticmethod
    def _rrect_points(x, y, w, h, r, steps=8) -> list[tuple[float, float]]:
        pts = [(x + r, y), (x + w - r, y)]
        for i in range(steps + 1):
            a = -math.pi / 2 + i * (math.pi / 2) / steps
            pts.append((x + w - r + r * math.cos(a), y + r + r * math.sin(a)))
        pts.append((x + w, y + h - r))
        for i in range(steps + 1):
            a = i * (math.pi / 2) / steps
            pts.append((x + w - r + r * math.cos(a), y + h - r + r * math.sin(a)))
        pts.append((x + r, y + h))
        for i in range(steps + 1):
            a = math.pi / 2 + i * (math.pi / 2) / steps
            pts.append((x + r + r * math.cos(a), y + h - r + r * math.sin(a)))
        pts.append((x, y + r))
        for i in range(steps + 1):
            a = math.pi + i * (math.pi / 2) / steps
            pts.append((x + r + r * math.cos(a), y + r + r * math.sin(a)))
        return pts

    def dashed_path(self, points, dash=12, gap=7, width=2, color=None) -> None:
        color = color or (*self.style.c("line"), 255)
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            ux, uy = dx / length, dy / length
            pos = 0.0
            while pos < length:
                end = min(pos + dash, length)
                self.draw.line([(self.s(x1 + ux * pos), self.s(y1 + uy * pos)),
                                (self.s(x1 + ux * end), self.s(y1 + uy * end))],
                               fill=color, width=max(1, self.s(width)))
                pos += dash + gap

    def line(self, points, color="orange", width=3, dashed=False, glow=False) -> None:
        if glow and not dashed:
            layer = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            ld.line([(self.s(x), self.s(y)) for x, y in points],
                    fill=(*self.style.c(color), 110), width=max(2, self.s(width * 2.4)), joint="curve")
            layer = layer.filter(ImageFilter.GaussianBlur(self.s(8)))
            self.img.alpha_composite(layer)
            self.draw = ImageDraw.Draw(self.img)
        color = (*self.style.c(color), 255)
        if dashed:
            self.dashed_path(points, 14, 8, width, color)
            return
        pts = [(self.s(x), self.s(y)) for x, y in points]
        self.draw.line(pts, fill=color, width=max(1, self.s(width)), joint="curve")
        for x, y in pts[1:-1]:
            r = max(1, self.s(width) / 2)
            self.draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def arrow(self, points, color="orange", width=3, head=14, terminal=True, glow=False) -> None:
        self.line(points, color=color, width=width, glow=glow)
        (x1, y1), (x2, y2) = points[-2], points[-1]
        angle = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2, y2)
        p2 = (x2 - head * math.cos(angle - 0.45), y2 - head * math.sin(angle - 0.45))
        p3 = (x2 - head * math.cos(angle + 0.45), y2 - head * math.sin(angle + 0.45))
        self.draw.polygon([(self.s(p1[0]), self.s(p1[1])), (self.s(p2[0]), self.s(p2[1])),
                           (self.s(p3[0]), self.s(p3[1]))], fill=(*self.style.c(color), 255))
        if terminal:
            self.terminal(*points[0], color=color)

    def terminal(self, x, y, color="ink", r=6) -> None:
        self.draw.ellipse(self.box(x - r, y - r, 2 * r, 2 * r), fill=(*self.style.c("card"), 255),
                          outline=(*self.style.c(color), 255), width=max(1, self.s(2)))

    def chip(self, x, y, text, size=20, fill="blue", color="white", kind="mono_bold",
             pad_x=12, pad_y=6) -> tuple[float, float]:
        w = self.measure(text, size, kind) + 2 * pad_x
        h = size + 2 * pad_y
        self.rrect(x, y, w, h, radius=7, fill=fill, outline=None, shadow=False)
        self.text(x + w / 2, y + h / 2, text, size=size, color=color, kind=kind, anchor="mm")
        return w, h

    def badge(self, x, y, text, size=46, fill="blue", color="white", radius=10, font_size=24):
        self.rrect(x, y, size, size, radius=radius, fill=fill, outline=None, shadow=False)
        self.text(x + size / 2, y + size / 2, text, size=font_size, color=color,
                  kind="mono_bold", anchor="mm")

    def tone(self, name: str | None) -> tuple[str, str]:
        if name in COLOR_KEYS:
            return name, f"{name}_soft"
        return "line", "card"

    # ---------- заголовок и подпись ----------

    def title_block(self, text: str, y=44) -> float:
        if not text:
            return 0
        self.rrect(self.margin, y + 4, 6, 38, radius=3, fill="blue", outline=None, shadow=False)
        self.text(self.margin + 22, y, text, size=40, color="ink", kind="bold")
        return 74

    def caption(self, text: str) -> None:
        if text:
            self.text(self.w / 2, self.h - 44, text, size=22, color="muted", anchor="mm")


# ------------------------------------------------------------------
#  Сцены
# ------------------------------------------------------------------


def scene_array(sc: Scene, spec: dict) -> None:
    rows = spec.get("rows") or []
    if not rows:
        return
    n = max(len(r.get("values") or []) for r in rows)
    gap = 14
    avail = sc.w - 2 * sc.margin
    cell_w = min(150, (avail - gap * (n - 1)) / n)
    cell_h = min(118, cell_w * 0.86)
    row_w = n * cell_w + gap * (n - 1)
    x0 = (sc.w - row_w) / 2

    title_h = sc.title_block(spec.get("title") or "")
    top_min = 44 + title_h + 20
    bottom = sc.h - (76 if spec.get("caption") else 36)
    row_gap = 84
    block_h = cell_h + 62
    if top_min + len(rows) * block_h + (len(rows) - 1) * row_gap > bottom:
        cell_h = max(70, (bottom - top_min - (len(rows) - 1) * row_gap) / len(rows) - 62)
        block_h = cell_h + 62
    content_h = len(rows) * block_h + (len(rows) - 1) * row_gap
    top = top_min + max(0, (bottom - top_min - content_h) / 2)

    for r_i, row in enumerate(rows):
        values = [str(v) for v in (row.get("values") or [])]
        ry = top + r_i * (block_h + row_gap)
        tone = row.get("tone") or "blue"
        border, soft = sc.tone(tone)
        label = row.get("label")
        if label:
            sc.text(x0 - 32, ry + cell_h / 2, label, size=28, color="ink", kind="bold", anchor="rm")
        highlight = {int(i) for i in as_list(row.get("highlight"))}
        selected = [int(i) for i in as_list(row.get("selected"))]
        pointers = {str(k): str(v) for k, v in (row.get("pointers") or {}).items()}

        for i, value in enumerate(values):
            cx = x0 + i * (cell_w + gap)
            fill = soft if i in highlight else "card"
            outline = border if i in highlight else "line"
            sc.rrect(cx, ry, cell_w, cell_h, radius=12, fill=fill, outline=outline,
                     width=2, shadow=True, glow=border if i in highlight else None,
                     glow_alpha=50)
            sc.text(cx + cell_w / 2, ry + cell_h / 2 + 1, value, size=38,
                    color=border if i in highlight else "ink", kind="bold", anchor="mm")
            if row.get("show_index", True):
                sc.text(cx + cell_w / 2, ry + cell_h + 22, str(i), size=18,
                        color="muted", kind="mono", anchor="mm")
            if str(i) in pointers:
                pw, ph = 34, 30
                px = cx + cell_w / 2 - pw / 2
                sc.rrect(px, ry - 48, pw, ph, radius=7, fill=border, outline=None, shadow=False)
                sc.text(px + pw / 2, ry - 33, pointers[str(i)], size=18, color="white",
                        kind="mono_bold", anchor="mm")
                sc.line([(cx + cell_w / 2, ry - 16), (cx + cell_w / 2, ry - 2)],
                        color=border, width=2, dashed=False)

        if selected:
            first, last = min(selected), max(selected)
            sx = x0 + first * (cell_w + gap) - 9
            sw = (last - first + 1) * cell_w + (last - first) * gap + 18
            sc.rrect(sx, ry - 9, sw, cell_h + 18, radius=15, fill=None, outline="red",
                     width=2, dashed=True)

    sc.caption(spec.get("caption") or "")




def scene_division(sc: Scene, spec: dict) -> None:
    """Деление уголком в российской записи: делимое слева, делитель за чертой.

    Частное пишется под делителем, произведение — под делимым, остаток —
    под чертой вычитания. Японская/американская запись (делитель слева в
    скобке, частное над делимым) в российских учебниках не используется.
    """
    base = int(spec.get("base") or 2)
    raw_steps = spec.get("steps")
    steps: list[dict] = []
    if raw_steps:
        steps = [dict(item) for item in raw_steps]
    else:
        n = int(spec.get("number") or 0)
        while n > 0:
            q, r = divmod(n, base)
            steps.append({"dividend": n, "quotient": q, "remainder": r})
            n = q
    if not steps:
        return

    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 70 if spec.get("caption") else 30
    count = len(steps)
    gap = 16
    top = 100 + title_h
    block_h = min(125, (sc.h - top - caption_h - (count - 1) * gap) / count)

    # Российская запись «уголком»: 13 │ 2, под 13 — произведение 12,
    # под двойкой — частное 6, под чертой — остаток 1.
    x_left = 170
    col_w = 150
    x_right = x_left + col_w          # правый край столбца делимого
    bar_x = x_right + 14              # вертикальная черта уголка
    div_x = bar_x + 26                # делитель и частное — за чертой
    rx = 800
    k = max(0.72, min(1.0, block_h / 118))
    s_big = int(34 * k)
    s_mid = int(31 * k)
    s_small = int(27 * k)
    row2 = 38 * k
    line_y = 69 * k
    rem_y = 91 * k
    chip_mid = min(rem_y, block_h - 30)   # центр плашки с остатком

    for i, step in enumerate(steps):
        by = top + i * (block_h + gap)
        dividend = str(step.get("dividend"))
        quotient = str(step.get("quotient", ""))
        remainder = str(step.get("remainder", ""))
        product = int(quotient) * base if quotient.lstrip("-").isdigit() else 0

        sc.line([(bar_x, by - 6), (bar_x, by + rem_y + 14)], color="ink", width=3)

        div_w = sc.measure(dividend, s_big, "mono_bold")
        line_from = x_right - div_w - 16
        product_text = f"−{product}" if product else str(product)

        sc.text(x_right, by, dividend, size=s_big, color="ink", kind="mono_bold", anchor="ra")
        sc.text(div_x, by, str(base), size=s_big, color="ink", kind="mono_bold")
        sc.text(x_right, by + row2, product_text, size=s_small, color="muted",
                kind="mono", anchor="ra")
        sc.text(div_x, by + row2, quotient, size=s_mid, color="blue", kind="mono_bold")
        sc.line([(line_from, by + line_y), (bar_x, by + line_y)], color="ink", width=3)
        sc.text(x_right - div_w / 2, by + rem_y, remainder, size=s_mid, color="red",
                kind="mono_bold", anchor="mm")

        chip_y = by + chip_mid - 26
        sc.rrect(rx, chip_y, 52, 52, radius=10, fill="red_soft", outline="red", width=2,
                 glow="red", glow_alpha=45)
        sc.text(rx + 26, chip_y + 26, remainder, size=24, color="red", kind="mono_bold", anchor="mm")
        sc.dashed_path([(div_x + 16, by + rem_y), (rx - 8, by + rem_y)],
                       dash=6, gap=5, width=1, color=(*sc.style.c("line"), 255))

    first_y = top
    last_y = top + (count - 1) * (block_h + gap)
    sc.arrow([(rx + 80, last_y + chip_mid), (rx + 80, first_y + chip_mid)],
             color="red", width=3, head=12, terminal=False, glow=True)
    sc.text(rx + 96, (first_y + last_y) / 2 + chip_mid, "читаем снизу вверх",
            size=20, color="muted")
    answer = str(spec.get("answer") or "".join(str(step.get("remainder")) for step in reversed(steps)))
    sc.rrect(1135, top, 285, 100, radius=12, fill="blue_soft", outline="blue", width=2,
             glow="blue", glow_alpha=55)
    sc.text(1155, top + 12, "Ответ", size=20, color="muted")
    sc.text(1155, top + 40, answer, size=38, color="blue", kind="mono_bold")
    sc.arrow([(rx + 80, first_y + chip_mid), (1130, top + 50)], color="red", width=3, head=10, terminal=False)

    sc.caption(spec.get("caption") or "")



def scene_recursion(sc: Scene, spec: dict) -> None:
    """Стек вызовов рекурсивной функции: вызовы вниз, возвраты вверх."""
    func_name = str(spec.get("function") or "f")
    calls = [str(c) for c in (spec.get("calls") or [])]
    returns = [str(r) for r in (spec.get("returns") or [])]
    if not calls:
        return
    count = len(calls)
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 70 if spec.get("caption") else 30
    top = 100 + title_h
    gap = 38
    block_h = min(90, (sc.h - top - caption_h - (count - 1) * gap) / count)
    x = 430
    width = 520
    rx = 1040
    last_y = top + (count - 1) * (block_h + gap)

    for i, call in enumerate(calls):
        by = top + i * (block_h + gap)
        base = i == count - 1
        border, soft = sc.tone("teal" if base else None)
        sc.rrect(x, by, width, block_h, radius=14,
                 fill=soft if base else "card",
                 outline=border if base else "line", width=2, shadow=True,
                 glow="teal" if base else None, glow_alpha=50)
        sc.text(x + 30, by + block_h / 2, f"{func_name}({call})", size=30,
                color="ink", kind="mono_bold", anchor="lm")
        if base:
            sc.chip(x + width - 116, by + 12, "база", size=17, fill="teal", color="white")
        if i < count - 1:
            sc.arrow([(x + 90, by + block_h + 3), (x + 90, by + block_h + gap - 3)],
                     color="blue", width=3, head=10, terminal=False, glow=True)
            sc.text(x + 108, by + block_h + gap / 2, "вызов", size=18, color="blue", anchor="lm")
        if i < len(returns):
            sc.rrect(rx, by + (block_h - 52) / 2, 54, 54, radius=10,
                     fill="blue_soft", outline="blue", width=2,
                     glow="blue", glow_alpha=40)
            sc.text(rx + 27, by + (block_h - 52) / 2 + 27, returns[i], size=24,
                    color="blue", kind="mono_bold", anchor="mm")

    sc.arrow([(rx + 90, last_y + block_h / 2), (rx + 90, top + block_h / 2)],
             color="teal", width=3, head=12, terminal=False, glow=True)
    sc.text(rx + 108, (top + last_y) / 2 + block_h / 2, "возврат", size=18, color="teal", anchor="lm")

    base_label = str(spec.get("base_label") or "")
    if base_label:
        sc.text(x, last_y + block_h + 18, f"база: {base_label}", size=20, color="teal",
                kind="mono")

    sc.caption(spec.get("caption") or "")


def scene_radix(sc: Scene, spec: dict) -> None:
    """Разряды числа: цифра, вес разряда, значение и сумма."""
    digits = [str(d) for d in (spec.get("digits") or [])]
    if not digits:
        return
    n = len(digits)
    weights = [str(w) for w in (spec.get("weights") or [])]
    values = spec.get("values") or []
    highlight = {int(i) for i in as_list(spec.get("highlight"))}
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 60 if spec.get("caption") else 20

    gap = 26
    card_w = min(190, (sc.w - 2 * sc.margin - gap * (n - 1)) / n)
    card_h = 160
    row_w = n * card_w + gap * (n - 1)
    x0 = (sc.w - row_w) / 2
    block_h = 300
    y = 70 + title_h + max(0, (sc.h - 70 - title_h - caption_h - block_h) / 2)

    for i, digit in enumerate(digits):
        cx = x0 + i * (card_w + gap)
        active = i in highlight
        border, soft = sc.tone("blue" if active else None)
        if weights:
            label = weights[i]
            tw = sc.measure(label, 22, "mono_bold") + 22
            sc.rrect(cx + card_w / 2 - tw / 2, y - 48, tw, 34, radius=7,
                     fill="blue_soft" if active else "card", outline="line", width=1)
            sc.text(cx + card_w / 2, y - 31, label, size=22, color="blue" if active else "muted",
                    kind="mono_bold", anchor="mm")
            sc.line([(cx + card_w / 2, y - 14), (cx + card_w / 2, y - 2)],
                    color="blue" if active else "line", width=2)
        sc.rrect(cx, y, card_w, card_h, radius=14, fill=soft if active else "card",
                 outline=border if active else "line", width=2, shadow=True,
                 glow=border if active else None, glow_alpha=55)
        sc.text(cx + card_w / 2, y + card_h / 2, digit, size=64,
                color="blue" if active else "ink", kind="bold", anchor="mm")
        if i < len(values):
            sc.text(cx + card_w / 2, y + card_h + 22, str(values[i]), size=25,
                    color="muted", kind="mono", anchor="mm")
        if i < n - 1:
            sc.text(cx + card_w + gap / 2, y + card_h + 22, "+", size=24,
                    color="line", kind="bold", anchor="mm")

    total = 0
    terms = []
    for i, digit in enumerate(digits):
        value = int(values[i]) if i < len(values) else 0
        total += int(digit) * value
        terms.append(f"{digit}·{value}")
    sum_text = spec.get("sum") or f"{' + '.join(terms)} = {total}"
    sc.text(sc.w / 2, y + card_h + 74, sum_text, size=27, color="ink",
            kind="mono_bold", anchor="mm")

    sc.caption(spec.get("caption") or "")


def scene_flow(sc: Scene, spec: dict) -> None:
    steps = spec.get("steps") or []
    if not steps:
        return
    direction = spec.get("direction", "horizontal")
    title_h = sc.title_block(spec.get("title") or "")
    highlight = {int(i) for i in as_list(spec.get("highlight"))}
    caption_h = 60 if spec.get("caption") else 20

    if direction == "horizontal":
        gap = 78
        card_w = min(340, (sc.w - 2 * sc.margin - gap * (len(steps) - 1)) / len(steps))
        card_h = 240
        total = len(steps) * card_w + gap * (len(steps) - 1)
        x0 = (sc.w - total) / 2
        y = 120 + title_h + max(0, (sc.h - 120 - title_h - caption_h - 240) / 2 - 20)
        for i, step in enumerate(steps):
            x = x0 + i * (card_w + gap)
            border, soft = sc.tone("red" if i in highlight else None)
            sc.rrect(x, y, card_w, card_h, radius=14, fill=soft if i in highlight else "card",
                     outline=border if i in highlight else "line", width=2,
                     dashed=i in highlight, shadow=True)
            sc.badge(x + 24, y + 22, str(i + 1), size=44, fill="blue")
            sc.text(x + 26, y + 82, str(step.get("title") or ""), size=28, color="ink", kind="bold")
            body = str(step.get("text") or "")
            kind = "mono" if step.get("mono") else "body"
            sc.paragraph(x + 26, y + 128, card_w - 52, body, size=21, kind=kind,
                         color="muted", line=1.3, max_lines=4)
            if i < len(steps) - 1:
                ax = x + card_w + 12
                bx = x + card_w + gap - 12
                sc.arrow([(ax, y + card_h / 2), (bx, y + card_h / 2)], color="orange", width=3, head=12, glow=True)
    else:
        gap = 34
        card_w = min(900, sc.w - 2 * sc.margin)
        card_h = min(120, (sc.h - 160 - title_h - caption_h - gap * (len(steps) - 1)) / len(steps))
        x = (sc.w - card_w) / 2
        total = len(steps) * card_h + gap * (len(steps) - 1)
        y = 100 + title_h + max(0, (sc.h - 100 - title_h - caption_h - total) / 2 - 10)
        for i, step in enumerate(steps):
            cy = y + i * (card_h + gap)
            border, soft = sc.tone("red" if i in highlight else None)
            sc.rrect(x, cy, card_w, card_h, radius=14, fill=soft if i in highlight else "card",
                     outline=border if i in highlight else "line", width=2,
                     dashed=i in highlight, shadow=True)
            sc.badge(x + 22, cy + card_h / 2 - 22, str(i + 1), size=44, fill="blue")
            sc.text(x + 88, cy + 22, str(step.get("title") or ""), size=26, color="ink", kind="bold")
            sc.text(x + 88, cy + 62, str(step.get("text") or ""), size=21, color="muted",
                    kind="mono" if step.get("mono") else "body")
            if i < len(steps) - 1:
                sc.arrow([(x + card_w / 2, cy + card_h + 6), (x + card_w / 2, cy + card_h + gap - 6)],
                         color="orange", width=3, head=12, glow=True)

    sc.caption(spec.get("caption") or "")


def scene_layers(sc: Scene, spec: dict) -> None:
    layers = spec.get("layers") or []
    if not layers:
        return
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 92 if spec.get("caption") else 36
    gap = 14
    n = len(layers)
    top = 110 + title_h
    bottom = sc.h - caption_h
    card_h = min(118, (bottom - top - gap * (n - 1)) / n)
    width = min(1160, sc.w - 2 * sc.margin)
    x = (sc.w - width) / 2
    total = n * card_h + gap * (n - 1)
    y = top + max(0, (bottom - top - total) / 2)
    highlight = {int(i) for i in as_list(spec.get("highlight"))}
    palette = ["blue", "teal", "purple", "orange", "red"]

    for i, layer in enumerate(layers):
        cy = y + i * (card_h + gap)
        tone = palette[i % len(palette)]
        selected = i in highlight
        border, soft = sc.tone("red" if selected else None)
        sc.rrect(x, cy, width, card_h, radius=12, fill=soft if selected else "card",
                 outline=border if selected else "line", width=2, dashed=selected, shadow=True,
                 glow="red" if selected else None, glow_alpha=40)
        sc.rrect(x, cy, 8, card_h, radius=4, fill="red" if selected else tone, outline=None, shadow=False)
        sc.text(x + 36, cy + card_h / 2, str(layer.get("label") or ""), size=27,
                color="ink", kind="bold", anchor="lm")
        note = str(layer.get("text") or "")
        if note:
            sc.text(x + width - 32, cy + card_h / 2, note, size=21, color="muted",
                    kind="mono", anchor="rm")

    sc.caption(spec.get("caption") or "")


def scene_schema(sc: Scene, spec: dict) -> None:
    nodes = spec.get("nodes") or []
    if not nodes:
        return
    title_h = sc.title_block(spec.get("title") or "")
    direction = spec.get("direction", "horizontal")
    caption_h = 60 if spec.get("caption") else 20
    highlight = {str(v) for v in as_list(spec.get("highlight"))}
    by_id = {str(n.get("id")): n for n in nodes}

    if direction == "horizontal":
        n = len(nodes)
        gap = 130
        node_w = min(280, (sc.w - 2 * sc.margin - gap * (n - 1)) / n)
        node_h = 170
        total = n * node_w + gap * (n - 1)
        x0 = (sc.w - total) / 2
        y = 120 + title_h + max(0, (sc.h - 120 - title_h - caption_h - node_h) / 2 - 20)
        centers = {}
        for i, node in enumerate(nodes):
            x = x0 + i * (node_w + gap)
            centers[str(node.get("id"))] = (x, y, node_w, node_h)
            _draw_node(sc, x, y, node_w, node_h, node, str(node.get("id")) in highlight)
        for link in spec.get("links") or []:
            a = centers.get(str(link.get("from")))
            b = centers.get(str(link.get("to")))
            if not a or not b:
                continue
            p1 = (a[0] + a[2] + 2, a[1] + a[3] / 2)
            p2 = (b[0] - 2, b[1] + b[3] / 2)
            mid = (p1[0] + p2[0]) / 2
            sc.arrow([p1, (mid, p1[1]), (mid, p2[1]), p2], color="orange", width=3, head=12, glow=True)
            label = str(link.get("label") or "")
            if label:
                tw = sc.measure(label, 18, "mono_bold") + 20
                sc.rrect(mid - tw / 2, p1[1] - 34, tw, 28, radius=6, fill="card", outline="line", width=1)
                sc.text(mid, p1[1] - 20, label, size=18, color="orange", kind="mono_bold", anchor="mm")
    else:
        gap = 46
        node_w = min(720, sc.w - 2 * sc.margin)
        node_h = 110
        total = len(nodes) * node_h + gap * (len(nodes) - 1)
        x = (sc.w - node_w) / 2
        y = 110 + title_h + max(0, (sc.h - 110 - title_h - caption_h - total) / 2)
        centers = {}
        for i, node in enumerate(nodes):
            cy = y + i * (node_h + gap)
            centers[str(node.get("id"))] = (x, cy, node_w, node_h)
            _draw_node(sc, x, cy, node_w, node_h, node, str(node.get("id")) in highlight)
        for link in spec.get("links") or []:
            a = centers.get(str(link.get("from")))
            b = centers.get(str(link.get("to")))
            if not a or not b:
                continue
            p1 = (a[0] + a[2] / 2, a[1] + a[3] + 2)
            p2 = (b[0] + b[2] / 2, b[1] - 2)
            sc.arrow([p1, p2], color="orange", width=3, head=12, glow=True)
            label = str(link.get("label") or "")
            if label:
                sc.text((p1[0] + p2[0]) / 2 + 14, (p1[1] + p2[1]) / 2, label, size=18,
                        color="orange", kind="mono_bold", anchor="lm")

    sc.caption(spec.get("caption") or "")


def _draw_node(sc: Scene, x, y, w, h, node: dict, selected: bool) -> None:
    border, soft = sc.tone("red" if selected else (node.get("tone") or "blue"))
    sc.rrect(x, y, w, h, radius=14, fill=soft if selected else "card",
             outline=border, width=2, dashed=selected, shadow=True,
             glow=border, glow_alpha=50)
    sc.rrect(x + 20, y + 20, 12, 12, radius=3, fill=border, outline=None, shadow=False)
    sc.text(x + 24, y + 46, str(node.get("title") or ""), size=26, color="ink", kind="bold")
    text = str(node.get("text") or "")
    if text:
        sc.paragraph(x + 24, y + 84, w - 48, text, size=19, kind="mono" if node.get("mono") else "body",
                     color="muted", line=1.25, max_lines=2)


def scene_tree(sc: Scene, spec: dict) -> None:
    root = spec.get("root")
    if not root:
        return
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 60 if spec.get("caption") else 20
    highlight = {str(v) for v in as_list(spec.get("highlight"))}
    nodes: list[dict] = []

    def walk(node, depth=0):
        if not node:
            return
        walk(node.get("left"), depth + 1)
        nodes.append({"node": node, "depth": depth})
        walk(node.get("right"), depth + 1)

    walk(root)
    n = len(nodes)
    max_depth = max(item["depth"] for item in nodes)
    radius = 34 if n <= 12 else 27
    step_x = min(110, (sc.w - 2 * sc.margin) / max(1, n - 1))
    step_y = min(100, (sc.h - 150 - title_h - caption_h - 2 * radius) / max(1, max_depth))
    total_w = (n - 1) * step_x
    x0 = (sc.w - total_w) / 2
    y0 = 100 + title_h + max(0, (sc.h - 100 - title_h - caption_h - max_depth * step_y - 2 * radius) / 2)
    positions = {}
    for i, item in enumerate(nodes):
        x = x0 + i * step_x
        y = y0 + item["depth"] * step_y
        positions[id(item["node"])] = (x, y)

    def edges(node):
        if not node:
            return
        for child in (node.get("left"), node.get("right")):
            if child and id(child) in positions:
                p1 = positions[id(node)]
                p2 = positions[id(child)]
                sc.line([p1, p2], color="line", width=3)
                edges(child)

    edges(root)
    for item in nodes:
        node = item["node"]
        x, y = positions[id(node)]
        value = str(node.get("value") or "")
        selected = value in highlight
        sc.ellipse(x - radius, y - radius, 2 * radius, 2 * radius,
                   fill="blue" if selected else "card",
                   outline="blue" if selected else "line", width=3,
                   glow="blue" if selected else None, glow_alpha=55)
        sc.text(x, y, value, size=22 if n > 10 else 26, color="white" if selected else "ink",
                kind="mono_bold", anchor="mm")

    sc.caption(spec.get("caption") or "")


def scene_dots(sc: Scene, spec: dict) -> None:
    count = int(spec.get("count", 55))
    color = spec.get("color", "teal")
    seed = int(spec.get("seed", 7))
    rng = random.Random(seed)
    min_r = float(spec.get("min_radius", 6))
    max_r = float(spec.get("max_radius", 24))
    margin = float(spec.get("margin", 40))
    dots: list[tuple[float, float, float]] = []
    attempts = 0
    while len(dots) < count and attempts < count * 300:
        attempts += 1
        r = rng.uniform(min_r, max_r)
        x = rng.uniform(margin + r, sc.w - margin - r)
        y = rng.uniform(margin + r, sc.h - margin - r)
        if all(math.hypot(x - dx, y - dy) > r + dr + 6 for dx, dy, dr in dots):
            dots.append((x, y, r))
    for x, y, r in sorted(dots, key=lambda d: -d[2]):
        sc.draw.ellipse(sc.box(x - r, y - r, 2 * r, 2 * r), fill=(*sc.style.c(color), 255))


# ------------------------------------------------------------------
#  Логика: схема с прямым и инверсным ключом
# ------------------------------------------------------------------


def _battery(sc: Scene, x, y, label=True) -> None:
    color = sc.style.c("ink")
    sc.line([(x - 14, y - 34), (x - 14, y + 34)], color="ink", width=4)
    sc.line([(x + 14, y - 18), (x + 14, y + 18)], color="ink", width=4)
    sc.text(x - 26, y - 52, "+", size=24, color="ink", kind="mono_bold", anchor="mm")
    sc.text(x + 30, y - 52, "−", size=24, color="ink", kind="mono_bold", anchor="mm")
    if label:
        sc.text(x, y + 58, "батарея", size=19, color="muted", anchor="mm")


def _lamp(sc: Scene, x, y, on: bool, label="лампа") -> None:
    r = 36
    if on:
        glow = Image.new("RGBA", sc.img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse(sc.box(x - r * 2.0, y - r * 2.0, 4 * r, 4 * r),
                   fill=(*sc.style.c("orange"), 70))
        glow = glow.filter(ImageFilter.GaussianBlur(sc.s(18)))
        sc.img.alpha_composite(glow)
        sc.draw = ImageDraw.Draw(sc.img)
    sc.draw.ellipse(sc.box(x - r, y - r, 2 * r, 2 * r),
                    fill=(255, 255, 255, 255), outline=(*sc.style.c("ink"), 255),
                    width=max(1, sc.s(3)))
    d = r * 0.62
    sc.line([(x - d, y - d), (x + d, y + d)], color="ink", width=3)
    sc.line([(x - d, y + d), (x + d, y - d)], color="ink", width=3)
    sc.text(x, y + r + 26, f"{label} F={1 if on else 0}", size=19,
            color="orange" if on else "muted", kind="mono_bold", anchor="mm")


def _switch_card(sc: Scene, x, y, w, h, label, state, inverted: bool) -> float:
    closed = (state == 0) if inverted else (state == 1)
    tone = "red" if inverted else "blue"
    border, soft = sc.tone(tone)
    sc.rrect(x, y, w, h, radius=13, fill=soft if inverted else "card",
             outline=border, width=2, dashed=inverted, shadow=True,
             glow=border, glow_alpha=45)
    prefix = "¬" if inverted else ""
    sc.text(x + 20, y + 16, f"{prefix}{label}", size=31, color=border, kind="bold")
    sc.text(x + w - 20, y + h - 14, f"{label}={state}", size=21, color="muted",
            kind="mono", anchor="rs")

    ty = y + h - 40
    lx, rx = x + 34, x + w - 34
    sc.terminal(lx, ty, r=6)
    sc.terminal(rx, ty, r=6)
    end_y = ty if closed else ty - 30
    sc.line([(lx, ty), (rx - 6, end_y)], color="ink", width=4)
    return ty


def scene_logic(sc: Scene, spec: dict) -> None:
    """Сравнение прямого и инверсного ключа при одном значении A."""
    value = int(spec.get("value", 1))
    cases = spec.get("cases") or [
        {"label": "Прямой ключ", "inverted": False},
        {"label": "Инверсный ключ", "inverted": True},
    ]
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 60 if spec.get("caption") else 20
    n = len(cases)
    gap = 56
    panel_w = min(760, (sc.w - 2 * sc.margin - gap * (n - 1)) / n)
    panel_h = 370
    total = n * panel_w + gap * (n - 1)
    x0 = (sc.w - total) / 2
    y = 96 + title_h + max(0, (sc.h - 96 - title_h - caption_h - panel_h) / 2 - 6)

    for i, case in enumerate(cases):
        inverted = bool(case.get("inverted"))
        closed = (value == 0) if inverted else (value == 1)
        lamp_on = closed
        px = x0 + i * (panel_w + gap)
        sc.rrect(px, y, panel_w, panel_h, radius=18, fill="card", outline="line",
                 width=2, shadow=True)

        sc.text(px + 24, y + 18, str(case.get("label") or ""), size=27, color="ink", kind="bold")
        state_text = f"A = {value}"
        tw = sc.measure(state_text, 20, "mono_bold") + 24
        sc.rrect(px + panel_w - tw - 20, y + 16, tw, 30, radius=7,
                 fill="blue_soft", outline=None, shadow=False)
        sc.text(px + panel_w - tw / 2 - 20, y + 31, state_text, size=20, color="blue",
                kind="mono_bold", anchor="mm")

        cy = y + 220
        bx = px + 86
        lx = px + panel_w - 86
        _battery(sc, bx, cy, label=True)
        _lamp(sc, lx, cy, lamp_on, label="лампа")

        card_w = min(300, panel_w - 260)
        card_h = 140
        sx = px + (panel_w - card_w) / 2
        sy = cy - card_h / 2
        term_y = _switch_card(sc, sx, sy, card_w, card_h, "A", value, inverted=inverted)

        top_y = y + 96
        bottom_y = y + panel_h - 56
        sc.arrow([(bx, cy - 34), (bx, top_y), (sx, top_y), (sx, term_y)],
                 color="orange", width=3, head=12, terminal=True, glow=True)
        sc.arrow([(sx + card_w, term_y), (lx - 38, term_y)],
                 color="orange", width=3, head=12, terminal=False, glow=True)
        sc.arrow([(lx, cy + 36), (lx, bottom_y), (bx, bottom_y), (bx, cy + 34)],
                 color="orange", width=3, head=12, terminal=False, glow=True)

    sc.caption(spec.get("caption") or "")


# ------------------------------------------------------------------
#  Логические элементы
# ------------------------------------------------------------------


def _gate_not(sc: Scene, x, y, size=64) -> None:
    sc.draw.polygon([(sc.s(x), sc.s(y - size / 2)), (sc.s(x), sc.s(y + size / 2)),
                     (sc.s(x + size), sc.s(y))], fill=(*sc.style.c("card"), 255),
                    outline=(*sc.style.c("ink"), 255), width=sc.s(3))
    r = 9
    sc.draw.ellipse(sc.box(x + size + 2, y - r, 2 * r, 2 * r), fill=(255, 255, 255, 255),
                    outline=(*sc.style.c("ink"), 255), width=sc.s(3))
    sc.line([(x - 30, y), (x, y)], color="orange", width=3)
    sc.line([(x + size + 2 * r, y), (x + size + 2 * r + 30, y)], color="orange", width=3)


def _gate_and(sc: Scene, x, y, size=64) -> None:
    r = size / 2
    points = [(x, y - r)]
    for i in range(21):
        a = -math.pi / 2 + i * math.pi / 20
        points.append((x + size * 0.55 + r * math.cos(a), y + r * math.sin(a)))
    points += [(x, y + r)]
    sc.draw.polygon([(sc.s(px), sc.s(py)) for px, py in points],
                    fill=(*sc.style.c("card"), 255), outline=(*sc.style.c("ink"), 255),
                    width=sc.s(3))
    sc.line([(x - 30, y - 20), (x, y - 20)], color="orange", width=3)
    sc.line([(x - 30, y + 20), (x, y + 20)], color="orange", width=3)
    sc.line([(x + size * 0.55 + r, y), (x + size * 0.55 + r + 30, y)], color="orange", width=3)


def _qbez(p0, p1, p2, n=18):
    points = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        points.append((x, y))
    return points


def _gate_or(sc: Scene, x, y, size=64) -> None:
    r = size / 2
    tip = (x + size * 0.95, y)
    top = _qbez((x, y - r), (x + size * 0.55, y - r * 1.02), tip)
    bottom = _qbez(tip, (x + size * 0.55, y + r * 1.02), (x, y + r))
    left = _qbez((x, y + r), (x + size * 0.30, y), (x, y - r))
    points = top + bottom[1:] + left[1:]
    sc.draw.polygon([(sc.s(px), sc.s(py)) for px, py in points],
                    fill=(*sc.style.c("card"), 255), outline=(*sc.style.c("ink"), 255),
                    width=sc.s(3))
    sc.line([(x - 30, y - 24), (x + size * 0.05, y - 24)], color="orange", width=3)
    sc.line([(x - 30, y + 24), (x + size * 0.05, y + 24)], color="orange", width=3)
    sc.line([(tip[0], tip[1]), (tip[0] + 30, tip[1])], color="orange", width=3)


def scene_gates(sc: Scene, spec: dict) -> None:
    gates = spec.get("gates") or []
    if not gates:
        return
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 60 if spec.get("caption") else 20
    n = len(gates)
    gap = 36
    card_w = min(420, (sc.w - 2 * sc.margin - gap * (n - 1)) / n)
    card_h = 330
    total = n * card_w + gap * (n - 1)
    x0 = (sc.w - total) / 2
    y = 100 + title_h + max(0, (sc.h - 100 - title_h - caption_h - card_h) / 2 - 10)
    symbols = {"not": "НЕ", "and": "И", "or": "ИЛИ"}
    subtitles = {"not": "инверсия", "and": "конъюнкция", "or": "дизъюнкция"}
    expressions = {"not": "F = ¬A", "and": "F = A · B", "or": "F = A + B"}

    for i, gate in enumerate(gates):
        kind = str(gate.get("kind") or "and")
        x = x0 + i * (card_w + gap)
        sc.rrect(x, y, card_w, card_h, radius=16, fill="card", outline="line", width=2, shadow=True)
        sc.text(x + 24, y + 18, symbols.get(kind, kind.upper()), size=32, color="blue", kind="bold")
        sc.text(x + 24, y + 58, subtitles.get(kind, ""), size=20, color="muted", kind="body")
        gx = x + 120
        gy = y + 175
        if kind == "not":
            _gate_not(sc, gx, gy, size=84)
            inputs = [gate.get("input", 1)]
            output = gate.get("output", 0)
            sc.text(x + 24, gy - 58, f"A = {inputs[0]}", size=22, color="ink", kind="mono_bold")
            sc.text(x + card_w - 24, gy + 52, f"F = {output}", size=22, color="orange",
                    kind="mono_bold", anchor="ra")
        elif kind == "and":
            _gate_and(sc, gx, gy, size=84)
            inputs = gate.get("inputs", [1, 1])
            output = gate.get("output", 1)
            sc.text(x + 24, gy - 62, f"A = {inputs[0]}", size=22, color="ink", kind="mono_bold")
            sc.text(x + 24, gy + 28, f"B = {inputs[1]}", size=22, color="ink", kind="mono_bold")
            sc.text(x + card_w - 24, gy + 52, f"F = {output}", size=22, color="orange",
                    kind="mono_bold", anchor="ra")
        else:
            _gate_or(sc, gx, gy, size=84)
            inputs = gate.get("inputs", [0, 1])
            output = gate.get("output", 1)
            sc.text(x + 24, gy - 62, f"A = {inputs[0]}", size=22, color="ink", kind="mono_bold")
            sc.text(x + 24, gy + 28, f"B = {inputs[1]}", size=22, color="ink", kind="mono_bold")
            sc.text(x + card_w - 24, gy + 52, f"F = {output}", size=22, color="orange",
                    kind="mono_bold", anchor="ra")
        sc.text(x + card_w / 2, y + card_h - 26, expressions.get(kind, ""), size=22,
                color="muted", kind="mono", anchor="mm")

    sc.caption(spec.get("caption") or "")


def scene_frames(sc: Scene, spec: dict) -> None:
    """Заглушки: пунктирные рамки под QR-коды или скриншоты."""
    items = spec.get("items") or []
    if not items:
        return
    title_h = sc.title_block(spec.get("title") or "")
    caption_h = 60 if spec.get("caption") else 20
    n = len(items)
    gap = 110
    card_w = min(620, (sc.w - 2 * sc.margin - gap * (n - 1)) / n)
    total = n * card_w + gap * (n - 1)
    x0 = (sc.w - total) / 2
    aspect = list(spec.get("aspect") or [1, 1])
    aw, ah = float(aspect[0]), float(aspect[1])
    frame_w = card_w - 48
    frame_h = frame_w * ah / aw
    max_h = 430
    if frame_h > max_h:
        frame_h = max_h
        frame_w = frame_h * aw / ah
    text_h = 60 if any(str(i.get("text") or "") for i in items) else 0
    card_h = 24 + 40 + frame_h + 16 + 26 + text_h + 20
    y = 110 + title_h + max(0, (sc.h - 110 - title_h - caption_h - card_h) / 2 - 10)
    for i, item in enumerate(items):
        x = x0 + i * (card_w + gap)
        border, _ = sc.tone(item.get("tone") or "blue")
        sc.rrect(x, y, card_w, card_h, radius=14, fill="card", outline=border,
                 width=2, shadow=True, glow=border, glow_alpha=50)
        sc.rrect(x + 20, y + 20, 12, 12, radius=3, fill=border, outline=None, shadow=False)
        sc.text(x + 44, y + 46, str(item.get("title") or ""), size=26, color="ink", kind="bold")
        fx = x + (card_w - frame_w) / 2
        fy = y + 76
        sc.rrect(fx, fy, frame_w, frame_h, radius=10, fill="paper", outline="muted",
                 width=2, dashed=True)
        mark = 26
        for cx, cy in ((fx, fy), (fx + frame_w - mark, fy),
                       (fx, fy + frame_h - mark), (fx + frame_w - mark, fy + frame_h - mark)):
            sc.rrect(cx, cy, mark, mark, radius=4, outline="muted", width=3)
        sc.text(x + card_w / 2, fy + frame_h + 26, str(item.get("label") or "заглушка"),
                size=18, color="muted", kind="mono", anchor="mm")
        text = str(item.get("text") or "")
        if text:
            sc.paragraph(x + 24, fy + frame_h + 52, card_w - 48, text, size=19,
                         color="muted", line=1.3, max_lines=2)
    sc.caption(spec.get("caption") or "")


SCENES = {
    "array": scene_array,
    "radix": scene_radix,
    "recursion": scene_recursion,
    "division": scene_division,
    "flow": scene_flow,
    "layers": scene_layers,
    "schema": scene_schema,
    "tree": scene_tree,
    "dots": scene_dots,
    "logic": scene_logic,
    "gates": scene_gates,
    "frames": scene_frames,
}


def render(spec: dict[str, Any], style: Style) -> Image.Image:
    kind = str(spec.get("type") or "").strip().lower()
    if kind not in SCENES:
        raise SystemExit(f"Неизвестный тип иллюстрации: {kind}. Доступны: {', '.join(sorted(SCENES))}")
    scene = Scene(spec, style)
    SCENES[kind](scene, spec)
    image = scene.img.resize((scene.w, scene.h), Image.LANCZOS)
    if scene.background == "paper":
        return image.convert("RGB")
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description="Сгенерировать иллюстрации из YAML-описаний")
    parser.add_argument("specs", nargs="*", help="YAML-файлы или папки со спецификациями")
    parser.add_argument("--style", default=str(DEFAULT_STYLE), help="Файл стиля")
    parser.add_argument("--out", help="Файл PNG или папка (по умолчанию рядом со спецификацией)")
    parser.add_argument("--types", action="store_true", help="Показать доступные типы")
    args = parser.parse_args()

    if args.types:
        print("Доступные типы:", ", ".join(sorted(SCENES)))
        return 0
    if not args.specs:
        parser.print_help()
        return 1

    style = Style.load(args.style)
    files: list[Path] = []
    for item in args.specs:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob("*.yaml")))
        elif path.exists():
            files.append(path)
        else:
            print(f"! Не найдено: {path}", file=sys.stderr)
    if not files:
        print("Нет файлов для обработки.", file=sys.stderr)
        return 1

    out_arg = Path(args.out) if args.out else None
    single = len(files) == 1
    count = 0
    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            spec = yaml.safe_load(fh) or {}
        image = render(spec, style)
        if out_arg and (out_arg.suffix.lower() == ".png" and single):
            target = out_arg
        elif out_arg:
            target = out_arg / f"{path.stem}.png"
        else:
            target = path.with_suffix(".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, optimize=True)
        print(f"  ✓ {path.stem}: {target} ({image.width}×{image.height})")
        count += 1
    print(f"Готово: {count} иллюстраций.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
