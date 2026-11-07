"""Шаблон оформления: цвета, шрифты, логотип и геометрия слайда."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_THEME_DIR = PROJECT_ROOT / "templates" / "default"

DEFAULTS: dict[str, Any] = {
    "name": "default",
    "slide": {"width": 13.333, "height": 7.5},
    "colors": {
        "primary": "#12305B",
        "primary_dark": "#0A1D3A",
        "accent": "#0AB2A9",
        "accent_soft": "#E1F7F5",
        "ink": "#16202B",
        "muted": "#5A6B7B",
        "line": "#D8E1EA",
        "surface": "#FFFFFF",
        "surface_alt": "#F2F7FB",
        "dark_panel": "#0A1623",
        "code_bg": "#0F2233",
        "code_text": "#E6EDF3",
    },
    "fonts": {"heading": "Arial", "body": "Arial", "mono": "Courier New", "scale": 1.0},
    "background": {"light": "assets/bg-light.png", "dark": "assets/bg-dark.png"},
    "logo": {"file": "assets/logo.png", "file_dark": "assets/logo_dark.png", "width": 0.62},
    "footer": "",
    "margins": {"left": 0.85, "right": 0.85, "top": 0.55, "bottom": 0.55},
}


class ThemeError(Exception):
    pass


def _merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = str(value).strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ThemeError(f"Некорректный цвет: {value!r}. Ожидается вид #RRGGBB.")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def mix(color_a: str, color_b: str, ratio: float) -> str:
    """Смешивает цвета: ratio=0 → color_a, ratio=1 → color_b."""
    a = hex_to_rgb(color_a)
    b = hex_to_rgb(color_b)
    ratio = max(0.0, min(1.0, ratio))
    out = tuple(round(a[i] + (b[i] - a[i]) * ratio) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*out)


def readable_on(background: str) -> str:
    """Возвращает #FFFFFF или #16202B в зависимости от яркости фона."""
    r, g, b = hex_to_rgb(background)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#FFFFFF" if luminance < 0.62 else "#16202B"


@dataclass
class Theme:
    name: str
    base_dir: Path
    width: float
    height: float
    colors: dict[str, str]
    fonts: dict[str, Any]
    background_light: Path | None
    background_dark: Path | None
    logo_file: Path | None
    logo_dark_file: Path | None
    logo_width: float
    footer: str
    margins: dict[str, float]
    raw: dict[str, Any] = field(default_factory=dict)

    # ---------- загрузка ----------

    @classmethod
    def load(cls, theme_dir: str | Path | None = None) -> "Theme":
        base = Path(theme_dir).resolve() if theme_dir else DEFAULT_THEME_DIR
        theme_file = base / "theme.yaml"
        if not theme_file.exists():
            raise ThemeError(f"Не найден шаблон оформления: {theme_file}")

        with theme_file.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        data = _merge(DEFAULTS, raw)

        def resolve_logo(value: Any) -> Path | None:
            path = Path(str(value or ""))
            if not path.is_absolute():
                path = base / path
            return path if path.exists() else None

        logo_path = resolve_logo(data["logo"].get("file"))
        logo_dark = resolve_logo(data["logo"].get("file_dark")) or logo_path
        background_light = resolve_logo(data.get("background", {}).get("light"))
        background_dark = resolve_logo(data.get("background", {}).get("dark"))

        scale = float(data["fonts"].get("scale", 1.0))
        return cls(
            name=str(data.get("name") or "default"),
            base_dir=base,
            width=float(data["slide"]["width"]),
            height=float(data["slide"]["height"]),
            colors={k: str(v) for k, v in data["colors"].items()},
            fonts={**data["fonts"], "scale": scale},
            background_light=background_light,
            background_dark=background_dark,
            logo_file=logo_path,
            logo_dark_file=logo_dark,
            logo_width=float(data["logo"].get("width", 0.62)),
            footer=str(data.get("footer") or ""),
            margins={k: float(v) for k, v in data["margins"].items()},
            raw=data,
        )

    # ---------- геометрия ----------

    @property
    def content_left(self) -> float:
        return self.margins["left"]

    @property
    def content_right(self) -> float:
        return self.width - self.margins["right"]

    @property
    def content_width(self) -> float:
        return self.content_right - self.content_left

    @property
    def content_top(self) -> float:
        return 0.55

    @property
    def content_bottom(self) -> float:
        return self.height - 0.78

    def pt(self, points: float) -> float:
        return points * float(self.fonts.get("scale", 1.0))

    def color(self, key: str) -> str:
        try:
            return self.colors[key]
        except KeyError as exc:
            raise ThemeError(f"В theme.yaml нет цвета «{key}».") from exc

    def rgb(self, key: str) -> tuple[int, int, int]:
        return hex_to_rgb(self.color(key))

    def pdf_color(self, key: str):
        from reportlab.lib.colors import Color

        r, g, b = self.rgb(key)
        return Color(r / 255, g / 255, b / 255)


# ---------------------------------------------------------------
#  Шрифты для PDF
# ---------------------------------------------------------------

_FONT_CANDIDATES = {
    "regular": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ],
    "bold": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ],
    "mono": [
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ],
    "mono_bold": [
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
        "C:/Windows/Fonts/courbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    ],
}


class FontBook:
    """Регистрирует TTF-шрифты для ReportLab (кириллица обязательна)."""

    def __init__(self, theme: Theme):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        self.theme = theme
        self.names: dict[str, str] = {}
        self._pdfmetrics = pdfmetrics

        if not self._register(pdfmetrics, TTFont, "body", "regular"):
            raise ThemeError(
                "Не найден шрифт с поддержкой кириллицы для PDF. "
                "Установите Arial, Liberation Sans или DejaVu Sans."
            )
        if not self._register(pdfmetrics, TTFont, "bold", "bold"):
            self.names["bold"] = self.names["body"]
        if not self._register(pdfmetrics, TTFont, "mono", "mono"):
            self.names["mono"] = self.names["body"]
        if not self._register(pdfmetrics, TTFont, "mono_bold", "mono_bold"):
            self.names["mono_bold"] = self.names["mono"]

    def _register(self, pdfmetrics, TTFont, name: str, kind: str) -> bool:
        own = self.theme.base_dir / "assets" / "fonts"
        own_candidates = [
            own / f"{kind}.ttf",
            own / f"{self.theme.fonts.get('body', 'Arial').replace(' ', '')}-{kind}.ttf",
        ]
        for path in [*own_candidates, *[Path(p) for p in _FONT_CANDIDATES[kind]]]:
            if not path.exists():
                continue
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                self.names[name] = name
                return True
            except Exception as exc:  # noqa: BLE001
                print(f"  ! Не удалось загрузить шрифт {path}: {exc}", file=sys.stderr)
        return False

    def get(self, kind: str = "body") -> str:
        return self.names.get(kind, self.names["body"])


def ensure_utf8_stdio() -> None:
    """Чтобы русские сообщения не падали в консоли Windows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def pil_font_path(kind: str = "regular") -> Path | None:
    """Путь к TTF-файлу для Pillow (иллюстрации)."""
    for candidate in _FONT_CANDIDATES.get(kind, []):
        path = Path(candidate)
        if path.exists():
            return path
    return None
