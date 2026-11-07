"""Загрузка и нормализация содержимого презентации (deck.yaml)."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LAYOUTS = {
    "title",
    "section",
    "bullets",
    "two-col",
    "cards",
    "steps",
    "quote",
    "table",
    "code",
    "image",
    "team",
    "summary",
    "end",
}

# Сколько элементов разумно держать на слайде: (минимум, максимум).
CAPACITY = {
    "bullets": (1, 7),
    "cards": (2, 4),
    "steps": (2, 5),
    "two-col": (1, 5),
    "table": (2, 7),
}

SLUG_RE = re.compile(r"[^a-z0-9]+")


class DeckError(Exception):
    """Понятная пользователю ошибка в deck.yaml."""


@dataclass
class Bullet:
    text: str
    level: int = 0
    strong: str | None = None  # часть строки, которую выделить жирным


@dataclass
class Slide:
    layout: str
    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class Deck:
    path: Path
    meta: dict[str, Any]
    slides: list[Slide]

    @property
    def slug(self) -> str:
        raw = str(self.meta.get("slug") or self.meta.get("title") or self.path.stem)
        translit = _translit(raw)
        slug = SLUG_RE.sub("-", translit.lower()).strip("-")
        return slug or "presentation"

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or "Без названия")

    @property
    def subtitle(self) -> str:
        return str(self.meta.get("subtitle") or "")

    @property
    def formats(self) -> list[str]:
        raw = self.meta.get("formats") or ["pdf"]
        if isinstance(raw, str):
            raw = [p.strip() for p in raw.split(",") if p.strip()]
        return [str(f).lower() for f in raw]


def _translit(text: str) -> str:
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    return "".join(table.get(ch, ch) for ch in text)


def normalize_bullets(raw: Any) -> list[Bullet]:
    """Приводит список тезисов к единому виду.

    Допустимые формы:
      - "строка"
      - {text: "...", level: 1}
      - {text: "...", strong: "слово"}
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    result: list[Bullet] = []
    for item in raw:
        if isinstance(item, str):
            result.append(Bullet(text=item))
        elif isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            level = int(item.get("level", 0) or 0)
            result.append(Bullet(text=text, level=max(0, min(level, 2)), strong=item.get("strong")))
        else:
            raise DeckError(f"Тезис должен быть строкой или словарём, получено: {item!r}")
    return result


def load_deck(path: str | Path) -> Deck:
    path = Path(path)
    if path.is_dir():
        candidates = [path / "deck.yaml", path / "deck.yml", path / "deck.json"]
        path = next((p for p in candidates if p.exists()), candidates[0])
    if not path.exists():
        raise DeckError(f"Файл не найден: {path}")

    with path.open("r", encoding="utf-8") as fh:
        if path.suffix == ".json":
            raw = yaml.safe_load(fh)
        else:
            raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise DeckError("Корень deck.yaml должен быть словарём с ключами meta и slides.")

    meta = dict(raw.get("meta") or {})
    if not meta.get("title"):
        raise DeckError("В meta не заполнено поле title (название презентации).")

    slides_raw = raw.get("slides")
    if not isinstance(slides_raw, list) or not slides_raw:
        raise DeckError("В deck.yaml нужен непустой список slides.")

    slides: list[Slide] = []
    for index, item in enumerate(slides_raw, start=1):
        if not isinstance(item, dict):
            raise DeckError(f"Слайд №{index}: ожидался словарь с полем layout.")
        layout = str(item.get("layout") or "bullets").strip()
        if layout not in LAYOUTS:
            raise DeckError(
                f"Слайд №{index}: неизвестный layout «{layout}». "
                f"Доступны: {', '.join(sorted(LAYOUTS))}."
            )
        data = dict(item)
        data.pop("layout", None)
        slides.append(Slide(layout=layout, data=_normalize_slide(layout, data, index)))

    deck = Deck(path=path.resolve(), meta=meta, slides=slides)
    validate(deck)
    return deck


