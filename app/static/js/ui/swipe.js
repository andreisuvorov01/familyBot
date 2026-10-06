// Свайпы по карточкам задач: вправо — выполнить, влево — удалить.
const THRESHOLD = 90;

export function attachSwipe(container, { onSwipeRight, onSwipeLeft }) {
    let row = null;
    let card = null;
    let startX = 0;
    let startY = 0;
    let dx = 0;
    let locked = null; // 'x' | 'y'

    container.addEventListener('touchstart', (e) => {
        card = e.target.closest('.task-card');
        if (!card || e.target.closest('.check')) {
            card = null;
            return;
        }
        row = card.parentElement;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        dx = 0;
        locked = null;
    }, { passive: true });

    container.addEventListener('touchmove', (e) => {
        if (!card) return;
        const x = e.touches[0].clientX - startX;
        const y = e.touches[0].clientY - startY;
        if (!locked) {
            if (Math.abs(x) < 8 && Math.abs(y) < 8) return;
            locked = Math.abs(x) > Math.abs(y) * 1.2 ? 'x' : 'y';
        }
        if (locked !== 'x') return;
        if (e.cancelable) e.preventDefault();
        dx = x;
        card.style.transition = 'none';
        card.style.transform = `translateX(${dx}px)`;
        row.classList.toggle('swiping-right', dx > 0);
        row.classList.toggle('swiping-left', dx < 0);
        card.dataset.swiped = '1';
    }, { passive: false });

    container.addEventListener('touchend', () => {
        if (!card) return;
        const el = card;
        const parent = row;
        const id = Number(el.dataset.id);
        card = null;
        el.style.transition = '';
        if (locked === 'x' && dx > THRESHOLD) {
            el.style.transform = '';
            onSwipeRight(id);
        } else if (locked === 'x' && dx < -THRESHOLD) {
            el.style.transform = 'translateX(-110%)';
            onSwipeLeft(id);
        } else {
            el.style.transform = '';
        }
        setTimeout(() => {
            parent.classList.remove('swiping-left', 'swiping-right');
            delete el.dataset.swiped;
        }, 250);
    });
}
