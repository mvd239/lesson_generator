/* Кастомный drag-and-drop для детской игры-сопоставления.
   Работает на Pointer Events, при их отсутствии — на Touch/Mouse Events.
   HTML5 Drag-and-Drop не используется.

   Подключение:
     const dnd = createDragAndDrop({
       cardSelector: '[data-card]',
       zoneSelector: '[data-dropzone]',
       onDrop(card, zone) { ... },
       onTap(card) { ... },
     });

   Разметка: карточка — [data-card], зона — [data-dropzone].
   Занятая зона должна иметь класс .is-filled.
*/
function createDragAndDrop({ cardSelector, zoneSelector, onDrop, onTap }) {
  const MOVE_THRESHOLD = 6;
  let drag = null;

  function pointOf(e) {
    const src =
      (e.changedTouches && e.changedTouches[0]) ||
      (e.touches && e.touches[0]) ||
      e;
    return { x: src.clientX, y: src.clientY };
  }

  function makeGhost(card) {
    const rect = card.getBoundingClientRect();
    const ghost = card.cloneNode(true);
    ghost.classList.add("drag-ghost");
    ghost.removeAttribute("data-card");
    ghost.removeAttribute("id");
    ghost.removeAttribute("tabindex");
    ghost.setAttribute("aria-hidden", "true");
    Object.assign(ghost.style, {
      position: "fixed",
      left: rect.left + "px",
      top: rect.top + "px",
      width: rect.width + "px",
      height: rect.height + "px",
      margin: "0",
      pointerEvents: "none",
      zIndex: "9999",
      willChange: "transform",
      transform: "translate3d(0, 0, 0)",
    });
    document.body.appendChild(ghost);
    return ghost;
  }

  function zoneAt(x, y) {
    const hit = document.elementFromPoint(x, y);
    const zone = hit && hit.closest(zoneSelector);
    if (!zone) return null;
    if (zone.classList.contains("is-filled")) return null;
    return zone;
  }

  function start(card, p) {
    if (!card || drag) return false;
    if (card.dataset.placed === "true") return false;

    drag = {
      card: card,
      ghost: makeGhost(card),
      startX: p.x,
      startY: p.y,
      lastX: p.x,
      lastY: p.y,
      moved: false,
      zone: null,
    };
    card.classList.add("is-dragging");
    return true;
  }

  function move(p) {
    if (!drag) return;

    drag.lastX = p.x;
    drag.lastY = p.y;

    const dx = p.x - drag.startX;
    const dy = p.y - drag.startY;

    if (!drag.moved && Math.hypot(dx, dy) < MOVE_THRESHOLD) return;
    drag.moved = true;

    drag.ghost.style.transform = "translate3d(" + dx + "px," + dy + "px,0)";

    const zone = zoneAt(p.x, p.y);
    if (zone !== drag.zone) {
      if (drag.zone) drag.zone.classList.remove("is-over");
      drag.zone = zone;
      if (zone) zone.classList.add("is-over");
    }
  }

  function finish(cancelled) {
    if (!drag) return;

    const d = drag;
    drag = null;

    if (d.zone) d.zone.classList.remove("is-over");
    d.card.classList.remove("is-dragging");

    if (cancelled) {
      d.ghost.remove();
      return;
    }

    if (!d.moved) {
      d.ghost.remove();
      if (onTap) onTap(d.card);
      return;
    }

    const zone = zoneAt(d.lastX, d.lastY);
    if (zone) {
      d.ghost.remove();
      if (onDrop) onDrop(d.card, zone);
      return;
    }

    d.ghost.style.transition = "transform 180ms ease, opacity 180ms ease";
    d.ghost.style.transform = "translate3d(0,0,0)";
    d.ghost.style.opacity = "0.65";
    window.setTimeout(function () {
      d.ghost.remove();
    }, 200);
  }

  function onDown(e) {
    if (e.button != null && e.button !== 0) return;
    if (e.touches && e.touches.length > 1) return;
    if (e.target.closest(zoneSelector)) return;

    const card = e.target.closest(cardSelector);
    if (!card) return;

    if (start(card, pointOf(e)) && e.cancelable) e.preventDefault();
  }

  function onMove(e) {
    if (!drag) return;
    if (e.cancelable) e.preventDefault();
    move(pointOf(e));
  }

  function onUp(e) {
    if (!drag) return;
    const p = pointOf(e);
    drag.lastX = p.x;
    drag.lastY = p.y;
    finish(false);
  }

  function onCancel() {
    finish(true);
  }

  const pointerMode = "PointerEvent" in window;

  if (pointerMode) {
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

  window.addEventListener("blur", onCancel);
  window.addEventListener("resize", onCancel);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) onCancel();
  });
  document.addEventListener("dragstart", function (e) {
    e.preventDefault();
  });

  return {
    destroy: function () {
      onCancel();
      if (pointerMode) {
        document.removeEventListener("pointerdown", onDown);
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        document.removeEventListener("pointercancel", onCancel);
      } else {
        document.removeEventListener("touchstart", onDown);
        document.removeEventListener("touchmove", onMove);
        document.removeEventListener("touchend", onUp);
        document.removeEventListener("touchcancel", onCancel);
        document.removeEventListener("mousedown", onDown);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }
      window.removeEventListener("blur", onCancel);
      window.removeEventListener("resize", onCancel);
    },
  };
}
