/**
 * Certify Intel - Keyboard Navigation Manager
 * WCAG 2.1 AA: Keyboard shortcuts, focus trapping for modals, and screen reader announcements.
 */

(function() {
    'use strict';

    const shortcuts = {};

    /**
     * Register a keyboard shortcut.
     * @param {string} keys - Key combo e.g. "ctrl+k", "ctrl+/"
     * @param {Function} handler - Callback
     * @param {string} description - Human-readable description
     */
    function registerShortcut(keys, handler, description) {
        shortcuts[keys] = { handler, description };
    }

    /**
     * Initialize keyboard navigation and global listeners.
     */
    function initKeyboardNavigation() {
        document.addEventListener('keydown', (e) => {
            // Escape closes modals/dropdowns
            if (e.key === 'Escape') {
                const openModal = document.querySelector(
                    '.modal.show, .modal[style*="display: block"], .company-list-modal[style*="display: block"], .company-list-modal[style*="display: flex"]'
                );
                if (openModal) {
                    openModal.style.display = 'none';
                    if (openModal._triggerElement) {
                        openModal._triggerElement.focus();
                    }
                    return;
                }

                // Close open dropdowns
                const openDropdown = document.querySelector(
                    '.notification-dropdown[style*="display: block"], .user-dropdown[style*="display: block"], .ai-notification-panel[style*="display: block"]'
                );
                if (openDropdown) {
                    openDropdown.style.display = 'none';
                    return;
                }
            }

            // Ctrl + key shortcuts (only when not typing in input/textarea)
            if (e.ctrlKey && !e.shiftKey && !e.altKey) {
                const activeTag = document.activeElement?.tagName;
                if (activeTag === 'INPUT' || activeTag === 'TEXTAREA' || activeTag === 'SELECT') {
                    // Allow browser defaults in form fields (ctrl+a, ctrl+c, etc.)
                    if (['a', 'c', 'v', 'x', 'z'].includes(e.key)) return;
                }

                const key = `ctrl+${e.key}`;
                if (shortcuts[key]) {
                    e.preventDefault();
                    shortcuts[key].handler();
                }
            }
        });

        // Register default shortcuts
        registerShortcut('ctrl+k', () => {
            if (typeof window.toggleCommandPalette === 'function') {
                window.toggleCommandPalette();
            } else {
                const searchInput = document.getElementById('globalSearch');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }
        }, 'Command palette');

        registerShortcut('ctrl+/', () => showKeyboardHelp(), 'Show keyboard shortcuts');
    }

    /**
     * Trap focus within a container (for modals/dialogs).
     * Returns a cleanup function to remove the listener.
     * @param {HTMLElement} element - Container to trap focus within
     * @returns {Function} Cleanup function
     */
    function trapFocus(element) {
        const focusable = element.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return () => {};

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        function handleTab(e) {
            if (e.key !== 'Tab') return;
            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }

        element.addEventListener('keydown', handleTab);
        first.focus();

        return () => element.removeEventListener('keydown', handleTab);
    }

    /**
     * Announce a message to screen readers via the aria-live region.
     * @param {string} message - Text to announce
     */
    function announceToScreenReader(message) {
        const region = document.getElementById('sr-announcements');
        if (region) {
            region.textContent = message;
            // Clear after a delay so the same message can be announced again
            setTimeout(() => { region.textContent = ''; }, 3000);
        }
    }

    /**
     * Update aria-current on nav items when page changes.
     * @param {string} pageName - The data-page value of the active nav item
     */
    function updateNavAriaState(pageName) {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            if (item.dataset.page === pageName) {
                item.setAttribute('aria-current', 'page');
            } else {
                item.removeAttribute('aria-current');
            }
        });
    }

    /**
     * Show keyboard shortcuts help dialog.
     */
    function showKeyboardHelp() {
        const existing = document.getElementById('keyboardHelpDialog');
        if (existing) {
            existing.style.display = 'flex';
            return;
        }

        const overlay = document.createElement('div');
        overlay.id = 'keyboardHelpDialog';
        overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:10000;display:flex;align-items:center;justify-content:center;';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-label', 'Keyboard shortcuts');

        const dialog = document.createElement('div');
        dialog.style.cssText = 'background:var(--bg-secondary,#1e293b);color:var(--text-primary,#f1f5f9);border-radius:12px;padding:24px;max-width:400px;width:90%;max-height:80vh;overflow-y:auto;';

        const title = document.createElement('h3');
        title.textContent = 'Keyboard Shortcuts';
        title.style.cssText = 'margin:0 0 16px;font-size:18px;';
        dialog.appendChild(title);

        const table = document.createElement('table');
        table.style.cssText = 'width:100%;border-collapse:collapse;';

        Object.entries(shortcuts).forEach(([key, { description }]) => {
            const row = document.createElement('tr');
            const kbdCell = document.createElement('td');
            kbdCell.style.cssText = 'padding:8px 12px 8px 0;';
            const kbd = document.createElement('kbd');
            kbd.textContent = key;
            kbd.style.cssText = 'background:var(--bg-tertiary,#334155);padding:2px 8px;border-radius:4px;font-family:monospace;font-size:13px;';
            kbdCell.appendChild(kbd);
            const descCell = document.createElement('td');
            descCell.textContent = description;
            descCell.style.cssText = 'padding:8px 0;font-size:14px;';
            row.appendChild(kbdCell);
            row.appendChild(descCell);
            table.appendChild(row);
        });

        dialog.appendChild(table);

        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        closeBtn.setAttribute('aria-label', 'Close keyboard shortcuts');
        closeBtn.style.cssText = 'margin-top:16px;padding:8px 16px;background:var(--primary-color,#3b82f6);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;';
        closeBtn.onclick = () => { overlay.style.display = 'none'; };
        dialog.appendChild(closeBtn);

        overlay.appendChild(dialog);
        overlay.onclick = (e) => { if (e.target === overlay) overlay.style.display = 'none'; };
        document.body.appendChild(overlay);

        trapFocus(dialog);
    }

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initKeyboardNavigation);
    } else {
        initKeyboardNavigation();
    }

    // Expose to global scope for backward compatibility
    window.trapFocus = trapFocus;
    window.initKeyboardNavigation = initKeyboardNavigation;
    window.registerShortcut = registerShortcut;
    window.announceToScreenReader = announceToScreenReader;
    window.updateNavAriaState = updateNavAriaState;

})();
