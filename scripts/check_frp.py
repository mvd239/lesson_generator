#!/usr/bin/env python3
"""Сверка презентации с федеральной рабочей программой (ФРП).

Примеры:
    python3 scripts/check_frp.py decks/01-algebra-logiki-8-klass
    python3 scripts/check_frp.py decks/02-algoritmy-sortirovki --grade 10
    python3 scripts/check_frp.py decks/01-algebra-logiki-8-klass --grade 8 --json

Скрипт только сверяет и печатает отчёт: он не меняет deck.yaml и не блокирует
сборку. Смысл — показать, какие темы ФРП для класса раскрыты на слайдах,
какие остались за кадром и не вышла ли презентация за программу класса.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import DeckError, Slide, load_deck  # noqa: E402

DEFAULT_TOPICS = (
    PROJECT_ROOT / ".opencode" / "skills" / "presentation-standards"
    / "references" / "topics.yaml"
)

SKIP_KEYS = {"notes", "code", "image", "language", "layout", "mascot", "mascot_pose"}
GRADE_RE = re.compile(r"(\d{1,2})\s*(?:класс|курс)", re.IGNORECASE)


@dataclass
class Topic:
    grade: int
    module: str
    id: str
    name: str
    keywords: list[str]


@dataclass
class Hit:
    topic: Topic
    slides: list[int] = field(default_factory=list)
    matched: set[str] = field(default_factory=set)


def normalize(text: str) -> str:
    text = str(text).lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text)
    return f" {text.strip()} "


def stem_regex(stem: str) -> re.Pattern[str]:
    stem = normalize(stem).strip()
    if not stem:
        return re.compile(r"$^")
    escaped = re.escape(stem)
    if len(stem) <= 4:
        return re.compile(rf"(?<![0-9a-zа-я]){escaped}(?![0-9a-zа-я])")
    return re.compile(escaped)


def keyword_matches(keyword: str, text: str) -> bool:
    """Ключ из нескольких слов — словосочетание: слова идут подряд."""
    parts = [p for p in normalize(keyword).split() if p]
    if not parts:
        return False
    if len(parts) == 1:
        return bool(stem_regex(parts[0]).search(text))
    chunks = []
    for part in parts:
        guard = r"(?<![0-9a-zа-я])" if len(part) <= 4 else ""
        tail = r"(?![0-9a-zа-я])" if len(part) <= 4 else r"\w*"
        chunks.append(guard + re.escape(part) + tail)
    return bool(re.search(r"\W+".join(chunks), text))


def collect_text(value: Any, out: list[str]) -> None:
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, bool) or value is None:
        return
    elif isinstance(value, (int, float)):
        out.append(str(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in SKIP_KEYS:
                continue
            collect_text(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            collect_text(item, out)
    else:
        text = getattr(value, "text", None)
        if text:
            out.append(str(text))


def slide_text(slide: Slide) -> str:
    parts: list[str] = []
    collect_text(slide.data, parts)
    return normalize(" ".join(parts))


def load_topics(path: Path) -> tuple[dict[int, list[Topic]], dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    grades: dict[int, list[Topic]] = {}
    for grade, items in (raw.get("grades") or {}).items():
        topics = []
        for item in items or []:
            keywords = [str(k) for k in item.get("keywords") or [] if str(k).strip()]
            if not keywords:
                continue
            topics.append(Topic(
                grade=int(grade),
                module=str(item["module"]),
                id=str(item.get("id") or item["name"]),
                name=str(item["name"]),
                keywords=keywords,
            ))
        grades[int(grade)] = topics
    return grades, raw


def detect_grade(deck, override: int | None) -> tuple[int | None, str]:
    if override:
        return override, "ключ --grade"
    meta = deck.meta
    if meta.get("grade"):
        try:
            return int(meta["grade"]), "meta.grade"
        except (TypeError, ValueError):
            pass
    for key in ("org", "audience_label", "subtitle"):
        match = GRADE_RE.search(str(meta.get(key) or ""))
        if match:
            return int(match.group(1)), f"meta.{key}"
    return None, "не указан"


def detect_level(deck, override: str | None) -> str:
    if override:
        return override
    return str(deck.meta.get("level") or "advanced").lower()


def match_topics(texts: list[str], topics: list[Topic]) -> list[Hit]:
    hits: list[Hit] = []
    for topic in topics:
        slides = []
        matched: set[str] = set()
        for index, text in enumerate(texts, start=1):
            for keyword in topic.keywords:
                if keyword_matches(keyword, text):
                    matched.add(keyword)
                    if index not in slides:
                        slides.append(index)
        hits.append(Hit(topic=topic, slides=slides, matched=matched))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Сверить презентацию с ФРП")
    parser.add_argument("deck", help="Папка с deck.yaml")
    parser.add_argument("--grade", type=int, help="Класс (перекрывает meta.grade)")
    parser.add_argument("--level", choices=("base", "advanced"), help="Уровень программы")
    parser.add_argument("--topics", default=str(DEFAULT_TOPICS), help="Файл с темами ФРП")
    parser.add_argument("--json", action="store_true", help="Вывести отчёт в JSON")
    parser.add_argument("--strict", action="store_true",
                        help="Ненулевой код, если ни одна тема класса не найдена")
    parser.add_argument("--explain", action="store_true",
                        help="Показать, какие ключевые слова совпали")
    args = parser.parse_args()

    try:
        deck = load_deck(args.deck)
    except DeckError as exc:
        print(f"Ошибка в презентации: {exc}", file=sys.stderr)
        return 2

    grades, meta = load_topics(Path(args.topics))
    grade, grade_source = detect_grade(deck, args.grade)
    level = detect_level(deck, args.level)

    program = meta.get("source") or []
    if grade is None:
        print("Не удалось определить класс. Укажите meta.grade или --grade N.", file=sys.stderr)
        print(f"Доступны классы: {', '.join(map(str, sorted(grades)))}.", file=sys.stderr)
        return 2
    if grade not in grades:
        print(f"Для {grade} класса нет данных ФРП. Доступны: "
              f"{', '.join(map(str, sorted(grades)))}.", file=sys.stderr)
        return 2

    texts = [slide_text(s) for s in deck.slides]
    current = grades[grade]
    hits = match_topics(texts, current)

    current_ids = {t.id for t in current}
    outside: dict[str, dict[str, Any]] = {}
    for other_grade, items in grades.items():
        if other_grade == grade:
            continue
        for hit in match_topics(texts, items):
            if not hit.slides or hit.topic.id in current_ids:
                continue
            if len(hit.slides) < 3 or len(hit.matched) < 2:
                continue
            entry = outside.setdefault(hit.topic.id, {
                "name": hit.topic.name, "grades": set(), "slides": set(),
            })
            entry["grades"].add(other_grade)
            entry["slides"].update(hit.slides)

    covered = [h for h in hits if h.slides]
    total = len(hits)
    result = {
        "title": deck.title,
        "slides": len(deck.slides),
        "grade": grade,
        "grade_source": grade_source,
        "level": level,
        "program": program,
        "topics": [
            {
                "module": h.topic.module,
                "name": h.topic.name,
                "id": h.topic.id,
                "slides": h.slides,
                "covered": bool(h.slides),
            }
            for h in hits
        ],
        "covered": len(covered),
        "total": total,
        "outside": [
            {"name": v["name"], "grades": sorted(v["grades"]), "slides": sorted(v["slides"])}
            for v in sorted(outside.values(), key=lambda x: x["name"])
        ],
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        level_ru = {"advanced": "углублённый", "base": "базовый"}.get(level, level)
        print(f"Презентация: «{deck.title}» · слайдов: {len(deck.slides)}")
        print(f"Класс: {grade} ({grade_source}) · уровень: {level_ru}")
        if program:
            print(f"Программа: {program[0]}")
            for extra in program[1:]:
                print(f"           {extra}")
        if level != "advanced":
            print("  ! Файл тем собран по углублённой программе; "
                  "для базового уровня сверяйте с базовой ФРП.")
        print()

        by_module: dict[str, list[Hit]] = {}
        for hit in hits:
            by_module.setdefault(hit.topic.module, []).append(hit)
        for module, items in by_module.items():
            print(module)
            for hit in items:
                if hit.slides:
                    slides = ", ".join(str(n) for n in hit.slides)
                    print(f"  ✓ {hit.topic.name} — слайды {slides}")
                    if args.explain:
                        print(f"      ключи: {', '.join(sorted(hit.matched))}")
                else:
                    print(f"  · {hit.topic.name} — не раскрыто")
            print()

        print(f"Итог: раскрыто {len(covered)} из {total} тем класса.")
        modules_done = sorted({h.topic.module for h in covered})
        if modules_done:
            print(f"Затронутые разделы: {', '.join(modules_done)}.")

        if outside:
            print()
            print("Вне программы класса")
            for item in result["outside"]:
                grades_str = ", ".join(str(g) for g in item["grades"])
                slides = ", ".join(str(n) for n in item["slides"])
                print(f"  ! {item['name']} — по ФРП это {grades_str} класс "
                      f"(слайды {slides}). Проверьте рабочую программу учителя.")

        if not covered:
            print()
            print("Соответствия темам класса не найдено: проверьте класс, "
                  "уровень и формулировки на слайдах.")

    if args.strict and not covered:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
