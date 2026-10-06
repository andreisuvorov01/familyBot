// Создание и редактирование задачи.
import { formatSmart, parseDate } from '../dates.js';
import { createTask, getTask, state, updateTask } from '../store.js';
import { haptic, mainButton } from '../tg.js';
import { $, $$ } from '../ui/dom.js';
import { closeSheet, openSheet } from '../ui/sheets.js';
import { toast, toastError } from '../ui/toast.js';
import { pickDate } from './datepicker.js';

const REPEAT_LABELS = { '': 'Нет', daily: 'Каждый день', weekly: 'Каждую неделю', monthly: 'Каждый месяц' };

let editingId = null;
let draft = null; // { visibility, priority, deadline: Date|null, repeat }
let saving = false;
let initialized = false;

function renderDraft() {
    $$('#editor-visibility .choice').forEach((b) => b.classList.toggle('active', b.dataset.visibility === draft.visibility));
    $$('#editor-priority button').forEach((b) => b.classList.toggle('active', b.dataset.prio === (draft.priority || '')));

    const dateValue = $('#editor-date-value');
    dateValue.textContent = draft.deadline ? formatSmart(draft.deadline) : 'Нет';
    dateValue.classList.toggle('set', Boolean(draft.deadline));

    const repeatValue = $('#editor-repeat-value');
    repeatValue.textContent = REPEAT_LABELS[draft.repeat || ''];
    repeatValue.classList.toggle('set', Boolean(draft.repeat));

    const task = editingId ? getTask(editingId) : null;
    const canMakePrivate = !task || task.owner_id === state.profile?.id;
    $('#editor-visibility [data-visibility="private"]').disabled = !canMakePrivate && draft.visibility !== 'private';
    $('#editor-visibility-note').classList.toggle('hidden', canMakePrivate);
}

function init() {
    if (initialized) return;
    initialized = true;

    $('#editor-visibility').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-visibility]');
        if (!btn || btn.disabled) return;
        draft.visibility = btn.dataset.visibility;
        haptic.select();
        renderDraft();
    });
    $('#editor-priority').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-prio]');
        if (!btn) return;
        draft.priority = btn.dataset.prio || null;
        haptic.select();
        renderDraft();
    });
    $('#editor-date-row').addEventListener('click', async () => {
        const value = await pickDate(draft.deadline);
        if (value !== undefined) {
            draft.deadline = value;
            if (!value) draft.repeat = null; // повтор без даты не имеет смысла
            renderDraft();
        }
    });
    $('#editor-repeat-row').addEventListener('click', () => {
        $$('#repeat-options .list-row').forEach((row) => row.classList.toggle('selected', row.dataset.repeat === (draft.repeat || '')));
        openSheet('sheet-repeat');
    });
    $('#repeat-options').addEventListener('click', async (e) => {
        const row = e.target.closest('[data-repeat]');
        if (!row) return;
        draft.repeat = row.dataset.repeat || null;
        haptic.select();
        closeSheet('sheet-repeat');
        if (draft.repeat && !draft.deadline) {
            const value = await pickDate(null);
            if (value) draft.deadline = value;
            else draft.repeat = null;
        }
        renderDraft();
    });
    $('#editor-name').addEventListener('input', () => $('#editor-title-field').classList.remove('invalid'));
    $('#editor-name').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            e.target.blur();
        }
    });
    $('#editor-save').addEventListener('click', save);
}

async function save() {
    if (saving) return;
    const title = $('#editor-name').value.trim();
    if (!title) {
        $('#editor-title-field').classList.add('invalid');
        haptic.error();
        $('#editor-name').focus();
        return;
    }

    const payload = {
        title,
        description: $('#editor-desc').value.trim() || null,
        visibility: draft.visibility,
        priority: draft.priority || null,
        deadline: draft.deadline ? draft.deadline.toISOString() : null,
        repeat_rule: draft.repeat || null,
    };

    saving = true;
    mainButton.progress(true);
    $('#editor-save').disabled = true;
    try {
        if (editingId) {
            await updateTask(editingId, payload);
            toast('Изменения сохранены', { type: 'success' });
        } else {
            await createTask(payload);
            toast(payload.visibility === 'common' ? 'Задача создана — партнёр получит уведомление' : 'Личная задача создана', { type: 'success' });
        }
        haptic.success();
        closeSheet('sheet-editor');
    } catch (e) {
        haptic.error();
        toastError(e);
    } finally {
        saving = false;
        mainButton.progress(false);
        $('#editor-save').disabled = false;
    }
}

/** task — редактирование; иначе создание (presetDate — день, выбранный в календаре). */
export function openEditor({ task = null, presetDate = null } = {}) {
    init();
    editingId = task?.id ?? null;
    draft = task
        ? {
            visibility: task.visibility === 'common' ? 'common' : 'private',
            priority: task.priority,
            deadline: parseDate(task.deadline),
            repeat: task.repeat_rule,
        }
        : { visibility: 'common', priority: null, deadline: presetDate, repeat: null };

    $('#editor-title').textContent = task ? 'Редактирование' : 'Новая задача';
    $('#editor-name').value = task?.title ?? '';
    $('#editor-desc').value = task?.description ?? '';
    $('#editor-title-field').classList.remove('invalid');
    renderDraft();

    const text = task ? 'Сохранить' : 'Создать';
    $('#editor-save').textContent = text;
    openSheet('sheet-editor', {
        mainButton: { text, onClick: save },
        fallbackButton: $('#editor-save'),
    });
    if (!task) setTimeout(() => $('#editor-name').focus(), 350);
}
