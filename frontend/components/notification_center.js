/**
 * Certify Intel - Notification Center
 * Client-side notification management with localStorage persistence.
 * Integrates with existing AI task notifications and page events.
 */
(function () {
    'use strict';

    const STORAGE_KEY = 'ci_notifications';
    const MAX_NOTIFICATIONS = 50;
    const AUTO_DISMISS_MS = 24 * 60 * 60 * 1000; // 24 hours

    let notifications = [];
    let panelOpen = false;

    // ---- Storage ----

    function loadFromStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                notifications = JSON.parse(raw);
                // Prune expired
                const now = Date.now();
                notifications = notifications.filter(n => now - n.timestamp < AUTO_DISMISS_MS);
            }
        } catch {
            notifications = [];
        }
    }

    function saveToStorage() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications.slice(0, MAX_NOTIFICATIONS)));
        } catch {
            // localStorage full
        }
    }

    // ---- Public API ----

    function addNotification(type, title, message, meta) {
        const notif = {
            id: Date.now() + '_' + Math.random().toString(36).substring(2, 7),
            type: type || 'info', // info, success, warning, error
            title: title || '',
            message: message || '',
            timestamp: Date.now(),
            read: false,
            meta: meta || null,
        };

        notifications.unshift(notif);
        if (notifications.length > MAX_NOTIFICATIONS) {
            notifications = notifications.slice(0, MAX_NOTIFICATIONS);
        }

        saveToStorage();
        updateBadge();
        renderPanel();

        return notif.id;
    }

    function markAsRead(id) {
        const notif = notifications.find(n => n.id === id);
        if (notif) {
            notif.read = true;
            saveToStorage();
            updateBadge();
            renderPanel();
        }
    }

    function markAllAsRead() {
        notifications.forEach(n => { n.read = true; });
        saveToStorage();
        updateBadge();
        renderPanel();
    }

    function dismissNotification(id) {
        notifications = notifications.filter(n => n.id !== id);
        saveToStorage();
        updateBadge();
        renderPanel();
    }

    function clearAll() {
        notifications = [];
        saveToStorage();
        updateBadge();
        renderPanel();
    }

    // ---- Badge ----

    function getUnreadCount() {
        return notifications.filter(n => !n.read).length;
    }

    function updateBadge() {
        const badge = document.getElementById('notifCenterBadge');
        if (!badge) return;

        const count = getUnreadCount();
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }

    // ---- Panel ----

    function createPanelDOM() {
        if (document.getElementById('notifCenterPanel')) return;

        const panel = document.createElement('div');
        panel.id = 'notifCenterPanel';
        panel.className = 'notif-center-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Notification center');

        const backdrop = document.createElement('div');
        backdrop.id = 'notifCenterBackdrop';
        backdrop.className = 'notif-center-backdrop';
        backdrop.addEventListener('click', closePanel);

        document.body.appendChild(backdrop);
        document.body.appendChild(panel);
    }

    function openPanel() {
        createPanelDOM();
        const panel = document.getElementById('notifCenterPanel');
        const backdrop = document.getElementById('notifCenterBackdrop');
        if (!panel || !backdrop) return;

        panelOpen = true;
        panel.classList.add('open');
        backdrop.classList.add('open');
        renderPanel();
    }

    function closePanel() {
        const panel = document.getElementById('notifCenterPanel');
        const backdrop = document.getElementById('notifCenterBackdrop');
        if (panel) panel.classList.remove('open');
        if (backdrop) backdrop.classList.remove('open');
        panelOpen = false;
    }

    function togglePanel() {
        if (panelOpen) {
            closePanel();
        } else {
            openPanel();
        }
    }

    function renderPanel() {
        const panel = document.getElementById('notifCenterPanel');
        if (!panel) return;

        // Header
        const unread = getUnreadCount();
        let html = '';

        // Build header
        const header = document.createElement('div');
        header.className = 'notif-center-header';

        const titleEl = document.createElement('h3');
        titleEl.textContent = 'Notifications';
        header.appendChild(titleEl);

        const headerActions = document.createElement('div');
        headerActions.className = 'notif-center-header-actions';

        if (unread > 0) {
            const markAllBtn = document.createElement('button');
            markAllBtn.className = 'notif-center-action-btn';
            markAllBtn.textContent = 'Mark all read';
            markAllBtn.addEventListener('click', markAllAsRead);
            headerActions.appendChild(markAllBtn);
        }

        if (notifications.length > 0) {
            const clearBtn = document.createElement('button');
            clearBtn.className = 'notif-center-action-btn';
            clearBtn.textContent = 'Clear all';
            clearBtn.addEventListener('click', clearAll);
            headerActions.appendChild(clearBtn);
        }

        const closeBtn = document.createElement('button');
        closeBtn.className = 'notif-center-close-btn';
        closeBtn.textContent = '\u2715';
        closeBtn.setAttribute('aria-label', 'Close notification panel');
        closeBtn.addEventListener('click', closePanel);
        headerActions.appendChild(closeBtn);

        header.appendChild(headerActions);

        // Body
        const body = document.createElement('div');
        body.className = 'notif-center-body';

        if (notifications.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'notif-center-empty';
            empty.textContent = 'No notifications';
            body.appendChild(empty);
        } else {
            notifications.forEach(n => {
                const item = document.createElement('div');
                item.className = 'notif-center-item' + (n.read ? '' : ' unread');
                item.dataset.id = n.id;

                const iconMap = {
                    success: '\u2705',
                    warning: '\u26A0\uFE0F',
                    error: '\u274C',
                    info: '\u{1F514}',
                };

                const icon = document.createElement('span');
                icon.className = 'notif-center-item-icon';
                icon.textContent = iconMap[n.type] || iconMap.info;

                const content = document.createElement('div');
                content.className = 'notif-center-item-content';

                const title = document.createElement('div');
                title.className = 'notif-center-item-title';
                title.textContent = n.title;

                const msg = document.createElement('div');
                msg.className = 'notif-center-item-message';
                msg.textContent = n.message;

                const time = document.createElement('div');
                time.className = 'notif-center-item-time';
                time.textContent = formatTimeAgo(n.timestamp);

                content.appendChild(title);
                if (n.message) content.appendChild(msg);
                content.appendChild(time);

                const actions = document.createElement('div');
                actions.className = 'notif-center-item-actions';

                if (!n.read) {
                    const readBtn = document.createElement('button');
                    readBtn.className = 'notif-item-btn';
                    readBtn.title = 'Mark as read';
                    readBtn.textContent = '\u2713';
                    readBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        markAsRead(n.id);
                    });
                    actions.appendChild(readBtn);
                }

                const dismissBtn = document.createElement('button');
                dismissBtn.className = 'notif-item-btn';
                dismissBtn.title = 'Dismiss';
                dismissBtn.textContent = '\u2715';
                dismissBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    dismissNotification(n.id);
                });
                actions.appendChild(dismissBtn);

                item.appendChild(icon);
                item.appendChild(content);
                item.appendChild(actions);
                body.appendChild(item);
            });
        }

        panel.innerHTML = '';
        panel.appendChild(header);
        panel.appendChild(body);
    }

    function formatTimeAgo(ts) {
        const diff = Date.now() - ts;
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'Just now';
        if (mins < 60) return mins + 'm ago';
        const hours = Math.floor(mins / 60);
        if (hours < 24) return hours + 'h ago';
        const days = Math.floor(hours / 24);
        return days + 'd ago';
    }

    // ---- Event hooks ----

    function hookIntoExistingEvents() {
        // Listen for AI task completions
        const origShowToast = window.showToast;
        if (origShowToast && !window._notifCenterHooked) {
            window._notifCenterHooked = true;
            window.showToast = function (message, type) {
                // Only capture success/error toasts as notifications
                if (type === 'success' && message && (
                    message.includes('exported') ||
                    message.includes('generated') ||
                    message.includes('completed') ||
                    message.includes('discovery') ||
                    message.includes('battlecard') ||
                    message.includes('refresh')
                )) {
                    addNotification('success', 'Task Complete', message);
                } else if (type === 'error' && message) {
                    addNotification('error', 'Error', message);
                }
                return origShowToast.apply(this, arguments);
            };
        }
    }

    // ---- Sidebar button injection ----

    function injectSidebarButton() {
        const sidebar = document.querySelector('.sidebar-footer');
        if (!sidebar) return;
        if (document.getElementById('notifCenterBtn')) return;

        const btn = document.createElement('button');
        btn.id = 'notifCenterBtn';
        btn.className = 'notif-center-sidebar-btn';
        btn.setAttribute('aria-label', 'Open notification center');
        btn.addEventListener('click', togglePanel);

        const bellIcon = document.createElement('span');
        bellIcon.className = 'notif-center-bell';
        bellIcon.textContent = '\u{1F514}';

        const label = document.createElement('span');
        label.textContent = 'Notifications';

        const badge = document.createElement('span');
        badge.id = 'notifCenterBadge';
        badge.className = 'notif-center-badge';
        badge.style.display = 'none';

        btn.appendChild(bellIcon);
        btn.appendChild(label);
        btn.appendChild(badge);

        sidebar.insertBefore(btn, sidebar.firstChild);
    }

    // ---- Init ----

    function init() {
        loadFromStorage();
        injectSidebarButton();
        updateBadge();
        hookIntoExistingEvents();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose
    window.NotificationCenter = {
        add: addNotification,
        markAsRead,
        markAllAsRead,
        dismiss: dismissNotification,
        clearAll,
        open: openPanel,
        close: closePanel,
        toggle: togglePanel,
        getUnreadCount,
    };
})();
