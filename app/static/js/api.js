const API_URL = '/api/tasks';

class ApiClient {
    constructor() {
        this.tg = window.Telegram.WebApp;
    }

    get headers() {
        return {
            'Content-Type': 'application/json',
            'X-TG-Data': this.tg.initData
        };
    }

    async getTasks() {
        const res = await fetch(`${API_URL}/`, { headers: this.headers });
        if (!res.ok) throw new Error('Failed to fetch');
        return await res.json();
    }

    async createTask(data) {
        const res = await fetch(`${API_URL}/`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(data)
        });
        return await res.json();
    }

    async toggleTaskStatus(id, newStatus) {
        await fetch(`${API_URL}/${id}`, {
            method: 'PATCH',
            headers: this.headers,
            body: JSON.stringify({ status: newStatus })
        });
    }

    async deleteTask(id) {
        await fetch(`${API_URL}/${id}`, {
            method: 'DELETE',
            headers: this.headers
        });
    }
    async updateTask(id, data) {
            await fetch(`${API_URL}/${id}`, {
                method: 'PATCH',
                headers: this.headers,
                body: JSON.stringify(data)
            });
        }
    async addSubtask(taskId, title) {
        const res = await fetch(`${API_URL}/${taskId}/subtasks`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ title })
        });
        return await res.json();
    }

    async toggleSubtask(subId, isDone) {
        await fetch(`${API_URL}/subtasks/${subId}?is_done=${isDone}`, {
            method: 'PATCH',
            headers: this.headers
        });
    }
}

const api = new ApiClient();
