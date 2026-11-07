"""Сборка автономного HTML-файла: показ в браузере + печать в PDF."""

from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path

from model import Deck, Slide, resolve_asset
from textfit import fit_size
from theme import Theme, mix

PT = 4 / 3  # 1pt = 4/3 px при 96 dpi
CIRCLE = '<div class="decor dc1"></div><div class="decor dc2"></div><div class="side-bar"></div>'


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def data_uri(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def logo_tag(theme: Theme, dark: bool, corner: str) -> str:
    path = theme.logo_dark_file if dark and theme.logo_dark_file else theme.logo_file
    uri = data_uri(path)
    if not uri:
        return ""
    return f'<img class="logo-mark {corner}" src="{uri}" alt="">'


def footer(theme: Theme, index: int, total: int, dark: bool = False) -> str:
    if dark:
        color = mix(theme.color("primary"), "#FFFFFF", 0.72)
        line = mix(theme.color("primary"), "#FFFFFF", 0.28)
    else:
        color = theme.color("muted")
        line = theme.color("line")
    label = esc(theme.footer or theme.name)
    return (
        f'<footer class="slide-footer" style="border-color:{line};color:{color}">'
        f'<span>{label}</span><span>{index:02d} / {total:02d}</span></footer>'
    )


def header(theme: Theme, title: str, kicker: str | None, dark: bool = False) -> str:
    available_pt = (theme.content_width - theme.logo_width - 0.45) * 72
    base = 30 if len(title) <= 46 else 26 if len(title) <= 72 else 22
    size = fit_size([(title, 0)], available_pt / 72, 1.35, base, 18, spacing=1.12)
    kicker_html = f'<div class="kicker">{esc(kicker).upper()}</div>' if kicker else ""
    logo = logo_tag(theme, dark=dark, corner="corner-right")
    color = ";color:#FFFFFF" if dark else ""
    return f"""
    {logo}
    <header class="head{' with-kicker' if kicker else ''}">
      {kicker_html}
      <div class="head-row">
        <span class="head-bar"></span>
        <h2 style="font-size:{size * PT:.1f}px{color}">{esc(title)}</h2>
      </div>
    </header>"""


def notes_html(slide: Slide) -> str:
    notes = slide.get("notes")
    return f'<div class="notes-src" hidden>{esc(notes)}</div>' if notes else ""


# ------------------------------------------------------------------
#  Макеты
# ------------------------------------------------------------------


def layout_title(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    subject = str(deck.meta.get("subject") or "Информатика")
    kicker = subject
    size = fit_size([(deck.title, 0)], theme.content_width - 0.4, 2.0, 46, 26, spacing=1.1)
    meta = "  ·  ".join(str(v) for v in (deck.meta.get("author"), deck.meta.get("org"), deck.meta.get("date")) if v)
    sub = ""
    if deck.subtitle:
        sub_size = 19 if len(deck.subtitle) < 120 else 16
        sub = f'<p class="title-sub" style="font-size:{sub_size * PT:.1f}px">{esc(deck.subtitle)}</p>'
    meta_html = ""
    if meta:
        meta_html = f'<div class="title-meta"><span class="rule"></span><span>{esc(meta)}</span></div>'
    return f"""
    <section class="slide layout-title theme-dark">
      {CIRCLE}
      {logo_tag(theme, dark=True, corner="corner-left")}
      <div class="title-kicker">{esc(kicker).upper()}</div>
      <h1 style="font-size:{size * PT:.1f}px">{esc(deck.title)}</h1>
      {sub}
      {meta_html}
    </section>"""


def layout_section(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    title = str(s.get("title") or "")
    size = fit_size([(title, 0)], theme.content_width - 1.0, 1.8, 40, 24, spacing=1.08)
    number = f'<div class="section-number">{esc(s.get("number") or "")}</div>' if s.get("number") else ""
    kicker = f'<div class="title-kicker">{esc(s.get("kicker")).upper()}</div>' if s.get("kicker") else ""
    lead = f'<p class="section-lead">{esc(s.get("lead"))}</p>' if s.get("lead") else ""
    return f"""
    <section class="slide layout-section theme-dark">
      {CIRCLE}
      {logo_tag(theme, dark=True, corner="corner-right")}
      <div class="section-inner">
        {number}{kicker}
        <h2 style="font-size:{size * PT:.1f}px">{esc(title)}</h2>
        {lead}
      </div>
    </section>"""


def layout_bullets(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    top = 2.28
    lead = ""
    if s.get("lead"):
        lead = f'<p class="lead">{esc(s.get("lead"))}</p>'
        top += 0.55 + 0.22
    bottom = 6.5
    note = ""
    if s.get("note"):
        bottom -= 1.05
        note = f'<div class="note">{esc(s.get("note"))}</div>'
        bottom -= 0.1

    bullets = s.get("bullets") or []
    columns = int(s.get("columns") or 1)
    gap = 0.45
    if columns >= 2 and len(bullets) >= 4:
        half = (len(bullets) + 1) // 2
        col_w = (theme.content_width - gap) / 2
        size = fit_size([(b.text, 0.32 * (b.level + 1)) for b in bullets[:half]],
                        col_w, bottom - top, 20, 13, spacing=1.18, para_gap=9)
        left = _ul(bullets[:half], theme, size)
        right = _ul(bullets[half:], theme, size)
        columns_html = f'<div class="cols" style="gap:{gap * 96:.0f}px">{left}{right}</div>'
    else:
        width = theme.content_width - (1.4 if len(bullets) < 4 else 0.4)
        size = fit_size([(b.text, 0.32 * (b.level + 1)) for b in bullets],
                        width, bottom - top, 20, 13, spacing=1.18, para_gap=9)
        columns_html = _ul(bullets, theme, size)
    return f'<section class="slide">{body}<div class="body">{lead}{columns_html}{note}</div>{footer(theme, index, total)}</section>'


def _ul(bullets, theme: Theme, size: float) -> str:
    items = []
    for bullet in bullets:
        cls = f"lvl{bullet.level}"
        text = esc(bullet.text)
        if bullet.strong:
            safe_strong = esc(bullet.strong)
            text = text.replace(safe_strong, f"<strong>{safe_strong}</strong>", 1)
        items.append(f'<li class="{cls}">{text}</li>')
    return f'<ul class="bullets" style="font-size:{size * PT:.1f}px">{"".join(items)}</ul>'


def layout_two_col(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    cols = []
    for side in ("left", "right"):
        col = s.get(side) or {}
        heading = f'<h3>{esc(col.get("heading"))}</h3><span class="mini-rule"></span>' if col.get("heading") else ""
        inner = ""
        if col.get("bullets"):
            size = fit_size([(b.text, 0.32 * (b.level + 1)) for b in col["bullets"]],
                            (theme.content_width - 0.55) / 2, 3.6, 18, 12, spacing=1.18, para_gap=8)
            inner = _ul(col["bullets"], theme, size)
        elif col.get("text"):
            inner = f'<p class="col-text">{esc(col.get("text"))}</p>'
        cols.append(f'<div class="col">{heading}{inner}</div>')
    return (
        f'<section class="slide">{body}<div class="body"><div class="two-col">'
        f'{cols[0]}<span class="vline"></span>{cols[1]}</div></div>{footer(theme, index, total)}</section>'
    )


def layout_cards(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    lead = f'<p class="lead">{esc(s.get("lead"))}</p>' if s.get("lead") else ""
    cards = (s.get("cards") or [])[:4]
    count = max(1, len(cards))
    items = []
    for i, card in enumerate(cards):
        items.append(f"""
        <article class="card">
          <span class="card-strip"></span>
          <span class="card-badge">{esc(card.get("number") or i + 1)}</span>
          <h3>{esc(card.get("title"))}</h3>
          <p>{esc(card.get("text"))}</p>
        </article>""")
    return (
        f'<section class="slide">{body}<div class="body">{lead}'
        f'<div class="cards" style="grid-template-columns:repeat({count},1fr)">{"".join(items)}</div>'
        f'</div>{footer(theme, index, total)}</section>'
    )


def layout_steps(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    steps = s.get("steps") or []
    items = []
    for i, step in enumerate(steps):
        items.append(f"""
        <li class="step">
          <span class="step-num">{i + 1}</span>
          <div class="step-body"><h3>{esc(step.get("title"))}</h3><p>{esc(step.get("text"))}</p></div>
        </li>""")
    return f'<section class="slide">{body}<div class="body"><ol class="steps">{"".join(items)}</ol></div>{footer(theme, index, total)}</section>'


def layout_quote(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    quote = str(s.get("quote") or "")
    size = fit_size([(quote, 0)], theme.content_width - 2.2, 2.6, 30, 18, spacing=1.25)
    author = ""
    if s.get("author"):
        author = f'<div class="quote-author"><span class="mini-rule"></span><span>{esc(s.get("author"))}</span></div>'
    return f"""
    <section class="slide layout-quote">
      <div class="side-bar"></div>
      {logo_tag(theme, dark=False, corner="corner-right")}
      <div class="quote-wrap">
        <div class="quote-mark">«</div>
        <blockquote style="font-size:{size * PT:.1f}px">{esc(quote)}</blockquote>
        {author}
      </div>
      {footer(theme, index, total)}
    </section>"""


def layout_table(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    columns = [str(c) for c in (s.get("columns") or [])]
    rows = s.get("rows") or []
    if not columns and rows:
        columns = [str(c) for c in rows[0]]
        rows = rows[1:]
    n_rows = len(rows) + 1
    base = 14 if n_rows <= 5 else 12.5 if n_rows <= 7 else 11.5
    weights = s.get("column_widths") or [1.0] * max(1, len(columns))
    colgroup = "".join(f'<col style="width:{float(w) / sum(float(x) for x in weights) * 100:.2f}%">' for w in weights)
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{esc(str(cell))}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"""
    <section class="slide">{body}
      <div class="body">
        <table class="data-table" style="font-size:{base * PT:.1f}px">
          <colgroup>{colgroup}</colgroup>
          <thead><tr>{head}</tr></thead>
          <tbody>{body_rows}</tbody>
        </table>
      </div>
      {footer(theme, index, total)}
    </section>"""


def layout_code(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    code = s.get("code")
    if isinstance(code, list):
        code = "\n".join(str(line) for line in code)
    code = str(code or "").rstrip("\n")
    lines = code.split("\n") if code else [""]
    longest = max((len(line) for line in lines), default=1)
    width_pt = (theme.content_width - 0.75) * 72
    size = min(15.0, width_pt / max(1, longest) / 0.60)
    size = max(9.0, min(size, (4.1 - 0.5) * 72 / max(1, len(lines)) / 1.18))
    language = str(s.get("language") or "").upper()
    language_html = f'<span class="code-lang">{esc(language)}</span>' if language else ""
    note = f'<p class="code-note">{esc(s.get("note"))}</p>' if s.get("note") else ""
    return f"""
    <section class="slide">{body}
      <div class="body">
        <div class="code-panel">
          <span class="code-strip"></span>{language_html}
          <pre style="font-size:{size * PT:.1f}px">{esc(code)}</pre>
        </div>
        {note}
      </div>
      {footer(theme, index, total)}
    </section>"""


def layout_image(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    path = resolve_asset(deck, s.get("image"))
    uri = data_uri(path)
    caption = f'<figcaption>{esc(s.get("caption"))}</figcaption>' if s.get("caption") else ""
    if not uri:
        content = f'<div class="image-missing">Изображение не найдено: {esc(s.get("image"))}</div>'
    else:
        content = f'<img src="{uri}" alt="{esc(s.get("caption"))}">'
    return f"""
    <section class="slide">{body}
      <div class="body"><figure class="figure">{content}{caption}</figure></div>
      {footer(theme, index, total)}
    </section>"""



def layout_summary(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    dark = bool(s.get("dark"))
    body = header(theme, str(s.get("title") or ""), s.get("kicker"), dark=dark)
    columns = (s.get("columns") or [])[:4]
    cols_html = []
    for col in columns:
        items = col.get("items") or []
        cols_html.append(
            f'<div class="summary-col"><h3>{esc(col.get("heading"))}</h3>'
            f'<span class="mini-rule"></span>{_ul(items, theme, 17)}</div>'
        )
    note = f'<div class="note">{esc(s.get("note"))}</div>' if s.get("note") else ""
    cls = "slide theme-dark summary-dark" if dark else "slide"
    return (
        f'<section class="{cls}">{body}<div class="body">'
        f'<div class="summary-grid">{"".join(cols_html)}</div>{note}</div>'
        f'{footer(theme, index, total, dark=dark)}</section>'
    )


def layout_team(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    body = header(theme, str(s.get("title") or ""), s.get("kicker"))
    people = [str(pr.get("name") or "") for pr in (s.get("people") or []) if str(pr.get("name") or "")]
    persons = "".join(
        f'<div class="team-person"><span class="team-photo">фото</span>'
        f'<span class="team-name">{esc(name)}</span></div>'
        for name in people)
    links = "".join(
        f'<div class="team-qr"><span class="team-qr-title">{esc(link.get("title"))}</span>'
        f'<span class="team-qr-box">QR</span>'
        f'<span class="team-qr-label">{esc(link.get("label"))}</span></div>'
        for link in (s.get("links") or [])[:3])
    return (
        f'<section class="slide">{body}<div class="body">'
        f'<div class="team-people">{persons}</div>'
        f'<div class="team-links">{links}</div></div>'
        f'{footer(theme, index, total)}</section>'
    )


def layout_end(deck: Deck, theme: Theme, index: int, total: int, s: Slide) -> str:
    title = str(s.get("title") or "Спасибо за внимание")
    lead = f'<p class="end-lead">{esc(s.get("lead"))}</p>' if s.get("lead") else ""
    contacts = "".join(f"<li>{esc(c)}</li>" for c in (s.get("contacts") or [])[:3])
    contacts_html = f'<div class="end-contacts"><span class="rule"></span><ul>{contacts}</ul></div>' if contacts else ""
    return f"""
    <section class="slide layout-end theme-dark">
      {CIRCLE}
      {logo_tag(theme, dark=True, corner="corner-right")}
      <div class="end-inner">
        <h2>{esc(title)}</h2>
        {lead}
        {contacts_html}
      </div>
    </section>"""


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


# ------------------------------------------------------------------
#  Каркас документа
# ------------------------------------------------------------------

def build_css(theme: Theme) -> str:
    return """
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
:root {
  --primary: %(primary)s;
  --primary-dark: %(primary_dark)s;
  --accent: %(accent)s;
  --accent-soft: %(accent_soft)s;
  --ink: %(ink)s;
  --muted: %(muted)s;
  --line: %(line)s;
  --surface: %(surface)s;
  --surface-alt: %(surface_alt)s;
  --dark-panel: %(dark_panel)s;
  --bg-light: %(bg_light)s;
  --bg-dark: %(bg_dark)s;
  --code-bg: %(code_bg)s;
  --code-text: %(code_text)s;
  --heading: "%(heading)s", Arial, sans-serif;
  --body: "%(body)s", Arial, sans-serif;
  --mono: "%(mono)s", "Courier New", monospace;
  --s: 1;
  --left: %(left).1fpx;
  --right: %(right).1fpx;
  --top: %(top).1fpx;
}
body { background: #0d1218; font-family: var(--body); color: var(--ink); -webkit-font-smoothing: antialiased; }
.deck { position: fixed; inset: 0; overflow: hidden; }
.slide {
  width: 1280px; height: 720px; flex: none;
  background-color: var(--surface); background-image: var(--bg-light);
  background-size: cover; background-position: center;
  position: absolute; display: none;
  left: 50%%; top: 50%%; margin-left: -640px; margin-top: -360px;
  flex-direction: column; padding: var(--top) var(--right) 52px var(--left);
  transform: scale(var(--s)); transform-origin: center center;
  box-shadow: 0 30px 80px rgba(0,0,0,.45); overflow: hidden;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.slide.active { display: flex; }
h1, h2, h3 { margin: 0; font-family: var(--heading); font-weight: 700; color: var(--primary); letter-spacing: -0.01em; }
p { margin: 0; }

/* ---------- общие блоки ---------- */
.logo-mark { position: absolute; top: 40px; width: 59px; height: auto; }
.corner-right { right: var(--right); }
.corner-left { left: var(--left); }
.head { margin-bottom: 26px; position: relative; }
.head.with-kicker { padding-top: 26px; }
.kicker { color: var(--accent); font-weight: 700; font-size: 14px; letter-spacing: 1.6px; margin-bottom: 9px; }
.head-row { display: flex; gap: 20px; align-items: flex-start; }
.head-bar { flex: none; width: 7px; align-self: stretch; min-height: 38px; background: var(--accent); margin-top: 8px; }
.head h2 { line-height: 1.05; }
.body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.lead { color: var(--muted); font-size: 23px; line-height: 1.25; margin-bottom: 22px; max-width: 88%%; }
.bullets { margin: 0; padding: 0; list-style: none; line-height: 1.2; }
.bullets li { position: relative; padding-left: 30px; margin-bottom: 12px; }
.bullets li:last-child { margin-bottom: 0; }
.bullets li::before { position: absolute; left: 2px; top: -0.05em; color: var(--accent); font-weight: 700; content: "•"; }
.bullets li.lvl1 { margin-left: 34px; color: var(--muted); margin-bottom: 8px; }
.bullets li.lvl1::before { content: "–"; color: var(--muted); font-weight: 400; }
.bullets strong { color: var(--primary); }
.cols { display: flex; }
.cols > ul { flex: 1; }
.note { margin-top: auto; background: var(--accent-soft); border-left: 6px solid var(--accent);
        border-radius: 10px; padding: 15px 22px; color: var(--primary); font-size: 17px; line-height: 1.25; }
.summary-grid { display: flex; gap: 26px; flex: 1; min-height: 0; }
.summary-col { flex: 1; min-width: 0; }
.summary-col + .summary-col { border-left: 1px solid var(--line); padding-left: 26px; }
.summary-col h3 { font-size: 24px; }
.summary-col .mini-rule { margin: 10px 0 18px; }
.summary-col .bullets li { margin-bottom: 14px; }
.summary-dark .bullets { color: rgba(255,255,255,.88); }
.summary-dark .summary-col + .summary-col { border-color: rgba(255,255,255,.22); }
.summary-dark .note { background: rgba(255,255,255,.08); color: #FFFFFF; }

.slide-footer { position: absolute; left: var(--left); right: var(--right); bottom: 28px;
  border-top: 1px solid var(--line); padding-top: 9px; display: flex; justify-content: space-between;
  font-size: 12.5px; letter-spacing: .2px; }

/* ---------- титул ---------- */
.layout-title, .layout-section, .layout-end { padding: 0; }
.theme-dark { background-color: var(--primary); background-image: var(--bg-dark); color: #fff; }
.theme-dark h1, .theme-dark h2, .theme-dark h3 { color: #fff; }
.side-bar { position: absolute; left: 0; top: 0; width: 21px; height: 100%%; background: var(--accent); }
.decor { position: absolute; border-radius: 50%%; }
.dc1 { width: 672px; height: 672px; right: -130px; top: -200px; background: rgba(255,255,255,.05); }
.dc2 { width: 420px; height: 420px; right: -40px; bottom: -180px; background: var(--accent); opacity: .18; }
.title-kicker { position: absolute; left: var(--left); top: 194px; color: %(kicker_on_dark)s;
  font-size: 16px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; }
.layout-title h1 { position: absolute; left: var(--left); top: 232px; width: calc(100%% - 2 * var(--left) - 20px);
  line-height: 1.05; }
.title-sub { position: absolute; left: var(--left); top: 424px; width: 78%%; color: %(sub_on_dark)s;
  font-size: 25px; line-height: 1.25; }
.title-meta { position: absolute; left: var(--left); bottom: 118px; display: flex; align-items: center; gap: 18px;
  color: %(meta_on_dark)s; font-size: 15px; }
.rule { display: block; width: 84px; height: 5px; background: var(--accent); border-radius: 3px; }

/* ---------- разделитель ---------- */
.section-inner { position: absolute; left: var(--left); top: 118px; right: var(--right); }
.section-number { font-size: 92px; line-height: 1; font-weight: 700; color: %(number_on_dark)s; margin-bottom: 18px; }
.layout-section .title-kicker { position: static; margin-bottom: 10px; }
.layout-section h2 { line-height: 1.06; max-width: 88%%; }
.section-lead { margin-top: 26px; max-width: 70%%; color: %(sub_on_dark)s; font-size: 22px; line-height: 1.25; }

/* ---------- две колонки ---------- */
.two-col { display: flex; gap: 0; flex: 1; min-height: 0; }
.two-col .col { flex: 1; min-width: 0; padding-right: 26px; }
.two-col .col:last-child { padding-right: 0; padding-left: 26px; }
.two-col h3 { font-size: 23px; }
.mini-rule { display: block; width: 54px; height: 5px; background: var(--accent); border-radius: 3px; margin: 9px 0 20px; }
.vline { width: 1px; background: var(--line); margin: 4px 0; }
.col-text { font-size: 20px; line-height: 1.3; }

/* ---------- карточки ---------- */
.cards { display: grid; gap: 30px; flex: 1; min-height: 0; }
.card { position: relative; background: var(--surface); border: 1px solid var(--line);
  border-radius: 14px; padding: 44px 24px 24px; overflow: hidden;
  box-shadow: 0 12px 30px rgba(15, 34, 51, .06); }
.card-strip { position: absolute; left: 0; top: 0; width: 100%%; height: 6px; background: var(--accent); }
.card-badge { position: absolute; left: 24px; top: 30px; width: 44px; height: 44px; border-radius: 50%%;
  background: var(--accent-soft); color: var(--accent); font-weight: 700; font-size: 18px;
  display: grid; place-items: center; }
.card h3 { margin-top: 46px; font-size: 21px; line-height: 1.15; }
.card p { margin-top: 14px; color: var(--muted); font-size: 17px; line-height: 1.3; }

/* ---------- шаги ---------- */
.steps { list-style: none; margin: 0; padding: 0; flex: 1; display: flex; flex-direction: column; justify-content: center; }
.step { position: relative; display: flex; gap: 26px; padding: 14px 0; }
.step:not(:last-child)::after { content: ""; position: absolute; left: 27px; top: 68px; bottom: -6px; width: 2px;
  background: var(--line); }
.step-num { flex: none; width: 56px; height: 56px; border-radius: 50%%; background: var(--accent-soft);
  color: var(--accent); font-weight: 700; font-size: 19px; display: grid; place-items: center; z-index: 1; }
.step-body { padding-top: 2px; }
.step h3 { font-size: 22px; margin-bottom: 5px; }
.step p { color: var(--muted); font-size: 17px; line-height: 1.25; }

/* ---------- команда ---------- */
.team-people { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr;
  gap: 18px; margin: 26px 0 0; }
.team-person { display: flex; flex-direction: column; align-items: center; gap: 14px; }
.team-photo { width: 128px; height: 128px; border-radius: 50%%; background: var(--accent-soft);
  border: 2px solid var(--accent); color: var(--muted); font-family: var(--mono); font-size: 15px;
  display: grid; place-items: center; }
.team-name { font-weight: 700; font-size: 17px; color: var(--primary); text-align: center; }
.team-links { display: flex; justify-content: center; gap: 90px; margin-top: 40px; }
.team-qr { display: flex; flex-direction: column; align-items: center; gap: 9px; }
.team-qr-title { font-weight: 700; font-size: 17px; color: var(--primary); }
.team-qr-box { width: 148px; height: 148px; border-radius: 10px; border: 2px dashed var(--accent);
  background: var(--surface); color: var(--muted); font-family: var(--mono); font-size: 24px;
  display: grid; place-items: center; }
.team-qr-label { color: var(--muted); font-size: 13px; font-family: var(--mono); }

/* ---------- цитата ---------- */
.layout-quote { background: var(--surface-alt); padding: 0; }
.quote-wrap { position: absolute; left: calc(var(--left) + 40px); top: 120px; right: var(--right); }
.quote-mark { font-family: var(--heading); font-size: 150px; line-height: .8; color: var(--accent); height: 84px; }
blockquote { margin: 26px 0 0; font-family: var(--heading); color: var(--primary); line-height: 1.25;
  max-width: 86%%; }
.quote-author { margin-top: 42px; color: var(--muted); font-size: 18px; display: flex; align-items: center; gap: 18px; }

/* ---------- таблица ---------- */
.data-table { width: 100%%; height: 355px; border-collapse: collapse; table-layout: fixed; }
.data-table th { background: var(--primary); color: #fff; font-weight: 700; text-align: left; }
.data-table th, .data-table td { padding: 11px 14px; line-height: 1.2; vertical-align: middle; }
.data-table tbody tr:nth-child(odd) { background: var(--surface); }
.data-table tbody tr:nth-child(even) { background: var(--surface-alt); }
.data-table td { color: var(--ink); }

/* ---------- код ---------- */
.code-panel { position: relative; background: var(--code-bg); border-radius: 12px; padding: 30px 26px 24px 32px;
  flex: 0 1 auto; min-height: 0; overflow: hidden; }
.code-strip { position: absolute; left: 0; top: 0; bottom: 0; width: 5px; background: var(--accent); }
.code-lang { position: absolute; right: 22px; top: 14px; color: %(code_lang)s; font-family: var(--mono);
  font-size: 12px; letter-spacing: 1.2px; }
.code-panel pre { margin: 14px 0 0; font-family: var(--mono); color: var(--code-text); line-height: 1.18;
  white-space: pre; tab-size: 4; }
.code-note { color: var(--muted); font-size: 15px; margin-top: 14px; }

/* ---------- изображение ---------- */
.figure { flex: 1; min-height: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.figure img { flex: 1; min-height: 0; width: 100%%; object-fit: contain; border-radius: 10px; background: var(--dark-panel); }
.figure figcaption { text-align: center; color: var(--muted); font-size: 14px; }
.image-missing { flex: 1; display: grid; place-items: center; background: var(--surface-alt);
  border-radius: 12px; color: var(--muted); font-size: 17px; }

/* ---------- финал ---------- */
.layout-end .end-inner { position: absolute; left: var(--left); top: 226px; right: var(--right); }
.layout-end h2 { font-size: 53px; line-height: 1.06; max-width: 82%%; }
.end-lead { margin-top: 30px; max-width: 66%%; color: %(sub_on_dark)s; font-size: 22px; line-height: 1.25; }
.end-contacts { margin-top: 78px; color: %(meta_on_dark)s; font-size: 17px; }
.end-contacts ul { list-style: none; margin: 18px 0 0; padding: 0; display: grid; gap: 10px; }

/* ---------- интерфейс ---------- */
.hud { position: fixed; right: 22px; bottom: 38px; display: flex; align-items: center; gap: 10px;
  font: 13px/1 var(--body); color: #9fb0c0; user-select: none; z-index: 20; }
.hud button { width: 38px; height: 38px; border-radius: 10px; border: 1px solid #2b3a49; background: #16212c;
  color: #dbe6ef; font-size: 18px; cursor: pointer; }
.hud button:hover { background: #1e2c3a; }
.counter { min-width: 64px; text-align: center; }
.progress { position: fixed; left: 0; top: 0; height: 3px; background: var(--accent); z-index: 30; transition: width .2s; }
.notes-panel { position: fixed; left: 24px; bottom: 24px; width: 380px; max-height: 45vh; overflow: auto;
  background: #16212c; border: 1px solid #2b3a49; border-radius: 12px; padding: 14px 16px;
  color: #dbe6ef; font: 13px/1.45 var(--body); white-space: pre-wrap; display: none; z-index: 25; }
body.show-notes .notes-panel { display: block; }
.help { position: fixed; left: 24px; bottom: 24px; color: #6b7d8e; font: 12px/1.4 var(--body); z-index: 10; }
@media (max-width: 760px) { .help { display: none; } }

@media print {
  @page { size: 1280px 720px; margin: 0; }
  html, body { background: #fff !important; }
  .deck { position: static; display: block; }
  .slide { display: flex !important; position: relative; left: auto; top: auto;
    margin: 0; transform: none !important; box-shadow: none !important;
    page-break-after: always; break-after: page; }
  .slide.layout-title, .slide.layout-section, .slide.layout-end, .slide.layout-quote { display: block !important; }
  .hud, .progress, .notes-panel, .help { display: none !important; }
}
""" % {
    "primary": theme.color("primary"),
    "primary_dark": theme.color("primary_dark"),
    "accent": theme.color("accent"),
    "accent_soft": theme.color("accent_soft"),
    "ink": theme.color("ink"),
    "muted": theme.color("muted"),
    "line": theme.color("line"),
    "surface": theme.color("surface"),
    "surface_alt": theme.color("surface_alt"),
    "dark_panel": theme.color("dark_panel"),
    "bg_light": f'url("{data_uri(theme.background_light)}")' if theme.background_light else "none",
    "bg_dark": f'url("{data_uri(theme.background_dark)}")' if theme.background_dark else "none",
    "code_bg": theme.color("code_bg"),
    "code_text": theme.color("code_text"),
    "heading": theme.fonts["heading"],
    "body": theme.fonts["body"],
    "mono": theme.fonts["mono"],
    "left": theme.margins["left"] * 96,
    "right": theme.margins["right"] * 96,
    "top": theme.margins["top"] * 96,
    "kicker_on_dark": mix(theme.color("accent"), "#FFFFFF", 0.35),
    "sub_on_dark": mix(theme.color("primary"), "#FFFFFF", 0.76),
    "meta_on_dark": mix(theme.color("primary"), "#FFFFFF", 0.64),
    "number_on_dark": mix(theme.color("accent"), "#FFFFFF", 0.12),
    "code_lang": mix(theme.color("code_bg"), "#FFFFFF", 0.55),
}

JS = """
const slides = Array.from(document.querySelectorAll('.slide'));
const notes = slides.map(s => { const n = s.querySelector('.notes-src'); return n ? n.textContent.trim() : ''; });
let index = 0;
const panel = document.querySelector('.notes-panel');
const counter = document.querySelector('.counter');
const progress = document.querySelector('.progress');

function show(n) {
  index = Math.max(0, Math.min(slides.length - 1, n));
  slides.forEach((s, i) => s.classList.toggle('active', i === index));
  counter.textContent = `${String(index + 1).padStart(2, '0')} / ${String(slides.length).padStart(2, '0')}`;
  progress.style.width = `${(index + 1) / slides.length * 100}%`;
  panel.textContent = notes[index] || 'Заметок к этому слайду нет.';
  try { history.replaceState(null, '', `#${index + 1}`); } catch (e) {}
}
function fit() {
  const s = Math.min(window.innerWidth / 1280, window.innerHeight / 720) * 0.94;
  document.documentElement.style.setProperty('--s', String(s));
}
window.addEventListener('resize', fit);
window.addEventListener('keydown', (e) => {
  if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); show(index + 1); }
  else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(e.key)) { e.preventDefault(); show(index - 1); }
  else if (e.key === 'Home') { e.preventDefault(); show(0); }
  else if (e.key === 'End') { e.preventDefault(); show(slides.length - 1); }
  else if (e.key.toLowerCase() === 'n') { document.body.classList.toggle('show-notes'); }
  else if (e.key.toLowerCase() === 'f') {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  }
});
document.querySelector('.prev').addEventListener('click', () => show(index - 1));
document.querySelector('.next').addEventListener('click', () => show(index + 1));
fit();
const start = parseInt(location.hash.replace('#', ''), 10);
show(Number.isFinite(start) && start > 0 ? start - 1 : 0);
window.addEventListener('beforeprint', () => slides.forEach(s => s.classList.add('active')));
window.addEventListener('afterprint', () => show(index));
"""


def render_html(deck: Deck, theme: Theme, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(deck.slides)
    parts = []
    for i, s in enumerate(deck.slides, start=1):
        block = LAYOUTS[s.layout](deck, theme, i, total, s)
        notes = notes_html(s)
        if notes:
            block = block.rsplit("</section>", 1)[0] + notes + "</section>"
        parts.append(block)
    slides_html = "\n".join(parts)
    doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(deck.title)}</title>
<style>{build_css(theme)}</style>
</head>
<body>
<div class="progress"></div>
<main class="deck">
{slides_html}
</main>
<div class="notes-panel"></div>
<div class="hud">
  <button class="prev" type="button" aria-label="Назад">‹</button>
  <span class="counter">01 / {total:02d}</span>
  <button class="next" type="button" aria-label="Вперёд">›</button>
</div>
<div class="help">← → — слайды · N — заметки · F — полный экран · Ctrl/Cmd+P — PDF</div>
<script>{JS}</script>
</body>
</html>
"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path
