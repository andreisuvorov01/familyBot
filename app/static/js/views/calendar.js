import { MONTHS, WEEKDAYS, addDays, dayKey, isSameDay, occursOn, parseDate, relativeDayLabel, startOfDay, startOfWeek } from '../dates.js';
import { state } from '../store.js';
import { filterTasks } from './list.js';

/** Сетка дней месяца/недели. selectable(day) — можно ли выбрать день; counts(day) — бейдж. */
export function calendarGridHtml({ days, cursorMonth, selectedKey, counts, past = false }) {
    const today = startOfDay(new Date());
    const cells = WEEKDAYS.map((w) => `<div class="weekday">${w}</div>`);
    for (const day of days) {
        const key = dayKey(day);
        const classes = ['day'];
        if (cursorMonth !== null && day.getMonth() !== cursorMonth) classes.push('outside');
        if (isSameDay(day, today)) classes.push('today');
        if (key === selectedKey) classes.push('selected');
        if (past && day < today) classes.push('past');
        const info = counts ? counts(day) : null;
        const badge = info
            ? `<span class="badge ${info.late ? 'late' : ''}">${info.count}</span>`
            : counts ? '<span class="badge empty-badge">0</span>' : '';
        cells.push(`<button class="${classes.join(' ')}" data-day="${key}"><span class="num">${day.getDate()}</span>${badge}</button>`);
    }
    return `<div class="calendar-grid">${cells.join('')}</div>`;
}

export function monthDays(cursor) {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const start = startOfWeek(first);
    const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    const days = [];
    for (let d = start; d <= last || days.length % 7; d = addDays(d, 1)) days.push(d);
    return days;
}

export function weekDays(cursor) {
    const start = startOfWeek(cursor);
    return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

export function renderCalendar(container) {
    const cursor = state.calendarCursor;
    const isWeek = state.calendarMode === 'week';
    const days = isWeek ? weekDays(cursor) : monthDays(cursor);
    const tasks = filterTasks(state.tasks).filter((t) => t.deadline);
    const now = new Date();
    const today = startOfDay(now);

    const counts = (day) => {
        let count = 0;
        let late = false;
        for (const t of tasks) {
            if (t.status !== 'pending' && !isSameDay(parseDate(t.deadline), day)) continue;
            if (!occursOn(t, day)) continue;
            count++;
            if (t.status === 'pending' && parseDate(t.deadline) < now && day <= today) late = true;
        }
        return count ? { count, late } : null;
    };

    const title = isWeek
        ? `${days[0].getDate()} – ${days[6].getDate()} ${MONTHS[days[6].getMonth()].toLowerCase()}`
        : `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`;

    const selected = state.selectedDay;
    const selectedLabel = selected ? relativeDayLabel(new Date(selected + 'T00:00:00'), now) : '';

    container.innerHTML = `
        <div class="calendar">
            <div class="calendar-head">
                <h2>${title}</h2>
                <div class="calendar-nav">
                    <button data-cal="prev" aria-label="Назад"><i class="fa-solid fa-chevron-left"></i></button>
                    <button data-cal="today" aria-label="Сегодня"><i class="fa-regular fa-circle-dot"></i></button>
                    <button data-cal="next" aria-label="Вперёд"><i class="fa-solid fa-chevron-right"></i></button>
                </div>
            </div>
            ${calendarGridHtml({ days, cursorMonth: isWeek ? null : cursor.getMonth(), selectedKey: selected, counts })}
            <div class="calendar-footer">
                <div class="segmented calendar-mode">
                    <button data-cal-mode="month" class="${isWeek ? '' : 'active'}">Месяц</button>
                    <button data-cal-mode="week" class="${isWeek ? 'active' : ''}">Неделя</button>
                </div>
                ${selected ? `<button class="link-btn" data-cal="clear">${selectedLabel} ✕</button>` : '<span class="label"></span>'}
            </div>
        </div>`;
}

export function shiftCursor(direction) {
    const c = new Date(state.calendarCursor);
    if (state.calendarMode === 'week') c.setDate(c.getDate() + 7 * direction);
    else c.setMonth(c.getMonth() + direction, 1);
    return c;
}
