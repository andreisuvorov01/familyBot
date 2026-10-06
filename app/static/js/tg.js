// Обёртка над Telegram.WebApp: проверки версий, промисы вместо колбэков, запасные варианты для браузера.
const WebApp = window.Telegram?.WebApp;

export const tg = WebApp;
export const inTelegram = Boolean(WebApp && WebApp.initData);

export function supports(version) {
    try {
        return Boolean(WebApp?.isVersionAtLeast?.(version));
    } catch {
        return false;
    }
}

function safe(fn) {
    try {
        fn();
    } catch {
        /* метод не поддерживается этой версией клиента */
    }
}

export const haptic = {
    impact: (style = 'light') => safe(() => supports('6.1') && WebApp.HapticFeedback.impactOccurred(style)),
    success: () => safe(() => supports('6.1') && WebApp.HapticFeedback.notificationOccurred('success')),
    error: () => safe(() => supports('6.1') && WebApp.HapticFeedback.notificationOccurred('error')),
    warning: () => safe(() => supports('6.1') && WebApp.HapticFeedback.notificationOccurred('warning')),
    select: () => safe(() => supports('6.1') && WebApp.HapticFeedback.selectionChanged()),
};

export function applyThemeClass() {
    const root = document.documentElement;
    root.classList.toggle('tg-dark', WebApp?.colorScheme === 'dark');
    root.classList.toggle('tg-light', WebApp?.colorScheme === 'light');
}

export function setupTelegram({ onSettings } = {}) {
    if (!WebApp) return;
    safe(() => WebApp.ready());
    safe(() => WebApp.expand());
    if (supports('7.7')) safe(() => WebApp.disableVerticalSwipes()); // жест вниз не сворачивает приложение
    if (supports('6.1')) {
        safe(() => WebApp.setHeaderColor('secondary_bg_color'));
        safe(() => WebApp.setBackgroundColor('secondary_bg_color'));
    }
    if (supports('7.10')) safe(() => WebApp.setBottomBarColor('secondary_bg_color'));

    const platform = WebApp.platform || '';
    document.body.classList.add(['ios', 'macos'].includes(platform) ? 'is-ios' : 'is-android');

    applyThemeClass();
    WebApp.onEvent?.('themeChanged', applyThemeClass);

    if (onSettings && supports('7.0')) {
        safe(() => {
            WebApp.SettingsButton.show();
            WebApp.SettingsButton.onClick(onSettings);
        });
    }
}

export function onAppActivated(callback) {
    // activated — Bot API 8.0; visibilitychange — запасной вариант
    safe(() => WebApp?.onEvent?.('activated', callback));
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') callback();
    });
}

export function showAlert(message) {
    return new Promise((resolve) => {
        if (supports('6.2')) WebApp.showAlert(message, resolve);
        else {
            window.alert(message);
            resolve();
        }
    });
}

export function showConfirm(message) {
    return new Promise((resolve) => {
        if (supports('6.2')) WebApp.showConfirm(message, (ok) => resolve(Boolean(ok)));
        else resolve(window.confirm(message));
    });
}

export function showPopup(params) {
    return new Promise((resolve) => {
        if (supports('6.2')) WebApp.showPopup(params, (id) => resolve(id || null));
        else {
            const options = params.buttons.filter((b) => b.id);
            const answer = window.prompt(`${params.message}\n${options.map((b, i) => `${i + 1}. ${b.text}`).join('\n')}`);
            const index = Number(answer) - 1;
            resolve(options[index]?.id ?? null);
        }
    });
}

export function openLink(url) {
    if (WebApp?.openLink) WebApp.openLink(url);
    else window.open(url, '_blank', 'noopener');
}

export function startParam() {
    const fromUrl = new URLSearchParams(window.location.search);
    return WebApp?.initDataUnsafe?.start_param || fromUrl.get('startapp') || (fromUrl.get('task') ? `task_${fromUrl.get('task')}` : null);
}

export function currentUser() {
    return WebApp?.initDataUnsafe?.user || null;
}

// --- Хранилище настроек интерфейса: CloudStorage (синхронизируется между устройствами) или localStorage ---
export const storage = {
    async get(key) {
        if (supports('6.9')) {
            const value = await new Promise((resolve) => {
                try {
                    WebApp.CloudStorage.getItem(key, (err, v) => resolve(err ? null : v));
                } catch {
                    resolve(null);
                }
            });
            if (value) return value;
        }
        try {
            return window.localStorage.getItem(key);
        } catch {
            return null;
        }
    },
    async set(key, value) {
        if (supports('6.9')) safe(() => WebApp.CloudStorage.setItem(key, String(value)));
        try {
            window.localStorage.setItem(key, String(value));
        } catch {
            /* приватный режим */
        }
    },
};

// --- MainButton / BackButton с одним активным обработчиком ---
let mainHandler = null;
export const mainButton = {
    available: () => inTelegram && Boolean(WebApp?.MainButton),
    show(text, handler) {
        if (!this.available()) return false;
        if (mainHandler) WebApp.MainButton.offClick(mainHandler);
        mainHandler = handler;
        WebApp.MainButton.setText(text);
        WebApp.MainButton.onClick(mainHandler);
        WebApp.MainButton.enable();
        WebApp.MainButton.show();
        return true;
    },
    hide() {
        if (!this.available()) return;
        if (mainHandler) WebApp.MainButton.offClick(mainHandler);
        mainHandler = null;
        WebApp.MainButton.hideProgress();
        WebApp.MainButton.hide();
    },
    progress(on) {
        if (!this.available()) return;
        if (on) WebApp.MainButton.showProgress(false);
        else WebApp.MainButton.hideProgress();
    },
};

let backHandler = null;
export const backButton = {
    show(handler) {
        if (!supports('6.1')) return;
        if (backHandler) WebApp.BackButton.offClick(backHandler);
        backHandler = handler;
        WebApp.BackButton.onClick(backHandler);
        WebApp.BackButton.show();
    },
    hide() {
        if (!supports('6.1')) return;
        if (backHandler) WebApp.BackButton.offClick(backHandler);
        backHandler = null;
        WebApp.BackButton.hide();
    },
};
