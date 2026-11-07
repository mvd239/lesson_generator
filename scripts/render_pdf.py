"""Сборка PDF напрямую через ReportLab — без LibreOffice и внешних конвертеров."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from PIL import Image

from model import Bullet, Deck, Slide, resolve_asset
from textfit import estimate_lines, fit_size
from theme import FontBook, Theme, mix

H = 7.5 * 72

DARK_LAYOUTS = {"title", "section", "end"}


def C(color: str) -> HexColor:
    return HexColor(str(color))


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Перенос текста по словам с измерением реальной ширины."""
    lines: list[str] = []
    for raw in str(text).split("\n"):
        words = raw.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if pdfmetrics.stringWidth(trial, font, size) <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def rich_words(text: str, strong: str | None) -> list[tuple[str, bool]]:
    if not strong:
        return [(w, False) for w in str(text).split()]
    words = str(text).split()
    result: list[tuple[str, bool]] = []
    for word in words:
        core = word.strip(".,;:!?()«»\"'—-")
        bold = bool(core) and (core in str(strong) or str(strong) in core)
        result.append((word, bold))
    return result


class Painter:
    def __init__(self, canv: canvas.Canvas, theme: Theme, fonts: FontBook):
        self.c = canv
        self.t = theme
        self.f = fonts
        self.width = theme.width * 72

    # --- координаты: дюймы сверху-слева -> пункты снизу-слева ---
    def _y(self, y: float, h: float) -> float:
        return H - (y + h) * 72

    def rect(self, x, y, w, h, color, alpha=None, rounded=False, radius=0.08,
             outline=None, outline_width=1.0):
        self.c.saveState()
        self.c.setFillColor(C(color))
        if alpha is not None:
            self.c.setFillAlpha(alpha)
        if outline:
            self.c.setStrokeColor(C(outline))
            self.c.setLineWidth(outline_width)
        if rounded:
            self.c.roundRect(x * 72, self._y(y, h), w * 72, h * 72, radius * 72,
                             stroke=1 if outline else 0, fill=1)
        else:
            self.c.rect(x * 72, self._y(y, h), w * 72, h * 72,
                        stroke=1 if outline else 0, fill=1)
        self.c.restoreState()

    def ellipse(self, x, y, w, h, color, alpha=None, outline=None, outline_width=1.0):
        self.c.saveState()
        self.c.setFillColor(C(color))
        if alpha is not None:
            self.c.setFillAlpha(alpha)
        if outline:
            self.c.setStrokeColor(C(outline))
            self.c.setLineWidth(outline_width)
        self.c.ellipse(x * 72, self._y(y, h), (x + w) * 72, H - y * 72,
                       stroke=1 if outline else 0, fill=1)
        self.c.restoreState()

    def text(self, x, y, w, h, text, *, font="body", size=18, color="#000000",
             line=1.18, align="left", valign="top", bold=False, char_space=0):
        if text is None:
            return
        font_name = self.f.get("bold" if bold else font)
        text = str(text)
        lines = wrap(text, font_name, size, w * 72)
        leading = size * line
        block = len(lines) * leading
        if valign == "middle":
            offset = max(0.0, (h * 72 - block) / 2)
        elif valign == "bottom":
            offset = max(0.0, h * 72 - block)
        else:
            offset = 0.0
        base = H - y * 72 - offset - size * 0.82
        self.c.setFillColor(C(color))
        self.c.setFont(font_name, size)
        for i, line_text in enumerate(lines):
            xx = x * 72
            if align == "center":
                xx += (w * 72 - pdfmetrics.stringWidth(line_text, font_name, size)) / 2
            elif align == "right":
                xx += w * 72 - pdfmetrics.stringWidth(line_text, font_name, size)
            self.c.drawString(xx, base - i * leading, line_text, charSpace=char_space or 0)
        return len(lines) * leading

    def bullets(self, x, y, w, h, bullets: list[Bullet], size: float, color: str, gap=9):
        indent = 0.30 * 72
        cursor = H - y * 72
        for i, bullet in enumerate(bullets):
            level = bullet.level
            bullet_color = C(self.t.color("accent") if level == 0 else self.t.color("muted"))
            char = "•" if level == 0 else "–"
            size_i = size if level == 0 else max(12, size - 2)
            text_x = x * 72 + (level + 1) * indent
            width = w * 72 - (level + 1) * indent
            font_name = self.f.get("body")
            words = rich_words(bullet.text, bullet.strong)
            lines: list[list[tuple[str, bool]]] = []
            current: list[tuple[str, bool]] = []
            current_w = 0.0
            space_w = pdfmetrics.stringWidth(" ", font_name, size_i)
            for word, is_bold in words:
                word_font = self.f.get("bold" if is_bold else "body")
                wd = pdfmetrics.stringWidth(word, word_font, size_i)
                add = wd + (space_w if current else 0)
                if current and current_w + add > width:
                    lines.append(current)
                    current = [(word, is_bold)]
                    current_w = wd
                else:
                    current.append((word, is_bold))
                    current_w += add
            if current:
                lines.append(current)

            leading = size_i * 1.18
            self.c.setFont(self.f.get("body"), size_i)
            self.c.setFillColor(bullet_color)
            self.c.drawString(x * 72 + level * indent + 2, cursor - size_i * 0.82, char)
            for line_words in lines:
                xx = text_x
                for word, is_bold in line_words:
                    word_font = self.f.get("bold" if is_bold else "body")
                    self.c.setFont(word_font, size_i)
                    self.c.setFillColor(C(color))
                    self.c.drawString(xx, cursor - size_i * 0.82, word)
                    xx += pdfmetrics.stringWidth(word + " ", word_font, size_i)
                cursor -= leading
            cursor -= gap if i < len(bullets) - 1 else 0

    def full_image(self, path: Path):
        self.c.drawImage(str(path), 0, 0, width=self.width, height=H,
                         mask="auto", preserveAspectRatio=False)

    def image(self, path: Path, x, y, w, h, contain=True):
        try:
            reader = ImageReader(str(path))
            px_w, px_h = reader.getSize()
        except Exception:  # noqa: BLE001
            return
        ratio = px_w / max(px_h, 1)
        if ratio >= w / h:
            width, height = w, w / ratio
        else:
            height, width = h, h * ratio
        left = x + (w - width) / 2
        top = y + (h - height) / 2
        self.c.drawImage(str(path), left * 72, self._y(top, height), width * 72, height * 72,
                         mask="auto", preserveAspectRatio=False)

    def logo(self, dark: bool, x=None, y=0.5, width=None):
        path = self.t.logo_dark_file if dark and self.t.logo_dark_file else self.t.logo_file
        if not path:
            return
        width = width or self.t.logo_width
        try:
            with Image.open(path) as img:
                px_w, px_h = img.size
        except Exception:  # noqa: BLE001
            return
        height = width * px_h / max(px_w, 1)
        left = self.t.content_right - width if x is None else x
        self.image(path, left, y, width, height)


