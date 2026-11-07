#!/usr/bin/env python3
"""Кодирует секретные поля заданий теста ВПР в base64 (UTF-8).

Зачем: чтобы правильные ответы и пояснения не читались в исходном коде
HTML (ученик может открыть «Просмотр кода» / DevTools). Движок теста
декодирует их в рантайме функцией decodeSecrets().

Использование:
    python encode.py input.json [output.json]

input.json — файл с полем "tasks" (список заданий) или просто список:
    {"tasks": [ {"type": "single", "instruction": "...", "options": [...],
                 "correct": 0, "explanation": "..."}, ... ]}

Секретные поля, которые кодируются в base64:
    correct      (single: число-индекс; multi: список индексов)
    correctText  (text: эталон ответа)
    accept       (text: список дополнительных вариантов)
    pairs[].correct (match: правильный вариант для пары)
    sample       (open: образец ответа)
    explanation  (любой тип: пояснение)

Остальные поля (type, instruction, text, options, pairs[].left,
pairs[].options) не меняются.
"""
import json
import sys
import base64
import pathlib


def enc(value):
    return base64.b64encode(str(value).encode("utf-8")).decode("ascii")


def encode_task(task):
    t = dict(task)
    typ = t.get("type")

    if t.get("correct") is not None:
        if typ == "multi":
            # кодируем JSON-массив, например "[0,2]"
            t["correct"] = enc(json.dumps(t["correct"], ensure_ascii=False, separators=(",", ":")))
        else:
            t["correct"] = enc(t["correct"])

    if t.get("correctText") is not None:
        t["correctText"] = enc(t["correctText"])

    if t.get("accept"):
        t["accept"] = [enc(x) for x in t["accept"]]

    if t.get("sample"):
        t["sample"] = enc(t["sample"])

    if t.get("explanation"):
        t["explanation"] = enc(t["explanation"])

    if t.get("pairs"):
        for p in t["pairs"]:
            if p.get("correct") is not None:
                p["correct"] = enc(p["correct"])

    return t


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # utf-8-sig корректно обрабатывает BOM, который добавляет PowerShell
    data = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    tasks = data["tasks"] if isinstance(data, dict) and "tasks" in data else data
    out = {"tasks": [encode_task(t) for t in tasks]}
    text = json.dumps(out, ensure_ascii=False, indent=2)

    if len(sys.argv) >= 3:
        pathlib.Path(sys.argv[2]).write_text(text, encoding="utf-8")
        print(f"OK: {len(out['tasks'])} заданий -> {sys.argv[2]}")
    else:
        print(text)


if __name__ == "__main__":
    main()
