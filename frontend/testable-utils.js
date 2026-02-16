/**
 * Certify Intel - Testable Utility Functions
 *
 * Pure utility functions extracted from app_v2.js for testability.
 * In the browser these attach to window; in Node.js/Jest they export via module.exports.
 *
 * app_v2.js delegates to these implementations so there is a single source of truth.
 */

// ---------------------------------------------------------------------------
// escapeHtml
// ---------------------------------------------------------------------------
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ---------------------------------------------------------------------------
// formatDate
// ---------------------------------------------------------------------------
function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

// ---------------------------------------------------------------------------
// truncateText
// ---------------------------------------------------------------------------
function truncateText(text, maxLength) {
    if (!text) return '\u2014';
    const str = String(text);
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength) + '...';
}

// ---------------------------------------------------------------------------
// extractDomain
// ---------------------------------------------------------------------------
function extractDomain(url) {
    try { return new URL(url).hostname.replace('www.', ''); }
    catch { return ''; }
}

// ---------------------------------------------------------------------------
// debounce
// ---------------------------------------------------------------------------
function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ---------------------------------------------------------------------------
// getScoreColor
// ---------------------------------------------------------------------------
function getScoreColor(score) {
    if (score >= 70) return '#22c55e';
    if (score >= 50) return '#f59e0b';
    return '#ef4444';
}

// ---------------------------------------------------------------------------
// getMatchScore
// ---------------------------------------------------------------------------
function getMatchScore(candidate) {
    return candidate.match_score ?? candidate.qualification_score ?? candidate.relevance_score ?? candidate.score ?? null;
}

// ---------------------------------------------------------------------------
// getErrorMessage
// ---------------------------------------------------------------------------
function getErrorMessage(status, endpoint) {
    const messages = {
        400: 'Invalid request. Please check your input.',
        401: 'Session expired. Please log in again.',
        403: 'You do not have permission to access this resource.',
        404: 'The requested resource was not found.',
        408: 'Request timed out. Please try again.',
        429: 'Too many requests. Please wait a moment.',
        500: 'Server error. Our team has been notified.',
        502: 'Service temporarily unavailable. Please try again.',
        503: 'Service is under maintenance. Please try again later.',
        504: 'Request timed out. Please try again.'
    };
    return messages[status] || `An error occurred (${status})`;
}

// ---------------------------------------------------------------------------
// APIError
// ---------------------------------------------------------------------------
class APIError extends Error {
    constructor(status, message, endpoint) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.endpoint = endpoint;
    }
}

// ---------------------------------------------------------------------------
// Export / attach to window
// ---------------------------------------------------------------------------
const _exports = {
    escapeHtml,
    formatDate,
    truncateText,
    extractDomain,
    debounce,
    getScoreColor,
    getMatchScore,
    getErrorMessage,
    APIError,
};

if (typeof module !== 'undefined' && module.exports) {
    module.exports = _exports;
} else if (typeof window !== 'undefined') {
    Object.assign(window, _exports);
}
