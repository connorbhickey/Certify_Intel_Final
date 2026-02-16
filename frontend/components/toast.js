/**
 * Certify Intel - Toast Notification Component
 * Provides user feedback via temporary toast messages.
 */

const TOAST_ICONS = {
    success: '\u2713',
    error: '\u2715',
    warning: '\u26A0',
    info: '\u2139'
};

/**
 * Show a toast notification
 * @param {string} message - The message to display
 * @param {string} type - One of: 'success', 'error', 'warning', 'info'
 * @param {Object} options - Additional options
 * @param {string} options.title - Optional title line
 * @param {number} options.duration - Auto-dismiss duration in ms (default 5000, 0 = persistent)
 * @param {boolean} options.closable - Show close button (default true)
 * @returns {HTMLElement} The toast element
 */
export function showToast(message, type = 'info', options = {}) {
    const { title, duration = 5000, closable = true } = options;

    // Ensure toast container exists
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${TOAST_ICONS[type] || '\u2139'}</span>
        <div class="toast-content">
            ${title ? `<div class="toast-title">${title}</div>` : ''}
            <div class="toast-message">${message}</div>
        </div>
        ${closable ? '<button class="toast-close" onclick="this.parentElement.remove()">&times;</button>' : ''}
    `;

    container.appendChild(toast);

    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            toast.classList.add('exiting');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    return toast;
}

// Alias for backward compatibility
export const showNotification = showToast;

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (!window.showToast) window.showToast = showToast;
if (!window.showNotification) window.showNotification = showToast;
