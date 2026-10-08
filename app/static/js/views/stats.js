import { pluralize } from '../dates.js';
import { escapeHtml } from '../ui/dom.js';

const WEEKDAY_SHORT = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];

export function renderStatsSkeleton(container) {
    container.innerHTML = `<div class="stats-grid">${'<div class="skeleton" style="height:96px;margin:0"></div>'.repeat(4)}</div><div class="skeleton" style="height:180px"></div>`;
}

export function renderStats(container, stats) {
    const max = Math.max(1, ...stats.week.map((d) => d.count));
    const bars = stats.week.map((d) => {
        const date = new Date(`${d.date}T00:00:00`);
        const h = Math.round((d.count / max) * 100);
        return `
            <div class="bar">
                <span class="num">${d.count || ''}</span>
                <div class="fill ${d.count ? '' : 'zero'}" style="height:${d.count ? h : 3}%"></div>
                <span class="day-label">${WEEKDAY_SHORT[date.getDay()]}</span>
            </div>`;
    }).join('');

    const memberMax = Math.max(1, ...stats.members.map((m) => m.done_week));
    const members = stats.members.map((m) => `
        <div class="member">
            <span class="name">${escapeHtml(m.name)}</span>
            <span class="progress"><div style="width:${Math.round((m.done_week / memberMax) * 100)}%"></div></span>
            <span class="count">${m.done_week}</span>
        </div>`).join('');

    const levels = stats.members.map((m) => `
        <div class="level">
            <div class="level-head"><span class="name">${escapeHtml(m.name)}</span><span class="lvl">Ур. ${m.level} · ${m.xp} XP</span></div>
            <span class="progress"><div style="width:${Math.round((m.level_xp / m.level_xp_needed) * 100)}%"></div></span>
            <div class="badges">${m.badges.map((b) => `<span class="badge ${b.earned ? '' : 'locked'}" title="${escapeHtml(b.title)}">${b.icon}</span>`).join('')}</div>
        </div>`).join('');

    const percent = stats.total ? Math.round((stats.done / stats.total) * 100) : 0;
    const streakText = stats.streak_days
        ? `${stats.streak_days} ${pluralize(stats.streak_days, 'день', 'дня', 'дней')} подряд`
        : 'Выполните задачу сегодня';

    container.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="icon">✅</div><div class="value">${stats.done_this_week}</div><div class="label">выполнено за неделю</div></div>
            <div class="stat-card"><div class="icon">🔥</div><div class="value">${stats.streak_days}</div><div class="label">${escapeHtml(streakText)}</div></div>
            <div class="stat-card"><div class="icon">📋</div><div class="value">${stats.pending}</div><div class="label">в работе</div></div>
            <div class="stat-card"><div class="icon">⏰</div><div class="value" style="${stats.overdue ? 'color:var(--danger)' : ''}">${stats.overdue}</div><div class="label">просрочено</div></div>
        </div>
        <div class="card">
            <h3>Уровни и достижения</h3>
            ${levels}
        </div>
        <div class="card">
            <h3>Последние 7 дней</h3>
            <div class="bars">${bars}</div>
        </div>
        <div class="card">
            <h3>Кто сколько сделал за неделю</h3>
            ${members}
        </div>
        <div class="card">
            <h3>Всего</h3>
            <div class="member"><span class="name">Задач</span><span class="count">${stats.total}</span></div>
            <div class="member"><span class="name">Выполнено</span><span class="progress"><div style="width:${percent}%"></div></span><span class="count">${percent}%</span></div>
        </div>`;
}
