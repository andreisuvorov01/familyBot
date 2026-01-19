const tg = window.Telegram.WebApp;
tg.expand();

// 1. ИСПРАВЛЕННЫЙ STATE (убраны state. и точки с запятой внутри)
let state = {
    tasks: [],
    filter: 'all',
    currentTask: null,
    view: 'list',
    calendarDate: new Date(),
    selectedDateStr: null,
    tempDate: null,   // Исправлено
    tempRepeat: null  // Исправлено
};

// --- INIT ---
async function init() {
    setupTheme();
    setupEventListeners();
    initSwipeGestures();
    await loadTasks();
    setInterval(loadTasks, 15000);
}

function setupTheme() {
    const platform = tg.platform;
    if (['ios', 'macos'].includes(platform)) {
        document.body.classList.add('is-ios');
    } else {
        document.body.classList.add('is-android');
    }

    document.body.style.backgroundColor = 'var(--bg-page)';

    const user = tg.initDataUnsafe?.user;
    if (user) {
        const avatarEl = document.getElementById('user-avatar');
        if (user.photo_url) {
            avatarEl.innerHTML = `<img src="${user.photo_url}" style="width:100%; height:100%; object-fit:cover;">`;
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
        console.error("API Error:", e);
    }
}

// === DATE LOGIC ===
function checkTaskOnDate(task, targetDate) {
    if (!task.deadline) return false;

    let dStr = task.deadline.endsWith('Z') ? task.deadline : task.deadline + 'Z';
    const taskDate = new Date(dStr);
    const taskMidnight = new Date(taskDate.getFullYear(), taskDate.getMonth(), taskDate.getDate());

    const targetMidnight = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate());

    if (targetMidnight < taskMidnight) return false;
    if (targetMidnight.getTime() === taskMidnight.getTime()) return true;

    if (task.repeat_rule) {
        if (task.repeat_rule === 'daily') return true;
        if (task.repeat_rule === 'weekly') return targetMidnight.getDay() === taskMidnight.getDay();
        if (task.repeat_rule === 'monthly') return targetMidnight.getDate() === taskMidnight.getDate();
    }
    return false;
}

// --- VIEWS ---
function toggleView() {
    state.view = state.view === 'list' ? 'calendar' : 'list';
    const wrapper = document.getElementById('calendar-wrapper');
    const btn = document.getElementById('view-toggle-btn');

    if (state.view === 'calendar') {
        wrapper.classList.remove('hidden');
        btn.innerHTML = 'Список';
        renderCalendar();
    } else {
        wrapper.classList.add('hidden');
        btn.innerHTML = 'Календарь';
        resetCalendarFilter();
    }
}

