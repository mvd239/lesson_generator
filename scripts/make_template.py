"""Сборка базового шаблона PPTX: размер слайда, цвета и шрифты темы.

Полученный templates/default/base.pptx используется как основа для всех
презентаций, поэтому цвета темы видны в PowerPoint, Р7-Офисе, МойОфис и
LibreOffice в разделе «Оформление».
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Inches

from theme import Theme, mix, readable_on

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"a": A_NS}


def _set_color(scheme, tag: str, value: str) -> None:
    node = scheme.find(f"a:{tag}", NS)
    if node is None:
        return
    for child in list(node):
        node.remove(child)
    color = etree.SubElement(node, f"{{{A_NS}}}srgbClr")
    color.set("val", value.lstrip("#").upper())


def _build_theme_xml(theme: Theme) -> bytes:
    prs = Presentation()
    theme_part = prs.slide_masters[0].part.part_related_by(RT.THEME)
    root = etree.fromstring(theme_part.blob)

    root.set("name", theme.name)
    scheme = root.find(".//a:clrScheme", NS)
    if scheme is None:
        raise RuntimeError("Не удалось найти цветовую схему в шаблоне PowerPoint.")
    mapping = {
        "dk1": theme.color("ink"),
        "lt1": theme.color("surface"),
        "dk2": theme.color("primary"),
        "lt2": theme.color("surface_alt"),
        "accent1": theme.color("primary"),
        "accent2": theme.color("accent"),
        "accent3": mix(theme.color("accent"), theme.color("primary"), 0.45),
        "accent4": mix(theme.color("accent"), "#FFFFFF", 0.35),
        "accent5": mix(theme.color("primary"), "#FFFFFF", 0.55),
        "accent6": mix(theme.color("primary"), theme.color("accent"), 0.6),
        "hlink": theme.color("accent"),
        "folHlink": mix(theme.color("accent"), theme.color("primary"), 0.5),
    }
    for tag, value in mapping.items():
        _set_color(scheme, tag, value)

    for font_tag in ("majorFont", "minorFont"):
        font = root.find(f".//a:{font_tag}", NS)
        if font is None:
            continue
        for lang in ("latin", "ea", "cs"):
            node = font.find(f"a:{lang}", NS)
            if node is not None:
                node.set("typeface", theme.fonts["body"])

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def build_template(theme: Theme, out_path: Path) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(theme.width)
    prs.slide_height = Inches(theme.height)

    theme_part = prs.slide_masters[0].part.part_related_by(RT.THEME)
    theme_part._blob = _build_theme_xml(theme)

    prs.core_properties.title = f"Шаблон: {theme.name}"
    prs.core_properties.subject = "Шаблон оформления презентаций по информатике"
    prs.core_properties.comments = "Сгенерировано scripts/make_template.py из theme.yaml"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Собрать base.pptx из theme.yaml")
    parser.add_argument("--theme-dir", default=str(Path(__file__).resolve().parent.parent / "templates" / "default"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    theme = Theme.load(args.theme_dir)
    out = Path(args.out) if args.out else Path(args.theme_dir) / "base.pptx"
    build_template(theme, out)
    print(f"Шаблон собран: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
