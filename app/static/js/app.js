const tg = window.Telegram.WebApp;
tg.expand();

// Глобальное состояние
let state = {
    tasks: [],
    filter: 'all',
    currentTask: null,
    view: 'list',
    calendarDate: new Date(),
    selectedDateStr: null
};

// --- Инициализация ---
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
        if (state.view === 'calendar') renderCalendar();
    } catch (e) {
        console.error("Ошибка загрузки:", e);
    }
}

// === ЛОГИКА ПОВТОРЕНИЙ (ГЛАВНАЯ МАГИЯ) ===
function checkTaskOnDate(task, targetDate) {
    if (!task.deadline) return false;

    // 1. Нормализуем дату задачи (UTC -> Local Midnight)
    let dStr = task.deadline;
    if (!dStr.endsWith('Z')) dStr += 'Z';
    const taskDate = new Date(dStr);
    // Сбрасываем время до 00:00 для корректного сравнения
    const taskMidnight = new Date(taskDate.getFullYear(), taskDate.getMonth(), taskDate.getDate());

    // 2. Нормализуем целевую дату
    const targetMidnight = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate());

    // Оптимизация: Задача не может быть в прошлом относительно своего начала
    if (targetMidnight < taskMidnight) return false;

    // 3. Проверяем точное совпадение (для разовых задач и первого дня повтора)
    if (targetMidnight.getTime() === taskMidnight.getTime()) return true;

    // 4. Проверяем правила повтора
    if (task.repeat_rule) {
        if (task.repeat_rule === 'daily') {
            return true; // Ежедневно начиная с даты старта
        }
        if (task.repeat_rule === 'weekly') {
            // Совпадает день недели (0-6)
            return targetMidnight.getDay() === taskMidnight.getDay();
        }
        if (task.repeat_rule === 'monthly') {
            // Совпадает число месяца (1-31)
            return targetMidnight.getDate() === taskMidnight.getDate();
        }
    }
    return false;
}

// --- Переключение Видов ---
function toggleView() {
    state.view = state.view === 'list' ? 'calendar' : 'list';
    const wrapper = document.getElementById('calendar-wrapper');
    const btn = document.getElementById('view-toggle-btn');

    if (state.view === 'calendar') {
        wrapper.classList.remove('hidden');
        btn.innerHTML = '<i class="fa-solid fa-list"></i> Список';
        renderCalendar();
    } else {
        wrapper.classList.add('hidden');
        btn.innerHTML = '<i class="fa-regular fa-calendar"></i> Календарь';
        resetCalendarFilter();
    }
}

