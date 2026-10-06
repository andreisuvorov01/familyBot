import { api } from './api.js';
import { defaultTimeFor, fromDayKey } from './dates.js';
import { openDetail } from './sheets/detail.js';
import { openEditor } from './sheets/editor.js';
import { deviceTimezone, openSettings, syncSettingsView } from './sheets/settings.js';
import {
    deleteTaskWithUndo, flushPendingDeletes, getTask, loadProfile, loadTasks, persistPrefs,
    restorePrefs, saveProfile, setState, state, subscribe, toggleDone,
} from './store.js';
import { currentUser, haptic, inTelegram, onAppActivated, setupTelegram, startParam } from './tg.js';
import { $, $$, escapeHtml } from './ui/dom.js';
import { closeAll, initSheets, openSheet } from './ui/sheets.js';
import { attachSwipe } from './ui/swipe.js';
import { toast, toastError } from './ui/toast.js';
import { renderCalendar, shiftCursor } from './views/calendar.js';
import { renderError, renderList, renderSkeleton, subtitleText } from './views/list.js';
import { renderStats, renderStatsSkeleton } from './views/stats.js';

const REFRESH_MS = 60000;

// ---------- Рендер ----------

function renderChips() {
    const me = state.profile?.id;
    const pending = state.tasks.filter((t) => t.status === 'pending');
    const counts = {
        all: pending.length,
        mine: pending.filter((t) => t.owner_id === me).length,
        common: pending.filter((t) => t.visibility === 'common').length,
        private: pending.filter((t) => t.visibility !== 'common').length,
    };
    const labels = { all: 'Все', mine: 'Мои', common: 'Общие', private: 'Личные' };
    $$('#filter-chips .chip').forEach((chip) => {
        const key = chip.dataset.filter;
        chip.classList.toggle('active', key === state.filter);
        chip.innerHTML = `${labels[key]}${state.loaded && counts[key] ? `<span class="count">${counts[key]}</span>` : ''}`;
    });
}

function render() {
    $('#page-subtitle').textContent = subtitleText();
    $$('#view-switch button').forEach((b) => b.classList.toggle('active', b.dataset.view === state.view));

    const isStats = state.view === 'stats';
    $('#view-tasks').classList.toggle('hidden', isStats);
    $('#view-stats').classList.toggle('hidden', !isStats);
    $('#fab').classList.toggle('hidden', isStats);
    if (isStats) {
        scheduleStatsRefresh();
        return;
    }

    if (state.view === 'calendar') renderCalendar($('#calendar-host'));
    else $('#calendar-host').innerHTML = '';

    renderChips();
    const list = $('#task-list');
    if (state.loadError && !state.loaded) renderError(list, state.loadError);
    else if (state.loaded) renderList(list);
    syncSettingsView();
}

let statsTimer = null;
function scheduleStatsRefresh() {
    clearTimeout(statsTimer);
    statsTimer = setTimeout(async () => {
        const host = $('#view-stats');
        if (!host.dataset.loaded) renderStatsSkeleton(host);
        try {
            renderStats(host, await api.getStats());
            host.dataset.loaded = '1';
        } catch (e) {
            if (!host.dataset.loaded) host.innerHTML = `<div class="empty"><i class="fa-solid fa-chart-simple"></i><h3>Статистика недоступна</h3><p>${escapeHtml(e.message)}</p></div>`;
        }
    }, 150);
}

// ---------- События ----------

function setView(view) {
    if (view === state.view) return;
    haptic.select();
    setState({ view, selectedDay: view === 'calendar' ? state.selectedDay : null });
    persistPrefs();
    window.scrollTo({ top: 0 });
}

