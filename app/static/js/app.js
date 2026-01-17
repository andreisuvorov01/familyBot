const tg = window.Telegram.WebApp;
tg.expand();

// Глобальное состояние
let state = {
    tasks: [],
    filter: 'all', // all | common | personal
    currentTask: null
};

// --- Инициализация ---
async function init() {
    setupTheme();
    setupEventListeners();

    // Начальная загрузка
    await loadTasks();

    // Авто-обновление каждые 15 сек (чтобы видеть задачи от партнера)
    setInterval(loadTasks, 15000);
}

function setupTheme() {
    // Красим фон приложения в цвет темы Telegram
    document.body.style.backgroundColor = tg.themeParams.secondary_bg_color || '#f3f4f6';

    // Аватарка (первая буква имени)
    const user = tg.initDataUnsafe?.user;
    if (user) {
        document.getElementById('avatar-letter').innerText = user.first_name ? user.first_name[0] : 'U';
    }
}

// --- Работа с Задачами ---

async function loadTasks() {
    try {
        state.tasks = await api.getTasks();
        renderList();
    } catch (e) {
        console.error("Ошибка загрузки задач:", e);
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

    // Пустой список
    if (filtered.length === 0) {
        list.innerHTML = `
            <div class="flex flex-col items-center justify-center pt-20 opacity-40 fade-in">
                <i class="fa-solid fa-clipboard-check text-5xl mb-4"></i>
                <p>Задач нет. Отдыхаем!</p>
            </div>`;
        return;
    }

    // Рендеринг карточек
    filtered.forEach(task => {
        const isDone = task.status === 'done';
        const isCommon = task.visibility === 'common';

        // Логика Дедлайна
        let timeBadge = '';
        if (task.deadline) {
            const d = new Date(task.deadline);
            const now = new Date();
            const isLate = now > d && !isDone;

            // Формат: "15 янв 14:30"
            const timeStr = d.toLocaleDateString('ru-RU', {
                day: 'numeric', month: 'short', hour: '2-digit', minute:'2-digit'
            });

            // Если просрочено - красный, иначе серый
            const colorClass = isLate ? 'text-red-500 font-bold bg-red-50' : 'text-gray-500 bg-gray-100';
            const icon = isLate ? '<i class="fa-solid fa-fire"></i>' : '<i class="fa-regular fa-clock"></i>';

            timeBadge = `<span class="px-2 py-0.5 rounded text-[10px] ${colorClass} mr-2 flex items-center gap-1">${icon} ${timeStr}</span>`;
        }

        const el = document.createElement('div');
        // Стили карточки
        el.className = `bg-[var(--tg-theme-bg-color)] p-4 rounded-2xl mb-3 shadow-sm flex items-center gap-3 active:scale-[0.98] transition fade-in border-l-4 ${isCommon ? 'border-l-blue-400' : 'border-l-transparent'} ${isDone ? 'opacity-50 grayscale' : ''}`;

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
                    ${isCommon ? '<span class="flex items-center gap-1"><i class="fa-solid fa-users"></i> Семья</span>' : '<span class="flex items-center gap-1"><i class="fa-solid fa-lock"></i> Личное</span>'}

                    ${task.subtasks.length > 0 ? `<span>• ${task.subtasks.filter(s => s.is_done).length}/${task.subtasks.length}</span>` : ''}
                </div>
            </div>

            <i class="fa-solid fa-chevron-right opacity-10 text-xs"></i>
        `;

        el.onclick = () => openDetail(task);
        list.appendChild(el);
    });
}

// --- Создание Задачи ---

function openCreateModal() {
    tg.HapticFeedback.impactOccurred('light');

    // Сброс полей
    document.getElementById('new-title').value = '';
    document.getElementById('new-deadline').value = '';

    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');

    tg.MainButton.setText("СОЗДАТЬ");
    tg.MainButton.show();
    tg.MainButton.onClick(submitCreate);
}

async function submitCreate() {
    const title = document.getElementById('new-title').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const dateVal = document.getElementById('new-deadline').value;

    if(!title.trim()) {
        tg.HapticFeedback.notificationOccurred('error');
        // Трясем поле ввода (визуальный эффект можно добавить в CSS)
        document.getElementById('new-title').focus();
        return;
    }

    // Формируем дату для API (ISO string)
    let deadline = null;
    if (dateVal) {
        deadline = new Date(dateVal).toISOString();
    }

    tg.MainButton.showProgress();
    try {
        await api.createTask({ title, visibility, deadline });
        tg.HapticFeedback.notificationOccurred('success');
        closeModals();
        loadTasks(); // Обновляем список немедленно
    } catch (e) {
        tg.HapticFeedback.notificationOccurred('error');
        alert("Ошибка создания: " + e.message);
    } finally {
        tg.MainButton.hideProgress();
    }
}

// --- Детальный просмотр ---

function openDetail(task) {
    state.currentTask = task;
    const isDone = task.status === 'done';

    // Заголовок
    const titleEl = document.getElementById('detail-title');
    titleEl.innerText = task.title;
    titleEl.className = `text-xl font-bold leading-tight mr-2 ${isDone ? 'line-through opacity-50' : ''}`;

    // Кнопка статуса (Зеленая или Серая)
    const btn = document.getElementById('btn-status');
    if (isDone) {
        btn.innerHTML = '<i class="fa-solid fa-rotate-left mr-2"></i> Вернуть в работу';
        btn.className = 'w-full py-3 rounded-xl font-semibold bg-gray-100 text-gray-800 active:scale-95 transition';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Завершить задачу';
        btn.className = 'w-full py-3 rounded-xl font-semibold bg-green-500 text-white shadow-lg shadow-green-200 active:scale-95 transition';
    }
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
        el.className = 'flex items-center gap-3 py-3 border-b border-gray-100 last:border-0';
        el.innerHTML = `
            <div class="relative flex items-center">
                <input type="checkbox" class="custom-checkbox w-5 h-5 rounded border-2 border-gray-300 checked:bg-blue-500 checked:border-blue-500 transition cursor-pointer" ${sub.is_done ? 'checked' : ''}>
            </div>
            <span class="text-sm flex-1 ${sub.is_done ? 'line-through opacity-50' : ''}">${sub.title}</span>
        `;

        // Клик по чекбоксу
        const checkbox = el.querySelector('input');
        checkbox.onchange = async (e) => {
            tg.HapticFeedback.selectionChanged();
            // Оптимистичное обновление (сразу меняем UI)
            sub.is_done = e.target.checked;
            renderSubtasks(subtasks);
            // Шлем запрос
            try {
                await api.toggleSubtask(sub.id, e.target.checked);
            } catch(err) {
                // Если ошибка - откатываем
                sub.is_done = !sub.is_done;
                renderSubtasks(subtasks);
                alert("Ошибка связи");
            }
        };
        list.appendChild(el);
    });
}

async function addSubtask() {
    const input = document.getElementById('new-subtask');
    const title = input.value.trim();
    if(!title) return;

    input.value = ''; // Очищаем сразу

    try {
        const sub = await api.addSubtask(state.currentTask.id, title);
        state.currentTask.subtasks.push(sub);
        renderSubtasks(state.currentTask.subtasks);
        tg.HapticFeedback.lightImpact();
    } catch(e) {
        alert("Не удалось добавить подзадачу");
    }
}

async function toggleTaskStatus(task) {
    const newStatus = task.status === 'done' ? 'pending' : 'done';
    tg.HapticFeedback.notificationOccurred('success');

    // Закрываем модалку сразу
    closeModals();

    // Оптимистичное обновление списка
    task.status = newStatus;
    renderList();

    // Шлем запрос
    await api.toggleTaskStatus(task.id, newStatus);
    loadTasks(); // Синхронизируем с сервером на всякий случай
}

async function deleteTask() {
    tg.showConfirm("Удалить задачу навсегда?", async (ok) => {
        if(ok) {
            tg.HapticFeedback.notificationOccurred('warning');
            closeModals();

            // Удаляем из UI сразу
            state.tasks = state.tasks.filter(t => t.id !== state.currentTask.id);
            renderList();

            // Шлем запрос
            await api.deleteTask(state.currentTask.id);
            loadTasks();
        }
    });
}

// --- Утилиты ---

function setFilter(type) {
    if (state.filter === type) return;
    state.filter = type;
    tg.HapticFeedback.selectionChanged();

    // Обновляем кнопки табов
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

    // Снимаем обработчики
    tg.MainButton.offClick(submitCreate);
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

    // Enter в поле подзадачи
    document.getElementById('new-subtask').onkeypress = (e) => {
        if(e.key === 'Enter') addSubtask();
    };
}

// Поехали!
init();