// --- Рендеринг Списка ---
function renderList() {
    const list = document.getElementById('task-list');
    list.innerHTML = '';

    // 1. Фильтр по типу (Табы)
    let filtered = state.tasks.filter(t => {
        if (state.filter === 'all') return true;
        if (state.filter === 'common') return t.visibility === 'common';
        return t.visibility !== 'common';
    });

    // 2. Фильтр по дате (Календарь)
    if (state.selectedDateStr) {
        // Парсим строку YYYY-MM-DD
        const [y, m, d] = state.selectedDateStr.split('-').map(Number);
        const selectedDate = new Date(y, m - 1, d);

        // Используем нашу умную проверку повторов
        filtered = filtered.filter(t => checkTaskOnDate(t, selectedDate));
    }

    // Пустой список
    if (filtered.length === 0) {
        list.innerHTML = `<div class="flex flex-col items-center justify-center pt-20 opacity-40 fade-in">
            <i class="fa-solid fa-mug-hot text-4xl mb-3"></i>
            <p>На этот день задач нет</p>
        </div>`;
        return;
    }

    filtered.forEach(task => {
        const isDone = task.status === 'done';
        const isCommon = task.visibility === 'common';

        // --- ЛОГИКА ВИЗУАЛИЗАЦИИ ДАТЫ ---
        // По умолчанию берем реальный дедлайн
        let displayDeadlineStr = task.deadline;

        // ЕСЛИ выбран день в календаре И задача повторяющаяся -> Подменяем дату визуально
        // (Чтобы задача на "следующий вторник" показывала дату вторника, а не прошлого дедлайна)
        if (state.selectedDateStr && task.repeat_rule && task.deadline) {
            // Берем время (часы:минуты) от оригинальной задачи
            let origStr = task.deadline.endsWith('Z') ? task.deadline : task.deadline + 'Z';
            let origDate = new Date(origStr);

            // Берем год-месяц-день от выбранной в календаре даты
            let [selY, selM, selD] = state.selectedDateStr.split('-').map(Number);

            // Создаем новую дату: Выбранный день + Оригинальное время
            let virtualDate = new Date(selY, selM - 1, selD, origDate.getHours(), origDate.getMinutes());

            // Превращаем в строку для дальнейшей обработки
            displayDeadlineStr = virtualDate.toISOString();
        }
        // ----------------------------------

        // Бейдж времени
        let timeBadge = '';
        if (displayDeadlineStr) {
            let dStr = displayDeadlineStr;
            if (!dStr.endsWith('Z')) dStr += 'Z';
            const d = new Date(dStr);
            const now = new Date();

            // Просрочено только если реальное время больше дедлайна
            // И если мы НЕ смотрим в будущее через календарь (для будущих дат isLate всегда false)
            let isLate = now > d && !isDone;
            if (state.selectedDateStr && new Date(state.selectedDateStr) > now) {
                isLate = false;
            }

            const timeStr = d.toLocaleDateString('ru-RU', {day: 'numeric', month: 'short', hour: '2-digit', minute:'2-digit'});
            const colorClass = isLate ? 'text-red-500 font-bold bg-red-50' : 'text-tg-hint bg-tg-secondary';
            const icon = isLate ? '<i class="fa-solid fa-fire"></i>' : '<i class="fa-regular fa-clock"></i>';

            timeBadge = `<span class="px-2 py-0.5 rounded text-[10px] ${colorClass} mr-2 flex items-center gap-1">${icon} ${timeStr}</span>`;
        }

        const repeatIcon = task.repeat_rule ? '<i class="fa-solid fa-rotate text-xs opacity-50 ml-2 text-tg-link"></i>' : '';

        const el = document.createElement('div');
        el.className = `task-card bg-tg-main p-4 rounded-2xl mb-3 shadow-sm flex items-center gap-3 active:scale-[0.98] transition fade-in border-l-4 ${isCommon ? 'border-l-blue-400' : 'border-l-transparent'} ${isDone ? 'opacity-50 grayscale' : ''}`;

        el.innerHTML = `
            <div class="w-6 h-6 rounded-full border-2 ${isDone ? 'bg-green-500 border-green-500' : 'border-gray-300'} grid place-content-center shrink-0">
                ${isDone ? '<i class="fa-solid fa-check text-white text-[10px]"></i>' : ''}
            </div>

            <div class="flex-1 min-w-0">
                <div class="flex items-center mb-1">
                    ${timeBadge}
                    <h3 class="font-medium truncate text-sm text-tg-main ${isDone ? 'line-through' : ''}">${task.title} ${repeatIcon}</h3>
                </div>
                <div class="flex items-center gap-3 text-[10px] text-tg-hint opacity-80">
                    ${isCommon ? '<span><i class="fa-solid fa-users"></i> Семья</span>' : '<span><i class="fa-solid fa-lock"></i> Личное</span>'}
                    ${task.subtasks.length > 0 ? `<span>• ${task.subtasks.filter(s => s.is_done).length}/${task.subtasks.length}</span>` : ''}
                </div>
            </div>
            <i class="fa-solid fa-chevron-right text-tg-hint opacity-20 text-xs"></i>
        `;
        el.onclick = () => openDetail(task);
        list.appendChild(el);
    });
}

// --- Календарь ---

function changeMonth(delta) {
    state.calendarDate.setMonth(state.calendarDate.getMonth() + delta);
    renderCalendar();
}

