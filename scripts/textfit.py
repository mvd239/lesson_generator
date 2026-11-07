"""Оценка объёма текста: подбор размера шрифта под блок."""

from __future__ import annotations


def estimate_lines(text: str, width_pt: float, font_pt: float, factor: float = 0.53) -> int:
    """Грубая оценка числа строк с учётом переноса по словам."""
    text = str(text)
    if not text:
        return 0
    chars_per_line = max(4, int(width_pt / max(1.0, font_pt * factor)))
    lines = 1
    current = 0
    for word in text.split():
        piece = len(word) + (1 if current else 0)
        if current + piece <= chars_per_line:
            current += piece
        else:
            lines += 1
            current = len(word)
            if len(word) > chars_per_line:
                lines += len(word) // chars_per_line
                current = len(word) % chars_per_line
    return lines


def fit_size(texts: list[tuple[str, float]], width_in: float, height_in: float, base: float,
             minimum: float, spacing: float = 1.2, para_gap: float = 0) -> float:
    """Подбирает максимальный размер шрифта, при котором текст влезает в блок."""
    size = base
    while size > minimum:
        total = 0.0
        for text, indent in texts:
            lines = estimate_lines(text, max(30.0, (width_in - indent) * 72), size)
            total += max(1, lines) * size * spacing + para_gap
        if total <= height_in * 72:
            return round(size, 1)
        size -= 0.5
    return minimum
