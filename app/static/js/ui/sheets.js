// Стек нижних шторок: оверлей, кнопка «Назад» Telegram, MainButton верхней шторки, закрытие свайпом вниз.
import { backButton, mainButton } from '../tg.js';
import { $ } from './dom.js';

const stack = []; // [{ el, options }]

function overlay() {
    return $('#overlay');
}

function refreshChrome() {
    const top = stack[stack.length - 1];
    overlay().classList.toggle('active', stack.length > 0);
    document.body.classList.toggle('sheet-open', stack.length > 0);

    if (top) backButton.show(() => closeTop());
    else backButton.hide();

    if (top?.options.mainButton) {
        const { text, onClick } = top.options.mainButton;
        const shown = mainButton.show(text, onClick);
        // Вне Telegram показываем запасную кнопку внутри шторки
        top.options.fallbackButton?.classList.toggle('hidden', shown);
    } else {
        mainButton.hide();
    }
    top?.options.onTop?.();
}

/**
 * options: { mainButton: {text, onClick}, fallbackButton: Element, onClose(), onTop() }
 */
export function openSheet(id, options = {}) {
    const el = document.getElementById(id);
    const existing = stack.findIndex((s) => s.el === el);
    if (existing !== -1) stack.splice(existing, 1);
    stack.push({ el, options });
    el.style.zIndex = String(60 + stack.length * 2);
    overlay().style.zIndex = String(59 + stack.length * 2);
    el.scrollTop = 0;
    requestAnimationFrame(() => el.classList.add('active'));
    refreshChrome();
}

export function closeSheet(id) {
    const index = stack.findIndex((s) => s.el.id === id);
    if (index === -1) return;
    const [{ el, options }] = stack.splice(index, 1);
    el.classList.remove('active');
    el.style.transform = '';
    if (document.activeElement && el.contains(document.activeElement)) document.activeElement.blur();
    overlay().style.zIndex = String(59 + stack.length * 2);
    options.onClose?.();
    refreshChrome();
}

export function closeTop() {
    const top = stack[stack.length - 1];
    if (top) closeSheet(top.el.id);
}

export function closeAll() {
    while (stack.length) closeTop();
}

export const isOpen = (id) => stack.some((s) => s.el.id === id);
export const topSheet = () => stack[stack.length - 1]?.el.id || null;

/** Обновить MainButton верхней шторки (например, текст «Создать» → «Сохранить»). */
export function setMainButton(id, mainButtonOptions) {
    const entry = stack.find((s) => s.el.id === id);
    if (!entry) return;
    entry.options.mainButton = mainButtonOptions;
    if (stack[stack.length - 1] === entry) refreshChrome();
}

export function initSheets() {
    overlay().addEventListener('click', closeTop);
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-close-sheet]')) closeTop();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeTop();
    });
    initDragToClose();
}

function initDragToClose() {
    let sheet = null;
    let startY = 0;
    let delta = 0;
    let startTime = 0;

    document.addEventListener('touchstart', (e) => {
        const top = stack[stack.length - 1];
        if (!top || !top.el.contains(e.target)) return;
        if (e.target.closest('input, textarea, select, .wheel-col, .no-drag')) return;
        const onHandle = e.target.classList.contains('sheet-handle');
        if (!onHandle && top.el.scrollTop > 0) return;
        sheet = top.el;
        startY = e.touches[0].clientY;
        delta = 0;
        startTime = Date.now();
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!sheet) return;
        delta = e.touches[0].clientY - startY;
        if (delta <= 0) {
            sheet.classList.remove('dragging');
            sheet.style.transform = '';
            return;
        }
        if (e.cancelable) e.preventDefault();
        sheet.classList.add('dragging');
        sheet.style.transform = `translateY(${delta}px)`;
    }, { passive: false });

    document.addEventListener('touchend', () => {
        if (!sheet) return;
        const velocity = delta / Math.max(1, Date.now() - startTime);
        sheet.classList.remove('dragging');
        const el = sheet;
        sheet = null;
        if (delta > 120 || (delta > 50 && velocity > 0.5)) {
            closeSheet(el.id);
        } else {
            el.style.transform = '';
        }
    });
}
