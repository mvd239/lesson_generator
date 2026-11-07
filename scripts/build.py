#!/usr/bin/env python3
"""Сборка презентации из deck.yaml в PPTX, PDF и HTML.

Примеры:
    python3 scripts/build.py decks/01-algebra-logiki-8-klass
    python3 scripts/build.py decks/01-algebra-logiki-8-klass --formats pptx,pdf
    python3 scripts/build.py --refresh-template
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_template import build_template  # noqa: E402
from model import DeckError, load_deck  # noqa: E402
from render_html import render_html  # noqa: E402
from render_pdf import render_pdf  # noqa: E402
from render_pptx import render_pptx  # noqa: E402
from theme import Theme, ThemeError, ensure_utf8_stdio  # noqa: E402

SUPPORTED = ("pptx", "pdf", "html")


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} МБ"
    if size >= 1024:
        return f"{size / 1024:.0f} КБ"
    return f"{size} Б"


def parse_formats(value: str | None, fallback: list[str]) -> list[str]:
    raw = value.split(",") if value else fallback
    result: list[str] = []
    for item in raw:
        fmt = str(item).strip().lower().lstrip(".")
        if not fmt:
            continue
        if fmt not in SUPPORTED:
            raise DeckError(
                f"Формат «{fmt}» не поддерживается. Доступны: {', '.join(SUPPORTED)}."
            )
        if fmt not in result:
            result.append(fmt)
    return result


def main() -> int:
    ensure_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Собрать презентацию по информатике из deck.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("deck", nargs="?", help="Папка с deck.yaml или путь к deck.yaml")
    parser.add_argument("--formats", help="Список форматов через запятую: pptx,pdf,html")
    parser.add_argument("--out", help="Папка для результатов (по умолчанию dist/<slug>)")
    parser.add_argument("--theme-dir", help="Папка шаблона (по умолчанию templates/default)")
    parser.add_argument("--refresh-template", action="store_true",
                        help="Пересобрать base.pptx из theme.yaml")
    parser.add_argument("--check", action="store_true", help="Только проверить deck.yaml")
    args = parser.parse_args()

    theme_dir = Path(args.theme_dir).resolve() if args.theme_dir else PROJECT_ROOT / "templates" / "default"
    try:
        theme = Theme.load(theme_dir)
    except ThemeError as exc:
        print(f"Ошибка шаблона: {exc}", file=sys.stderr)
        return 1

    base_pptx = theme_dir / "base.pptx"
    if args.refresh_template or not base_pptx.exists():
        build_template(theme, base_pptx)
        print(f"Шаблон обновлён: {base_pptx.relative_to(PROJECT_ROOT) if base_pptx.is_relative_to(PROJECT_ROOT) else base_pptx}")

    if not args.deck:
        if args.refresh_template:
            return 0
        parser.print_help()
        return 1

    try:
        deck = load_deck(args.deck)
        formats = parse_formats(args.formats, deck.formats)
    except DeckError as exc:
        print(f"Ошибка в презентации: {exc}", file=sys.stderr)
        return 1

    print(f"Презентация: «{deck.title}»")
    print(f"Слайдов: {len(deck.slides)} · формат: {', '.join(formats)}")
    print(f"Шаблон: {theme.name}")

    if args.check:
        print("Проверка пройдена.")
        return 0

    out_dir = Path(args.out).resolve() if args.out else PROJECT_ROOT / "dist" / deck.slug
    out_dir.mkdir(parents=True, exist_ok=True)

    builders = {
        "pptx": lambda path: render_pptx(deck, theme, path, base_pptx),
        "pdf": lambda path: render_pdf(deck, theme, path),
        "html": lambda path: render_html(deck, theme, path),
    }

    print()
    builds: list[tuple[str, Path]] = []
    for fmt in formats:
        target = out_dir / f"{deck.slug}.{fmt}"
        try:
            builders[fmt](target)
        except ThemeError as exc:
            print(f"  ✗ {fmt.upper()}: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {fmt.upper()}: {exc}", file=sys.stderr)
            return 1
        builds.append((fmt, target))
        print(f"  ✓ {fmt.upper():4} {human_size(target.stat().st_size):>8}  {target}")

    print()
    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