function renderCalendar() {
    const grid = document.getElementById('calendar-grid');
    if (!grid) return;

    const oldCells = grid.querySelectorAll('div:not(.calendar-day-name)');
    oldCells.forEach(c => c.remove());

    const year = state.calendarDate.getFullYear();
    const month = state.calendarDate.getMonth();
    const monthNames = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];

    document.getElementById('calendar-month-year').innerText = `${monthNames[month]} ${year}`;

    const firstDayIndex = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const adjustedFirstDay = firstDayIndex === 0 ? 6 : firstDayIndex - 1;

    for (let i = 0; i < adjustedFirstDay; i++) {
        const div = document.createElement('div');
        div.className = 'calendar-empty'; // Пустой класс, чтобы можно было удалить
        grid.appendChild(div);
    }

    const today = new Date();

    for (let day = 1; day <= daysInMonth; day++) {
        const currentDate = new Date(year, month, day);
        const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;

        const el = document.createElement('div');
        el.className = 'calendar-day';
        el.innerText = day;

        if (day === today.getDate() && month === today.getMonth() && year === today.getFullYear()) {
            el.classList.add('today');
        }
        if (state.selectedDateStr === dateStr) {
            el.classList.add('selected');
        }

        // ИЩЕМ ЗАДАЧИ НА ЭТОТ ДЕНЬ ЧЕРЕЗ ХЕЛПЕР
        const dayTasks = state.tasks.filter(t => checkTaskOnDate(t, currentDate));

        if (dayTasks.length > 0) {
            const dotsContainer = document.createElement('div');
            dotsContainer.className = 'task-dots';
            dayTasks.slice(0, 4).forEach(t => {
                const dot = document.createElement('div');
                dot.className = `dot ${t.status === 'done' ? 'bg-gray-300' : (t.visibility === 'common' ? 'common' : 'private')}`;
                if (new Date() > new Date(t.deadline) && t.status !== 'done') dot.className = 'dot late';
                dotsContainer.appendChild(dot);
            });
            el.appendChild(dotsContainer);
        }

        el.onclick = () => selectDate(dateStr);
        grid.appendChild(el);
    }
}

function selectDate(dateStr) {
    tg.HapticFeedback.selectionChanged();
    state.selectedDateStr = dateStr;
    document.getElementById('reset-filter-btn').style.display = 'block';
    renderCalendar();
    renderList();
}

function resetCalendarFilter() {
    state.selectedDateStr = null;
    document.getElementById('reset-filter-btn').style.display = 'none';
    renderCalendar();
    renderList();
}

// --- Модалки ---

