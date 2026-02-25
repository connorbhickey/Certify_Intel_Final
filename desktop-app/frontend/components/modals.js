/**
 * Certify Intel - Modal Component
 * Generic modal show/hide and loading overlay functions.
 */

// ============== Generic Modal ==============

/**
 * Show a modal with the given HTML content
 */
export function showModal(content) {
    const modal = document.getElementById('modal');
    const modalBody = document.getElementById('modalBody');
    const modalContent = modal.querySelector('.modal-content');
    modalBody.innerHTML = content;
    // Auto-detect wide content (battlecards, comparisons) and expand modal
    if (modalBody.querySelector('.battlecard-full') || modalBody.querySelector('.comparison-view')) {
        modalContent.classList.add('modal-wide');
    } else {
        modalContent.classList.remove('modal-wide');
    }
    modal.classList.add('active');
}

/**
 * Close the generic modal
 */
export function closeModal() {
    document.getElementById('modal').classList.remove('active');
}

// ============== Loading Overlay ==============

let loadingOverlay = null;

/**
 * Show a full-page loading overlay
 */
export function showLoading(text = 'Loading...') {
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loadingOverlay';
        loadingOverlay.className = 'loading-overlay';
        loadingOverlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <div class="loading-text">${text}</div>
            </div>
        `;
        document.body.appendChild(loadingOverlay);
    } else {
        const textEl = loadingOverlay.querySelector('.loading-text');
        if (textEl) textEl.textContent = text;
        loadingOverlay.style.display = 'flex';
    }
}

/**
 * Hide the loading overlay
 */
export function hideLoading() {
    if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
    }
}

/**
 * Update the text on the loading overlay
 */
export function updateLoadingText(text) {
    if (loadingOverlay) {
        const textEl = loadingOverlay.querySelector('.loading-text');
        if (textEl) textEl.textContent = text;
    }
}

/**
 * Set a button's loading state
 */
export function setButtonLoading(button, loading = true) {
    if (!button) return;
    if (loading) {
        button.dataset.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText || button.innerHTML;
    }
}

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (!window.showModal) window.showModal = showModal;
if (!window.closeModal) window.closeModal = closeModal;
if (!window.showLoading) window.showLoading = showLoading;
if (!window.hideLoading) window.hideLoading = hideLoading;
if (!window.updateLoadingText) window.updateLoadingText = updateLoadingText;
if (!window.setButtonLoading) window.setButtonLoading = setButtonLoading;
