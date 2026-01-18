const tg = window.Telegram.WebApp;
tg.expand();

let state = {
    tasks: [],
    filter: 'all',
    currentTask: null
};

async function init() {
    setupTheme();
    setupEventListeners();
    await loadTasks();
    setInterval(loadTasks, 15000);
}

function setupTheme() {
    document.body.style.backgroundColor = tg.themeParams.secondary_bg_color || '#f3f4f6';
    const user = tg.initDataUnsafe?.user;
    if (user) {
        const avatarEl = document.getElementById('user-avatar');
        if (user.photo_url) {
            avatarEl.innerHTML = `<img src="${user.photo_url}" class="w-full h-full object-cover">`;
            avatarEl.style.background = 'none';
        } else {
            document.getElementById('avatar-letter').innerText = user.first_name ? user.first_name[0] : 'U';
        }
    }
}

async function loadTasks() {
    try {
        state.tasks = await api.getTasks();
        renderList();
    } catch (e) {
        console.error(e);
    }
}

function renderList() {
    const list = document.getElementById('task-list');
    list.innerHTML = '';

    const filtered = state.tasks.filter(t => {
        if (state.filter === 'all') return true;
        if (state.filter === 'common') return t.visibility === 'common';
        return t.visibility !== 'common';
    });

    if (filtered.length === 0) {
        list.innerHTML = `<div class="text-center pt-20 opacity-40"><p>Нет задач</p></div>`;
        return;
    }

    filtered.forEach(task => {
        const isDone = task.status === 'done';
        const isCommon = task.visibility === 'common';

        let timeBadge = '';
        if (task.deadline) {
            const d = new Date(task.deadline);
            const isLate = new Date() > d && !isDone;
            const timeStr = d.toLocaleDateString('ru-RU', {day: 'numeric', month: 'short', hour: '2-digit', minute:'2-digit'});
            const colorClass = isLate ? 'text-red-500 font-bold bg-red-50' : 'text-gray-500 bg-gray-100';
            timeBadge = `<span class="px-2 py-0.5 rounded text-[10px] ${colorClass} mr-2"><i class="fa-regular fa-clock"></i> ${timeStr}</span>`;
        }

        const el = document.createElement('div');
        el.className = `bg-[var(--tg-theme-bg-color)] p-4 rounded-2xl mb-3 shadow-sm flex items-center gap-3 active:scale-[0.98] transition fade-in border-l-4 ${isCommon ? 'border-l-blue-400' : 'border-l-transparent'} ${isDone ? 'opacity-50' : ''}`;

        el.innerHTML = `
            <div class="w-6 h-6 rounded-full border-2 ${isDone ? 'bg-green-500 border-green-500' : 'border-gray-300'} grid place-content-center shrink-0">
                ${isDone ? '<i class="fa-solid fa-check text-white text-[10px]"></i>' : ''}
            </div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center mb-1">
                    ${timeBadge}
                    <h3 class="font-medium truncate text-sm ${isDone ? 'line-through' : ''}">${task.title}</h3>
                </div>
                <div class="flex items-center gap-3 text-[10px] opacity-60">
                    ${isCommon ? '<span><i class="fa-solid fa-users"></i> Семья</span>' : '<span><i class="fa-solid fa-lock"></i> Личное</span>'}
                    ${task.subtasks.length > 0 ? `<span>• ${task.subtasks.filter(s => s.is_done).length}/${task.subtasks.length}</span>` : ''}
                </div>
            </div>
        `;
        el.onclick = () => openDetail(task);
        list.appendChild(el);
    });
}

// --- Detail & Edit ---