// --- RENDER LIST ---
function renderList() {
    const list = document.getElementById('task-list');
    list.innerHTML = '';

    let filtered = state.tasks.filter(t => {
        if (state.filter === 'all') return true;
        if (state.filter === 'common') return t.visibility === 'common';
        return t.visibility !== 'common';
    });

    if (state.selectedDateStr) {
        const [y, m, d] = state.selectedDateStr.split('-').map(Number);
        const selectedDate = new Date(y, m - 1, d);
        filtered = filtered.filter(t => checkTaskOnDate(t, selectedDate));
    }

    if (filtered.length === 0) {
        list.innerHTML = `
            <div style="text-align: center; padding-top: 80px; opacity: 0.5;">
                <i class="fa-solid fa-mug-hot" style="font-size: 48px; margin-bottom: 16px; color: var(--text-hint);"></i>
                <p style="font-size: 16px; font-weight: 500; color: var(--text-hint);">Нет задач</p>
            </div>`;
        return;
    }

    filtered.forEach((task, index) => {
        const isDone = task.status === 'done';
        const isCommon = task.visibility === 'common';

        let displayDeadlineStr = task.deadline;
        if (state.selectedDateStr && task.repeat_rule && task.deadline) {
            let origStr = task.deadline.endsWith('Z') ? task.deadline : task.deadline + 'Z';
            let origDate = new Date(origStr);
            let [selY, selM, selD] = state.selectedDateStr.split('-').map(Number);
            let virtualDate = new Date(selY, selM - 1, selD, origDate.getHours(), origDate.getMinutes());
            displayDeadlineStr = virtualDate.toISOString();
        }

        let timeBadge = '';
        if (displayDeadlineStr) {
            let dStr = displayDeadlineStr.endsWith('Z') ? displayDeadlineStr : displayDeadlineStr + 'Z';
            const d = new Date(dStr);
            const now = new Date();
            let isLate = now > d && !isDone;
            if (state.selectedDateStr && new Date(state.selectedDateStr) > now) isLate = false;

            const timeStr = d.toLocaleDateString('ru-RU', {day:'numeric', month:'short', hour:'2-digit', minute:'2-digit'});
            const color = isLate ? '#ff3b30' : 'var(--text-hint)';
            const weight = isLate ? '700' : '500';
            const icon = isLate ? 'fa-solid fa-fire' : 'fa-regular fa-clock';
            timeBadge = `<span style="color: ${color}; font-weight: ${weight}; font-size: 12px; display: flex; align-items: center; gap: 4px; margin-right: 8px;">
                <i class="${icon}"></i> ${timeStr}
            </span>`;
        }

        const repeatIcon = task.repeat_rule ? '<i class="fa-solid fa-rotate" style="font-size: 12px; opacity: 0.6; margin-left: 6px;"></i>' : '';
        const iconType = isCommon ? '<i class="fa-solid fa-users"></i>' : '<i class="fa-solid fa-lock"></i>';
        const borderLeft = isCommon ? '4px solid var(--accent)' : '4px solid transparent';

        const el = document.createElement('div');
        el.className = 'task-card';
        el.classList.add('animate-enter');
        el.style.animationDelay = `${index * 0.05}s`;

        el.style.borderLeft = borderLeft;
        if (isDone) el.style.opacity = '0.6';

         el.innerHTML = `
            <div style="width: 24px; height: 24px; border: 2px solid ${isDone ? '#34c759' : 'var(--text-hint)'}; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: ${isDone ? '#34c759' : 'transparent'}; flex-shrink: 0;">
                ${isDone ? '<i class="fa-solid fa-check" style="color: white; font-size: 12px;"></i>' : ''}
            </div>

            <div style="flex: 1; min-width: 0;">
                <div style="display: flex; align-items: center; margin-bottom: 4px;">
                    ${timeBadge}
                    <div style="font-weight: 600; font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-decoration: ${isDone ? 'line-through' : 'none'}; color: var(--text-primary);">
                        ${task.title} ${repeatIcon}
                    </div>
                </div>
                <div style="font-size: 13px; color: var(--text-hint); display: flex; gap: 10px;">
                    <span style="display: flex; align-items: center; gap: 4px;">${iconType} ${isCommon ? 'Семья' : 'Личное'}</span>
                    ${task.subtasks.length > 0 ? `<span>• ${task.subtasks.filter(s => s.is_done).length}/${task.subtasks.length}</span>` : ''}
                </div>
            </div>
            <i class="fa-solid fa-chevron-right" style="color: var(--text-hint); opacity: 0.3; font-size: 14px;"></i>
        `;

        el.onclick = () => openDetail(task);
        list.appendChild(el);
    });
}