# ------------------------------------------------------------------
#  Общие блоки
# ------------------------------------------------------------------


def background(p: Painter, key="surface"):
    path = p.t.background_dark if key == "primary" else p.t.background_light
    if path:
        p.full_image(path)
        return
    p.rect(0, 0, p.t.width, p.t.height, p.t.color(key))


def footer(p: Painter, index: int, total: int, dark=False):
    theme = p.t
    color = mix(theme.color("primary"), "#FFFFFF", 0.72) if dark else theme.color("muted")
    line_color = mix(theme.color("primary"), "#FFFFFF", 0.30) if dark else theme.color("line")
    y = theme.height - 0.66
    p.rect(theme.content_left, y, theme.content_width, 0.012, line_color)
    p.text(theme.content_left, y + 0.09, theme.content_width * 0.7, 0.3,
           theme.footer or theme.name, font="body", size=9.5, color=color)
    p.text(theme.content_right - 1.6, y + 0.09, 1.6, 0.3, f"{index:02d} / {total:02d}",
           font="body", size=9.5, color=color, align="right")


def header(p: Painter, title: str, kicker: str | None, dark: bool = False) -> float:
    theme = p.t
    x = theme.content_left
    p.logo(dark=dark, x=None, y=0.42)
    if kicker:
        kicker_color = mix(theme.color("accent"), "#FFFFFF", 0.35) if dark else theme.color("accent")
        p.text(x + 0.02, 0.52, theme.content_width * 0.8, 0.28, str(kicker).upper(),
               font="body", size=10.5, color=kicker_color, bold=True, char_space=1.2)
        title_y = 0.82
    else:
        title_y = 0.62

    available = theme.content_width - (theme.logo_width + 0.45)
    size = 30 if len(title) <= 46 else 26 if len(title) <= 72 else 22
    size = fit_size([(title, 0)], available, 1.35, size, 18, spacing=1.12)
    p.rect(x, title_y + 0.06, 0.075, 0.52 + (size - 18) * 0.012, theme.color("accent"))
    p.text(x + 0.28, title_y, available, 1.25, title, font="body", size=size,
           color="#FFFFFF" if dark else theme.color("primary"), bold=True, line=1.03)
    return 2.28


