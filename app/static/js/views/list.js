import { addDays, formatDeadline, formatTime, fromDayKey, isSameDay, occursOn, parseDate, pluralize, relativeDayLabel, startOfDay } from '../dates.js';
import { state } from '../store.js';
import { escapeHtml } from '../ui/dom.js';

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const PRIORITY_MARK = { high: '!!!', medium: '!!', low: '!' };
const renderedIds = new Set(); // анимация появления — только для новых карточек

export function filterTasks(tasks) {
    const me = state.profile?.id;
    const q = state.search.trim().toLowerCase();
    return tasks.filter((t) => {
        if (state.filter === 'common' && t.visibility !== 'common') return false;
        if (state.filter === 'private' && t.visibility === 'common') return false;
        if (state.filter === 'mine' && t.owner_id !== me) return false;
        if (q) {
            const haystack = [t.title, t.description || '', ...t.subtasks.map((s) => s.title)].join('\n').toLowerCase();
            if (!haystack.includes(q)) return false;
        }
        return true;
    });
}

const byDeadline = (a, b) => parseDate(a.deadline) - parseDate(b.deadline) || (PRIORITY_RANK[a.priority] ?? 3) - (PRIORITY_RANK[b.priority] ?? 3);
const byPriority = (a, b) => (PRIORITY_RANK[a.priority] ?? 3) - (PRIORITY_RANK[b.priority] ?? 3) || parseDate(b.created_at) - parseDate(a.created_at);
const byCompleted = (a, b) => parseDate(b.completed_at || b.updated_at || b.created_at) - parseDate(a.completed_at || a.updated_at || a.created_at);

export function groupTasks(tasks, now = new Date()) {
    const today = startOfDay(now);
    const tomorrow = addDays(today, 1);
    const groups = {
        overdue: { title: 'Просрочено', items: [] },
        today: { title: 'Сегодня', items: [] },
        tomorrow: { title: 'Завтра', items: [] },
        later: { title: 'Позже', items: [] },
        nodate: { title: 'Без срока', items: [] },
        done: { title: 'Выполнено', items: [] },
    };
    for (const t of tasks) {
        if (t.status !== 'pending') {
            groups.done.items.push(t);
            continue;
        }
        const d = parseDate(t.deadline);
        if (!d) groups.nodate.items.push(t);
        else if (d < now) groups.overdue.items.push(t);
        else if (isSameDay(d, today)) groups.today.items.push(t);
        else if (isSameDay(d, tomorrow)) groups.tomorrow.items.push(t);
        else groups.later.items.push(t);
    }
    ['overdue', 'today', 'tomorrow', 'later'].forEach((k) => groups[k].items.sort(byDeadline));
    groups.nodate.items.sort(byPriority);
    groups.done.items.sort(byCompleted);
    return groups;
}

function deadlineBadge(task, now, dayContext) {
    let d = parseDate(task.deadline);
    if (!d) return '';
    // В выбранном дне календаря повторяющаяся задача показывается со временем этого дня
    if (dayContext && !isSameDay(d, dayContext)) {
        d = new Date(dayContext.getFullYear(), dayContext.getMonth(), dayContext.getDate(), d.getHours(), d.getMinutes());
    }
    const pending = task.status === 'pending';
    const late = pending && d < now;
    const soon = pending && !late && d - now < 2 * 3600 * 1000;
    const cls = late ? 'late' : soon ? 'soon' : '';
    const icon = late ? 'fa-solid fa-fire' : 'fa-regular fa-clock';
    const label = dayContext ? formatTime(d) : formatDeadline(d, now);
    return `<span class="${cls}"><i class="${icon}"></i>${escapeHtml(label)}</span>`;
}

export function taskCardHtml(task, { now = new Date(), dayContext = null } = {}) {
    const me = state.profile?.id;
    const done = task.status !== 'pending';
    const prio = task.priority ? `prio-${task.priority}` : '';
    const subDone = task.subtasks.filter((s) => s.is_done).length;
    const isNew = !renderedIds.has(task.id);
    renderedIds.add(task.id);

    const meta = [
        deadlineBadge(task, now, dayContext),
        task.repeat_rule ? '<span><i class="fa-solid fa-rotate"></i></span>' : '',
        task.visibility === 'common'
            ? '<span><i class="fa-solid fa-users"></i>Семья</span>'
            : '<span><i class="fa-solid fa-lock"></i>Личное</span>',
        task.subtasks.length ? `<span><i class="fa-regular fa-square-check"></i>${subDone}/${task.subtasks.length}</span>` : '',
        task.owner_id !== me ? '<span title="Добавил партнёр"><i class="fa-solid fa-user-group"></i>от партнёра</span>' : '',
        task.description ? '<span><i class="fa-regular fa-note-sticky"></i></span>' : '',
    ].filter(Boolean).join('');

    return `
        <div class="task-row">
            <div class="swipe-action complete"><i class="fa-solid fa-check"></i>${done ? 'Вернуть' : 'Выполнить'}</div>
            <div class="swipe-action delete">Удалить<i class="fa-solid fa-trash"></i></div>
            <div class="task-card ${prio} ${done ? 'is-done' : ''} ${isNew ? 'enter' : ''}" data-id="${task.id}" role="button" tabindex="0">
                <button class="check ${done ? 'checked' : ''} ${prio}" data-action="toggle" aria-label="${done ? 'Вернуть в работу' : 'Выполнить'}">
                    <i class="fa-solid fa-check"></i>
                </button>
                <div class="task-main">
                    <div class="task-title">${escapeHtml(task.title)}</div>
                    <div class="task-meta">${meta}</div>
                </div>
                ${task.priority && !done ? `<span class="prio-mark ${prio}">${PRIORITY_MARK[task.priority]}</span>` : ''}
            </div>
        </div>`;
}