function bindEvents() {
    $('#view-switch').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-view]');
        if (btn) setView(btn.dataset.view);
    });

    $('#filter-chips').addEventListener('click', (e) => {
        const chip = e.target.closest('[data-filter]');
        if (!chip) return;
        haptic.select();
        setState({ filter: chip.dataset.filter });
        persistPrefs();
    });

    let searchTimer = null;
    $('#search').addEventListener('input', (e) => {
        $('#search-clear').classList.toggle('hidden', !e.target.value);
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => setState({ search: e.target.value }), 120);
    });
    $('#search-clear').addEventListener('click', () => {
        $('#search').value = '';
        $('#search-clear').classList.add('hidden');
        setState({ search: '' });
    });

    const list = $('#task-list');
    list.addEventListener('click', (e) => {
        const action = e.target.closest('[data-action]')?.dataset.action;
        const card = e.target.closest('.task-card');
        if (action === 'toggle' && card) {
            e.stopPropagation();
            e.target.closest('.check').classList.add('pop');
            toggleDone(Number(card.dataset.id));
            return;
        }
        if (action === 'retry') return void loadTasks();
        if (action === 'create') return void createFromContext();
        if (action === 'reset-filter') return void setState({ filter: 'all' });
        if (action === 'toggle-done') {
            setState({ showDone: !state.showDone });
            persistPrefs();
            return;
        }
        if (card && !card.dataset.swiped) {
            haptic.impact();
            openDetail(Number(card.dataset.id));
        }
    });
    list.addEventListener('keydown', (e) => {
        const card = e.target.closest('.task-card');
        if (card && e.key === 'Enter') openDetail(Number(card.dataset.id));
    });
    attachSwipe(list, {
        onSwipeRight: (id) => toggleDone(id),
        onSwipeLeft: (id) => deleteTaskWithUndo(id),
    });

    $('#calendar-host').addEventListener('click', (e) => {
        const nav = e.target.closest('[data-cal]')?.dataset.cal;
        const mode = e.target.closest('[data-cal-mode]')?.dataset.calMode;
        const day = e.target.closest('[data-day]')?.dataset.day;
        if (nav === 'prev' || nav === 'next') setState({ calendarCursor: shiftCursor(nav === 'prev' ? -1 : 1) });
        else if (nav === 'today') setState({ calendarCursor: new Date() });
        else if (nav === 'clear') setState({ selectedDay: null });
        else if (mode) {
            setState({ calendarMode: mode, calendarCursor: state.selectedDay ? fromDayKey(state.selectedDay) : new Date() });
            persistPrefs();
        } else if (day) {
            haptic.select();
            setState({ selectedDay: state.selectedDay === day ? null : day });
        }
    });

    $('#fab').addEventListener('click', () => {
        haptic.impact('medium');
        createFromContext();
    });
    $('#btn-help').addEventListener('click', () => openSheet('sheet-help'));
    $('#btn-avatar').addEventListener('click', openSettings);

    // Обновление данных: при возврате в приложение и периодически, пока оно открыто
    onAppActivated(() => loadTasks({ silent: true }));
    setInterval(() => {
        if (document.visibilityState === 'visible') loadTasks({ silent: true });
    }, REFRESH_MS);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') flushPendingDeletes();
    });
    window.addEventListener('pagehide', flushPendingDeletes);
}

function createFromContext() {
    const presetDate = state.view === 'calendar' && state.selectedDay ? defaultTimeFor(fromDayKey(state.selectedDay)) : null;
    openEditor({ presetDate });
}

// ---------- Старт ----------

function renderAvatar() {
    const user = currentUser();
    if (!user) return;
    const avatar = $('#btn-avatar');
    if (user.photo_url) {
        const img = document.createElement('img');
        img.src = user.photo_url;
        img.alt = '';
        img.onerror = () => img.remove();
        avatar.replaceChildren(img);
    } else {
        $('#avatar-letter').textContent = (user.first_name || 'U')[0].toUpperCase();
    }
}

function renderStandalone(title, text) {
    document.body.innerHTML = `
        <div class="standalone">
            <div class="empty">
                <i class="fa-brands fa-telegram"></i>
                <h3>${escapeHtml(title)}</h3>
                <p>${escapeHtml(text)}</p>
            </div>
        </div>`;
}

async function syncTimezone() {
    const device = deviceTimezone();
    if (device && state.profile && state.profile.timezone !== device) {
        try {
            await saveProfile({ timezone: device });
        } catch {
            /* неизвестный серверу пояс — оставляем как есть */
        }
    }
}

function handleDeepLink() {
    const param = startParam();
    if (!param) return;
    if (param === 'new') {
        openEditor();
        return;
    }
    const match = /^task_(\d+)$/.exec(param);
    if (match) {
        const id = Number(match[1]);
        if (getTask(id)) openDetail(id);
        else toast('Задача не найдена — возможно, её уже удалили', { type: 'error' });
    }
}

async function init() {
    if (!inTelegram) {
        renderStandalone('Откройте через Telegram', 'Mini App работает внутри Telegram: нажмите «Открыть Mini App» в чате с ботом.');
        return;
    }

    setupTelegram({ onSettings: openSettings });
    initSheets();
    renderAvatar();
    renderSkeleton($('#task-list'));
    await restorePrefs();
    bindEvents();
    subscribe(render);
    render();

    try {
        await loadProfile();
    } catch (e) {
        if (e.status === 403) {
            renderStandalone('Завершите регистрацию', 'Вернитесь в чат с ботом, выберите роль и создайте семью или введите код партнёра.');
            return;
        }
        toastError(e);
    }
    syncTimezone();

    await loadTasks();
    handleDeepLink();
}

init().catch((e) => {
    console.error(e);
    toastError(e);
    closeAll();
});
