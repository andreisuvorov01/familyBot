import { tg } from './tg.js';

const TIMEOUT_MS = 15000;

const STATUS_MESSAGES = {
    401: 'Сессия устарела — откройте приложение заново',
    403: 'Нет доступа',
    404: 'Не найдено — возможно, уже удалено',
    429: 'Слишком много запросов, подождите немного',
    503: 'Функция временно недоступна',
};

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}

async function request(endpoint, { method = 'GET', body } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    let response;
    try {
        response = await fetch(endpoint, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-TG-Data': tg?.initData || '',
            },
            body: body === undefined ? undefined : JSON.stringify(body),
            signal: controller.signal,
        });
    } catch (e) {
        throw new ApiError(e.name === 'AbortError' ? 'Сервер не отвечает' : 'Нет соединения с сервером', 0);
    } finally {
        clearTimeout(timer);
    }

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data.detail === 'string' && !/^[A-Z]/.test(data.detail) ? data.detail : null;
        throw new ApiError(detail || STATUS_MESSAGES[response.status] || `Ошибка сервера (${response.status})`, response.status);
    }
    return response.json();
}

export const api = {
    // Задачи
    getTasks: () => request('/api/tasks/'),
    getTask: (id) => request(`/api/tasks/${id}`),
    createTask: (data) => request('/api/tasks/', { method: 'POST', body: data }),
    updateTask: (id, data) => request(`/api/tasks/${id}`, { method: 'PATCH', body: data }),
    deleteTask: (id) => request(`/api/tasks/${id}`, { method: 'DELETE' }),
    getStats: () => request('/api/tasks/stats'),

    // Подзадачи
    addSubtask: (taskId, title) => request(`/api/tasks/${taskId}/subtasks`, { method: 'POST', body: { title } }),
    toggleSubtask: (id, isDone) => request(`/api/tasks/subtasks/${id}`, { method: 'PATCH', body: { is_done: isDone } }),
    deleteSubtask: (id) => request(`/api/tasks/subtasks/${id}`, { method: 'DELETE' }),

    // Профиль
    getProfile: () => request('/api/tasks/profile'),
    updateProfile: (data) => request('/api/tasks/profile', { method: 'PATCH', body: data }),
    deleteProfile: () => request('/api/tasks/profile', { method: 'DELETE' }),

    // Google Calendar
    googleStatus: () => request('/api/google/status'),
    googleAuthUrl: () => request('/api/google/auth-url', { method: 'POST' }),
    googleResync: () => request('/api/google/resync', { method: 'POST' }),
    googleDisconnect: () => request('/api/google', { method: 'DELETE' }),
};
