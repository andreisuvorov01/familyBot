// Даты: сервер отдаёт UTC (ISO), интерфейс работает в локальном времени устройства.
export const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
export const MONTHS_GEN = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
export const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const WEEKDAYS_LONG = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];

export function parseDate(value) {
    if (!value) return null;
    if (value instanceof Date) return value;
    const hasZone = /Z$|[+-]\d{2}:?\d{2}$/.test(value);
    return new Date(hasZone ? value : `${value}Z`);
}

export function startOfDay(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function addDays(d, n) {
    const r = new Date(d);
    r.setDate(r.getDate() + n);
    return r;
}

export function isSameDay(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function dayKey(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function fromDayKey(key) {
    const [y, m, d] = key.split('-').map(Number);
    return new Date(y, m - 1, d);
}

export function startOfWeek(d) {
    const day = (d.getDay() + 6) % 7; // понедельник = 0
    return startOfDay(addDays(d, -day));
}

export const pad = (n) => String(n).padStart(2, '0');
export const formatTime = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

export function relativeDayLabel(d, now = new Date()) {
    const diff = Math.round((startOfDay(d) - startOfDay(now)) / 86400000);
    if (diff === 0) return 'Сегодня';
    if (diff === 1) return 'Завтра';
    if (diff === -1) return 'Вчера';
    if (diff > 1 && diff < 7) return WEEKDAYS_LONG[d.getDay()].replace(/^./, (c) => c.toUpperCase());
    const sameYear = d.getFullYear() === now.getFullYear();
    return `${d.getDate()} ${MONTHS_GEN[d.getMonth()]}${sameYear ? '' : ` ${d.getFullYear()}`}`;
}

export function formatDeadline(d, now = new Date()) {
    return `${relativeDayLabel(d, now)}, ${formatTime(d)}`;
}

/** «Сегодня, 18:00» для ближайшей недели, иначе «пятница, 12 октября, 18:00». */
export function formatSmart(d, now = new Date()) {
    const diff = Math.round((startOfDay(d) - startOfDay(now)) / 86400000);
    return diff >= -1 && diff < 7 ? formatDeadline(d, now) : formatLong(d);
}

export function formatLong(d) {
    return `${WEEKDAYS_LONG[d.getDay()]}, ${d.getDate()} ${MONTHS_GEN[d.getMonth()]}, ${formatTime(d)}`;
}

/** Попадает ли задача на день (с учётом повторов — «виртуальные» вхождения в будущем). */
export function occursOn(task, day) {
    const deadline = parseDate(task.deadline);
    if (!deadline) return false;
    const base = startOfDay(deadline);
    const target = startOfDay(day);
    if (target.getTime() === base.getTime()) return true;
    if (target < base || !task.repeat_rule || task.status !== 'pending') return false;
    if (task.repeat_rule === 'daily') return true;
    if (task.repeat_rule === 'weekly') return target.getDay() === base.getDay();
    if (task.repeat_rule === 'monthly') {
        const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
        return target.getDate() === Math.min(base.getDate(), lastDay);
    }
    return false;
}

/** Время по умолчанию для новой даты: 09:00, а на сегодня — ближайший целый час. */
export function defaultTimeFor(day, now = new Date()) {
    const d = startOfDay(day);
    if (isSameDay(d, now)) {
        const h = Math.min(now.getHours() + 1, 23);
        d.setHours(Math.max(h, 9), 0, 0, 0);
        if (d < now) d.setHours(23, 55);
    } else {
        d.setHours(9, 0, 0, 0);
    }
    return d;
}

export function pluralize(n, one, few, many) {
    const mod10 = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
    return many;
}
