---
name: Child Friendly UI
description: Дизайн детской игры — Comic Neue, нейтральный фон с тематической анимацией, контраст, адаптив и одинаковые размеры карточек и зон
---

# Дизайн и адаптивность

Загружай вместе с `lesson-game-spec`. Цель — чисто, крупно, дружелюбно и
одинаково аккуратно на телефоне и на десктопе.

## 1. Токены

```css
:root {
  --bg: #f4f1ea;
  --surface: #fffdf8;
  --ink: #22304a;
  --muted: #5b6b85;
  --accent: #3d7bfd;
  --accent-soft: #e3ecff;
  --ok: #1f9d55;
  --ok-soft: #e6f7ee;
  --bad: #d64545;
  --bad-soft: #fdeaea;
  --radius: 14px;
  --shadow: 0 6px 0 rgba(34, 48, 74, 0.12), 0 10px 24px rgba(34, 48, 74, 0.08);
  --tile-w: 15rem;
  --tile-h: 4.25rem;
}
```

Фон нейтральный тёплый, не белый и не кислотный. Текст `--ink` на `--surface`
даёт контраст выше 7:1. Не опускайся ниже 4.5:1 для основного текста.

## 2. Шрифт

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&display=swap" rel="stylesheet">
```

```css
body {
  font-family: "Comic Neue", "Comic Sans MS", "Segoe UI", sans-serif;
}
```

- Основной текст 18–20 px, определения 18–22 px, заголовок `clamp(1.6rem, 5vw, 2.4rem)`.
- Межстрочный интервал 1.4–1.6.
- Никаких тонких начертаний: только 400 и 700.
- Без интернета игра работает на fallback-шрифте — это допустимо, вёрстка не
  должна ломаться.

## 3. Сетка

```css
.game {
  inline-size: min(1100px, 100% - 2rem);
  margin-inline: auto;
  padding-block: clamp(1rem, 4vw, 2.5rem);
}

.board {
  display: grid;
  grid-template-columns: minmax(15rem, 17rem) minmax(0, 1fr);
  gap: clamp(1rem, 3vw, 2.25rem);
  align-items: start;
}

.tokens { display: grid; gap: 0.75rem; }

.task {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.task__text { flex: 1 1 auto; min-inline-size: 0; }
```

Правая колонка — список из 6 строк; в каждой строке определение и зона ответа.
Определение может занимать 2–3 строки, зона при этом стоит справа по центру.

## 4. Одинаковый размер карточки и зоны

Это требование нельзя выполнять «на глаз». Один класс размеров:

```css
.token,
.slot {
  box-sizing: border-box;
  inline-size: var(--tile-w);
  block-size: var(--tile-h);
  border-radius: var(--radius);
  display: grid;
  place-items: center;
  padding: 0.4rem 0.6rem;
  text-align: center;
}
```

- Карточка и зона используют одни и те же `--tile-w` / `--tile-h`.
- На мобильном обе становятся `inline-size: 100%`, высота `3.5rem`.
- Не задавай карточке `width: fit-content` или `min-height` — размеры разойдутся.
- Длинный термин уменьшай через `font-size: clamp()` и `overflow-wrap: anywhere`,
  а не через изменение высоты.

## 5. Карточка и зона

Карточка: светлый фон, рамка 2 px, скругление, тень, лёгкий подъём при
наведении, `cursor: grab`, `user-select: none`, `touch-action: none`.
В состоянии `.is-dragging` — `opacity: 0.35`.

Зона: пунктирная рамка 2 px цвета `--muted`, фон прозрачный, внутри бледная
подпись «Перетащи сюда». В `.is-over` — синяя рамка и `--accent-soft`.

Обратная связь:

- `.is-correct` — фон `--ok-soft`, рамка `--ok`, галочка `✓` псевдоэлементом
  или внутри зоны.
- `.is-wrong` — фон `--bad-soft`, рамка `--bad`, крестик `✕`, анимация
  `shake 320ms`.
- После успеха карточка внутри зоны теряет тень и курсор.

```css
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px); }
  40% { transform: translateX(6px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
}
```

## 6. Фоновая тематическая анимация

Отдельный слой `position: fixed; inset: 0; pointer-events: none; z-index: 0;`,
контент выше (`position: relative; z-index: 1`).

- 5–7 крупных полупрозрачных фигур/символов по теме (листья, волны, звёзды,
  шестерёнки, буквы). Можно CSS-фигуры или inline SVG — без внешних картинок.
- Медленное плавное движение: `transform: translate3d()` + `rotate`,
  длительность 18–35 с, `ease-in-out infinite alternate`.
- Прозрачность 0.12–0.25, чтобы не мешать чтению.
- Анимация только через `transform`/`opacity` (без `left/top`, чтобы не
  тормозило на телефоне).
- Обязательно:

```css
@media (prefers-reduced-motion: reduce) {
  .bg__shape, .token, .slot, .modal { animation: none !important; transition: none !important; }
}
```

## 7. Мобильная версия

Контрольная точка — 880 px:

```css
@media (max-width: 880px) {
  .board { grid-template-columns: 1fr; }
  .tokens { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .token, .slot { inline-size: 100%; block-size: 3.5rem; }
  .task { flex-direction: column; align-items: stretch; gap: 0.5rem; }
  .task__text { font-size: 1.05rem; }
}
```

- Сначала блок терминов, затем задания — это порядок в DOM, не меняй его через
  `order`.
- Карточки в 2 колонки на телефоне допустимы, если термины короткие; если
  сомневаешься — одна колонка.
- Зона занимает всю ширину и равна карточке по высоте.
- Учитывай `env(safe-area-inset-bottom)` для нижнего отступа.
- Запрещена горизонтальная прокрутка: проверь на 320 px.
- Минимальная цель касания — 44×44 px.

## 8. Заголовок, счёт, модальное окно

- Шапка: тема и класс слева, компактные пилюли «Верно: 0/6» и «Ошибки: 0»
  справа; на мобильном — в две строки, не мельче 16 px.
- Модальное окно: центрированная карточка `max-inline-size: 26rem`, крупный
  счёт `clamp(2rem, 10vw, 3.5rem)`, кнопка высотой не меньше 52 px.
- Кнопка: заметная, `--accent`, белый текст, скругление, тень, `:focus-visible`
  с контрастным кольцом.
- Оверлей: `rgba(20, 28, 45, 0.55)` + `backdrop-filter: blur(2px)` (необязательно).

## 9. Доступность и мелочи

- `lang="ru"`, `meta viewport` с `viewport-fit=cover`.
- `:focus-visible` виден на карточках, зонах и кнопке.
- Не полагайся только на цвет: верно = зелёный + `✓`, неверно = красный + `✕`.
- `aria-live="polite"` для сообщений «Верно», «Попробуй ещё», «Игра
  завершена».
- Отключи выделение текста на карточках и зонах, но не на определениях.
- Не используй эмодзи как единственный носитель смысла.

Готовая заготовка токенов и сетки — в `references/layout.css`; адаптируй её,
а не копируй слепо.
