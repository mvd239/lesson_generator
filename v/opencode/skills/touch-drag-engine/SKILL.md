---
name: Touch Drag Engine
description: Перетаскивание карточек без HTML5 DnD — Pointer Events, touch-fallback, ghost-копия, hit-test и отмена
---

# Механика перетаскивания

Использовать HTML5 Drag-and-Drop (`draggable`, `dragstart`, `drop`) **нельзя**:
на сенсорных экранах он не работает без полифилов. Делаем собственное
перетаскивание.

## 1. Базовая схема

1. `pointerdown` на карточке → запоминаем точку старта, создаём `ghost`-копию
   с `position: fixed` на месте оригинала.
2. `pointermove` → двигаем ghost через `translate3d(dx, dy, 0)`. Смещение
   считаем от точки старта, а не от угла карточки, — иначе карточка «прыгает»
   под палец.
3. Во время движения определяем зону под указателем:
   `document.elementFromPoint(x, y).closest('[data-dropzone]')`. Ghost имеет
   `pointer-events: none`, поэтому не перехватывает hit-test.
4. `pointerup` → проверяем зону, вызываем `onDrop(card, zone)`; если зоны нет,
   плавно возвращаем ghost на место за 180 мс и удаляем.
5. Короткое касание без движения (< 6 px) — это не drag, а выбор карточки:
   вызываем `onTap(card)`.
6. `pointercancel`, `blur`, `visibilitychange`, `resize` → отменяем
   перетаскивание, ghost удаляем, карточка остаётся на месте.

## 2. Обязательные детали

- CSS карточки: `touch-action: none; user-select: none; -webkit-user-select: none;`.
- Слушатели `pointermove`/`touchmove` — с `{ passive: false }`, чтобы
  `preventDefault()` действительно останавливал прокрутку.
- Проверка мультитача: если `e.touches.length > 1` — игнорировать.
- Единый `drag`-объект: второй `pointerdown` во время drag не создаёт вторую
  копию.
- Ghost клонируем через `cloneNode(true)`, удаляем у клона `data-card`,
  `id`, `tabindex`; ставим `aria-hidden="true"`.
- Возврат и удаление ghost — по таймеру, а не по `transitionend` (событие может
  не прийти при `prefers-reduced-motion`).
- После успешного дропа карточка удаляется из левой колонки (или скрывается) и
  вставляется в зону; у неё ставится `data-placed="true"` и снимается
  `tabindex`.
- Занятая зона (`.is-filled`) не принимает дроп: `zoneAt` возвращает `null`.
- Не меняй DOM в `pointerdown`, пока не началось движение: короткий тап не
  должен двигать карточку.
- `preventDefault()` на `pointerdown` отменяет клики, поэтому выбор карточки и
  клик по зоне реализуй через свои обработчики (`onTap`, `click` на зонах), а
  не через нативный `click` на карточке.

## 3. Pointer Events + Touch Events

```js
if (window.PointerEvent) {
  document.addEventListener("pointerdown", onDown, { passive: false });
  document.addEventListener("pointermove", onMove, { passive: false });
  document.addEventListener("pointerup", onUp);
  document.addEventListener("pointercancel", onCancel);
} else {
  document.addEventListener("touchstart", onDown, { passive: false });
  document.addEventListener("touchmove", onMove, { passive: false });
  document.addEventListener("touchend", onUp);
  document.addEventListener("touchcancel", onCancel);
  document.addEventListener("mousedown", onDown);
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}
```

В обработчике точки бери `changedTouches[0]` для `touchend` и `touches[0]` для
`touchmove`: у `touchend` массив `touches` пуст, а координат на самом событии
нет.

Не навешивай одновременно pointer- и touch-обработчики: получишь двойные
события. Выбор — по `window.PointerEvent`, как выше.

Готовая реализация — в `references/drag-pattern.js`. Скопируй, подставь
селекторы и колбэки, проверь на реальном тач-экране или в эмуляции.

## 4. Хуки в игровую логику

```js
const dnd = createDragAndDrop({
  cardSelector: "[data-card]",
  zoneSelector: "[data-dropzone]",
  onDrop(card, zone) {
    validate(card, zone); // см. lesson-game-spec
  },
  onTap(card) {
    selectCard(card);
  },
});
```

`validate(card, zone)`:

```js
function validate(card, zone) {
  if (zone.classList.contains("is-filled")) return;

  if (card.dataset.key === zone.dataset.answer) {
    placeCard(card, zone);          // перенос в зону, .is-correct, +1
  } else {
    rejectAnswer(card, zone);       // .is-wrong, shake, ✕, ошибка +1
  }
}
```

`rejectAnswer` не перемещает карточку: она и не покидала левую колонку, двигался
только ghost. Достаточно снять `.is-wrong` через 500–650 мс и объявить
«Попробуй ещё» в `aria-live`.

## 5. Клик и клавиатура

- `onTap(card)` → `selectCard`: снять `.is-selected` с других, поставить на эту,
  `aria-pressed="true"`, объявить «Выбран термин: …».
- `click` на зоне: если есть выбранная карточка — `validate(selected, zone)`.
- `keydown` на карточке: Enter/Space — выбрать; Enter/Space на зоне — проверить.
- После успеха снять выделение.
- Клик по выбранной карточке повторно — снять выбор.

Это не замена drag-and-drop, а дополнительный способ, который делает игру
доступной и страхует от сбоев touch-событий.

## 6. Что проверять руками

- Мышь: карточка следует за курсором, дроп срабатывает над зоной и не срабатывает
  мимо.
- Палец: страница не прокручивается во время drag, карточка не «отлипает» от
  пальца при быстром движении.
- Тап по карточке, затем тап по зоне — ответ проверяется.
- Тап по карточке и повторный тап — выбор снимается.
- Дроп в занятую зону ничего не делает.
- Быстрые двойные тапы не создают дубль.
- Поворот экрана во время drag не оставляет ghost на странице.
- В консоли нет ошибок.