function openDetail(task) {
    state.currentTask = task;
    const isDone = task.status === 'done';

    document.getElementById('detail-title').innerText = task.title;
    document.getElementById('detail-title').className = `text-xl font-bold leading-tight mr-2 flex-1 ${isDone ? 'line-through opacity-50' : ''}`;

    // БЕЗОПАСНОЕ ЗАПОЛНЕНИЕ ОПИСАНИЯ
    const descEl = document.getElementById('detail-desc');
    if (descEl) {
        if (task.description && task.description.trim()) {
            descEl.innerText = task.description;
            descEl.classList.remove('opacity-50', 'italic');
        } else {
            descEl.innerText = "Нет описания";
            descEl.classList.add('opacity-50', 'italic');
        }
    }

    const btn = document.getElementById('btn-status');
    if (isDone) {
        btn.innerHTML = 'Вернуть в работу';
        btn.className = 'w-full py-3 rounded-xl font-semibold bg-gray-100 text-gray-800 transition';
    } else {
        btn.innerHTML = 'Завершить';
        btn.className = 'w-full py-3 rounded-xl font-semibold bg-green-500 text-white transition';
    }
    btn.onclick = () => toggleTaskStatus(task);

    renderSubtasks(task.subtasks);

    document.getElementById('detail-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    tg.BackButton.show();
}

function openCreateModal() {
    tg.HapticFeedback.impactOccurred('light');
    document.getElementById('new-title').value = '';
    document.getElementById('new-desc').value = ''; // Очищаем описание
    document.getElementById('new-deadline').value = '';

    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');

    tg.MainButton.setText("СОЗДАТЬ");
    tg.MainButton.show();
    tg.MainButton.offClick(submitUpdate);
    tg.MainButton.onClick(submitCreate);
}

function openEditMode() {
    const task = state.currentTask;
    closeModals();

    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');

    document.getElementById('new-title').value = task.title;
    document.getElementById('new-desc').value = task.description || ''; // Подставляем описание

    if(task.deadline) {
        document.getElementById('new-deadline').value = new Date(task.deadline).toISOString().slice(0, 16);
    } else {
        document.getElementById('new-deadline').value = '';
    }

    const vis = task.visibility === 'common' ? 'common' : 'private';
    document.querySelector(`input[name="visibility"][value="${vis}"]`).checked = true;

    tg.MainButton.setText("СОХРАНИТЬ");
    tg.MainButton.show();
    tg.MainButton.offClick(submitCreate);
    tg.MainButton.onClick(submitUpdate);
}

async function submitCreate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const dateVal = document.getElementById('new-deadline').value;

    if(!title.trim()) return;

    let deadline = null;
    if (dateVal) deadline = new Date(dateVal).toISOString();

    tg.MainButton.showProgress();
    await api.createTask({ title, description: desc, visibility, deadline });
    tg.HapticFeedback.notificationOccurred('success');
    closeModals();
    loadTasks();
    tg.MainButton.hideProgress();
}

async function submitUpdate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const dateVal = document.getElementById('new-deadline').value;

    let deadline = null;
    if (dateVal) deadline = new Date(dateVal).toISOString();

    tg.MainButton.showProgress();
    await api.updateTask(state.currentTask.id, { title, description: desc, visibility, deadline });
    tg.HapticFeedback.notificationOccurred('success');
    closeModals();
    tg.MainButton.offClick(submitUpdate);
    loadTasks();
    tg.MainButton.hideProgress();
}

// ... Остальные функции (toggleTaskStatus, renderSubtasks и т.д.) ...
// Скопируй их из предыдущего ответа, они не менялись,
// но убедись что toggleTaskStatus вызывает loadTasks()
async function toggleTaskStatus(task) {
    const newStatus = task.status === 'done' ? 'pending' : 'done';
    tg.HapticFeedback.notificationOccurred('success');
    closeModals();
    await api.toggleTaskStatus(task.id, newStatus);
    loadTasks();
}

function renderSubtasks(subtasks) {
    const list = document.getElementById('subtasks-list');
    list.innerHTML = '';
    subtasks.forEach(sub => {
        const el = document.createElement('div');
        el.className = 'flex items-center gap-3 py-2';
        el.innerHTML = `
            <input type="checkbox" class="custom-checkbox w-5 h-5 rounded border-gray-300" ${sub.is_done ? 'checked' : ''}>
            <span class="text-sm flex-1 ${sub.is_done ? 'line-through opacity-50' : ''}">${sub.title}</span>
        `;
        el.querySelector('input').onchange = (e) => {
            api.toggleSubtask(sub.id, e.target.checked);
            sub.is_done = e.target.checked;
            renderSubtasks(subtasks);
        };
        list.appendChild(el);
    });
}

async function addSubtask() {
    const input = document.getElementById('new-subtask');
    if(!input.value) return;
    try {
        const sub = await api.addSubtask(state.currentTask.id, input.value);
        state.currentTask.subtasks.push(sub);
        input.value = '';
        renderSubtasks(state.currentTask.subtasks);
    } catch(e) {}
}

async function deleteTask() {
    tg.showConfirm("Удалить?", async (ok) => {
        if(ok) {
            closeModals();
            await api.deleteTask(state.currentTask.id);
            loadTasks();
        }
    });
}

function setFilter(type) {
    state.filter = type;
    tg.HapticFeedback.selectionChanged();
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if(btn.dataset.filter === type) {
            btn.classList.remove('opacity-60');
            btn.classList.add('bg-[var(--tg-theme-button-color)]', 'text-white', 'shadow-md');
        } else {
            btn.classList.add('opacity-60');
            btn.classList.remove('bg-[var(--tg-theme-button-color)]', 'text-white', 'shadow-md');
        }
    });
    renderList();
}

function closeModals() {
    document.querySelectorAll('.bottom-sheet').forEach(el => el.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
    tg.MainButton.hide();
    tg.BackButton.hide();
    tg.MainButton.offClick(submitCreate);
    tg.MainButton.offClick(submitUpdate);
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.onclick = () => setFilter(btn.dataset.filter));
    document.getElementById('overlay').onclick = closeModals;
    tg.BackButton.onClick(closeModals);
    document.getElementById('new-subtask').onkeypress = (e) => { if(e.key === 'Enter') addSubtask(); };
}

init();
