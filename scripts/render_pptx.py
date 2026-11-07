"""Сборка PPTX из deck.yaml. Только базовые возможности OOXML —
чтобы файл одинаково открывался в PowerPoint, Р7-Офисе, МойОфис и LibreOffice."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

from model import Bullet, Deck, Slide, resolve_asset
from textfit import estimate_lines, fit_size
from theme import Theme, mix

EMU_IN = 914400
DARK_LAYOUTS = {"title", "section", "end"}


# ------------------------------------------------------------------
#  Мелкие помощники
# ------------------------------------------------------------------


def _rgb(value: str) -> RGBColor:
    return RGBColor.from_string(str(value).lstrip("#").upper())


def _no_line(shape) -> None:
    shape.line.fill.background()


def solid(shape, color: str, alpha: float | None = None) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(color)
    shape.shadow.inherit = False
    if alpha is not None:
        sp_pr = shape._element.spPr
        srgb = sp_pr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
        node = etree.SubElement(srgb, qn("a:alpha"))
        node.set("val", str(int(alpha * 100000)))


def rect(slide, x, y, w, h, color, alpha=None, rounded=False, radius=0.08,
         outline=None, outline_width=1.0):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    solid(shape, color, alpha)
    if outline:
        shape.line.color.rgb = _rgb(outline)
        shape.line.width = Pt(outline_width)
    else:
        _no_line(shape)
    if rounded:
        try:
            shape.adjustments[0] = radius
        except Exception:  # noqa: BLE001
            pass
    return shape


def ellipse(slide, x, y, w, h, color, alpha=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
    solid(shape, color, alpha)
    _no_line(shape)
    return shape


def _set_bullet(paragraph, char: str, color: str, indent: float, level: int) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_pr.set("marL", str(int(Inches(indent * (level + 1)))))
    p_pr.set("indent", str(int(-Inches(indent))))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buClr", "a:buFont", "a:buSzPct"):
        for node in p_pr.findall(qn(tag)):
            p_pr.remove(node)
    bu_clr = etree.SubElement(p_pr, qn("a:buClr"))
    srgb = etree.SubElement(bu_clr, qn("a:srgbClr"))
    srgb.set("val", str(color).lstrip("#").upper())
    bu_size = etree.SubElement(p_pr, qn("a:buSzPct"))
    bu_size.set("val", "100000")
    bu_font = etree.SubElement(p_pr, qn("a:buFont"))
    bu_font.set("typeface", "Arial")
    bu_char = etree.SubElement(p_pr, qn("a:buChar"))
    bu_char.set("char", char)


def _no_bullet(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    for tag in ("a:buChar", "a:buAutoNum", "a:buNone"):
        for node in p_pr.findall(qn(tag)):
            p_pr.remove(node)
    etree.SubElement(p_pr, qn("a:buNone"))


def _style_run(run, font: str, size: float, color: str, bold=False, italic=False, spc=None):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color)
    if spc is not None:
        run.font._rPr.set("spc", str(int(spc * 100)))


def textbox(
    slide,
    x,
    y,
    w,
    h,
    text="",
    *,
    font="Arial",
    size=18,
    color="#000000",
    bold=False,
    italic=False,
    align=PP_ALIGN.LEFT,
    anchor=MSO_ANCHOR.TOP,
    line_spacing=1.12,
    space_after=0,
    wrap=True,
    spc=None,
    margins=(0, 0, 0, 0),
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = wrap
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.vertical_anchor = anchor
    frame.margin_left, frame.margin_top, frame.margin_right, frame.margin_bottom = (
        Inches(margins[0]), Inches(margins[1]), Inches(margins[2]), Inches(margins[3])
    )
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.line_spacing = Pt(size * line_spacing) if isinstance(line_spacing, (int, float)) else line_spacing
    paragraph.space_after = Pt(space_after)
    _no_bullet(paragraph)
    run = paragraph.add_run()
    run.text = str(text)
    _style_run(run, font, size, color, bold, italic, spc)
    return box


def image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:  # noqa: BLE001
        return (16, 9)


# ------------------------------------------------------------------
#  Общие элементы слайда
# ------------------------------------------------------------------


def background(slide, theme: Theme, color_key: str = "surface") -> None:
    dark = color_key == "primary"
    path = theme.background_dark if dark else theme.background_light
    if path:
        slide.shapes.add_picture(str(path), 0, 0, width=Inches(theme.width), height=Inches(theme.height))
        return
    rect(slide, 0, 0, theme.width, theme.height, theme.color(color_key))


def logo(slide, theme: Theme, dark: bool, x: float | None = None, y: float = 0.5,
         width: float | None = None) -> None:
    path = theme.logo_dark_file if dark and theme.logo_dark_file else theme.logo_file
    if not path:
        return
    width = width or theme.logo_width
    px_w, px_h = image_size(path)
    height = width * px_h / max(px_w, 1)
    left = theme.content_right - width if x is None else x
    slide.shapes.add_picture(str(path), Inches(left), Inches(y), width=Inches(width), height=Inches(height))


def footer(slide, theme: Theme, index: int, total: int, dark: bool = False) -> None:
    color = mix(theme.color("primary"), "#FFFFFF", 0.72) if dark else theme.color("muted")
    line_color = mix(theme.color("primary"), "#FFFFFF", 0.30) if dark else theme.color("line")
    y = theme.height - 0.66
    rect(slide, theme.content_left, y, theme.content_width, 0.012, line_color)
    left = theme.footer or theme.name
    textbox(slide, theme.content_left, y + 0.09, theme.content_width * 0.7, 0.3, left,
            font=theme.fonts["body"], size=9.5, color=color)
    textbox(slide, theme.content_right - 1.6, y + 0.09, 1.6, 0.3, f"{index:02d} / {total:02d}",
            font=theme.fonts["body"], size=9.5, color=color, align=PP_ALIGN.RIGHT)


def header(slide, theme: Theme, title: str, kicker: str | None = None, show_logo: bool = True,
           dark: bool = False):
    """Заголовок контентного слайда. Возвращает Y начала тела."""
    x = theme.content_left
    if show_logo:
        logo(slide, theme, dark=dark, y=0.42)
    if kicker:
        kicker_color = mix(theme.color("accent"), "#FFFFFF", 0.35) if dark else theme.color("accent")
        textbox(slide, x + 0.02, 0.52, theme.content_width * 0.8, 0.28, kicker.upper(),
                font=theme.fonts["body"], size=10.5, color=kicker_color, bold=True, spc=1.2)
        title_y = 0.82
    else:
        title_y = 0.62

    available = theme.content_width - (theme.logo_width + 0.45 if show_logo else 0)
    title_size = 30 if len(title) <= 46 else 26 if len(title) <= 72 else 22
    title_size = fit_size([(title, 0)], available, 1.35, title_size, 18, spacing=1.12)
    rect(slide, x, title_y + 0.06, 0.075, 0.52 + (title_size - 18) * 0.012, theme.color("accent"))
    textbox(slide, x + 0.28, title_y, available, 1.25, title,
            font=theme.fonts["heading"], size=title_size,
            color="#FFFFFF" if dark else theme.color("primary"),
            bold=True, line_spacing=1.03, anchor=MSO_ANCHOR.TOP)
    return 2.28


def lead_text(slide, theme: Theme, text: str, y: float, width: float | None = None, dark=False) -> float:
    width = width or theme.content_width
    size = 17 if len(text) < 110 else 15
    color = mix(theme.color("primary"), "#FFFFFF", 0.30) if dark else theme.color("muted")
    lines = estimate_lines(text, width * 72, size)
    height = max(0.34, lines * size * 1.22 / 72 + 0.05)
    textbox(slide, theme.content_left, y, width, height, text,
            font=theme.fonts["body"], size=size, color=color, line_spacing=1.18)
    return y + height + 0.22


def bullets_block(slide, theme: Theme, bullets: list[Bullet], x, y, w, h,
                  size=20, min_size=13, color_key="ink", dark=False) -> None:
    if not bullets:
        return
    gap = 9
    body_size = fit_size(
        [(b.text, 0.32 * (b.level + 1)) for b in bullets], w, h, size, min_size,
        spacing=1.18, para_gap=gap,
    )
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = frame.margin_top = frame.margin_right = frame.margin_bottom = 0
    frame.vertical_anchor = MSO_ANCHOR.TOP

    for i, bullet in enumerate(bullets):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        if bullet.level == 0:
            char = "•"
            color = theme.color("accent")
            size_i = body_size
        else:
            char = "–"
            color = theme.color("muted")
            size_i = max(min_size, body_size - 2)
        paragraph.line_spacing = Pt(size_i * 1.18)
        paragraph.space_after = Pt(gap if i < len(bullets) - 1 else 0)
        _set_bullet(paragraph, char, color, 0.30, bullet.level)

        if bullet.strong:
            before, _, after = bullet.text.partition(bullet.strong)
            for piece, bold in ((before, False), (bullet.strong, True), (after, False)):
                if not piece:
                    continue
                run = paragraph.add_run()
                run.text = piece
                _style_run(run, theme.fonts["body"], size_i,
                           theme.color(color_key) if not dark else "#FFFFFF", bold=bold)
        else:
            run = paragraph.add_run()
            run.text = bullet.text
            _style_run(run, theme.fonts["body"], size_i,
                       theme.color(color_key) if not dark else "#FFFFFF")


# ------------------------------------------------------------------
#  Макеты
# ------------------------------------------------------------------


def layout_title(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme, "primary")
    ellipse(slide, theme.width - 4.6, -2.1, 7.0, 7.0, "#FFFFFF", alpha=0.05)
    ellipse(slide, theme.width - 2.9, theme.height - 2.6, 4.4, 4.4, theme.color("accent"), alpha=0.20)
    rect(slide, 0, 0, 0.22, theme.height, theme.color("accent"))

    logo(slide, theme, dark=True, x=theme.content_left, y=0.6, width=theme.logo_width * 1.35)

    kicker_parts = [str(deck.meta.get("subject") or "Информатика")]
    textbox(slide, theme.content_left, 2.02, theme.content_width * 0.9, 0.3,
            "  ·  ".join(kicker_parts), font=theme.fonts["body"], size=12,
            color=mix(theme.color("accent"), "#FFFFFF", 0.35), bold=True, spc=1.6)

    title_size = fit_size([(deck.title, 0)], theme.content_width - 0.4, 2.0, 46, 26, spacing=1.1)
    textbox(slide, theme.content_left, 2.4, theme.content_width - 0.4, 2.0, deck.title,
            font=theme.fonts["heading"], size=title_size, color="#FFFFFF", bold=True, line_spacing=1.04)

    y = 2.4 + 1.9
    if deck.subtitle:
        sub_size = 19 if len(deck.subtitle) < 120 else 16
        sub_lines = estimate_lines(deck.subtitle, (theme.content_width - 1.2) * 72, sub_size)
        textbox(slide, theme.content_left, 4.42, theme.content_width - 1.2,
                max(0.5, sub_lines * sub_size * 1.25 / 72 + 0.1), deck.subtitle,
                font=theme.fonts["body"], size=sub_size,
                color=mix(theme.color("primary"), "#FFFFFF", 0.78), line_spacing=1.2)
        y = 4.42 + sub_lines * sub_size * 1.25 / 72 + 0.2

    meta_line = "  ·  ".join(
        str(v) for v in (deck.meta.get("author"), deck.meta.get("org"), deck.meta.get("date")) if v
    )
    if meta_line:
        rect(slide, theme.content_left, theme.height - 1.55, 0.9, 0.045, theme.color("accent"))
        textbox(slide, theme.content_left, theme.height - 1.35, theme.content_width, 0.5, meta_line,
                font=theme.fonts["body"], size=12,
                color=mix(theme.color("primary"), "#FFFFFF", 0.62))


def layout_section(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme, "primary")
    ellipse(slide, -1.6, theme.height - 3.6, 5.4, 5.4, "#FFFFFF", alpha=0.045)
    rect(slide, 0, 0, 0.22, theme.height, theme.color("accent"))
    logo(slide, theme, dark=True, y=0.55)

    number = str(s.get("number") or "")
    kicker = s.get("kicker")
    y = 2.35
    if number:
        textbox(slide, theme.content_left, 1.15, 3.0, 1.1, number,
                font=theme.fonts["heading"], size=64,
                color=mix(theme.color("accent"), "#FFFFFF", 0.15), bold=True)
        y = 2.5
    if kicker:
        textbox(slide, theme.content_left, y - 0.42, theme.content_width, 0.3, kicker.upper(),
                font=theme.fonts["body"], size=11,
                color=mix(theme.color("accent"), "#FFFFFF", 0.35), bold=True, spc=1.4)
    title = str(s.get("title") or "")
    size = fit_size([(title, 0)], theme.content_width - 1.0, 1.8, 40, 24, spacing=1.08)
    textbox(slide, theme.content_left, y, theme.content_width - 1.0, 1.7, title,
            font=theme.fonts["heading"], size=size, color="#FFFFFF", bold=True, line_spacing=1.06)
    if s.get("lead"):
        textbox(slide, theme.content_left + 0.02, y + 1.55, theme.content_width - 1.6, 1.0,
                str(s.get("lead")), font=theme.fonts["body"], size=17,
                color=mix(theme.color("primary"), "#FFFFFF", 0.70), line_spacing=1.22)


def layout_bullets(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    if s.get("lead"):
        y = lead_text(slide, theme, str(s.get("lead")), y, theme.content_width - 2.0)
    bottom = theme.height - 0.85
    if s.get("note"):
        bottom -= 1.05
        rect(slide, theme.content_left, bottom, theme.content_width, 0.85, theme.color("accent_soft"), rounded=True)
        rect(slide, theme.content_left, bottom, 0.07, 0.85, theme.color("accent"))
        textbox(slide, theme.content_left + 0.3, bottom + 0.12, theme.content_width - 0.6, 0.62,
                str(s.get("note")), font=theme.fonts["body"], size=13,
                color=theme.color("primary"), line_spacing=1.18)
        bottom -= 0.25

    bullets = s.get("bullets") or []
    columns = int(s.get("columns") or 1)
    if columns >= 2 and len(bullets) >= 4:
        half = (len(bullets) + 1) // 2
        gap = 0.45
        col_w = (theme.content_width - gap) / 2
        bullets_block(slide, theme, bullets[:half], theme.content_left, y, col_w, bottom - y)
        bullets_block(slide, theme, bullets[half:], theme.content_left + col_w + gap, y, col_w, bottom - y)
    else:
        width = theme.content_width - (1.4 if len(bullets) < 4 else 0.4)
        bullets_block(slide, theme, bullets, theme.content_left, y, width, bottom - y)
    footer(slide, theme, index, total)


def layout_two_col(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    gap = 0.55
    col_w = (theme.content_width - gap) / 2
    mid = theme.content_left + col_w + gap / 2
    rect(slide, mid, y + 0.05, 0.012, theme.height - 0.9 - y, theme.color("line"))

    for side, x in (("left", theme.content_left), ("right", theme.content_left + col_w + gap)):
        col = s.get(side) or {}
        heading = col.get("heading")
        top = y
        if heading:
            textbox(slide, x, top, col_w, 0.42, str(heading), font=theme.fonts["heading"],
                    size=18, color=theme.color("primary"), bold=True)
            rect(slide, x, top + 0.44, 0.55, 0.045, theme.color("accent"))
            top += 0.72
        bullets = col.get("bullets") or []
        if bullets:
            bullets_block(slide, theme, bullets, x, top, col_w, theme.height - 0.95 - top, size=18)
        elif col.get("text"):
            textbox(slide, x, top, col_w, theme.height - 0.95 - top, str(col.get("text")),
                    font=theme.fonts["body"], size=16, color=theme.color("ink"), line_spacing=1.24)
    footer(slide, theme, index, total)


def layout_cards(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    if s.get("lead"):
        y = lead_text(slide, theme, str(s.get("lead")), y, theme.content_width - 1.0)

    cards = s.get("cards") or []
    count = max(1, min(4, len(cards)))
    gap = 0.32
    width = (theme.content_width - gap * (count - 1)) / count
    height = theme.height - 0.9 - y
    for i, card in enumerate(cards[:4]):
        x = theme.content_left + i * (width + gap)
        rect(slide, x, y, width, height, theme.color("surface"), rounded=True, radius=0.045,
             outline=theme.color("line"), outline_width=1.0)
        rect(slide, x, y, width, 0.055, theme.color("accent"))
        badge = str(card.get("number") or i + 1)
        ellipse(slide, x + 0.28, y + 0.34, 0.52, 0.52, theme.color("accent_soft"))
        textbox(slide, x + 0.28, y + 0.34, 0.52, 0.52, badge, font=theme.fonts["heading"],
                size=15, color=theme.color("accent"), bold=True, align=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE)
        title = str(card.get("title") or "")
        textbox(slide, x + 0.28, y + 1.02, width - 0.5, 0.9, title, font=theme.fonts["heading"],
                size=17, color=theme.color("primary"), bold=True, line_spacing=1.12)
        text = str(card.get("text") or "")
        textbox(slide, x + 0.28, y + 1.75, width - 0.5, height - 1.95, text,
                font=theme.fonts["body"], size=13.5, color=theme.color("muted"), line_spacing=1.22)
    footer(slide, theme, index, total)


def layout_steps(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    steps = s.get("steps") or []
    count = max(1, len(steps))
    bottom = theme.height - 0.9
    step_h = min(1.05, (bottom - y) / count)
    line_x = theme.content_left + 0.33

    rect(slide, line_x + 0.32, y + 0.3, 0.012, step_h * (count - 1), theme.color("line"))
    for i, step in enumerate(steps):
        top = y + i * step_h
        ellipse(slide, line_x, top + 0.08, 0.66, 0.66, theme.color("accent_soft"))
        textbox(slide, line_x, top + 0.08, 0.66, 0.66, str(i + 1), font=theme.fonts["heading"],
                size=15, color=theme.color("accent"), bold=True, align=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE)
        textbox(slide, line_x + 0.95, top + 0.02, theme.content_width - 1.0, 0.38,
                str(step.get("title") or ""), font=theme.fonts["heading"], size=17,
                color=theme.color("primary"), bold=True)
        textbox(slide, line_x + 0.95, top + 0.40, theme.content_width - 1.0, step_h - 0.42,
                str(step.get("text") or ""), font=theme.fonts["body"], size=13.5,
                color=theme.color("muted"), line_spacing=1.18)
    footer(slide, theme, index, total)


def layout_quote(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme, "surface_alt")
    rect(slide, 0, 0, 0.22, theme.height, theme.color("accent"))
    logo(slide, theme, dark=False, y=0.5)
    textbox(slide, theme.content_left, 1.05, 1.4, 2.0, "«", font=theme.fonts["heading"],
            size=120, color=theme.color("accent"), bold=True)
    quote = str(s.get("quote") or "")
    size = fit_size([(quote, 0)], theme.content_width - 2.2, 2.6, 30, 18, spacing=1.25)
    textbox(slide, theme.content_left + 1.0, 1.95, theme.content_width - 2.2, 3.2, quote,
            font=theme.fonts["heading"], size=size, color=theme.color("primary"),
            line_spacing=1.25, italic=False)
    author = str(s.get("author") or "")
    if author:
        rect(slide, theme.content_left + 1.02, 5.55, 0.6, 0.05, theme.color("accent"))
        textbox(slide, theme.content_left + 1.02, 5.72, theme.content_width - 2.2, 0.5, author,
                font=theme.fonts["body"], size=14, color=theme.color("muted"))
    footer(slide, theme, index, total)


def layout_table(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    columns = [str(c) for c in (s.get("columns") or [])]
    rows = s.get("rows") or []
    if not columns and rows:
        columns = [str(c) for c in rows[0]]
        rows = rows[1:]
    n_cols = max(1, len(columns))
    n_rows = len(rows) + 1

    bottom = theme.height - 0.9
    table_h = min(bottom - y, 0.55 + len(rows) * 0.78)
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(theme.content_left), Inches(y),
                                  Inches(theme.content_width), Inches(table_h))
    table = shape.table
    table.first_row = True
    table.horz_banding = False

    weights = s.get("column_widths") or [1.0] * n_cols
    if len(weights) != n_cols:
        weights = [1.0] * n_cols
    total_w = sum(float(w) for w in weights) or 1
    for i, weight in enumerate(weights):
        table.columns[i].width = Emu(int(Inches(theme.content_width) * float(weight) / total_w))

    row_h = table_h / n_rows
    for i in range(n_rows):
        table.rows[i].height = Inches(row_h)

    base_size = 14 if n_rows <= 5 else 12.5 if n_rows <= 7 else 11.5
    for r in range(n_rows):
        for c in range(n_cols):
            cell = table.cell(r, c)
            cell.margin_left = Inches(0.14)
            cell.margin_right = Inches(0.14)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = _rgb(theme.color("primary"))
                color = "#FFFFFF"
                bold = True
                size = base_size
            else:
                cell.fill.fore_color.rgb = _rgb(theme.color("surface" if r % 2 else "surface_alt"))
                color = theme.color("ink")
                bold = False
                size = base_size
            value = columns[c] if r == 0 else (str(rows[r - 1][c]) if c < len(rows[r - 1]) else "")
            lines = estimate_lines(value, (table.columns[c].width / EMU_IN) * 72 - 20, size)
            if lines > 2:
                size = max(9, size - (lines - 2) * 1.2)
            frame = cell.text_frame
            frame.word_wrap = True
            paragraph = frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT
            paragraph.line_spacing = Pt(size * 1.16)
            run = paragraph.add_run()
            run.text = value
            _style_run(run, theme.fonts["body"], size, color, bold=bold)
    footer(slide, theme, index, total)


def layout_code(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    code = s.get("code")
    if isinstance(code, list):
        code = "\n".join(str(line) for line in code)
    code = str(code or "").rstrip("\n")
    lines = code.split("\n") if code else [""]
    longest = max((len(line) for line in lines), default=1)

    note = s.get("note")
    bottom = theme.height - 0.9
    if note:
        bottom -= 1.0
    available_h = bottom - y

    width_pt = (theme.content_width - 0.75) * 72
    mono_factor = 0.60
    size = min(15.0, width_pt / max(1, longest) / mono_factor)
    size = max(9.0, min(size, (available_h - 0.5) * 72 / max(1, len(lines)) / 1.18))
    panel_h = min(available_h, 0.62 + len(lines) * size * 1.16 / 72)

    rect(slide, theme.content_left, y, theme.content_width, panel_h, theme.color("code_bg"),
         rounded=True, radius=0.035)
    rect(slide, theme.content_left, y, 0.06, panel_h, theme.color("accent"))

    language = str(s.get("language") or "").upper()
    if language:
        textbox(slide, theme.content_right - 2.0, y + 0.17, 1.75, 0.3, language,
                font=theme.fonts["mono"], size=9.5,
                color=mix(theme.color("code_bg"), "#FFFFFF", 0.55), align=PP_ALIGN.RIGHT, spc=1.0)

    if note:
        textbox(slide, theme.content_left, y + panel_h + 0.18, theme.content_width, 0.7,
                str(note), font=theme.fonts["body"], size=12,
                color=theme.color("muted"), line_spacing=1.18)

    box = slide.shapes.add_textbox(Inches(theme.content_left + 0.38), Inches(y + 0.34),
                                   Inches(theme.content_width - 0.72), Inches(panel_h - 0.55))
    frame = box.text_frame
    frame.word_wrap = False
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = frame.margin_top = frame.margin_right = frame.margin_bottom = 0
    for i, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.line_spacing = Pt(size * 1.16)
        paragraph.space_after = Pt(0)
        run = paragraph.add_run()
        run.text = line if line else " "
        _style_run(run, theme.fonts["mono"], size, theme.color("code_text"))
    footer(slide, theme, index, total)


def layout_image(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme)
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"))
    caption = str(s.get("caption") or "")
    bottom = theme.height - (1.05 if caption else 0.9)
    area_w = theme.content_width
    area_h = bottom - y
    path = resolve_asset(deck, s.get("image"))
    if not path:
        rect(slide, theme.content_left, y, area_w, area_h, theme.color("surface_alt"), rounded=True)
        textbox(slide, theme.content_left, y + area_h / 2 - 0.3, area_w, 0.6,
                f"Изображение не найдено: {s.get('image')}", font=theme.fonts["body"],
                size=14, color=theme.color("muted"), align=PP_ALIGN.CENTER)
        footer(slide, theme, index, total)
        return

    px_w, px_h = image_size(path)
    ratio = px_w / max(px_h, 1)
    box_ratio = area_w / area_h
    if ratio >= box_ratio:
        width, height = area_w, area_w / ratio
    else:
        height, width = area_h, area_h * ratio
    left = theme.content_left + (area_w - width) / 2
    top = y + (area_h - height) / 2
    rect(slide, theme.content_left, y, area_w, area_h, theme.color("dark_panel"))
    slide.shapes.add_picture(str(path), Inches(left), Inches(top), width=Inches(width), height=Inches(height))
    if caption:
        textbox(slide, theme.content_left, bottom + 0.12, theme.content_width, 0.35, caption,
                font=theme.fonts["body"], size=11, color=theme.color("muted"), align=PP_ALIGN.CENTER)
    footer(slide, theme, index, total)



def layout_summary(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    dark = bool(s.get("dark"))
    background(slide, theme, "primary" if dark else "surface")
    y = header(slide, theme, str(s.get("title") or ""), s.get("kicker"), dark=dark)
    columns = (s.get("columns") or [])[:4]
    note = s.get("note")
    bottom = theme.height - 0.88
    note_y = None
    if note:
        note_y = theme.height - 1.75
        bottom = note_y - 0.22

    divider = mix(theme.color("primary"), "#FFFFFF", 0.26) if dark else theme.color("line")
    head_color = "#FFFFFF" if dark else theme.color("primary")
    n = max(1, len(columns))
    gap = 0.38
    col_w = (theme.content_width - gap * (n - 1)) / n
    for i, col in enumerate(columns):
        x = theme.content_left + i * (col_w + gap)
        if i:
            rect(slide, x - gap / 2, y + 0.02, 0.012, bottom - y - 0.05, divider)
        textbox(slide, x, y, col_w, 0.4, str(col.get("heading") or ""),
                font=theme.fonts["heading"], size=18, color=head_color, bold=True)
        rect(slide, x, y + 0.45, 0.55, 0.045, theme.color("accent"))
        items = col.get("items") or []
        bullets_block(slide, theme, items, x, y + 0.72, col_w, bottom - (y + 0.72),
                      size=17, min_size=11.5, dark=dark)

    if note and note_y is not None:
        fill = mix(theme.color("primary"), "#FFFFFF", 0.10) if dark else theme.color("accent_soft")
        rect(slide, theme.content_left, note_y, theme.content_width, 0.85, fill, rounded=True)
        rect(slide, theme.content_left, note_y, 0.07, 0.85, theme.color("accent"))
        textbox(slide, theme.content_left + 0.3, note_y + 0.12, theme.content_width - 0.6, 0.62,
                str(note), font=theme.fonts["body"], size=12.5,
                color="#FFFFFF" if dark else theme.color("primary"), line_spacing=1.18)
    footer(slide, theme, index, total, dark=dark)


def layout_end(slide, deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> None:
    background(slide, theme, "primary")
    ellipse(slide, theme.width - 4.0, -1.8, 6.2, 6.2, "#FFFFFF", alpha=0.05)
    ellipse(slide, -1.2, theme.height - 3.2, 4.0, 4.0, theme.color("accent"), alpha=0.18)
    rect(slide, 0, 0, 0.22, theme.height, theme.color("accent"))
    logo(slide, theme, dark=True, y=0.55, width=theme.logo_width * 1.2)

    title = str(s.get("title") or "Спасибо за внимание")
    textbox(slide, theme.content_left, 2.35, theme.content_width - 1.4, 1.5, title,
            font=theme.fonts["heading"], size=40, color="#FFFFFF", bold=True, line_spacing=1.06)
    lead = s.get("lead")
    if lead:
        textbox(slide, theme.content_left, 3.75, theme.content_width - 2.6, 1.0, str(lead),
                font=theme.fonts["body"], size=17,
                color=mix(theme.color("primary"), "#FFFFFF", 0.72), line_spacing=1.22)
    contacts = [str(c) for c in (s.get("contacts") or [])]
    if contacts:
        rect(slide, theme.content_left, 5.35, 0.8, 0.045, theme.color("accent"))
        for i, line in enumerate(contacts[:3]):
            textbox(slide, theme.content_left, 5.55 + i * 0.34, theme.content_width, 0.32, line,
                    font=theme.fonts["body"], size=13,
                    color=mix(theme.color("primary"), "#FFFFFF", 0.68))


LAYOUTS = {
    "title": layout_title,
    "section": layout_section,
    "bullets": layout_bullets,
    "two-col": layout_two_col,
    "cards": layout_cards,
    "steps": layout_steps,
    "quote": layout_quote,
    "table": layout_table,
    "code": layout_code,
    "image": layout_image,
    "summary": layout_summary,
    "end": layout_end,
}


def _audience_label(meta: dict) -> str:
    if meta.get("audience_label"):
        return str(meta["audience_label"])
    mapping = {"school": "Школа", "college": "Колледж", "university": "Вуз", "universal": ""}
    return mapping.get(str(meta.get("audience") or "").lower(), "")


# ------------------------------------------------------------------
#  Точка входа
# ------------------------------------------------------------------


def render_pptx(deck: Deck, theme: Theme, out_path: str | Path, base_pptx: Path | None = None) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if base_pptx and Path(base_pptx).exists():
        prs = Presentation(str(base_pptx))
    else:
        prs = Presentation()

    prs.slide_width = Inches(theme.width)
    prs.slide_height = Inches(theme.height)
    prs.core_properties.title = deck.title
    prs.core_properties.subject = str(deck.meta.get("subject") or "Информатика")
    prs.core_properties.author = str(deck.meta.get("author") or "")
    prs.core_properties.comments = "Собрано из deck.yaml"

    blank = prs.slide_layouts[6]
    total = len(deck.slides)

    for index, s in enumerate(deck.slides, start=1):
        slide = prs.slides.add_slide(blank)
        LAYOUTS[s.layout](slide, deck, theme, index, total, s)
        notes = s.get("notes")
        if notes:
            slide.notes_slide.notes_text_frame.text = str(notes)

    prs.save(str(out_path))
    return out_path
