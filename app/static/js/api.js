const API_BASE = window.location.origin;

class TaskAPI {
    constructor() {
        this.initData = window.Telegram.WebApp.initData;
    }

    async request(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        
        const headers = {
            'Content-Type': 'application/json',
            'X-TG-Data': this.initData,
            ...options.headers
        };

        const config = {
            ...options,
            headers
        };

        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(
                    errorData.detail || `HTTP error ${response.status}`
                );
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // Tasks
    async getTasks() {
        return this.request('/api/tasks');
    }

    async createTask(taskData) {
        return this.request('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
    }

    async updateTask(taskId, updates) {
        return this.request(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            body: JSON.stringify(updates)
        });
    }

    async deleteTask(taskId) {
        return this.request(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
    }

    async toggleTaskStatus(taskId, status) {
        return this.updateTask(taskId, { status });
    }

    // Subtasks
    async addSubtask(taskId, title) {
        return this.request(`/api/tasks/${taskId}/subtasks`, {
            method: 'POST',
            body: JSON.stringify({ title })
        });
    }

    async toggleSubtask(subtaskId, isDone) {
        return this.request(`/api/tasks/subtasks/${subtaskId}`, {
            method: 'PATCH',
            body: JSON.stringify({ is_done: isDone })
        });
    }

    // Health check
    async healthCheck() {
        try {
            const response = await fetch(`${API_BASE}/health`);
            return response.ok;
        } catch {
            return false;
        }
    }

    // API info
    async getApiInfo() {
        return this.request('/api/info');
    }
}

// Экспортируем глобальный экземпляр API
window.api = new TaskAPI();