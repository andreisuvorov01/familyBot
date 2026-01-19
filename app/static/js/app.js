const tg = window.Telegram.WebApp;
tg.expand();

// === CONSTANTS ===
const ITEM_HEIGHT = 34; // Высота строки в барабане (должна совпадать с CSS)

// === STATE ===
let state = {
    tasks: [],
    filter: 'all',
    currentTask: null,
    view: 'list',
    calendarDate: new Date(),
    selectedDateStr: null,
    tempDate: null,
    tempRepeat: null
};

// Глобальные переменные для пикера
let selectedH = 12;
let selectedM = 0;
let pickerDate = new Date();
let renderedTaskIds = new Set(); // Храним ID отрисованных задач

// === INIT ===
async function init() {
    setupTheme();
    setupEventListeners();
    initSwipeGestures();
    initTimeSelectors(); // Генерация барабанов (1 раз)

    await loadTasks();
    setInterval(loadTasks, 15000);
}

function setupTheme() {
    const platform = tg.platform;
    if (['ios', 'macos'].includes(platform)) document.body.classList.add('is-ios');
    else document.body.classList.add('is-android');
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
        console.error(e);
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

// === VIEWS ===
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

// === RENDER LIST (Smart Animation) ===
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
        list.innerHTML = `<div style="text-align: center; padding-top: 80px; opacity: 0.5;"><i class="fa-solid fa-mug-hot" style="font-size: 48px; margin-bottom: 16px; color: var(--text-hint);"></i><p style="font-size: 16px; font-weight: 500; color: var(--text-hint);">Нет задач</p></div>`;
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
            timeBadge = `<span style="color: ${color}; font-weight: ${weight}; font-size: 12px; display: flex; align-items: center; gap: 4px; margin-right: 8px;"><i class="${icon}"></i> ${timeStr}</span>`;
        }

        const repeatIcon = task.repeat_rule ? '<i class="fa-solid fa-rotate" style="font-size: 12px; opacity: 0.6; margin-left: 6px;"></i>' : '';
        const iconType = isCommon ? '<i class="fa-solid fa-users"></i>' : '<i class="fa-solid fa-lock"></i>';
        const borderLeft = isCommon ? '4px solid var(--accent)' : '4px solid transparent';

        const el = document.createElement('div');
        el.className = 'task-card';

        // УМНАЯ АНИМАЦИЯ: Только если задачи не было в списке ранее
        if (!renderedTaskIds.has(task.id)) {
            el.classList.add('animate-enter');
            el.style.animationDelay = `${index * 0.05}s`;
            renderedTaskIds.add(task.id);
        } else {
            // Иначе показываем сразу
            el.style.opacity = isDone ? '0.6' : '1';
            el.style.transform = 'translateY(0)';
        }

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

// === WHEEL TIME PICKER (Optimized) ===
function initTimeSelectors() {
    const hCol = document.getElementById('wheel-h');
    const mCol = document.getElementById('wheel-m');

    // Очистка перед генерацией
    hCol.innerHTML = '';
    mCol.innerHTML = '';

    // Часы 00-23
    for (let i = 0; i < 24; i++) {
        createWheelItem(hCol, i);
    }
    // Минуты 00-59
    for (let i = 0; i < 60; i++) {
        createWheelItem(mCol, i);
    }

    setupWheelObserver(hCol, (val) => selectedH = val);
    setupWheelObserver(mCol, (val) => selectedM = val);
}

function createWheelItem(container, val) {
    const div = document.createElement('div');
    div.className = 'wheel-item';
    div.innerText = String(val).padStart(2, '0');
    div.dataset.val = val;
    div.onclick = () => {
        container.scrollTo({ top: val * ITEM_HEIGHT, behavior: 'smooth' });
    };
    container.appendChild(div);
}

function setupWheelObserver(container, callback) {
    let isScrolling = false;
    const update = () => {
        const index = Math.round(container.scrollTop / ITEM_HEIGHT);
        const maxIndex = container.children.length - 1;

        Array.from(container.children).forEach((child, idx) => {
            if (idx === index) {
                child.classList.add('active');
                callback(parseInt(child.dataset.val));
            } else {
                child.classList.remove('active');
            }
        });
        isScrolling = false;
    };

    container.addEventListener('scroll', () => {
        if (!isScrolling) {
            window.requestAnimationFrame(update);
            isScrolling = true;
        }
    }, { passive: true });
}

function setWheelTime(h, m) {
    const hCol = document.getElementById('wheel-h');
    const mCol = document.getElementById('wheel-m');
    // Прямой скролл без анимации для мгновенной установки
    if(hCol) hCol.scrollTop = h * ITEM_HEIGHT;
    if(mCol) mCol.scrollTop = m * ITEM_HEIGHT;

    selectedH = h;
    selectedM = m;
}

