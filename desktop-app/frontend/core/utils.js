/**
 * Certify Intel - Utility Functions Module
 * Pure utility functions with no side effects or dependencies on other modules.
 */

/**
 * Escape HTML special characters to prevent XSS
 */
export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Extract domain from a URL
 */
export function extractDomain(url) {
    try { return new URL(url).hostname.replace('www.', ''); }
    catch { return ''; }
}

/**
 * Debounce utility function
 */
export function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Format a date string into a readable format
 */
export function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

/**
 * Format file size from bytes to human-readable string
 */
export function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

/**
 * Truncate text to a max length with ellipsis
 */
export function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

/**
 * Format a field name from snake_case to Title Case
 */
export function formatFieldName(fieldName) {
    return fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Format a news date string with relative time
 */
export function formatNewsDate(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Format a source name for display
 */
export function formatSourceName(source) {
    if (!source) return 'Unknown';
    const sourceMap = {
        'google_news': 'Google News',
        'newsapi': 'NewsAPI',
        'rss': 'RSS Feed',
        'manual': 'Manual',
        'ai_discovery': 'AI Discovery'
    };
    return sourceMap[source] || source;
}

/**
 * Format activity timestamp
 */
export function formatActivityTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (!window.escapeHtml) window.escapeHtml = escapeHtml;
if (!window.extractDomain) window.extractDomain = extractDomain;
if (!window.debounce) window.debounce = debounce;
if (!window.formatDate) window.formatDate = formatDate;
if (!window.formatFileSize) window.formatFileSize = formatFileSize;
if (!window.truncateText) window.truncateText = truncateText;
if (!window.formatFieldName) window.formatFieldName = formatFieldName;
if (!window.formatNewsDate) window.formatNewsDate = formatNewsDate;
if (!window.formatSourceName) window.formatSourceName = formatSourceName;
if (!window.formatActivityTime) window.formatActivityTime = formatActivityTime;