def _normalize_slide(layout: str, data: dict[str, Any], index: int) -> dict[str, Any]:
    if "bullets" in data:
        data["bullets"] = normalize_bullets(data["bullets"])
    if layout == "two-col":
        for side in ("left", "right"):
            col = data.get(side)
            if isinstance(col, dict) and "bullets" in col:
                col["bullets"] = normalize_bullets(col["bullets"])
    if layout == "cards":
        cards = data.get("cards") or []
        if not isinstance(cards, list):
            raise DeckError(f"Слайд №{index}: cards должен быть списком.")
    if layout == "steps":
        steps = data.get("steps") or []
        if not isinstance(steps, list):
            raise DeckError(f"Слайд №{index}: steps должен быть списком.")
    if layout == "summary":
        columns = data.get("columns") or []
        if not isinstance(columns, list):
            raise DeckError(f"Слайд №{index}: columns должен быть списком.")
        for col in columns:
            if isinstance(col, dict) and "items" in col:
                col["items"] = normalize_bullets(col["items"])
    return data


def validate(deck: Deck) -> None:
    """Мягкая проверка: ошибки — исключение, перегруз — предупреждение."""
    warnings: list[str] = []
    if deck.meta.get("author"):
        warnings.append(
            "В meta указан author: для презентации учителя имя и фамилию убираем."
        )
    if deck.slides and deck.slides[-1].layout == "end":
        warnings.append(
            "Последний слайд — «Спасибо за внимание». Замените его опорным конспектом "
            "(layout: summary)."
        )
    if len(deck.slides) > 1 and deck.slides[1].layout == "section":
        warnings.append(
            "Слайд 2 — разделитель. Объедините титул и уточнение темы на первом слайде."
        )
    for index, slide in enumerate(deck.slides, start=1):
        layout = slide.layout
        if layout == "quote":
            warnings.append(
                f"Слайд №{index}: отдельный слайд-цитата. Перенесите цитату в тезис "
                "или в notes — без неё ничего не должно теряться."
            )
        if layout in CAPACITY and layout != "two-col":
            lo, hi = CAPACITY[layout]
            key = {"bullets": "bullets", "cards": "cards", "steps": "steps", "table": "rows"}[layout]
            count = len(slide.get(key) or [])
            if count < lo:
                warnings.append(f"Слайд №{index} ({layout}): мало элементов ({count}), рекомендуется от {lo}.")
            if layout == "bullets" and int(slide.get("columns") or 1) >= 2:
                hi *= 2
            if count > hi:
                warnings.append(
                    f"Слайд №{index} ({layout}): {count} элементов, это больше рекомендуемых {hi}. "
                    "Разделите слайд."
                )
        if layout == "table":
            rows = slide.get("rows") or []
            cols = slide.get("columns") or []
            width = len(cols) or (len(rows[0]) if rows else 0)
            if width == 0:
                warnings.append(f"Слайд №{index} (table): не заданы columns.")
            for r_i, row in enumerate(rows, start=1):
                if len(row) != width:
                    warnings.append(
                        f"Слайд №{index} (table): строка {r_i} содержит {len(row)} ячеек вместо {width}."
                    )
        if layout in {"section", "bullets", "code", "table", "image", "summary"}:
            if not slide.get("title"):
                warnings.append(f"Слайд №{index} ({layout}): не заполнен title.")
        if layout == "summary":
            columns = slide.get("columns") or []
            if not 2 <= len(columns) <= 4:
                warnings.append(
                    f"Слайд №{index} (summary): {len(columns)} колонок, рекомендуется 2–4."
                )
            for col_index, col in enumerate(columns, start=1):
                items = (col or {}).get("items") or []
                if not (col or {}).get("heading"):
                    warnings.append(
                        f"Слайд №{index} (summary), колонка {col_index}: нет heading."
                    )
                if not 1 <= len(items) <= 5:
                    warnings.append(
                        f"Слайд №{index} (summary), колонка {col_index}: "
                        f"{len(items)} пунктов, рекомендуется 1–5."
                    )
        if layout == "image" and not slide.get("image"):
            warnings.append(f"Слайд №{index} (image): не указан файл изображения.")
        if layout == "code" and not slide.get("code"):
            warnings.append(f"Слайд №{index} (code): пустой блок code.")

    for message in warnings:
        print(f"  ! {message}", file=sys.stderr)


def resolve_asset(deck: Deck, value: str | None) -> Path | None:
    """Ищет файл относительно папки презентации, затем проекта."""
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    roots = [deck.path.parent, deck.path.parent.parent, deck.path.parent.parent.parent]
    for root in roots:
        path = (root / candidate).resolve()
        if path.exists():
            return path
    return None