// === SHEETS LOGIC ===
function openDateSheet() {
    document.getElementById('sheet-date').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    renderPickerCalendar();

    let d = state.tempDate ? new Date(state.tempDate) : new Date();
    // Небольшая задержка чтобы DOM отрисовался
    setTimeout(() => setWheelTime(d.getHours(), d.getMinutes()), 50);

    document.getElementById('overlay').onclick = () => {
        closeSheets();
        document.getElementById('create-modal').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    };
}

// ... Остальные функции пикеров (selectQuickDate, applyDate, clearDate...)
// Скопируй их из предыдущего ответа, они корректны.
function selectQuickDate(offsetDays) {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    applyDate(d);
}

function applyDate(dateObj) {
    dateObj.setHours(selectedH);
    dateObj.setMinutes(selectedM);
    state.tempDate = dateObj;
    const el = document.getElementById('val-date');
    el.innerText = dateObj.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit' });
    el.classList.remove('placeholder');
    document.getElementById('sheet-date').classList.remove('active');
}

function clearDate() {
    state.tempDate = null;
    document.getElementById('val-date').innerText = "Нет";
    document.getElementById('val-date').classList.add('placeholder');
    document.getElementById('sheet-date').classList.remove('active');
}

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
    document.getElementById('val-repeat').innerText = map[value];
    if (value) document.getElementById('val-repeat').classList.remove('placeholder');
    else document.getElementById('val-repeat').classList.add('placeholder');
    document.getElementById('sheet-repeat').classList.remove('active');
}