def lead(p: Painter, text: str, y: float, width: float | None = None) -> float:
    theme = p.t
    width = width or theme.content_width
    size = 17 if len(str(text)) < 110 else 15
    lines = estimate_lines(str(text), width * 72, size)
    height = max(0.34, lines * size * 1.22 / 72 + 0.05)
    p.text(theme.content_left, y, width, height, text, font="body", size=size,
           color=theme.color("muted"), line=1.18)
    return y + height + 0.22


def bullets_block(p: Painter, bullets: list[Bullet], x, y, w, h, size=20, min_size=13, color=None):
    if not bullets:
        return
    size = fit_size([(b.text, 0.32 * (b.level + 1)) for b in bullets], w, h, size, min_size,
                    spacing=1.18, para_gap=9)
    p.bullets(x, y, w, h, bullets, size, color or p.t.color("ink"))


# ------------------------------------------------------------------
#  Макеты
# ------------------------------------------------------------------


def layout_title(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p, "primary")
    p.ellipse(t.width - 4.6, -2.1, 7.0, 7.0, "#FFFFFF", alpha=0.05)
    p.ellipse(t.width - 2.9, t.height - 2.6, 4.4, 4.4, t.color("accent"), alpha=0.20)
    p.rect(0, 0, 0.22, t.height, t.color("accent"))
    p.logo(dark=True, x=t.content_left, y=0.6, width=t.logo_width * 1.35)

    kicker_parts = [str(deck.meta.get("subject") or "Информатика")]
    p.text(t.content_left, 2.02, t.content_width * 0.9, 0.3, "  ·  ".join(kicker_parts),
           font="body", size=12, color=mix(t.color("accent"), "#FFFFFF", 0.35), bold=True, char_space=1.6)

    size = fit_size([(deck.title, 0)], t.content_width - 0.4, 2.0, 46, 26, spacing=1.1)
    p.text(t.content_left, 2.4, t.content_width - 0.4, 2.0, deck.title, font="body",
           size=size, color="#FFFFFF", bold=True, line=1.04)

    if deck.subtitle:
        sub_size = 19 if len(deck.subtitle) < 120 else 16
        lines = estimate_lines(deck.subtitle, (t.content_width - 1.2) * 72, sub_size)
        p.text(t.content_left, 4.42, t.content_width - 1.2, max(0.5, lines * sub_size * 1.25 / 72 + 0.1),
               deck.subtitle, font="body", size=sub_size, color=mix(t.color("primary"), "#FFFFFF", 0.78), line=1.2)

    meta = "  ·  ".join(str(v) for v in (deck.meta.get("author"), deck.meta.get("org"), deck.meta.get("date")) if v)
    if meta:
        p.rect(t.content_left, t.height - 1.55, 0.9, 0.045, t.color("accent"))
        p.text(t.content_left, t.height - 1.35, t.content_width, 0.5, meta, font="body", size=12,
               color=mix(t.color("primary"), "#FFFFFF", 0.62))


def layout_section(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p, "primary")
    p.ellipse(-1.6, t.height - 3.6, 5.4, 5.4, "#FFFFFF", alpha=0.045)
    p.rect(0, 0, 0.22, t.height, t.color("accent"))
    p.logo(dark=True, y=0.55)

    y = 2.5
    if s.get("number"):
        p.text(t.content_left, 1.15, 3.0, 0.9, str(s.get("number")), font="body", size=64,
               color=mix(t.color("accent"), "#FFFFFF", 0.15), bold=True)
    if s.get("kicker"):
        p.text(t.content_left, y - 0.42, t.content_width, 0.3, str(s.get("kicker")).upper(),
               font="body", size=11, color=mix(t.color("accent"), "#FFFFFF", 0.35), bold=True, char_space=1.4)
    title = str(s.get("title") or "")
    size = fit_size([(title, 0)], t.content_width - 1.0, 1.8, 40, 24, spacing=1.08)
    p.text(t.content_left, y, t.content_width - 1.0, 1.7, title, font="body", size=size,
           color="#FFFFFF", bold=True, line=1.06)
    if s.get("lead"):
        p.text(t.content_left + 0.02, y + 1.55, t.content_width - 1.6, 1.0, str(s.get("lead")),
               font="body", size=17, color=mix(t.color("primary"), "#FFFFFF", 0.70), line=1.22)


