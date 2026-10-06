import { $, escapeHtml } from './dom.js';

const ICONS = { info: 'fa-circle-info', success: 'fa-circle-check', error: 'fa-triangle-exclamation' };

/**
 * Всплывающее сообщение. action: { label, onClick } — например «Отменить».
 * Возвращает функцию, закрывающую тост.
 */
export function toast(message, { type = 'info', action = null, duration = 3000 } = {}) {
    const host = $('#toast-host');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.innerHTML = `<i class="fa-solid ${ICONS[type] || ICONS.info}"></i><span class="msg">${escapeHtml(message)}</span>`;

    let closed = false;
    const close = () => {
        if (closed) return;
        closed = true;
        el.classList.add('leaving');
        setTimeout(() => el.remove(), 200);
    };

    if (action) {
        const btn = document.createElement('button');
        btn.className = 'action';
        btn.textContent = action.label;
        btn.onclick = () => {
            action.onClick();
            close();
        };
        el.appendChild(btn);
    }

    // Не больше двух тостов одновременно
    while (host.children.length >= 2) host.firstElementChild.remove();
    host.appendChild(el);
    setTimeout(close, duration);
    return close;
}

export const toastError = (e) => toast(e?.message || String(e), { type: 'error', duration: 4000 });