// --- CALENDAR ---
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
        div.className = 'calendar-empty';
        grid.appendChild(div);
    }

    const today = new Date();
    const todayMidnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    for (let day = 1; day <= daysInMonth; day++) {
        const currentDate = new Date(year, month, day);
        const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;

        const el = document.createElement('div');
        el.className = 'calendar-day';

        const span = document.createElement('span');
        span.innerText = day;
        el.appendChild(span);

        // Today
        if (currentDate.getTime() === todayMidnight.getTime()) {
            el.classList.add('today');
        }
        if (state.selectedDateStr === dateStr) {
            el.classList.add('selected');
        }

        const dayTasks = state.tasks.filter(t => {
            // Обычная проверка
            const matches = checkTaskOnDate(t, currentDate);
            if (matches) return true;

            // Для "Сегодня" показываем просроченные
            if (currentDate.getTime() === todayMidnight.getTime() && t.status !== 'done' && t.deadline) {
                let dStr = t.deadline.endsWith('Z') ? t.deadline : t.deadline + 'Z';
                if (new Date(dStr) < today) return true;
            }
            return false;
        });

        if (dayTasks.length > 0) {
            const dotsContainer = document.createElement('div');
            dotsContainer.className = 'task-dots';
            dayTasks.slice(0, 3).forEach(t => {
                const dot = document.createElement('div');
                let dotClass = 'common';
                if (t.visibility !== 'common') dotClass = 'private';

                if (t.deadline) {
                    let dStr = t.deadline.endsWith('Z') ? t.deadline : t.deadline + 'Z';
                    if (new Date(dStr) < new Date() && t.status !== 'done') dotClass = 'late';
                }

                dot.className = `dot ${dotClass}`;
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
    document.getElementById('reset-filter-btn').style.display = 'inline-block';
    renderCalendar();
    renderList();
}

function resetCalendarFilter() {
    state.selectedDateStr = null;
    document.getElementById('reset-filter-btn').style.display = 'none';
    renderCalendar();
    renderList();
}

// --- MODALS & FORMS ---

function openCreateModal() {
    tg.HapticFeedback.impactOccurred('medium');
    document.getElementById('new-title').value = '';
    document.getElementById('new-desc').value = '';

    // Сброс кастомных пикеров
    state.tempDate = null;
    state.tempRepeat = null;
    document.getElementById('val-date').innerText = 'Нет';
    document.getElementById('val-date').classList.add('placeholder');
    document.getElementById('val-repeat').innerText = 'Нет';
    document.getElementById('val-repeat').classList.add('placeholder');

    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');

    setTimeout(() => document.getElementById('new-title').focus(), 300);

    tg.MainButton.setText("СОЗДАТЬ");
    tg.MainButton.show();
    tg.MainButton.offClick(submitUpdate);
    tg.MainButton.onClick(submitCreate);
}

// 2. ИСПРАВЛЕННАЯ ФУНКЦИЯ openEditMode (без дубликатов)
function openEditMode() {
    const task = state.currentTask;
    closeModals();

    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');

    // Текст
    document.getElementById('new-title').value = task.title;
    document.getElementById('new-desc').value = task.description || '';

    // Видимость
    const vis = task.visibility === 'common' ? 'common' : 'private';
    document.querySelector(`input[name="visibility"][value="${vis}"]`).checked = true;

    // Повтор (Custom UI)
    state.tempRepeat = task.repeat_rule;
    const repeatMap = { null: 'Нет', 'daily': 'Ежедневно', 'weekly': 'Еженедельно', 'monthly': 'Ежемесячно' };
    const repeatText = repeatMap[task.repeat_rule] || 'Нет';
    const repeatEl = document.getElementById('val-repeat');
    repeatEl.innerText = repeatText;
    if (task.repeat_rule) repeatEl.classList.remove('placeholder');
    else repeatEl.classList.add('placeholder');

    // Дата (Custom UI)
    if(task.deadline) {
        let dStr = task.deadline;
        if (!dStr.endsWith('Z')) dStr += 'Z';
        const d = new Date(dStr);
        state.tempDate = d;

        const dateText = d.toLocaleDateString('ru-RU', {
            day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit'
        });
        const dateEl = document.getElementById('val-date');
        dateEl.innerText = dateText;
        dateEl.classList.remove('placeholder');

        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        document.getElementById('time-picker').value = `${hours}:${minutes}`;
    } else {
        state.tempDate = null;
        document.getElementById('val-date').innerText = 'Нет';
        document.getElementById('val-date').classList.add('placeholder');
    }

    tg.MainButton.setText("СОХРАНИТЬ");
    tg.MainButton.show();
    tg.MainButton.offClick(submitCreate);
    tg.MainButton.onClick(submitUpdate);
}

function openDetail(task) {
    state.currentTask = task;
    const isDone = task.status === 'done';

    document.getElementById('detail-title').innerText = task.title;
    const titleEl = document.getElementById('detail-title');
    titleEl.style.textDecoration = isDone ? 'line-through' : 'none';
    titleEl.style.opacity = isDone ? '0.5' : '1';

    const descEl = document.getElementById('detail-desc');
    if (task.description && task.description.trim()) {
        descEl.innerText = task.description;
        descEl.style.opacity = '0.9';
    } else {
        descEl.innerText = "Нет описания";
        descEl.style.opacity = '0.5';
    }

    const btn = document.getElementById('btn-status');
    if (isDone) {
        btn.innerHTML = '<i class="fa-solid fa-rotate-left mr-2"></i> Вернуть';
        btn.style.backgroundColor = 'var(--bg-page)';
        btn.style.color = 'var(--text-main)';
    } else {
        btn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Завершить';
        btn.style.backgroundColor = 'var(--accent)';
        btn.style.color = 'white';
    }
    btn.onclick = () => toggleTaskStatus(task);

    renderSubtasks(task.subtasks);

    document.getElementById('detail-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    tg.BackButton.show();
}

// --- ACTIONS ---

async function submitCreate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;

    // Берем данные из state
    const repeat = state.tempRepeat || null;
    let deadline = null;
    if (state.tempDate) deadline = state.tempDate.toISOString();

    if (!title.trim()) {
        tg.HapticFeedback.notificationOccurred('error');
        document.getElementById('new-title').focus();
        return;
    }

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
    const visibility = document.querySelector('input[name="visibility"]:checked').value;

    const repeat = state.tempRepeat || null;
    let deadline = null;
    if (state.tempDate) deadline = state.tempDate.toISOString();

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
    const targetTask = task || state.currentTask;
    if (!targetTask) return;

    const newStatus = targetTask.status === 'done' ? 'pending' : 'done';

    targetTask.status = newStatus;
    renderList();
    closeModals();
    tg.HapticFeedback.notificationOccurred('success');

    try {
        await api.toggleTaskStatus(targetTask.id, newStatus);
    } catch (e) {
        alert("Ошибка");
        targetTask.status = targetTask.status === 'done' ? 'pending' : 'done';
        renderList();
    } finally {
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
    tg.showConfirm("Удалить задачу?", async (ok) => {
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
        el.className = 'flex items-center gap-3 py-3 border-b border-[var(--text-hint)]/10 last:border-0';
        el.style.borderBottom = '1px solid rgba(128,128,128,0.1)';

        el.innerHTML = `
            <input type="checkbox" class="custom-checkbox shrink-0" ${sub.is_done ? 'checked' : ''}>
            <span class="text-sm flex-1 text-main ${sub.is_done ? 'line-through opacity-50' : ''}">${sub.title}</span>
        `;
        el.querySelector('input').onchange = (e) => {
            api.toggleSubtask(sub.id, e.target.checked);
            sub.is_done = e.target.checked;
            renderSubtasks(subtasks);
        };
        list.appendChild(el);
    });
}

// --- UTILS ---
function setFilter(type) {
    state.filter = type;
    tg.HapticFeedback.selectionChanged();
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if(btn.dataset.filter === type) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    renderList();
}

function closeModals() {
    document.querySelectorAll('.bottom-sheet').forEach(el => el.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
    tg.MainButton.hide();
    tg.BackButton.hide();
    document.activeElement.blur();
}

function closeSheets() {
    document.querySelectorAll('.bottom-sheet').forEach(el => el.classList.remove('active'));
    document.getElementById('overlay').classList.remove('active');
}

// --- Custom Picker Logic ---
function openRepeatSheet() {
    document.getElementById('sheet-repeat').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    document.getElementById('overlay').onclick = () => {
        closeSheets();
        document.getElementById('create-modal').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    };
}

function selectRepeat(value) {
    state.tempRepeat = value;
    const map = { null: 'Нет', 'daily': 'Ежедневно', 'weekly': 'Еженедельно', 'monthly': 'Ежемесячно' };
    const el = document.getElementById('val-repeat');
    el.innerText = map[value];
    if (value) el.classList.remove('placeholder');
    else el.classList.add('placeholder');
    closeSheets();
    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function openDateSheet() {
    document.getElementById('sheet-date').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    renderPickerCalendar();
    document.getElementById('overlay').onclick = () => {
        closeSheets();
        document.getElementById('create-modal').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    };
}

function selectQuickDate(offsetDays) {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    applyDate(d);
}

function applyDate(dateObj) {
    const timeStr = document.getElementById('time-picker').value || "12:00";
    const [hours, minutes] = timeStr.split(':').map(Number);
    dateObj.setHours(hours);
    dateObj.setMinutes(minutes);
    state.tempDate = dateObj;

    const el = document.getElementById('val-date');
    el.innerText = dateObj.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit' });
    el.classList.remove('placeholder');

    closeSheets();
    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function clearDate() {
    state.tempDate = null;
    document.getElementById('val-date').innerText = "Нет";
    document.getElementById('val-date').classList.add('placeholder');
    closeSheets();
    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
}

function renderPickerCalendar() {
    const grid = document.getElementById('picker-calendar-grid');
    if(!grid) return;
    grid.innerHTML = '';
    const now = new Date();
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();

    for (let day = 1; day <= daysInMonth; day++) {
        const el = document.createElement('div');
        el.className = 'calendar-day';
        el.innerHTML = `<span>${day}</span>`;
        if (day === now.getDate()) el.classList.add('today');
        el.onclick = () => {
            const selected = new Date(now.getFullYear(), now.getMonth(), day);
            applyDate(selected);
        };
        grid.appendChild(el);
    }
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.onclick = () => setFilter(btn.dataset.filter));
    document.getElementById('overlay').onclick = closeModals;
    tg.BackButton.onClick(closeModals);
    document.getElementById('new-subtask').onkeypress = (e) => { if(e.key === 'Enter') addSubtask(); };
}
// === SWIPE TO CLOSE LOGIC ===

function initSwipeGestures() {
    const sheets = document.querySelectorAll('.bottom-sheet');

    sheets.forEach(sheet => {
        let startY = 0;
        let currentY = 0;
        let isDragging = false;

        // 1. Начало касания
        sheet.addEventListener('touchstart', (e) => {
            // Если скролл внутри контента не на самом верху, не активируем свайп закрытия
            if (sheet.scrollTop > 0) return;

            startY = e.touches[0].clientY;
            isDragging = true;
            sheet.style.transition = 'none'; // Отключаем плавность для прямого следования за пальцем
        }, { passive: true });

        // 2. Движение пальца
        sheet.addEventListener('touchmove', (e) => {
            if (!isDragging) return;

            currentY = e.touches[0].clientY;
            let delta = currentY - startY;

            // Если тянем вниз (delta > 0)
            if (delta > 0) {
                e.preventDefault(); // Блокируем скролл страницы
                sheet.style.transform = `translateY(${delta}px)`;
            }
        }, { passive: false });

        // 3. Конец касания
        sheet.addEventListener('touchend', () => {
            if (!isDragging) return;
            isDragging = false;

            // Возвращаем анимацию
            sheet.style.transition = 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)';

            let delta = currentY - startY;

            // Если утянули больше чем на 100px - закрываем
            if (delta > 100) {
                // Закрываем всё (и пикеры, и модалки)
                closeSheets();
                closeModals();
            } else {
                // Возвращаем на место (отскок)
                sheet.style.transform = ''; // Сброс инлайнового стиля вернет класс .active (translateY(0))
            }
        });
    });
}

init();
