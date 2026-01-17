const tg = window.Telegram.WebApp;
tg.expand();

// Состояние приложения
let state = {
    tasks: [],
    filter: 'all', // all | common | personal
    currentTask: null
};

// --- Инициализация ---
async function init() {
    setupTheme();
    setupEventListeners();
    await loadTasks();

    // Авто-обновление каждые 15 секунд (чтобы видеть задачи партнера)
    setInterval(loadTasks, 15000);
}

function setupTheme() {
    document.body.style.backgroundColor = tg.themeParams.secondary_bg_color;
    // Аватарка
    const user = tg.initDataUnsafe?.user;
    if (user) {
        document.getElementById('avatar-letter').innerText = user.first_name[0];
    }
}

// --- Логика Задач ---

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

    // Фильтрация
    const filtered = state.tasks.filter(t => {
        if (state.filter === 'all') return true;
        if (state.filter === 'common') return t.visibility === 'common';
        return t.visibility !== 'common'; // personal
    });

    if (filtered.length === 0) {
        list.innerHTML = `
            <div class="flex flex-col items-center justify-center pt-20 opacity-40 fade-in">
                <i class="fa-solid fa-clipboard-check text-5xl mb-4"></i>
                <p>Задач нет. Можно отдыхать!</p>
            </div>`;
        return;
    }

    filtered.forEach(task => {
        const isDone = task.status === 'done';
        const isCommon = task.visibility === 'common';

        const el = document.createElement('div');
        el.className = `bg-[var(--tg-theme-bg-color)] p-4 rounded-2xl mb-3 shadow-sm flex items-center gap-3 active:scale-95 transition fade-in border border-transparent ${isDone ? 'opacity-50' : ''}`;
        if(isCommon) el.classList.add('border-l-4', 'border-l-blue-400'); // Метка общих

        el.innerHTML = `
            <div class="w-6 h-6 rounded-full border-2 ${isDone ? 'bg-green-500 border-green-500' : 'border-gray-300'} grid place-content-center">
                ${isDone ? '<i class="fa-solid fa-check text-white text-xs"></i>' : ''}
            </div>
            <div class="flex-1 min-w-0">
                <h3 class="font-medium truncate ${isDone ? 'line-through' : ''}">${task.title}</h3>
                <div class="flex items-center gap-2 text-xs opacity-60">
                    ${isCommon ? '<i class="fa-solid fa-users"></i> Семья' : '<i class="fa-solid fa-lock"></i> Личное'}
                    <span>• ${task.subtasks.filter(s => s.is_done).length}/${task.subtasks.length}</span>
                </div>
            </div>
            <i class="fa-solid fa-chevron-right opacity-20 text-sm"></i>
        `;

        el.onclick = () => openDetail(task);
        list.appendChild(el);
    });
}

// --- Создание Задачи ---

function openCreateModal() {
    tg.HapticFeedback.impactOccurred('light');
    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');

    tg.MainButton.setText("СОЗДАТЬ");
    tg.MainButton.show();
    tg.MainButton.onClick(submitCreate);
}

async function submitCreate() {
    const title = document.getElementById('new-title').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;

    if(!title) {
        tg.HapticFeedback.notificationOccurred('error');
        return;
    }

    tg.MainButton.showProgress();
    try {
        await api.createTask({ title, visibility });
        tg.HapticFeedback.notificationOccurred('success');
        closeModals();
        document.getElementById('new-title').value = '';
        loadTasks();
    } finally {
        tg.MainButton.hideProgress();
    }
}

// --- Детали и Подзадачи ---

function openDetail(task) {
    state.currentTask = task;
    const isDone = task.status === 'done';

    document.getElementById('detail-title').innerText = task.title;
    document.getElementById('detail-title').className = `text-xl font-bold ${isDone ? 'line-through opacity-50' : ''}`;

    // Кнопка статуса
    const btn = document.getElementById('btn-status');
    btn.innerHTML = isDone ? '<i class="fa-solid fa-rotate-left"></i> Вернуть' : '<i class="fa-solid fa-check"></i> Завершить';
    btn.className = `flex-1 py-3 rounded-xl font-semibold transition ${isDone ? 'bg-gray-200 text-gray-800' : 'bg-green-500 text-white'}`;
    btn.onclick = () => toggleTaskStatus(task);

    renderSubtasks(task.subtasks);

    document.getElementById('detail-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    tg.BackButton.show();
}

function renderSubtasks(subtasks) {
    const list = document.getElementById('subtasks-list');
    list.innerHTML = '';

    subtasks.forEach(sub => {
        const el = document.createElement('div');
        el.className = 'flex items-center gap-3 py-2 border-b border-gray-100 last:border-0';
        el.innerHTML = `
            <input type="checkbox" class="custom-checkbox shrink-0" ${sub.is_done ? 'checked' : ''}>
            <span class="text-sm flex-1 ${sub.is_done ? 'line-through opacity-50' : ''}">${sub.title}</span>
        `;
        // Обработчик чекбокса
        el.querySelector('input').onchange = (e) => {
            tg.HapticFeedback.selectionChanged();
            api.toggleSubtask(sub.id, e.target.checked);
            // Оптимистичное обновление
            sub.is_done = e.target.checked;
            renderSubtasks(subtasks); // перерисовка стилей
        };
        list.appendChild(el);
    });
}

async function addSubtask() {
    const input = document.getElementById('new-subtask');
    if(!input.value) return;

    const sub = await api.addSubtask(state.currentTask.id, input.value);
    state.currentTask.subtasks.push(sub);
    input.value = '';
    renderSubtasks(state.currentTask.subtasks);
}

async function toggleTaskStatus(task) {
    const newStatus = task.status === 'done' ? 'pending' : 'done';
    tg.HapticFeedback.notificationOccurred('success');
    await api.toggleTaskStatus(task.id, newStatus);
    closeModals();
    loadTasks();
}

async function deleteTask() {
    tg.showConfirm("Удалить задачу навсегда?", async (ok) => {
        if(ok) {
            await api.deleteTask(state.currentTask.id);
            closeModals();
            loadTasks();
        }
    });
}

// --- Utils ---

function setFilter(type) {
    state.filter = type;
    tg.HapticFeedback.selectionChanged();

    // UI Табов
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if(btn.dataset.filter === type) {
            btn.classList.add('bg-[var(--tg-theme-button-color)]', 'text-white', 'shadow-md');
            btn.classList.remove('opacity-60');
        } else {
            btn.classList.remove('bg-[var(--tg-theme-button-color)]', 'text-white', 'shadow-md');
            btn.classList.add('opacity-60');
        }
    });
    renderList();
}

function closeModals() {
    document.querySelectorAll('.bottom-sheet').forEach(el => el.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
    tg.MainButton.hide();
    tg.BackButton.hide();
}

function setupEventListeners() {
    // Табы
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.onclick = () => setFilter(btn.dataset.filter);
    });

    // Закрытие по клику на фон
    document.getElementById('overlay').onclick = closeModals;

    // Кнопка назад (Telegram)
    tg.BackButton.onClick(closeModals);

    // Enter в подзадачах
    document.getElementById('new-subtask').onkeypress = (e) => {
        if(e.key === 'Enter') addSubtask();
    };
}

// Старт
init();
