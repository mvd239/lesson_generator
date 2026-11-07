#!/usr/bin/env node
/* Статическая проверка одностраничной игры.
   Использование: node check-single-file.mjs path/to/index.html
   Без внешних зависимостей. */

import { existsSync, readFileSync, statSync } from "node:fs";

const file = process.argv[2] || "index.html";
const results = [];

const ok = (msg) => results.push({ level: "OK", msg });
const fail = (msg) => results.push({ level: "FAIL", msg });
const warn = (msg) => results.push({ level: "WARN", msg });

const need = (cond, okMsg, failMsg) => (cond ? ok(okMsg) : fail(failMsg));

if (!existsSync(file)) {
  console.error(`[FAIL] Файл не найден: ${file}`);
  process.exit(1);
}

const src = readFileSync(file, "utf8");
const size = statSync(file).size;

ok(`Файл найден: ${file} (${(size / 1024).toFixed(1)} KB)`);

/* ---------- Каркас документа ---------- */

need(/<!doctype\s+html>/i.test(src), "Есть <!DOCTYPE html>", "Нет <!DOCTYPE html>");
need(/<html[^>]+lang\s*=\s*["']ru["']/i.test(src), "Указан lang=\"ru\"", "Не указан lang=\"ru\"");
need(
  /<meta[^>]+name\s*=\s*["']viewport["']/i.test(src) && /width\s*=\s*device-width/i.test(src),
  "Есть meta viewport",
  "Нет meta viewport с width=device-width"
);
need(/<title>[^<]{3,}<\/title>/i.test(src), "Есть непустой <title>", "Нет непустого <title>");

/* ---------- Внешние зависимости ---------- */

const externalScript = /<script\b[^>]*\bsrc\s*=/i.test(src);
need(!externalScript, "Нет внешних <script src>", "Найден внешний <script src> — библиотеки запрещены");

const dynamicImport = /\bimport\s*(?:\(|[^;]*from\s*)["']https?:/i.test(src);
need(!dynamicImport, "Нет импортов по URL", "Найден import по URL");

const urls = src.match(/https?:\/\/[^\s"'<>)]+/g) || [];
const allowedHost = /^https?:\/\/(fonts\.googleapis\.com|fonts\.gstatic\.com|www\.w3\.org)\//i;
const badUrls = [...new Set(urls)].filter((u) => !allowedHost.test(u));
need(
  badUrls.length === 0,
  "Внешние URL только Google Fonts / SVG namespace",
  `Подозрительные внешние URL: ${badUrls.join(", ")}`
);

const fontLink =
  /fonts\.googleapis\.com\/css2\?[^"']*family=Comic\+Neue/i.test(src) ||
  /fonts\.googleapis\.com\/css\?[^"']*family=Comic\+Neue/i.test(src);
need(fontLink, "Подключён Comic Neue через Google Fonts", "Не найден Google Fonts с Comic Neue");
need(/display\s*=\s*swap/i.test(src), "Шрифт с display=swap", "У шрифта нет display=swap");
need(
  /Comic\s+Neue/i.test(src) && /(Comic Sans MS|sans-serif)/i.test(src),
  "Есть fallback-стек шрифтов",
  "Нет fallback-стека для шрифта"
);

/* ---------- Перетаскивание и сенсор ---------- */

need(
  /pointerdown|touchstart/i.test(src),
  "Обработка Pointer/Touch Events есть",
  "Нет обработки pointerdown/touchstart"
);
need(/touch-action\s*:\s*none/i.test(src), "touch-action: none задан", "Нет touch-action: none");
need(
  /elementFromPoint/i.test(src),
  "Hit-test через elementFromPoint",
  "Нет elementFromPoint для определения зоны"
);
need(
  !/draggable\s*=\s*["']true["']/i.test(src),
  "HTML5 Drag-and-Drop не используется",
  "Найден draggable=\"true\" — используйте Pointer/Touch"
);
need(
  /(pointermove|touchmove)/i.test(src),
  "Есть обработчик движения",
  "Нет pointermove/touchmove"
);
need(
  /(pointerup|touchend)/i.test(src),
  "Есть обработчик отпускания",
  "Нет pointerup/touchend"
);

/* ---------- Игровая логика ---------- */

const dropzones = (src.match(/data-dropzone/g) || []).length;
const answers = (src.match(/data-answer/g) || []).length;
if (dropzones >= 6) ok(`Зон ответа в разметке: ${dropzones}`);
else warn(`В исходнике ${dropzones} вхождений data-dropzone; проверь вручную, что зон 6`);
if (answers >= 6) ok(`Ключей ответов: ${answers}`);
else warn(`В исходнике ${answers} вхождений data-answer; проверь вручную, что пар 6`);

need(
  /role\s*=\s*["']dialog["']/i.test(src),
  "Финальное окно с role=\"dialog\"",
  "Нет role=\"dialog\" у финального окна"
);
need(
  /(location\.reload\s*\(|reset|restart)/i.test(src),
  "Есть перезапуск игры",
  "Не найден перезапуск (location.reload или reset)"
);
need(
  /aria-live\s*=\s*["'](polite|assertive)["']/i.test(src),
  "Есть aria-live для обратной связи",
  "Нет aria-live для объявления результата"
);
need(
  /:focus-visible/i.test(src),
  "Есть стиль :focus-visible",
  "Нет :focus-visible"
);

if (/prefers-reduced-motion/i.test(src)) ok("Учтён prefers-reduced-motion");
else warn("Нет prefers-reduced-motion — анимацию нельзя отключить");

if (/overflow-wrap\s*:\s*(anywhere|break-word)/i.test(src)) ok("Длинные термины переносятся");
else warn("Нет overflow-wrap — длинный термин может вылезти за карточку");

/* ---------- Гигиена ---------- */

if (/console\.log\s*\(/i.test(src)) warn("В коде остался console.log — уберите отладку");
else ok("Отладочных console.log нет");

if (size < 12 * 1024) warn("Файл меньше 12 KB — похоже, часть требований не реализована");
if (size > 350 * 1024) warn("Файл больше 350 KB — проверьте, нет ли лишних данных");

/* ---------- Вывод ---------- */

for (const r of results) {
  console.log(`[${r.level}] ${r.msg}`);
}

const fails = results.filter((r) => r.level === "FAIL").length;
const warns = results.filter((r) => r.level === "WARN").length;
const oks = results.filter((r) => r.level === "OK").length;

console.log("");
console.log(`Итог: ${fails} FAIL, ${warns} WARN, ${oks} OK`);
console.log(
  fails === 0
    ? "Статические проверки пройдены. Осталось ручное тестирование по чек-листу qa-verify."
    : "Есть блокирующие ошибки. Исправьте их и запустите проверку снова."
);

process.exit(fails > 0 ? 1 : 0);
