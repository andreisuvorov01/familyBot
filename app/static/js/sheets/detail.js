// Карточка задачи: описание, подзадачи, выполнение, редактирование, удаление.
import { formatSmart, parseDate, relativeDayLabel } from '../dates.js';
import { addSubtask, deleteSubtask, deleteTaskWithUndo, getTask, state, subscribe, toggleDone, toggleSubtask } from '../store.js';
import { haptic, showConfirm } from '../tg.js';
import { $, escapeHtml } from '../ui/dom.js';
import { closeSheet, isOpen, openSheet } from '../ui/sheets.js';
import { toastError } from '../ui/toast.js';
import { openEditor } from './editor.js';

const PRIORITY = { high: ['Высокий', '!!!'], medium: ['Средний', '!!'], low: ['Низкий', '!'] };
const REPEAT = { daily: 'Каждый день', weekly: 'Каждую неделю', monthly: 'Каждый месяц' };

let currentId = null;
let initialized = false;

function render() {
    const task = getTask(currentId);
    if (!task) {
        // Задачу удалили (в т.ч. партнёр) — закрываем карточку
        if (isOpen('sheet-detail')) closeSheet('sheet-detail');
        return;
    }
    const done = task.status !== 'pending';
    const now = new Date();

    const title = $('#detail-title');
    title.textContent = task.title;
    title.classList.toggle('done', done);

    const chips = [];
    const deadline = parseDate(task.deadline);
    if (deadline) {
        const late = !done && deadline < now;
        chips.push(`<span class="meta-chip ${late ? 'late' : ''}"><i class="fa-regular fa-clock"></i>${escapeHtml(formatSmart(deadline))}</span>`);
    }
    if (task.repeat_rule) chips.push(`<span class="meta-chip"><i class="fa-solid fa-rotate"></i>${REPEAT[task.repeat_rule]}</span>`);
    if (task.priority) chips.push(`<span class="meta-chip prio-${task.priority}">${PRIORITY[task.priority][1]} ${PRIORITY[task.priority][0]}</span>`);
    chips.push(task.visibility === 'common'
        ? '<span class="meta-chip"><i class="fa-solid fa-users"></i>Семья</span>'
        : '<span class="meta-chip"><i class="fa-solid fa-lock"></i>Личное</span>');
    if (done && task.completed_at) {
        const who = task.completed_by_id === state.profile?.id ? 'вами' : 'партнёром';
        chips.push(`<span class="meta-chip done"><i class="fa-solid fa-check"></i>Выполнено ${who}, ${escapeHtml(relativeDayLabel(parseDate(task.completed_at), now).toLowerCase())}</span>`);
    }
    $('#detail-meta').innerHTML = chips.join('');

    const desc = $('#detail-desc');
    desc.textContent = task.description?.trim() || 'Нет заметок';
    desc.classList.toggle('empty-text', !task.description?.trim());

    renderSubtasks(task);

    const btn = $('#detail-status');
    if (done) {
        btn.className = 'btn btn-tinted';
        btn.innerHTML = '<i class="fa-solid fa-rotate-left"></i> Вернуть в работу';
    } else {
        btn.className = 'btn btn-primary';
        btn.innerHTML = task.repeat_rule
            ? '<i class="fa-solid fa-check"></i> Выполнено, перенести дальше'
            : '<i class="fa-solid fa-check"></i> Выполнено';
    }

    const created = parseDate(task.created_at);
    const author = task.owner_id === state.profile?.id ? 'вами' : 'партнёром';
    $('#detail-footnote').textContent = `Создано ${author} · ${relativeDayLabel(created, now).toLowerCase()}`;
}

function renderSubtasks(task) {
    const total = task.subtasks.length;
    const doneCount = task.subtasks.filter((s) => s.is_done).length;
    $('#subtasks-count').textContent = total ? `${doneCount} из ${total}` : '';
    $('#subtasks-progress').classList.toggle('hidden', !total);
    $('#subtasks-progress div').style.width = total ? `${(doneCount / total) * 100}%` : '0';
    $('#subtasks-list').innerHTML = task.subtasks.map((s) => `
        <div class="subtask ${s.is_done ? 'done' : ''}" data-sub="${s.id}">
            <button class="check ${s.is_done ? 'checked' : ''}" data-sub-action="toggle" aria-label="Отметить"><i class="fa-solid fa-check"></i></button>
            <span>${escapeHtml(s.title)}</span>
            <button class="remove" data-sub-action="delete" aria-label="Удалить пункт"><i class="fa-solid fa-xmark"></i></button>
        </div>`).join('');
}

function init() {
    if (initialized) return;
    initialized = true;
    subscribe(() => {
        if (isOpen('sheet-detail')) render();
    });

    $('#detail-status').addEventListener('click', async () => {
        const task = getTask(currentId);
        if (!task) return;
        const completing = task.status === 'pending';
        const updated = await toggleDone(task.id);
        // Выполненную обычную задачу закрываем, повторяющуюся оставляем (видно новый срок)
        if (updated && completing && !updated.repeat_rule) closeSheet('sheet-detail');
    });
    $('#detail-edit').addEventListener('click', () => {
        const task = getTask(currentId);
        if (task) openEditor({ task });
    });
    $('#detail-delete').addEventListener('click', async () => {
        const task = getTask(currentId);
        if (!task) return;
        haptic.impact('medium');
        const message = task.visibility === 'common'
            ? `Удалить «${task.title}»? Задача исчезнет и у партнёра.`
            : `Удалить «${task.title}»?`;
        if (await showConfirm(message)) {
            closeSheet('sheet-detail');
            deleteTaskWithUndo(task.id);
        }
    });
    $('#subtasks-list').addEventListener('click', (e) => {
        const row = e.target.closest('[data-sub]');
        const action = e.target.closest('[data-sub-action]')?.dataset.subAction;
        if (!row || !action) return;
        const subId = Number(row.dataset.sub);
        const sub = getTask(currentId)?.subtasks.find((s) => s.id === subId);
        if (!sub) return;
        if (action === 'toggle') toggleSubtask(currentId, subId, !sub.is_done);
        if (action === 'delete') deleteSubtask(currentId, subId);
    });
    $('#subtask-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const input = $('#subtask-input');
        const title = input.value.trim();
        if (!title) return;
        input.value = '';
        try {
            await addSubtask(currentId, title);
            haptic.impact();
        } catch (err) {
            input.value = title;
            toastError(err);
        }
    });
}

export function openDetail(taskId) {
    init();
    if (!getTask(taskId)) return false;
    currentId = Number(taskId);
    render();
    $('#subtask-input').value = '';
    openSheet('sheet-detail');
    return true;
}
