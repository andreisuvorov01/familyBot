import { MONTHS, addDays, dayKey, defaultTimeFor, fromDayKey, pad, relativeDayLabel, startOfDay } from '../dates.js';
import { haptic } from '../tg.js';
import { $ } from '../ui/dom.js';
import { closeSheet, openSheet } from '../ui/sheets.js';
import { calendarGridHtml, monthDays } from '../views/calendar.js';

const ITEM_H = 36;
const MINUTE_STEP = 5;
const TIME_PRESETS = [[9, 0], [13, 0], [19, 0]];

let selectedDay = null; // Date (полночь)
let hour = 9;
let minute = 0;
let cursor = new Date();
let resolver = null;
let wheelsReady = false;

function buildWheel(col, count, step, onChange) {
    col.innerHTML = Array.from({ length: count }, (_, i) => `<div class="wheel-item" data-index="${i}">${pad(i * step)}</div>`).join('');
    let frame = null;
    let lastIndex = -1;
    col.addEventListener('scroll', () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
            const index = Math.max(0, Math.min(count - 1, Math.round(col.scrollTop / ITEM_H)));
            if (index !== lastIndex) {
                lastIndex = index;
                [...col.children].forEach((el, i) => el.classList.toggle('active', i === index));
                if (col.dataset.ready) haptic.select();
                onChange(index * step);
            }
        });
    }, { passive: true });
    col.addEventListener('click', (e) => {
        const item = e.target.closest('.wheel-item');
        if (item) col.scrollTo({ top: Number(item.dataset.index) * ITEM_H, behavior: 'smooth' });
    });
}

function setWheel(col, index) {
    col.dataset.ready = '';
    col.scrollTop = index * ITEM_H;
    [...col.children].forEach((el, i) => el.classList.toggle('active', i === index));
    setTimeout(() => { col.dataset.ready = '1'; }, 100);
}

function ensureWheels() {
    if (wheelsReady) return;
    wheelsReady = true;
    buildWheel($('#wheel-h'), 24, 1, (v) => { hour = v; updateTitle(); });
    buildWheel($('#wheel-m'), 60 / MINUTE_STEP, MINUTE_STEP, (v) => { minute = v; updateTitle(); });

    $('#time-presets').innerHTML = TIME_PRESETS.map(([h, m]) => `<button data-h="${h}" data-m="${m}">${pad(h)}:${pad(m)}</button>`).join('');
    $('#time-presets').addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        setTime(Number(btn.dataset.h), Number(btn.dataset.m), true);
    });

    $('#picker-calendar').addEventListener('click', (e) => {
        const nav = e.target.closest('[data-cal]');
        if (nav) {
            const dir = nav.dataset.cal === 'prev' ? -1 : nav.dataset.cal === 'next' ? 1 : 0;
            cursor = dir ? new Date(cursor.getFullYear(), cursor.getMonth() + dir, 1) : new Date();
            renderCalendar();
            return;
        }
        const dayBtn = e.target.closest('[data-day]');
        if (dayBtn) selectDay(fromDayKey(dayBtn.dataset.day));
    });

    $('#quick-dates').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-offset]');
        if (btn) selectDay(addDays(startOfDay(new Date()), Number(btn.dataset.offset)));
    });

    $('#date-done').addEventListener('click', () => {
        if (!selectedDay) selectedDay = startOfDay(new Date()); // время выбрано, день — сегодня
        finish(currentValue());
    });
    $('#date-clear').addEventListener('click', () => finish(null));
}

function setTime(h, m, smooth = false) {
    hour = h;
    minute = Math.round(m / MINUTE_STEP) * MINUTE_STEP % 60;
    const hCol = $('#wheel-h');
    const mCol = $('#wheel-m');
    if (smooth) {
        hCol.scrollTo({ top: hour * ITEM_H, behavior: 'smooth' });
        mCol.scrollTo({ top: (minute / MINUTE_STEP) * ITEM_H, behavior: 'smooth' });
    } else {
        setWheel(hCol, hour);
        setWheel(mCol, minute / MINUTE_STEP);
    }
    updateTitle();
}

function selectDay(day) {
    const isFirstPick = !selectedDay;
    selectedDay = startOfDay(day);
    cursor = new Date(selectedDay.getFullYear(), selectedDay.getMonth(), 1);
    haptic.select();
    if (isFirstPick) {
        const def = defaultTimeFor(selectedDay);
        setTime(def.getHours(), def.getMinutes(), true);
    }
    renderCalendar();
    updateTitle();
}

function currentValue() {
    if (!selectedDay) return null;
    const d = new Date(selectedDay);
    d.setHours(hour, minute, 0, 0);
    return d;
}

function updateTitle() {
    const value = currentValue();
    $('#date-title').textContent = value ? `${relativeDayLabel(value)}, ${pad(hour)}:${pad(minute)}` : 'Дата и время';
}

function renderQuickDates() {
    const today = startOfDay(new Date());
    const toSaturday = (6 - today.getDay() + 7) % 7 || 7;
    const options = [
        ['Сегодня', 0],
        ['Завтра', 1],
        ['Выходные', toSaturday],
        ['Через неделю', 7],
    ];
    $('#quick-dates').innerHTML = options.map(([label, offset]) => {
        const d = addDays(today, offset);
        return `<button data-offset="${offset}">${label}<small>${d.getDate()}.${pad(d.getMonth() + 1)}</small></button>`;
    }).join('');
}

function renderCalendar() {
    const host = $('#picker-calendar');
    host.innerHTML = `
        <div class="calendar-head">
            <h2>${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}</h2>
            <div class="calendar-nav">
                <button data-cal="prev" aria-label="Предыдущий месяц"><i class="fa-solid fa-chevron-left"></i></button>
                <button data-cal="today" aria-label="Текущий месяц"><i class="fa-regular fa-circle-dot"></i></button>
                <button data-cal="next" aria-label="Следующий месяц"><i class="fa-solid fa-chevron-right"></i></button>
            </div>
        </div>
        ${calendarGridHtml({ days: monthDays(cursor), cursorMonth: cursor.getMonth(), selectedKey: selectedDay ? dayKey(selectedDay) : null, past: true })}`;
}

function finish(value) {
    const resolve = resolver;
    resolver = null;
    closeSheet('sheet-date');
    resolve?.(value);
}

/**
 * Открыть выбор даты. Возвращает Date, null («без даты») или undefined (закрыли без выбора).
 */
export function pickDate(initial) {
    ensureWheels();
    renderQuickDates();
    selectedDay = initial ? startOfDay(initial) : null;
    cursor = new Date((initial || new Date()).getFullYear(), (initial || new Date()).getMonth(), 1);
    renderCalendar();
    const base = initial || defaultTimeFor(new Date());
    openSheet('sheet-date', {
        onClose: () => {
            if (resolver) {
                const resolve = resolver;
                resolver = null;
                resolve(undefined);
            }
        },
    });
    requestAnimationFrame(() => setTime(base.getHours(), base.getMinutes()));
    $('#date-clear').classList.toggle('hidden', !initial);
    return new Promise((resolve) => { resolver = resolve; });
}