def layout_bullets(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    if s.get("lead"):
        y = lead(p, str(s.get("lead")), y, t.content_width - 2.0)
    bottom = t.height - 0.85
    if s.get("note"):
        bottom -= 1.05
        p.rect(t.content_left, bottom, t.content_width, 0.85, t.color("accent_soft"), rounded=True)
        p.rect(t.content_left, bottom, 0.07, 0.85, t.color("accent"))
        p.text(t.content_left + 0.3, bottom + 0.12, t.content_width - 0.6, 0.62, str(s.get("note")),
               font="body", size=13, color=t.color("primary"), line=1.18)
        bottom -= 0.25

    bullets = s.get("bullets") or []
    columns = int(s.get("columns") or 1)
    if columns >= 2 and len(bullets) >= 4:
        half = (len(bullets) + 1) // 2
        gap = 0.45
        col_w = (t.content_width - gap) / 2
        bullets_block(p, bullets[:half], t.content_left, y, col_w, bottom - y)
        bullets_block(p, bullets[half:], t.content_left + col_w + gap, y, col_w, bottom - y)
    else:
        width = t.content_width - (1.4 if len(bullets) < 4 else 0.4)
        bullets_block(p, bullets, t.content_left, y, width, bottom - y)
    footer(p, index, total)


def layout_two_col(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    gap = 0.55
    col_w = (t.content_width - gap) / 2
    mid = t.content_left + col_w + gap / 2
    p.rect(mid, y + 0.05, 0.012, t.height - 0.9 - y, t.color("line"))
    for side, x in (("left", t.content_left), ("right", t.content_left + col_w + gap)):
        col = s.get(side) or {}
        top = y
        if col.get("heading"):
            p.text(x, top, col_w, 0.42, str(col.get("heading")), font="body", size=18,
                   color=t.color("primary"), bold=True)
            p.rect(x, top + 0.44, 0.55, 0.045, t.color("accent"))
            top += 0.72
        if col.get("bullets"):
            bullets_block(p, col["bullets"], x, top, col_w, t.height - 0.95 - top, size=18)
        elif col.get("text"):
            p.text(x, top, col_w, t.height - 0.95 - top, str(col.get("text")), font="body",
                   size=16, color=t.color("ink"), line=1.24)
    footer(p, index, total)


def layout_cards(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    if s.get("lead"):
        y = lead(p, str(s.get("lead")), y, t.content_width - 1.0)
    cards = (s.get("cards") or [])[:4]
    count = max(1, len(cards))
    gap = 0.32
    width = (t.content_width - gap * (count - 1)) / count
    height = t.height - 0.9 - y
    for i, card in enumerate(cards):
        x = t.content_left + i * (width + gap)
        p.rect(x, y, width, height, t.color("surface"), rounded=True, radius=0.045,
               outline=t.color("line"), outline_width=1)
        p.rect(x, y, width, 0.055, t.color("accent"))
        p.ellipse(x + 0.28, y + 0.34, 0.52, 0.52, t.color("accent_soft"))
        p.text(x + 0.28, y + 0.34, 0.52, 0.52, str(card.get("number") or i + 1), font="body",
               size=15, color=t.color("accent"), bold=True, align="center", valign="middle")
        p.text(x + 0.28, y + 1.02, width - 0.5, 0.9, str(card.get("title") or ""), font="body",
               size=17, color=t.color("primary"), bold=True, line=1.12)
        p.text(x + 0.28, y + 1.75, width - 0.5, height - 1.95, str(card.get("text") or ""),
               font="body", size=13.5, color=t.color("muted"), line=1.22)
    footer(p, index, total)


def layout_steps(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    steps = s.get("steps") or []
    count = max(1, len(steps))
    bottom = t.height - 0.9
    step_h = min(1.05, (bottom - y) / count)
    line_x = t.content_left + 0.33
    p.rect(line_x + 0.32, y + 0.3, 0.012, step_h * (count - 1), t.color("line"))
    for i, step in enumerate(steps):
        top = y + i * step_h
        p.ellipse(line_x, top + 0.08, 0.66, 0.66, t.color("accent_soft"))
        p.text(line_x, top + 0.08, 0.66, 0.66, str(i + 1), font="body", size=15,
               color=t.color("accent"), bold=True, align="center", valign="middle")
        p.text(line_x + 0.95, top + 0.02, t.content_width - 1.0, 0.38, str(step.get("title") or ""),
               font="body", size=17, color=t.color("primary"), bold=True)
        p.text(line_x + 0.95, top + 0.40, t.content_width - 1.0, step_h - 0.42,
               str(step.get("text") or ""), font="body", size=13.5, color=t.color("muted"), line=1.18)
    footer(p, index, total)


def layout_quote(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p, "surface_alt")
    p.rect(0, 0, 0.22, t.height, t.color("accent"))
    p.logo(dark=False, y=0.5)
    p.text(t.content_left, 1.05, 1.4, 1.4, "«", font="body", size=120, color=t.color("accent"), bold=True)
    quote = str(s.get("quote") or "")
    size = fit_size([(quote, 0)], t.content_width - 2.2, 2.6, 30, 18, spacing=1.25)
    p.text(t.content_left + 1.0, 1.95, t.content_width - 2.2, 3.2, quote, font="body",
           size=size, color=t.color("primary"), line=1.25)
    if s.get("author"):
        p.rect(t.content_left + 1.02, 5.55, 0.6, 0.05, t.color("accent"))
        p.text(t.content_left + 1.02, 5.72, t.content_width - 2.2, 0.5, str(s.get("author")),
               font="body", size=14, color=t.color("muted"))
    footer(p, index, total)


def layout_table(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    columns = [str(c) for c in (s.get("columns") or [])]
    rows = s.get("rows") or []
    if not columns and rows:
        columns = [str(c) for c in rows[0]]
        rows = rows[1:]
    n_cols = max(1, len(columns))
    n_rows = len(rows) + 1
    avail_h = (t.height - 0.9 - y) * 72
    avail_w = t.content_width * 72
    weights = s.get("column_widths") or [1.0] * n_cols
    if len(weights) != n_cols:
        weights = [1.0] * n_cols
    total_w = sum(float(w) for w in weights) or 1
    widths = [avail_w * float(w) / total_w for w in weights]

    font_name = p.f.get("body")
    bold_font = p.f.get("bold")
    base = 14.0 if n_rows <= 5 else 12.5 if n_rows <= 7 else 11.5
    size = base
    while size > 8.5:
        heights = _row_heights(columns, rows, widths, size, n_rows, font_name, bold_font)
        if sum(heights) <= avail_h:
            break
        size -= 0.5
    heights = _row_heights(columns, rows, widths, size, n_rows, font_name, bold_font)
    target_h = min(avail_h, 3.7 * 72)
    scale = min(1.8, target_h / max(sum(heights), 1))
    heights = [h * scale for h in heights]

    top = y
    for r in range(n_rows):
        row_h = heights[r] / 72
        if r == 0:
            p.rect(t.content_left, top, t.content_width, row_h, t.color("primary"))
            color = "#FFFFFF"
            bold = True
        else:
            color = t.color("ink")
            bold = False
            fill = t.color("surface" if r % 2 else "surface_alt")
            p.rect(t.content_left, top, t.content_width, row_h, fill)
        left = t.content_left
        for c_i in range(n_cols):
            value = columns[c_i] if r == 0 else (
                str(rows[r - 1][c_i]) if c_i < len(rows[r - 1]) else ""
            )
            p.text(left + 0.07, top, widths[c_i] / 72 - 0.14, row_h, value,
                   font="body", size=size, color=color, bold=bold, line=1.16, valign="middle")
            left += widths[c_i] / 72
        top += row_h
    footer(p, index, total)


def _row_heights(columns, rows, widths, size, n_rows, font_name, bold_font) -> list[float]:
    heights: list[float] = []
    for r in range(n_rows):
        line_counts = []
        for c in range(len(widths)):
            value = columns[c] if r == 0 else (str(rows[r - 1][c]) if c < len(rows[r - 1]) else "")
            font = bold_font if r == 0 else font_name
            lines = len(wrap(value, font, size, widths[c] - 10))
            line_counts.append(lines)
        heights.append(max(24.0, max(line_counts or [1]) * size * 1.16 + 9))
    return heights


def layout_code(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    code = s.get("code")
    if isinstance(code, list):
        code = "\n".join(str(line) for line in code)
    code = str(code or "").rstrip("\n")
    lines = code.split("\n") if code else [""]
    longest = max((len(line) for line in lines), default=1)
    note = s.get("note")
    bottom = t.height - 0.9
    if note:
        bottom -= 1.0
    available_h = bottom - y

    width_pt = (t.content_width - 0.75) * 72
    size = min(15.0, width_pt / max(1, longest) / 0.60)
    size = max(9.0, min(size, (available_h - 0.5) * 72 / max(1, len(lines)) / 1.18))
    panel_h = min(available_h, 0.62 + len(lines) * size * 1.16 / 72)

    p.rect(t.content_left, y, t.content_width, panel_h, t.color("code_bg"), rounded=True, radius=0.035)
    p.rect(t.content_left, y, 0.06, panel_h, t.color("accent"))
    language = str(s.get("language") or "").upper()
    if language:
        p.text(t.content_right - 2.0, y + 0.17, 1.75, 0.3, language, font="mono", size=9.5,
               color=mix(t.color("code_bg"), "#FFFFFF", 0.55), align="right", char_space=1.0)

    if note:
        p.text(t.content_left, y + panel_h + 0.18, t.content_width, 0.7, str(note),
               font="body", size=12, color=t.color("muted"), line=1.18)
    text_y = y + 0.34
    p.c.setFillColor(C(t.color("code_text")))
    p.c.setFont(p.f.get("mono"), size)
    leading = size * 1.16
    base = H - text_y * 72 - size * 0.82
    for i, line in enumerate(lines):
        p.c.drawString((t.content_left + 0.38) * 72, base - i * leading, line if line else " ")
    footer(p, index, total)


def layout_image(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    caption = str(s.get("caption") or "")
    bottom = t.height - (1.05 if caption else 0.9)
    area_w = t.content_width
    area_h = bottom - y
    path = resolve_asset(deck, s.get("image"))
    if not path:
        p.rect(t.content_left, y, area_w, area_h, t.color("surface_alt"), rounded=True)
        p.text(t.content_left, y + area_h / 2 - 0.3, area_w, 0.6,
               f"Изображение не найдено: {s.get('image')}", font="body", size=14,
               color=t.color("muted"), align="center")
    else:
        p.rect(t.content_left, y, area_w, area_h, t.color("dark_panel"))
        p.image(path, t.content_left, y, area_w, area_h)
    if caption:
        p.text(t.content_left, bottom + 0.12, t.content_width, 0.35, caption, font="body",
               size=11, color=t.color("muted"), align="center")
    footer(p, index, total)



def layout_summary(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    dark = bool(s.get("dark"))
    background(p, "primary" if dark else "surface")
    y = header(p, str(s.get("title") or ""), s.get("kicker"), dark=dark)
    columns = (s.get("columns") or [])[:4]
    note = s.get("note")
    bottom = t.height - 0.88
    note_y = None
    if note:
        note_y = t.height - 1.75
        bottom = note_y - 0.22

    divider = mix(t.color("primary"), "#FFFFFF", 0.26) if dark else t.color("line")
    head_color = "#FFFFFF" if dark else t.color("primary")
    item_color = mix(t.color("primary"), "#FFFFFF", 0.86) if dark else t.color("ink")
    n = max(1, len(columns))
    gap = 0.38
    col_w = (t.content_width - gap * (n - 1)) / n
    for i, col in enumerate(columns):
        x = t.content_left + i * (col_w + gap)
        if i:
            p.rect(x - gap / 2, y + 0.02, 0.012, bottom - y - 0.05, divider)
        p.text(x, y, col_w, 0.4, str(col.get("heading") or ""), font="body", size=18,
               color=head_color, bold=True)
        p.rect(x, y + 0.45, 0.55, 0.045, t.color("accent"))
        bullets_block(p, col.get("items") or [], x, y + 0.72, col_w, bottom - (y + 0.72),
                      size=17, min_size=11.5, color=item_color)

    if note and note_y is not None:
        fill = mix(t.color("primary"), "#FFFFFF", 0.10) if dark else t.color("accent_soft")
        p.rect(t.content_left, note_y, t.content_width, 0.85, fill, rounded=True)
        p.rect(t.content_left, note_y, 0.07, 0.85, t.color("accent"))
        p.text(t.content_left + 0.3, note_y + 0.12, t.content_width - 0.6, 0.62, str(note),
               font="body", size=12.5, color="#FFFFFF" if dark else t.color("primary"), line=1.18)
    footer(p, index, total, dark=dark)


def layout_end(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    t = p.t
    background(p, "primary")
    p.ellipse(t.width - 4.0, -1.8, 6.2, 6.2, "#FFFFFF", alpha=0.05)
    p.ellipse(-1.2, t.height - 3.2, 4.0, 4.0, t.color("accent"), alpha=0.18)
    p.rect(0, 0, 0.22, t.height, t.color("accent"))
    p.logo(dark=True, y=0.55, width=t.logo_width * 1.2)
    title = str(s.get("title") or "Спасибо за внимание")
    p.text(t.content_left, 2.35, t.content_width - 1.4, 1.5, title, font="body", size=40,
           color="#FFFFFF", bold=True, line=1.06)
    if s.get("lead"):
        p.text(t.content_left, 3.75, t.content_width - 2.6, 1.0, str(s.get("lead")), font="body",
               size=17, color=mix(t.color("primary"), "#FFFFFF", 0.72), line=1.22)
    contacts = [str(c) for c in (s.get("contacts") or [])][:3]
    if contacts:
        p.rect(t.content_left, 5.35, 0.8, 0.045, t.color("accent"))
        for i, line in enumerate(contacts):
            p.text(t.content_left, 5.55 + i * 0.34, t.content_width, 0.32, line, font="body",
                   size=13, color=mix(t.color("primary"), "#FFFFFF", 0.68))


def layout_team(p: Painter, deck: Deck, index: int, total: int, s: Slide):
    background(p)
    y = header(p, str(s.get("title") or ""), s.get("kicker"))
    t = p.t
    people = [str(pr.get("name") or "") for pr in (s.get("people") or []) if str(pr.get("name") or "")]
    links = s.get("links") or []

    n = max(1, len(people))
    slot = t.content_width / n
    d = 1.35
    cy = y + 0.10
    for i, name in enumerate(people[:6]):
        cx = t.content_left + slot * i + (slot - d) / 2
        p.ellipse(cx, cy, d, d, t.color("accent_soft"),
                  outline=t.color("accent"), outline_width=1.25)
        p.text(cx, cy, d, d, "фото", font="mono", size=12,
               color=t.color("muted"), align="center", valign="middle")
        p.text(t.content_left + slot * i + 0.08, cy + d + 0.06, slot - 0.16, 0.5, name,
               font="body", size=14, color=t.color("primary"), bold=True,
               align="center", line=1.08)

    count = max(1, len(links))
    side = 1.55
    gap = 1.3
    row_w = count * side + (count - 1) * gap
    qx0 = t.width / 2 - row_w / 2
    qy = cy + d + 0.72
    for i, link in enumerate(links[:3]):
        qx = qx0 + i * (side + gap)
        p.rect(qx, qy + 0.36, side, side, t.color("surface"), rounded=True,
               radius=0.06, outline=t.color("accent"), outline_width=1.5)
        p.text(qx, qy + 0.36, side, side, "QR", font="mono", size=21,
               color=t.color("muted"), align="center", valign="middle")
        p.text(qx - 0.75, qy, side + 1.5, 0.32, str(link.get("title") or ""),
               font="body", size=13.5, color=t.color("primary"), bold=True, align="center")
        p.text(qx - 0.55, qy + 0.36 + side + 0.08, side + 1.1, 0.26,
               str(link.get("label") or ""), font="body", size=11,
               color=t.color("muted"), align="center")
    footer(p, index, total)


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
    "team": layout_team,
    "summary": layout_summary,
    "end": layout_end,
}


def render_pdf(deck: Deck, theme: Theme, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fonts = FontBook(theme)
    canv = canvas.Canvas(str(out_path), pagesize=(theme.width * 72, theme.height * 72))
    canv.setTitle(deck.title)
    canv.setSubject(str(deck.meta.get("subject") or "Информатика"))
    canv.setAuthor(str(deck.meta.get("author") or ""))
    canv.setCreator("deck.yaml → ReportLab")

    painter = Painter(canv, theme, fonts)
    total = len(deck.slides)
    for index, s in enumerate(deck.slides, start=1):
        LAYOUTS[s.layout](painter, deck, index, total, s)
        canv.showPage()

    canv.save()
    return out_path
