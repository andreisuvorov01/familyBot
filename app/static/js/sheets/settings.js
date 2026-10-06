// Настройки профиля и подключение Google Календаря.
import { api } from '../api.js';
import { parseDate, relativeDayLabel, formatTime } from '../dates.js';
import { saveProfile, state } from '../store.js';
import { haptic, onAppActivated, openLink, showConfirm, showPopup, tg } from '../tg.js';
import { $, escapeHtml } from '../ui/dom.js';
import { isOpen, openSheet } from '../ui/sheets.js';
import { toast, toastError } from '../ui/toast.js';

const MODE_LABELS = { command: 'По префиксу', message: 'Любое сообщение' };
const ROLE_LABELS = { husband: 'Муж', wife: 'Жена' };

let google = null;
let initialized = false;
let awaitingGoogle = false;

export const deviceTimezone = () => {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
    } catch {
        return null;
    }
};

function renderProfile() {
    const p = state.profile;
    if (!p) return;
    $('#set-notifications').checked = p.notifications_enabled;
    $('#set-morning').checked = p.morning_summary_enabled;
    $('#set-mode-value').textContent = MODE_LABELS[p.task_creation_mode] || p.task_creation_mode;
    $('#set-tz-value').textContent = p.timezone.replace('_', ' ').split('/').pop();
    $('#set-role-value').textContent = ROLE_LABELS[p.role] || '—';
}

function renderGoogle() {
    const host = $('#google-block');
    if (!google) {
        host.innerHTML = '<div class="skeleton" style="height:48px;margin:0"></div>';
        return;
    }
    if (!google.available) {
        host.innerHTML = `
            <div class="google-card">
                <div class="g-logo"><i class="fa-brands fa-google"></i></div>
                <div class="info"><b>Недоступно</b><small>Интеграция не настроена на сервере</small></div>
            </div>`;
        return;
    }
    if (!google.connected) {
        host.innerHTML = `
            <div class="google-card" style="margin-bottom:12px">
                <div class="g-logo"><i class="fa-brands fa-google"></i></div>
                <div class="info"><b>Не подключён</b><small>Задачи с дедлайном появятся в календаре «FamilyBot»</small></div>
            </div>
            <button class="btn btn-primary" data-google="connect"><i class="fa-brands fa-google"></i> Подключить</button>`;
        return;
    }
    const synced = google.last_synced_at ? parseDate(google.last_synced_at) : null;
    const statusLine = !google.enabled
        ? `<small class="error"><span class="status-dot off"></span>${escapeHtml(google.last_error || 'Требуется повторное подключение')}</small>`
        : `<small><span class="status-dot"></span>${synced ? `Синхронизировано: ${escapeHtml(relativeDayLabel(synced).toLowerCase())}, ${formatTime(synced)}` : 'Синхронизация запущена'}</small>`;
    host.innerHTML = `
        <div class="google-card" style="margin-bottom:12px">
            <div class="g-logo"><i class="fa-brands fa-google"></i></div>
            <div class="info"><b>${escapeHtml(google.email || 'Google Календарь')}</b>${statusLine}</div>
        </div>
        <div class="btn-row">
            ${google.enabled
                ? '<button class="btn btn-tinted" data-google="resync"><i class="fa-solid fa-arrows-rotate"></i> Обновить</button>'
                : '<button class="btn btn-primary" data-google="connect">Подключить заново</button>'}
            <button class="btn btn-danger" data-google="disconnect">Отключить</button>
        </div>`;
}

export async function refreshGoogle() {
    try {
        google = await api.googleStatus();
    } catch {
        google = { available: false, connected: false };
    }
    renderGoogle();
    return google;
}

