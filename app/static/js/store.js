// Состояние приложения и действия с задачами (оптимистичные обновления + откат при ошибке).
import { api } from './api.js';
import { haptic, storage } from './tg.js';
import { toast, toastError } from './ui/toast.js';

const listeners = new Set();

export const state = {
    tasks: [],
    profile: null,
    loaded: false,
    loadError: null,
    view: 'list', // list | calendar | stats
    filter: 'all', // all | mine | common | private
    search: '',
    calendarMode: 'month', // month | week
    calendarCursor: new Date(),
    selectedDay: null, // 'YYYY-MM-DD'
    showDone: false,
};

let lastSnapshot = '';
const pendingDeletes = new Map(); // id -> { timer, task }

export function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
}

export function emit() {
    listeners.forEach((fn) => fn(state));
}

export function setState(patch) {
    Object.assign(state, patch);
    emit();
}

export const getTask = (id) => state.tasks.find((t) => t.id === Number(id)) || null;

function replaceTask(task) {
    const index = state.tasks.findIndex((t) => t.id === task.id);
    if (index === -1) state.tasks.unshift(task);
    else state.tasks[index] = task;
}

// --- Загрузка ---

export async function loadTasks({ silent = false } = {}) {
    try {
        const tasks = await api.getTasks();
        const visible = tasks.filter((t) => !pendingDeletes.has(t.id));
        const snapshot = JSON.stringify(visible);
        const changed = snapshot !== lastSnapshot;
        lastSnapshot = snapshot;
        state.tasks = visible;
        state.loaded = true;
        state.loadError = null;
        if (changed || !silent) emit();
    } catch (e) {
        if (!state.loaded) {
            state.loadError = e;
            emit();
        } else if (!silent) {
            toastError(e);
        }
    }
}

export async function loadProfile() {
    state.profile = await api.getProfile();
    return state.profile;
}

export async function saveProfile(patch) {
    const prev = { ...state.profile };
    Object.assign(state.profile, patch);
    emit();
    try {
        state.profile = await api.updateProfile(patch);
        haptic.success();
        emit();
        return state.profile;
    } catch (e) {
        state.profile = prev;
        haptic.error();
        toastError(e);
        emit();
        throw e;
    }
}

// --- Настройки интерфейса (CloudStorage) ---

const PREF_KEYS = ['view', 'filter', 'calendarMode', 'showDone'];

export async function restorePrefs() {
    const raw = await storage.get('ui_prefs');
    if (!raw) return;
    try {
        const prefs = JSON.parse(raw);
        PREF_KEYS.forEach((k) => {
            if (k in prefs) state[k] = prefs[k];
        });
    } catch {
        /* повреждённые настройки игнорируем */
    }
}

export function persistPrefs() {
    const prefs = Object.fromEntries(PREF_KEYS.map((k) => [k, state[k]]));
    storage.set('ui_prefs', JSON.stringify(prefs));
}

// --- Действия ---

export async function createTask(data) {
    const task = await api.createTask(data);
    replaceTask(task);
    emit();
    return task;
}

export async function updateTask(id, patch) {
    const task = await api.updateTask(id, patch);
    replaceTask(task);
    emit();
    return task;
}

export async function toggleDone(id) {
    const task = getTask(id);
    if (!task) return;
    const completing = task.status !== 'done';
    const prev = { ...task };

    // Оптимистично: обычная задача сразу помечается выполненной
    if (completing && !task.repeat_rule) task.status = 'done';
    if (!completing) task.status = 'pending';
    completing ? haptic.success() : haptic.impact();
    emit();

    try {
        const updated = await api.updateTask(id, { status: completing ? 'done' : 'pending' });
        replaceTask(updated);
        emit();
        if (completing) {
            if (updated.repeat_rule) {
                toast('Выполнено — задача перенесена на следующий раз', { type: 'success' });
            } else {
                toast('Задача выполнена', {
                    type: 'success',
                    action: { label: 'Отменить', onClick: () => toggleDone(id) },
                });
            }
        }
        return updated;
    } catch (e) {
        replaceTask(prev);
        emit();
        haptic.error();
        toastError(e);
        return null;
    }
}

const UNDO_MS = 4000;

/** Удаление с возможностью отмены: запрос уходит через 4 секунды (или при сворачивании приложения). */
export function deleteTaskWithUndo(id) {
    const task = getTask(id);
    if (!task) return;
    state.tasks = state.tasks.filter((t) => t.id !== task.id);
    haptic.warning();
    emit();

    const timer = setTimeout(() => commitDelete(task.id), UNDO_MS);
    pendingDeletes.set(task.id, { timer, task });
    toast('Задача удалена', {
        duration: UNDO_MS,
        action: {
            label: 'Отменить',
            onClick: () => {
                const pending = pendingDeletes.get(task.id);
                if (!pending) return;
                clearTimeout(pending.timer);
                pendingDeletes.delete(task.id);
                replaceTask(pending.task);
                emit();
            },
        },
    });
}

async function commitDelete(id) {
    const pending = pendingDeletes.get(id);
    if (!pending) return;
    pendingDeletes.delete(id);
    clearTimeout(pending.timer);
    try {
        await api.deleteTask(id);
    } catch (e) {
        if (e.status !== 404) {
            replaceTask(pending.task);
            emit();
            toastError(e);
        }
    }
}

export function flushPendingDeletes() {
    [...pendingDeletes.keys()].forEach((id) => commitDelete(id));
}

// --- Подзадачи ---

export async function addSubtask(taskId, title) {
    const sub = await api.addSubtask(taskId, title);
    getTask(taskId)?.subtasks.push(sub);
    emit();
    return sub;
}

export async function toggleSubtask(taskId, subId, isDone) {
    const sub = getTask(taskId)?.subtasks.find((s) => s.id === subId);
    if (!sub) return;
    sub.is_done = isDone;
    haptic.select();
    emit();
    try {
        await api.toggleSubtask(subId, isDone);
    } catch (e) {
        sub.is_done = !isDone;
        emit();
        toastError(e);
    }
}

export async function deleteSubtask(taskId, subId) {
    const task = getTask(taskId);
    if (!task) return;
    const prev = [...task.subtasks];
    task.subtasks = task.subtasks.filter((s) => s.id !== subId);
    emit();
    try {
        await api.deleteSubtask(subId);
    } catch (e) {
        task.subtasks = prev;
        emit();
        toastError(e);
    }
}