function openDetail(task) {
    state.currentTask = task;
    const isDone = task.status === 'done';

    document.getElementById('detail-title').innerText = task.title;
    document.getElementById('detail-title').className = `text-xl font-bold leading-tight mr-2 flex-1 text-tg-main ${isDone ? 'line-through opacity-50' : ''}`;

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
        btn.innerHTML = '<i class="fa-solid fa-rotate-left mr-2"></i> Вернуть';
        btn.className = 'w-full py-3 rounded-xl font-semibold bg-tg-secondary text-tg-main shadow-sm active:scale-95 transition';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Завершить';
        btn.className = 'w-full py-3 rounded-xl font-semibold bg-green-500 text-white shadow-lg active:scale-95 transition';
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
    document.getElementById('new-desc').value = '';
    document.getElementById('new-deadline').value = '';
    document.getElementById('new-repeat').value = '';

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
    document.getElementById('new-desc').value = task.description || '';
    document.getElementById('new-repeat').value = task.repeat_rule || '';

    if(task.deadline) {
        let dateStr = task.deadline;
        if (!dateStr.endsWith('Z')) dateStr += 'Z';
        const d = new Date(dateStr);
        const localIso = new Date(d.getTime() - (d.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
        document.getElementById('new-deadline').value = localIso;
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

// --- Submit Logic ---

async function submitCreate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const repeat = document.getElementById('new-repeat').value || null;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const dateVal = document.getElementById('new-deadline').value;

    if(!title.trim()) {
        tg.HapticFeedback.notificationOccurred('error');
        return;
    }

    let deadline = null;
    if (dateVal) deadline = new Date(dateVal).toISOString();

    tg.MainButton.showProgress();
    try {
        await api.createTask({
            title, description: desc, visibility, deadline, repeat_rule: repeat
        });
        tg.HapticFeedback.notificationOccurred('success');
        closeModals();
        loadTasks();
    } catch(e) {
        alert(e);
    } finally {
        tg.MainButton.hideProgress();
    }
}

async function submitUpdate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const repeat = document.getElementById('new-repeat').value || null;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const dateVal = document.getElementById('new-deadline').value;

    let deadline = null;
    if (dateVal) deadline = new Date(dateVal).toISOString();

    tg.MainButton.showProgress();
    await api.updateTask(state.currentTask.id, {
        title, description: desc, visibility, deadline, repeat_rule: repeat
    });
    tg.HapticFeedback.notificationOccurred('success');
    closeModals();
    loadTasks();
    tg.MainButton.hideProgress();
}

async function toggleTaskStatus(task) {
    // Если аргумент не передан, берем из state (для надежности)
    const targetTask = task || state.currentTask;

    if (!targetTask) {
        console.error("Task not found!");
        return;
    }

    const newStatus = targetTask.status === 'done' ? 'pending' : 'done';

    // Оптимистичное обновление (меняем UI мгновенно)
    targetTask.status = newStatus;

    // Закрываем модалку
    closeModals();

    // Обновляем список, чтобы галочка появилась сразу
    renderList();

    tg.HapticFeedback.notificationOccurred('success');

    try {
        // Шлем запрос на сервер
        await api.toggleTaskStatus(targetTask.id, newStatus);
    } catch (e) {
        // Если ошибка - откатываем изменения и ругаемся
        alert("Ошибка сети: " + e);
        targetTask.status = targetTask.status === 'done' ? 'pending' : 'done';
        renderList();
    } finally {
        // В любом случае обновляем данные с сервера
        loadTasks();
    }
}

async function addSubtask() {
    const input = document.getElementById('new-subtask');
    if(!input.value.trim()) return;
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

function renderSubtasks(subtasks) {
    const list = document.getElementById('subtasks-list');
    list.innerHTML = '';
    subtasks.forEach(sub => {
        const el = document.createElement('div');
        el.className = 'flex items-center gap-3 py-2 border-b border-tg-hint/10 last:border-0';
        el.innerHTML = `
            <input type="checkbox" class="custom-checkbox shrink-0" ${sub.is_done ? 'checked' : ''}>
            <span class="text-sm flex-1 text-tg-main ${sub.is_done ? 'line-through opacity-50' : ''}">${sub.title}</span>
        `;
        el.querySelector('input').onchange = (e) => {
            api.toggleSubtask(sub.id, e.target.checked);
            sub.is_done = e.target.checked;
            renderSubtasks(subtasks);
        };
        list.appendChild(el);
    });
}

// --- UI Utils ---

function setFilter(type) {
    state.filter = type;
    tg.HapticFeedback.selectionChanged();

    document.querySelectorAll('.tab-btn').forEach(btn => {
        if(btn.dataset.filter === type) {
            btn.classList.add('active', 'bg-tg-button', 'text-white', 'shadow-md');
            btn.classList.remove('opacity-60');
        } else {
            btn.classList.remove('active', 'bg-tg-button', 'text-white', 'shadow-md');
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
    tg.MainButton.offClick(submitCreate);
    tg.MainButton.offClick(submitUpdate);
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.onclick = () => setFilter(btn.dataset.filter));
    document.getElementById('overlay').onclick = closeModals;
    tg.BackButton.onClick(closeModals);
    document.getElementById('new-subtask').onkeypress = (e) => { if(e.key === 'Enter') addSubtask(); };
}

// Start
init();