// === CALENDAR ===
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
        el.innerHTML = `<span>${day}</span>`;

        if (currentDate.getTime() === todayMidnight.getTime()) el.classList.add('today');
        if (state.selectedDateStr === dateStr) el.classList.add('selected');

        const dayTasks = state.tasks.filter(t => {
            const matches = checkTaskOnDate(t, currentDate);
            if (matches) return true;
            // Для Сегодня показываем просроченные
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

// Calendar helpers
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
function renderPickerCalendar() {
    // ... (код календаря в пикере такой же, как в renderCalendar, только с кликом на applyDate)
    const grid = document.getElementById('picker-calendar-grid');
    if(!grid) return;
    grid.innerHTML = '';
    const now = new Date();
    const year = pickerDate.getFullYear();
    const month = pickerDate.getMonth();
    const monthNames = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];
    document.getElementById('picker-month-year').innerText = `${monthNames[month]} ${year}`;
    const firstDayIndex = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const adjustedFirstDay = firstDayIndex === 0 ? 6 : firstDayIndex - 1;
    for (let i = 0; i < adjustedFirstDay; i++) {
        const div = document.createElement('div');
        grid.appendChild(div);
    }
    for (let day = 1; day <= daysInMonth; day++) {
        const el = document.createElement('div');
        el.className = 'calendar-day';
        el.innerHTML = `<span>${day}</span>`;
        if (day === now.getDate() && month === now.getMonth() && year === now.getFullYear()) el.classList.add('today');
        if (state.tempDate && day === state.tempDate.getDate() && month === state.tempDate.getMonth() && year === state.tempDate.getFullYear()) el.classList.add('selected');
        el.onclick = () => {
            const selected = new Date(year, month, day);
            applyDate(selected);
        };
        grid.appendChild(el);
    }
}
function changePickerMonth(delta) {
    pickerDate.setMonth(pickerDate.getMonth() + delta);
    renderPickerCalendar();
}

// --- MODALS ---
function openCreateModal() {
    tg.HapticFeedback.impactOccurred('medium');
    document.getElementById('new-title').value = '';
    document.getElementById('new-desc').value = '';
    state.tempDate = null;
    state.tempRepeat = null;
    document.getElementById('val-date').innerText = 'Нет';
    document.getElementById('val-date').classList.add('placeholder');
    document.getElementById('val-repeat').innerText = 'Нет';
    document.getElementById('val-repeat').classList.add('placeholder');

    document.getElementById('create-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    document.getElementById('overlay').onclick = closeModals;
    setTimeout(() => document.getElementById('new-title').focus(), 300);
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
    document.getElementById('overlay').onclick = closeModals;

    document.getElementById('new-title').value = task.title;
    document.getElementById('new-desc').value = task.description || '';
    const vis = task.visibility === 'common' ? 'common' : 'private';
    document.querySelector(`input[name="visibility"][value="${vis}"]`).checked = true;

    state.tempRepeat = task.repeat_rule;
    const repeatMap = { null: 'Нет', 'daily': 'Ежедневно', 'weekly': 'Еженедельно', 'monthly': 'Ежемесячно' };
    document.getElementById('val-repeat').innerText = repeatMap[task.repeat_rule] || 'Нет';
    if (task.repeat_rule) document.getElementById('val-repeat').classList.remove('placeholder');
    else document.getElementById('val-repeat').classList.add('placeholder');

    if(task.deadline) {
        let dStr = task.deadline;
        if (!dStr.endsWith('Z')) dStr += 'Z';
        const d = new Date(dStr);
        state.tempDate = d;
        document.getElementById('val-date').innerText = d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit' });
        document.getElementById('val-date').classList.remove('placeholder');
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
    document.getElementById('detail-title').style.textDecoration = isDone ? 'line-through' : 'none';
    document.getElementById('detail-title').style.opacity = isDone ? '0.5' : '1';

    document.getElementById('detail-desc').innerText = (task.description && task.description.trim()) ? task.description : "Нет описания";

    const btn = document.getElementById('btn-status');
    if (isDone) {
        btn.innerText = 'Вернуть';
        btn.style.backgroundColor = 'var(--bg-page)';
        btn.style.color = 'var(--text-main)';
    } else {
        btn.innerText = 'Завершить';
        btn.style.backgroundColor = 'var(--accent)';
        btn.style.color = 'white';
    }
    btn.onclick = () => toggleTaskStatus(task);

    renderSubtasks(task.subtasks);
    document.getElementById('detail-modal').classList.add('active');
    document.getElementById('overlay').classList.add('active');
    document.getElementById('overlay').onclick = closeModals;
    tg.BackButton.show();
}

async function submitCreate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const repeat = state.tempRepeat || null;
    let deadline = state.tempDate ? state.tempDate.toISOString() : null;

    if (!title.trim()) return;

    tg.MainButton.showProgress();
    try {
        await api.createTask({ title, description: desc, visibility, deadline, repeat_rule: repeat });
        tg.HapticFeedback.notificationOccurred('success');
        closeModals();
        loadTasks();
    } catch(e) { alert(e); } finally { tg.MainButton.hideProgress(); }
}

async function submitUpdate() {
    const title = document.getElementById('new-title').value;
    const desc = document.getElementById('new-desc').value;
    const visibility = document.querySelector('input[name="visibility"]:checked').value;
    const repeat = state.tempRepeat || null;
    let deadline = state.tempDate ? state.tempDate.toISOString() : null;

    tg.MainButton.showProgress();
    await api.updateTask(state.currentTask.id, { title, description: desc, visibility, deadline, repeat_rule: repeat });
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

    try { await api.toggleTaskStatus(targetTask.id, newStatus); }
    catch (e) { alert("Ошибка"); targetTask.status = newStatus === 'done' ? 'pending' : 'done'; renderList(); }
    finally { loadTasks(); }
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
    document.querySelectorAll('[id^="sheet-"]').forEach(el => el.classList.remove('active'));
    if (!document.getElementById('create-modal').classList.contains('active')) {
        document.getElementById('overlay').classList.remove('active');
    } else {
        document.getElementById('overlay').onclick = closeModals;
    }
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.onclick = () => setFilter(btn.dataset.filter));
    tg.BackButton.onClick(closeModals);
    document.getElementById('new-subtask').onkeypress = (e) => { if(e.key === 'Enter') addSubtask(); };
}

function initSwipeGestures() {
    let activeSheet = null, startY = 0, currentY = 0, isDragging = false, startTime = 0;
    document.addEventListener('touchstart', (e) => {
        const sheets = Array.from(document.querySelectorAll('.bottom-sheet.active'));
        if (sheets.length === 0) return;
        activeSheet = sheets[sheets.length - 1];
        if (!activeSheet.contains(e.target)) return;

        // Fix: Игнорируем барабан
        if (e.target.closest('.wheel-column')) { activeSheet = null; return; }

        const isHandle = e.target.classList.contains('sheet-handle');
        if (!isHandle && activeSheet.scrollTop > 0) return;
        startY = e.touches[0].clientY;
        startTime = Date.now();
        isDragging = true;
        activeSheet.style.transition = 'none';
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!isDragging || !activeSheet) return;
        currentY = e.touches[0].clientY;
        let delta = currentY - startY;
        if (delta > 0) {
            e.preventDefault();
            activeSheet.style.transform = `translateY(${delta}px)`;
        }
    }, { passive: false });

    document.addEventListener('touchend', (e) => {
        if (!isDragging || !activeSheet) return;
        isDragging = false;
        const delta = currentY - startY;
        const velocity = delta / (Date.now() - startTime);
        activeSheet.style.transition = 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)';
        if (delta > 120 || (delta > 60 && velocity > 0.5)) {
            activeSheet.classList.remove('active');
            activeSheet.style.transform = '';
            if (activeSheet.id.startsWith('sheet-')) document.getElementById('overlay').onclick = closeModals;
            else closeModals();
        } else activeSheet.style.transform = '';
        activeSheet = null;
    });
}

init();