function emptyHtml({ icon, title, text, action }) {
    return `
        <div class="empty">
            <i class="${icon}"></i>
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(text)}</p>
            ${action ? `<button class="btn btn-tinted btn-inline" data-action="${action.id}">${escapeHtml(action.label)}</button>` : ''}
        </div>`;
}

export function renderSkeleton(container) {
    container.innerHTML = '<div class="skeleton"></div>'.repeat(5);
}

export function renderError(container, error) {
    container.innerHTML = emptyHtml({
        icon: 'fa-solid fa-plug-circle-xmark',
        title: 'Не удалось загрузить задачи',
        text: error?.message || 'Проверьте соединение',
        action: { id: 'retry', label: 'Повторить' },
    });
}

export function renderList(container) {
    const now = new Date();
    const filtered = filterTasks(state.tasks);

    // Выбран день в календаре: плоский список задач этого дня
    if (state.view === 'calendar' && state.selectedDay) {
        const day = fromDayKey(state.selectedDay);
        const items = filtered.filter((t) => occursOn(t, day)).sort((a, b) => (a.status !== 'pending') - (b.status !== 'pending') || byDeadline(a, b));
        if (!items.length) {
            container.innerHTML = emptyHtml({
                icon: 'fa-regular fa-calendar-check',
                title: `${relativeDayLabel(day, now)} — свободно`,
                text: 'На этот день задач нет.',
                action: { id: 'create', label: 'Добавить задачу' },
            });
            return;
        }
        container.innerHTML = `<div class="group-items">${items.map((t) => taskCardHtml(t, { now, dayContext: day })).join('')}</div>`;
        return;
    }

    if (!filtered.length) {
        const searching = state.search.trim();
        container.innerHTML = searching
            ? emptyHtml({ icon: 'fa-solid fa-magnifying-glass', title: 'Ничего не найдено', text: `По запросу «${searching}» задач нет.` })
            : state.tasks.length
                ? emptyHtml({ icon: 'fa-solid fa-filter', title: 'Здесь пусто', text: 'В этом фильтре задач нет.', action: { id: 'reset-filter', label: 'Показать все' } })
                : emptyHtml({ icon: 'fa-solid fa-mug-hot', title: 'Задач пока нет', text: 'Добавьте первую задачу — кнопкой «+» или сообщением боту.', action: { id: 'create', label: 'Создать задачу' } });
        return;
    }

    const groups = groupTasks(filtered, now);
    const pendingCount = filtered.length - groups.done.items.length;
    const html = [];
    for (const [key, group] of Object.entries(groups)) {
        if (!group.items.length) continue;
        const isDone = key === 'done';
        const collapsed = isDone && !state.showDone && !state.search;
        const toggle = isDone && !state.search
            ? `<button data-action="toggle-done">${collapsed ? `Показать (${group.items.length})` : 'Скрыть'}</button>`
            : `<span>${group.items.length}</span>`;
        html.push(`
            <section class="group">
                <div class="group-header ${key === 'overdue' ? 'overdue' : ''}"><span>${group.title}</span>${toggle}</div>
                ${collapsed ? '' : `<div class="group-items">${group.items.slice(0, isDone ? 50 : undefined).map((t) => taskCardHtml(t, { now })).join('')}</div>`}
            </section>`);
    }
    if (!pendingCount) {
        html.unshift(emptyHtml({ icon: 'fa-solid fa-champagne-glasses', title: 'Всё сделано!', text: 'Невыполненных задач нет.' }));
    }
    container.innerHTML = html.join('');
}

export function subtitleText() {
    const pending = state.tasks.filter((t) => t.status === 'pending');
    const now = new Date();
    const overdue = pending.filter((t) => t.deadline && parseDate(t.deadline) < now).length;
    const today = pending.filter((t) => {
        const d = parseDate(t.deadline);
        return d && d >= now && isSameDay(d, now);
    }).length;
    if (!pending.length) return state.loaded ? 'Все задачи выполнены' : '';
    const parts = [`${pending.length} ${pluralize(pending.length, 'задача', 'задачи', 'задач')} в работе`];
    if (today) parts.push(`${today} на сегодня`);
    if (overdue) parts.push(`${overdue} просрочено`);
    return parts.join(' · ');
}