async function onGoogleAction(action) {
    try {
        if (action === 'connect') {
            const { url } = await api.googleAuthUrl();
            awaitingGoogle = true;
            // Google не разрешает вход внутри WebView — открываем во внешнем браузере
            openLink(url);
            toast('Завершите вход в браузере и вернитесь в Telegram');
        } else if (action === 'resync') {
            const { queued } = await api.googleResync();
            haptic.success();
            toast(`Отправим в календарь задач: ${queued}`, { type: 'success' });
        } else if (action === 'disconnect') {
            if (!(await showConfirm('Отключить Google Календарь? Уже созданные события останутся в календаре «FamilyBot».'))) return;
            await api.googleDisconnect();
            haptic.success();
            toast('Google Календарь отключён');
            await refreshGoogle();
        }
    } catch (e) {
        haptic.error();
        toastError(e);
    }
}

function init() {
    if (initialized) return;
    initialized = true;

    $('#set-notifications').addEventListener('change', (e) => saveProfile({ notifications_enabled: e.target.checked }).catch(renderProfile));
    $('#set-morning').addEventListener('change', (e) => saveProfile({ morning_summary_enabled: e.target.checked }).catch(renderProfile));

    $('#set-mode-row').addEventListener('click', async () => {
        const id = await showPopup({
            title: 'Создание задач в чате',
            message: 'По префиксу — задачей становится сообщение, начинающееся с «л » или «с ». Любое сообщение — каждое сообщение боту.',
            buttons: [
                { id: 'command', type: 'default', text: MODE_LABELS.command },
                { id: 'message', type: 'default', text: MODE_LABELS.message },
                { type: 'cancel' },
            ],
        });
        if (id) await saveProfile({ task_creation_mode: id }).catch(() => {});
        renderProfile();
    });

    $('#set-tz-row').addEventListener('click', async () => {
        const device = deviceTimezone();
        const current = state.profile.timezone;
        const buttons = [];
        if (device && device !== current) buttons.push({ id: 'device', type: 'default', text: `Как на устройстве (${device.split('/').pop().replace('_', ' ')})` });
        if (current !== 'Europe/Moscow') buttons.push({ id: 'moscow', type: 'default', text: 'Москва' });
        buttons.push({ type: 'cancel' });
        const id = await showPopup({
            title: 'Часовой пояс',
            message: `Сейчас: ${current}. От него зависят время утренней сводки и время в уведомлениях бота.`,
            buttons,
        });
        if (id === 'device') await saveProfile({ timezone: device }).catch(() => {});
        if (id === 'moscow') await saveProfile({ timezone: 'Europe/Moscow' }).catch(() => {});
        renderProfile();
    });

    $('#set-role-row').addEventListener('click', async () => {
        const id = await showPopup({
            title: 'Роль в семье',
            message: 'Выберите вашу роль',
            buttons: [
                { id: 'husband', type: 'default', text: 'Муж' },
                { id: 'wife', type: 'default', text: 'Жена' },
                { type: 'cancel' },
            ],
        });
        if (id) await saveProfile({ role: id }).catch(() => {});
        renderProfile();
    });

    $('#set-logout').addEventListener('click', async () => {
        if (!(await showConfirm('Удалить профиль? Ваши задачи будут удалены, а вы выйдете из семьи. Это нельзя отменить.'))) return;
        try {
            await api.deleteProfile();
            haptic.success();
            tg?.close?.();
        } catch (e) {
            toastError(e);
        }
    });

    $('#google-block').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-google]');
        if (btn) onGoogleAction(btn.dataset.google);
    });

    // Вернулись из браузера после входа в Google — обновляем статус
    onAppActivated(async () => {
        if (!awaitingGoogle) return;
        const status = await refreshGoogle();
        if (status.connected && status.enabled) {
            awaitingGoogle = false;
            haptic.success();
            toast('Google Календарь подключён', { type: 'success' });
        }
    });
}

export function openSettings() {
    init();
    renderProfile();
    if (!isOpen('sheet-settings')) {
        google = null;
        renderGoogle();
        refreshGoogle();
    }
    openSheet('sheet-settings');
}

export function syncSettingsView() {
    if (isOpen('sheet-settings')) renderProfile();
}
