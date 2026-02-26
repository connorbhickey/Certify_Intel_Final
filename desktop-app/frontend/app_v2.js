/**
 * Certify Intel - Dashboard JavaScript
 * Frontend logic for competitive intelligence dashboard
 */

const API_BASE = window.location.origin;

// ==============================================================================
// GLOBAL ERROR HANDLERS - Catch all unhandled errors (Phase 2)
// ==============================================================================

// Catch synchronous errors - only log, don't show toast for every error
window.onerror = function(message, source, lineno, colno, error) {
    console.error('Global error:', { message, source, lineno, colno, error });
    // Only show toast for critical errors, not routine ones
    // This prevents error spam from API calls that are handled elsewhere
    return false; // Let errors propagate to console for debugging
};

// Catch unhandled promise rejections - only log, don't show toast
window.onunhandledrejection = function(event) {
    console.error('Unhandled promise rejection:', event.reason);
};

/**
 * Safe button click wrapper - ensures all button actions have proper error handling
 * @param {HTMLElement} button - The button element
 * @param {Function} asyncFn - The async function to execute
 * @param {string} successMsg - Optional success message
 */
async function safeButtonClick(button, asyncFn, successMsg = null) {
    if (!button) return;

    const originalHTML = button.innerHTML;
    const originalDisabled = button.disabled;

    try {
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';

        await asyncFn();

        if (successMsg) {
            showToast(successMsg, 'success');
        }
    } catch (error) {
        console.error('Button action failed:', error);
        showToast(error.message || 'Action failed. Please try again.', 'error');
    } finally {
        button.disabled = originalDisabled;
        button.innerHTML = originalHTML;
    }
}

// Make safeButtonClick globally available
window.safeButtonClick = safeButtonClick;

// ==============================================================================
// P3-8: WEBSOCKET REAL-TIME UPDATES
// ==============================================================================

/**
 * WebSocket client for real-time updates from the server.
 * Supports automatic reconnection and event-based subscriptions.
 */
class RealtimeUpdates {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.listeners = {};
        this.connected = false;
        this.subscriptions = ['all'];
    }

    /**
     * Connect to the WebSocket server
     * @param {Array<string>} subscriptions - Event types to subscribe to
     */
    connect(subscriptions = ['all']) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        this.subscriptions = subscriptions;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/updates?subscribe=${subscriptions.join(',')}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                this.connected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                this.emit('connected', { subscriptions: this.subscriptions });
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (e) {
                    console.error('[WS] Failed to parse message:', e);
                }
            };

            this.ws.onclose = (event) => {
                this.connected = false;
                this.emit('disconnected', { code: event.code, reason: event.reason });
                this.attemptReconnect();
            };

            this.ws.onerror = (error) => {
                console.error('[WS] Error:', error);
                this.emit('error', { error });
            };
        } catch (error) {
            console.error('[WS] Failed to create WebSocket:', error);
        }
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(data) {
        const eventType = data.event_type || data.type;

        // Emit specific event
        this.emit(eventType, data);

        // Also emit to 'message' listeners for any message
        this.emit('message', data);

        // Handle specific message types with UI updates
        switch (eventType) {
            case 'refresh_progress':
                this.handleRefreshProgress(data);
                break;
            case 'competitor_update':
                this.handleCompetitorUpdate(data);
                break;
            case 'news_alert':
                this.handleNewsAlert(data);
                break;
            case 'discovery_result':
                this.handleDiscoveryResult(data);
                break;
            case 'system_notification':
                this.handleSystemNotification(data);
                break;
        }
    }

    /**
     * Handle refresh progress updates
     */
    handleRefreshProgress(data) {
        // Update any refresh progress indicators on the page
        const progressBar = document.querySelector('.refresh-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${data.progress}%`;
        }
        const statusText = document.querySelector('.refresh-status-text');
        if (statusText) {
            statusText.textContent = `${data.competitor}: ${data.status}`;
        }
    }

    /**
     * Handle competitor data updates
     */
    handleCompetitorUpdate(data) {
        // Update competitors array if available
        if (typeof competitors !== 'undefined') {
            const comp = competitors.find(c => c.id === data.competitor_id);
            if (comp && data.field) {
                comp[data.field] = data.new_value;
            }
        }
        // Show subtle notification
        if (typeof showToast === 'function') {
            showToast(`${data.competitor_name}: ${data.field} updated`, 'info', { duration: 3000 });
        }
    }

    /**
     * Handle news alerts
     */
    handleNewsAlert(data) {
        if (typeof showToast === 'function') {
            showToast(`📰 ${data.competitor}: ${data.headline}`, 'info', {
                title: 'News Alert',
                duration: 5000
            });
        }
    }

    /**
     * Handle discovery results
     */
    handleDiscoveryResult(data) {
        if (typeof showToast === 'function') {
            showToast(`Found ${data.total_found} potential competitors`, 'success', {
                title: 'Discovery Complete'
            });
        }
    }

    /**
     * Handle system notifications
     */
    handleSystemNotification(data) {
        if (typeof showToast === 'function') {
            showToast(data.message, data.level || 'info', {
                title: data.title
            });
        }
    }

    /**
     * Attempt to reconnect with exponential backoff
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.emit('reconnect_failed', {});
            return;
        }

        this.reconnectAttempts++;

        setTimeout(() => {
            this.connect(this.subscriptions);
        }, this.reconnectDelay);

        // Exponential backoff with max of 30 seconds
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    }

    /**
     * Send a message to the server
     */
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    /**
     * Subscribe to an event type
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
        return this; // Allow chaining
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        }
    }

    /**
     * Emit an event to all listeners
     */
    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`[WS] Error in ${event} listener:`, e);
                }
            });
        }
    }

    /**
     * Update subscriptions
     */
    updateSubscriptions(subscriptions) {
        this.subscriptions = subscriptions;
        this.send({
            type: 'subscribe',
            subscriptions: subscriptions
        });
    }

    /**
     * Send a ping to keep connection alive
     */
    ping() {
        this.send({ type: 'ping' });
    }

    /**
     * Disconnect from the server
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Create global instance
const realtimeUpdates = new RealtimeUpdates();

// Auto-connect when page loads (if not in desktop app which may not support WS)
document.addEventListener('DOMContentLoaded', () => {
    // Only connect if we have a valid session (token exists)
    if (localStorage.getItem('access_token')) {
        // Small delay to ensure page is fully loaded
        setTimeout(() => {
            try {
                realtimeUpdates.connect(['refresh_progress', 'competitor_update', 'news_alert', 'system_notification']);
            } catch (e) {
            }
        }, 1000);
    }
});

// Make available globally
window.realtimeUpdates = realtimeUpdates;

// ==============================================================================
// FORM VALIDATION SYSTEM (P1-4)
// ==============================================================================

/**
 * Validation rules for common field types
 */
const validationRules = {
    required: (value) => {
        if (!value || (typeof value === 'string' && !value.trim())) {
            return 'This field is required';
        }
        return null;
    },
    url: (value) => {
        if (!value) return null; // Not required, skip if empty
        try {
            const url = new URL(value);
            if (!['http:', 'https:'].includes(url.protocol)) {
                return 'URL must start with http:// or https://';
            }
            return null;
        } catch {
            return 'Please enter a valid URL (e.g., https://example.com)';
        }
    },
    email: (value) => {
        if (!value) return null;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            return 'Please enter a valid email address';
        }
        return null;
    },
    minLength: (min) => (value) => {
        if (!value) return null;
        if (value.length < min) {
            return `Must be at least ${min} characters`;
        }
        return null;
    },
    maxLength: (max) => (value) => {
        if (!value) return null;
        if (value.length > max) {
            return `Must be no more than ${max} characters`;
        }
        return null;
    },
    number: (value) => {
        if (!value) return null;
        if (isNaN(Number(value))) {
            return 'Please enter a valid number';
        }
        return null;
    },
    positiveNumber: (value) => {
        if (!value) return null;
        const num = Number(value);
        if (isNaN(num) || num < 0) {
            return 'Please enter a positive number';
        }
        return null;
    }
};

/**
 * Validate a single field
 * @param {HTMLElement} input - The input element
 * @param {Array<Function>} rules - Array of validation rule functions
 * @returns {string|null} Error message or null if valid
 */
function validateField(input, rules) {
    const value = input.value;
    for (const rule of rules) {
        const error = rule(value);
        if (error) return error;
    }
    return null;
}

/**
 * Show validation error on a field
 * @param {HTMLElement} input - The input element
 * @param {string} message - Error message
 */
function showFieldError(input, message) {
    // Remove any existing error
    clearFieldError(input);

    // Add error styling to input
    input.classList.add('input-error');

    // Create and insert error message
    const errorEl = document.createElement('div');
    errorEl.className = 'field-error-message';
    errorEl.textContent = message;
    errorEl.id = `error-${input.name || input.id || Date.now()}`;

    // Insert after the input
    input.parentElement.appendChild(errorEl);
}

/**
 * Clear validation error from a field
 * @param {HTMLElement} input - The input element
 */
function clearFieldError(input) {
    input.classList.remove('input-error');
    const errorEl = input.parentElement.querySelector('.field-error-message');
    if (errorEl) errorEl.remove();
}

/**
 * Validate an entire form
 * @param {HTMLFormElement} form - The form element
 * @param {Object} fieldRules - Object mapping field names to arrays of validation rules
 * @returns {boolean} True if valid, false otherwise
 */
function validateForm(form, fieldRules) {
    let isValid = true;

    // Clear all existing errors first
    form.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
    form.querySelectorAll('.field-error-message').forEach(el => el.remove());

    // Validate each field
    for (const [fieldName, rules] of Object.entries(fieldRules)) {
        const input = form.querySelector(`[name="${fieldName}"]`);
        if (!input) continue;

        const error = validateField(input, rules);
        if (error) {
            showFieldError(input, error);
            isValid = false;
        }
    }

    return isValid;
}

/**
 * Setup real-time validation on form inputs
 * @param {HTMLFormElement} form - The form element
 * @param {Object} fieldRules - Object mapping field names to arrays of validation rules
 */
function setupRealtimeValidation(form, fieldRules) {
    for (const [fieldName, rules] of Object.entries(fieldRules)) {
        const input = form.querySelector(`[name="${fieldName}"]`);
        if (!input) continue;

        // Validate on blur (when user leaves field)
        input.addEventListener('blur', () => {
            const error = validateField(input, rules);
            if (error) {
                showFieldError(input, error);
            } else {
                clearFieldError(input);
            }
        });

        // Clear error when user starts typing
        input.addEventListener('input', () => {
            if (input.classList.contains('input-error')) {
                clearFieldError(input);
            }
        });
    }
}

// Make validation functions globally available
window.validationRules = validationRules;
window.validateField = validateField;
window.showFieldError = showFieldError;
window.clearFieldError = clearFieldError;
window.validateForm = validateForm;
window.setupRealtimeValidation = setupRealtimeValidation;

// ==============================================================================
// PHASE 3: SKELETON LOADING STATE SYSTEM
// ==============================================================================

/**
 * Show skeleton loading state in a container
 * @param {string} containerId - The ID of the container element
 * @param {string} type - Type of skeleton: 'table', 'cards', 'stats', 'list', 'chart'
 * @param {number} count - Number of skeleton items to show (default: 5)
 */
function showSkeleton(containerId, type = 'table', count = 5) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const skeletons = {
        table: `
            <div class="skeleton-table">
                <div class="skeleton-row skeleton-header"></div>
                ${Array(count).fill('<div class="skeleton-row"></div>').join('')}
            </div>
        `,
        cards: `
            <div class="skeleton-grid">
                ${Array(count).fill('<div class="skeleton-card"><div class="skeleton-card-header"></div><div class="skeleton-card-body"></div><div class="skeleton-card-footer"></div></div>').join('')}
            </div>
        `,
        stats: `
            <div class="skeleton-stats">
                ${Array(count).fill('<div class="skeleton-stat"><div class="skeleton-stat-value"></div><div class="skeleton-stat-label"></div></div>').join('')}
            </div>
        `,
        list: `
            <div class="skeleton-list">
                ${Array(count).fill('<div class="skeleton-list-item"><div class="skeleton-avatar"></div><div class="skeleton-text-block"><div class="skeleton-line"></div><div class="skeleton-line short"></div></div></div>').join('')}
            </div>
        `,
        chart: `
            <div class="skeleton-chart">
                <div class="skeleton-chart-bars">
                    ${Array(7).fill('<div class="skeleton-bar"></div>').join('')}
                </div>
            </div>
        `
    };

    container.innerHTML = skeletons[type] || skeletons.table;
    container.classList.add('loading');
}

/**
 * Hide skeleton and show actual content
 * @param {string} containerId - The ID of the container element
 */
function hideSkeleton(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.classList.remove('loading');
}

/**
 * Show inline loading indicator for buttons or small areas
 * @param {HTMLElement} element - The element to show loading in
 * @param {string} text - Loading text to display
 */
function showInlineLoading(element, text = 'Loading...') {
    if (!element) return;
    element.dataset.originalContent = element.innerHTML;
    element.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
    element.disabled = true;
}

/**
 * Hide inline loading and restore original content
 * @param {HTMLElement} element - The element to restore
 */
function hideInlineLoading(element) {
    if (!element || !element.dataset.originalContent) return;
    element.innerHTML = element.dataset.originalContent;
    element.disabled = false;
    delete element.dataset.originalContent;
}

// ==============================================================================
// PHASE 4: EMPTY STATE SYSTEM
// ==============================================================================

/**
 * Show empty state in a container
 * @param {string} containerId - The ID of the container element
 * @param {object} config - Configuration for the empty state
 * @param {string} config.icon - FontAwesome icon class (e.g., 'fa-inbox')
 * @param {string} config.title - Title text
 * @param {string} config.message - Description message
 * @param {object} config.action - Optional action button { text: string, onClick: string }
 * @param {string} config.type - Type: 'empty', 'error', 'no-results', 'first-use'
 */
function showEmptyState(containerId, config = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const {
        icon = 'fa-inbox',
        title = 'No Data',
        message = 'No data available.',
        action = null,
        type = 'empty'
    } = config;

    const iconColor = type === 'error' ? 'var(--danger, #ef4444)' : 'var(--text-muted, #64748b)';

    container.innerHTML = `
        <div class="empty-state empty-state-${type}" style="text-align: center; padding: 60px 20px;">
            <i class="fas ${icon}" style="font-size: 3rem; color: ${iconColor}; opacity: 0.5; margin-bottom: 20px; display: block;"></i>
            <h4 style="color: var(--text-primary, #f8fafc); margin-bottom: 10px;">${title}</h4>
            <p style="color: var(--text-muted, #94a3b8); max-width: 400px; margin: 0 auto 20px;">${message}</p>
            ${action ? `
                <button class="btn ${type === 'error' ? 'btn-danger' : 'btn-primary'}" onclick="${action.onClick}">
                    ${action.icon ? `<i class="fas ${action.icon}"></i> ` : ''}${action.text}
                </button>
            ` : ''}
        </div>
    `;
}

/**
 * Predefined empty state configurations for common scenarios
 */
const EMPTY_STATE_CONFIGS = {
    noData: {
        icon: 'fa-inbox',
        title: 'No Data Available',
        message: 'There is no data to display at this time.'
    },
    noResults: {
        icon: 'fa-search',
        title: 'No Results Found',
        message: 'No items match your current filters. Try adjusting your search criteria.'
    },
    error: {
        icon: 'fa-exclamation-circle',
        title: 'Something Went Wrong',
        message: 'An error occurred while loading data. Please try again.',
        type: 'error'
    },
    firstUse: {
        icon: 'fa-rocket',
        title: 'Get Started',
        message: 'Welcome! Start by adding your first item.'
    },
    noCompetitors: {
        icon: 'fa-users',
        title: 'No Competitors',
        message: 'No competitors have been added yet. Add competitors to start tracking.',
        action: { text: 'Add Competitor', icon: 'fa-plus', onClick: "showAddCompetitorModal()" }
    },
    noNews: {
        icon: 'fa-newspaper',
        title: 'No News Articles',
        message: 'No news articles found for the selected criteria. Try expanding your date range or filters.',
        action: { text: 'Reset Filters', icon: 'fa-undo', onClick: "resetNewsFeedFilters()" }
    },
    noChanges: {
        icon: 'fa-history',
        title: 'No Changes Detected',
        message: 'No competitor changes have been detected in the selected time period.',
        action: { text: 'Search Last 30 Days', icon: 'fa-search', onClick: "document.getElementById('filterDays').value = '30'; loadChanges();" }
    }
};

// State
let competitors = [];
let changes = [];
let stats = {};
let threatChart = null;
let topThreatsChart = null;
let threatTrendChart = null;
let marketShareChart = null;

// ==============================================================================
// PERF-002: Chart.js Central Registry - Prevents memory leaks
// ==============================================================================

const chartRegistry = {};

/**
 * Create a Chart.js chart with automatic cleanup of previous instance on same canvas.
 * @param {string} canvasId - The canvas element ID
 * @param {Object} config - Chart.js configuration object
 * @returns {Chart|null} The created chart instance or null
 */
function createChart(canvasId, config) {
    if (chartRegistry[canvasId]) {
        chartRegistry[canvasId].destroy();
        delete chartRegistry[canvasId];
    }

    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    const chart = new Chart(ctx, config);
    chartRegistry[canvasId] = chart;
    return chart;
}

/**
 * Destroy a specific chart by canvas ID.
 * @param {string} canvasId - The canvas element ID
 */
function destroyChart(canvasId) {
    if (chartRegistry[canvasId]) {
        chartRegistry[canvasId].destroy();
        delete chartRegistry[canvasId];
    }
}

/**
 * Destroy all registered charts. Called on page navigation.
 */
function destroyAllCharts() {
    Object.keys(chartRegistry).forEach(id => {
        chartRegistry[id].destroy();
        delete chartRegistry[id];
    });
}

window.createChart = createChart;
window.destroyChart = destroyChart;
window.destroyAllCharts = destroyAllCharts;

// ==============================================================================
// PERF-003: Virtual Scrolling for large lists
// ==============================================================================

/**
 * Render a large list with virtual scrolling for performance.
 * Only renders visible items plus a buffer zone.
 * @param {HTMLElement} container - The scrollable container element
 * @param {Array} items - Array of data items to render
 * @param {Function} renderItem - Function that returns HTML string for one item
 * @param {number} itemHeight - Approximate height of each item in pixels
 */
function renderVirtualList(container, items, renderItem, itemHeight = 80) {
    const visibleCount = Math.ceil(container.clientHeight / itemHeight) + 10;
    let scrollTop = 0;

    function render() {
        const startIndex = Math.floor(scrollTop / itemHeight);
        const endIndex = Math.min(startIndex + visibleCount, items.length);

        const topPadding = startIndex * itemHeight;
        const bottomPadding = (items.length - endIndex) * itemHeight;

        container.innerHTML = `
            <div style="height:${topPadding}px"></div>
            ${items.slice(startIndex, endIndex).map(renderItem).join('')}
            <div style="height:${bottomPadding}px"></div>
        `;
    }

    container.addEventListener('scroll', () => {
        scrollTop = container.scrollTop;
        requestAnimationFrame(render);
    });

    render();
}

window.renderVirtualList = renderVirtualList;

// ==============================================================================
// PERF-004: Image Lazy Loading Utility
// ==============================================================================

/**
 * Generate an img tag with native lazy loading.
 * @param {string} src - Image source URL
 * @param {string} alt - Alt text for the image
 * @param {string} className - CSS class name(s) to apply
 * @returns {string} HTML img tag string
 */
function lazyImage(src, alt, className = '') {
    return `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy" class="${className}">`;
}

window.lazyImage = lazyImage;

// ==============================================================================
// PERF-001: Real-Time WebSocket Updates
// ==============================================================================

let wsConnection = null;
let wsReconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000;

/**
 * Initialize WebSocket connection for real-time updates
 */
function initWebSocket() {
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
        return; // Already connected
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/refresh-progress`;

    try {
        wsConnection = new WebSocket(wsUrl);

        wsConnection.onopen = () => {
            wsReconnectAttempts = 0;
            updateConnectionStatus('connected');
        };

        wsConnection.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error('[WebSocket] Error parsing message:', e);
            }
        };

        wsConnection.onclose = () => {
            updateConnectionStatus('disconnected');
            attemptReconnect();
        };

        wsConnection.onerror = (error) => {
            console.error('[WebSocket] Error:', error);
            updateConnectionStatus('error');
        };
    } catch (error) {
        console.error('[WebSocket] Failed to connect:', error);
        attemptReconnect();
    }
}

/**
 * Attempt to reconnect WebSocket
 */
function attemptReconnect() {
    if (wsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        wsReconnectAttempts++;
        setTimeout(initWebSocket, RECONNECT_DELAY);
    } else {
    }
}

/**
 * Handle incoming WebSocket messages
 */
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'refresh_progress':
            updateRefreshProgress(data.payload);
            break;
        case 'news_update':
            handleNewsUpdate(data.payload);
            break;
        case 'competitor_update':
            handleCompetitorUpdate(data.payload);
            break;
        case 'alert':
            showToast(data.payload.message, data.payload.level || 'info');
            break;
        default:
    }
}

/**
 * Handle real-time news updates
 */
function handleNewsUpdate(payload) {
    // Show notification for new news
    if (payload.new_articles > 0) {
        showToast(`${payload.new_articles} new articles found`, 'info');

        // Update news badge if on different page
        const newsBadge = document.getElementById('newsBadge');
        if (newsBadge) {
            const currentCount = parseInt(newsBadge.textContent) || 0;
            newsBadge.textContent = currentCount + payload.new_articles;
            newsBadge.style.display = 'inline';
        }
    }
}

/**
 * Handle real-time competitor updates
 */
function handleCompetitorUpdate(payload) {
    // Find and update competitor in local cache
    const index = competitors.findIndex(c => c.id === payload.id);
    if (index !== -1) {
        competitors[index] = { ...competitors[index], ...payload };
        // Re-render if on competitors page
        if (document.getElementById('competitorsPage')?.classList.contains('active')) {
            renderCompetitors();
        }
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(status) {
    const indicator = document.getElementById('wsConnectionStatus');
    if (indicator) {
        indicator.className = `connection-status ${status}`;
        indicator.title = status === 'connected' ? 'Real-time updates active' :
                          status === 'disconnected' ? 'Reconnecting...' :
                          'Connection error';
    }
}

// ==============================================================================
// PERF-003: Progressive Data Loading with Skeleton States
// ==============================================================================

/**
 * Show skeleton loading state for a container
 */
function showSkeletonLoading(containerId, itemCount = 5, type = 'card') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const skeletonTypes = {
        card: `
            <div class="skeleton-card">
                <div class="skeleton-line short"></div>
                <div class="skeleton-line long"></div>
                <div class="skeleton-line medium"></div>
            </div>
        `,
        row: `
            <tr class="skeleton-row">
                <td><div class="skeleton-line short"></div></td>
                <td><div class="skeleton-line medium"></div></td>
                <td><div class="skeleton-line long"></div></td>
                <td><div class="skeleton-line short"></div></td>
            </tr>
        `,
        text: `<div class="skeleton-line full"></div>`
    };

    const skeleton = skeletonTypes[type] || skeletonTypes.card;
    container.innerHTML = Array(itemCount).fill(skeleton).join('');
    container.classList.add('loading');
}

/**
 * Remove skeleton loading state
 */
function hideSkeletonLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.classList.remove('loading');
    }
}

/**
 * Progressive load function with pagination
 */
async function progressiveLoad(endpoint, containerId, renderFn, options = {}) {
    const {
        pageSize = 20,
        page = 1,
        skeletonType = 'card',
        append = false
    } = options;

    if (!append) {
        showSkeletonLoading(containerId, pageSize, skeletonType);
    }

    try {
        const params = new URLSearchParams();
        params.append('page', page);
        params.append('page_size', pageSize);

        const data = await fetchAPI(`${endpoint}?${params.toString()}`);

        hideSkeletonLoading(containerId);

        if (data) {
            renderFn(data, append);
        }

        return data;
    } catch (error) {
        console.error('Progressive load error:', error);
        hideSkeletonLoading(containerId);
        // Show user-friendly error instead of throwing
        showToast('Failed to load data: ' + (error.message || 'Unknown error'), 'error');
        return null;
    }
}

/**
 * Implement infinite scroll for a container
 */
function initInfiniteScroll(containerId, loadMoreFn, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const { threshold = 100, debounceMs = 200 } = options;
    let isLoading = false;
    let page = 1;

    const handleScroll = debounce(() => {
        const scrollHeight = container.scrollHeight;
        const scrollTop = container.scrollTop;
        const clientHeight = container.clientHeight;

        if (scrollHeight - scrollTop - clientHeight < threshold && !isLoading) {
            isLoading = true;
            page++;
            loadMoreFn(page).then(() => {
                isLoading = false;
            }).catch(() => {
                isLoading = false;
            });
        }
    }, debounceMs);

    container.addEventListener('scroll', handleScroll);

    // Return cleanup function
    return () => container.removeEventListener('scroll', handleScroll);
}

/**
 * Debounce utility function
 */
function debounce(fn, delay) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn.apply(this, args), delay);
    };
}

// ==============================================================================
// PERF-004: Optimistic UI Updates
// ==============================================================================

const pendingOperations = new Map();

/**
 * Execute an optimistic update
 * @param {string} operationId - Unique ID for this operation
 * @param {Function} optimisticUpdate - Function to update UI immediately
 * @param {Function} apiCall - Async function that makes the API call
 * @param {Function} rollback - Function to revert changes if API fails
 */
async function optimisticUpdate(operationId, optimisticUpdate, apiCall, rollback) {
    // Store rollback function
    pendingOperations.set(operationId, { rollback, timestamp: Date.now() });

    // Apply optimistic update immediately
    try {
        optimisticUpdate();
    } catch (e) {
        console.error('[Optimistic] Error in optimistic update:', e);
    }

    // Make API call in background
    try {
        const result = await apiCall();
        pendingOperations.delete(operationId);
        return result;
    } catch (error) {
        console.error('[Optimistic] API call failed, rolling back:', error);
        pendingOperations.delete(operationId);

        // Execute rollback
        try {
            rollback();
            showToast('Operation failed. Changes reverted.', 'error');
        } catch (rollbackError) {
            console.error('[Optimistic] Rollback failed:', rollbackError);
            showToast('Error occurred. Please refresh the page.', 'error');
        }

        throw error;
    }
}

/**
 * Optimistic competitor update helper
 */
async function optimisticCompetitorUpdate(competitorId, updates) {
    const operationId = `competitor-update-${competitorId}-${Date.now()}`;

    // Find competitor and store original state
    const index = competitors.findIndex(c => c.id === competitorId);
    if (index === -1) return;

    const originalCompetitor = { ...competitors[index] };

    return optimisticUpdate(
        operationId,
        // Optimistic update
        () => {
            competitors[index] = { ...competitors[index], ...updates };
            renderCompetitors();
        },
        // API call
        async () => {
            return await fetchAPI(`/api/competitors/${competitorId}`, {
                method: 'PUT',
                body: JSON.stringify(updates)
            });
        },
        // Rollback
        () => {
            competitors[index] = originalCompetitor;
            renderCompetitors();
        }
    );
}

/**
 * Optimistic delete helper
 */
async function optimisticDelete(competitorId) {
    const operationId = `competitor-delete-${competitorId}-${Date.now()}`;

    // Find competitor and store original state
    const index = competitors.findIndex(c => c.id === competitorId);
    if (index === -1) return;

    const originalCompetitor = competitors[index];
    const originalIndex = index;

    return optimisticUpdate(
        operationId,
        // Optimistic update - remove from list
        () => {
            competitors.splice(index, 1);
            renderCompetitors();
            showToast('Competitor deleted', 'success');
        },
        // API call
        async () => {
            return await fetchAPI(`/api/competitors/${competitorId}`, {
                method: 'DELETE'
            });
        },
        // Rollback - add back
        () => {
            competitors.splice(originalIndex, 0, originalCompetitor);
            renderCompetitors();
        }
    );
}

// ==============================================================================
// UX-002: Enhanced Dark Mode
// ==============================================================================

const THEME_KEY = 'certify-intel-theme';
const THEMES = { LIGHT: 'light', DARK: 'dark', SYSTEM: 'system' };

/**
 * Initialize dark mode with system detection
 */
function initDarkMode() {
    const savedTheme = localStorage.getItem(THEME_KEY);

    if (savedTheme === THEMES.DARK) {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (savedTheme === THEMES.LIGHT) {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        // System preference detection
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.setAttribute('data-theme', 'dark');
        }
    }

    // Listen for system theme changes
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            const savedTheme = localStorage.getItem(THEME_KEY);
            if (!savedTheme || savedTheme === THEMES.SYSTEM) {
                document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
            }
        });
    }

    // Create and inject the toggle button
    createDarkModeToggle();
}

/**
 * Create dark mode toggle button
 */
function createDarkModeToggle() {
    // Check if toggle already exists
    if (document.getElementById('darkModeToggle')) return;

    const toggle = document.createElement('button');
    toggle.id = 'darkModeToggle';
    toggle.className = 'dark-mode-toggle';
    toggle.setAttribute('aria-label', 'Toggle dark mode');
    toggle.innerHTML = `
        <span class="moon-icon">🌙</span>
        <span class="sun-icon">☀️</span>
    `;
    toggle.onclick = toggleDarkMode;
    document.body.appendChild(toggle);
}

/**
 * Toggle between light and dark mode
 */
function toggleDarkMode() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem(THEME_KEY, newTheme);

    // Show feedback toast
    showToast(`${newTheme === 'dark' ? 'Dark' : 'Light'} mode enabled`, 'info');
}

/**
 * Get current theme
 */
function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'light';
}

/**
 * Set theme programmatically
 */
function setTheme(theme) {
    if (theme === THEMES.SYSTEM) {
        localStorage.setItem(THEME_KEY, THEMES.SYSTEM);
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
        localStorage.setItem(THEME_KEY, theme);
        document.documentElement.setAttribute('data-theme', theme);
    }
}

// Initialize dark mode immediately (before DOM fully loads for no flash)
(function() {
    const savedTheme = localStorage.getItem(THEME_KEY);
    if (savedTheme === THEMES.DARK) {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else if (savedTheme === THEMES.LIGHT) {
        document.documentElement.setAttribute('data-theme', 'light');
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
})();

// ==============================================================================
// UX-005: Bulk Operations UI
// ==============================================================================

let bulkSelectedItems = new Set();
let bulkActionBarVisible = false;

/**
 * Initialize bulk selection for a page
 */
function initBulkSelection(containerId, itemType = 'competitor') {
    // Create action bar if it doesn't exist
    createBulkActionBar(itemType);

    // Add select all checkbox to header if table exists
    const table = document.querySelector(`#${containerId} table`);
    if (table) {
        addSelectAllCheckbox(table);
    }
}

/**
 * Create bulk action bar
 */
function createBulkActionBar(itemType = 'competitor') {
    if (document.getElementById('bulkActionBar')) return;

    const bar = document.createElement('div');
    bar.id = 'bulkActionBar';
    bar.className = 'bulk-action-bar';
    bar.innerHTML = `
        <div class="bulk-action-bar-left">
            <div class="bulk-selection-count">
                <span class="count-badge" id="bulkSelectedCount">0</span>
                <span>${itemType}s selected</span>
            </div>
            <button class="bulk-clear-btn" onclick="clearBulkSelection()">Clear selection</button>
        </div>
        <div class="bulk-action-bar-right">
            <button class="bulk-action-btn" onclick="bulkExport('excel')">
                <span>Export Excel</span>
            </button>
            <button class="bulk-action-btn" onclick="bulkExport('pdf')">
                <span>Export PDF</span>
            </button>
            <div class="bulk-dropdown">
                <button class="bulk-action-btn" onclick="toggleBulkDropdown()">
                    <span>More Actions</span>
                    <span>▼</span>
                </button>
                <div class="bulk-dropdown-menu" id="bulkDropdownMenu">
                    <div class="bulk-dropdown-item" onclick="bulkUpdateThreatLevel()">
                        <span>⚠️</span>
                        <span>Update Threat Level</span>
                    </div>
                    <div class="bulk-dropdown-item" onclick="bulkCompare()">
                        <span>📊</span>
                        <span>Compare Selected</span>
                    </div>
                    <div class="bulk-dropdown-item" onclick="bulkRefresh()">
                        <span>🔄</span>
                        <span>Refresh Data</span>
                    </div>
                    <div class="bulk-dropdown-item danger" onclick="bulkDelete()">
                        <span>🗑️</span>
                        <span>Delete Selected</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(bar);
}

/**
 * Add select all checkbox to table header
 */
function addSelectAllCheckbox(table) {
    const headerRow = table.querySelector('thead tr');
    if (!headerRow) return;

    // Check if already added
    if (headerRow.querySelector('.bulk-select-header')) return;

    const th = document.createElement('th');
    th.className = 'bulk-select-header';
    th.innerHTML = `
        <input type="checkbox" class="bulk-select-checkbox" id="selectAllCheckbox"
               onchange="toggleSelectAll(this.checked)" title="Select all">
    `;
    headerRow.insertBefore(th, headerRow.firstChild);

    // Add checkbox to each row
    const rows = table.querySelectorAll('tbody tr');
    rows.forEach(row => {
        if (row.querySelector('.bulk-select-checkbox')) return;
        const td = document.createElement('td');
        const itemId = row.dataset.id || row.getAttribute('data-competitor-id');
        td.innerHTML = `
            <input type="checkbox" class="bulk-select-checkbox" data-item-id="${itemId}"
                   onchange="toggleBulkItem(${itemId}, this.checked)">
        `;
        row.insertBefore(td, row.firstChild);
    });
}

/**
 * Toggle individual item selection
 */
function toggleBulkItem(itemId, selected) {
    if (selected) {
        bulkSelectedItems.add(itemId);
    } else {
        bulkSelectedItems.delete(itemId);
    }

    // Update row visual state
    const row = document.querySelector(`tr[data-id="${itemId}"], tr[data-competitor-id="${itemId}"]`);
    if (row) {
        row.classList.toggle('bulk-selected', selected);
    }

    // Update card visual state
    const card = document.querySelector(`.competitor-card[data-id="${itemId}"]`);
    if (card) {
        card.classList.toggle('bulk-selected', selected);
    }

    updateBulkActionBar();
}

/**
 * Add bulk selection checkboxes to competitor cards
 */
function addBulkCheckboxesToCards() {
    const cards = document.querySelectorAll('.competitor-card[data-id]');
    cards.forEach(card => {
        if (card.querySelector('.bulk-card-checkbox')) return;
        const itemId = card.dataset.id;
        if (!itemId) return;

        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'bulk-card-checkbox';
        cb.title = 'Select for bulk actions';
        cb.checked = bulkSelectedItems.has(parseInt(itemId));
        cb.addEventListener('change', (e) => {
            e.stopPropagation();
            toggleBulkItem(parseInt(itemId), cb.checked);
        });

        card.style.position = 'relative';
        card.appendChild(cb);
    });

    // Ensure action bar exists
    createBulkActionBar('competitor');
}

/**
 * Toggle select all items
 */
function toggleSelectAll(selected) {
    const checkboxes = document.querySelectorAll('tbody .bulk-select-checkbox');
    checkboxes.forEach(cb => {
        const itemId = parseInt(cb.dataset.itemId);
        if (!isNaN(itemId)) {
            cb.checked = selected;
            toggleBulkItem(itemId, selected);
        }
    });
}

/**
 * Clear all selections
 */
function clearBulkSelection() {
    bulkSelectedItems.clear();

    // Uncheck all checkboxes
    document.querySelectorAll('.bulk-select-checkbox').forEach(cb => {
        cb.checked = false;
    });

    // Remove visual selection state
    document.querySelectorAll('.bulk-selected').forEach(el => {
        el.classList.remove('bulk-selected');
    });

    updateBulkActionBar();
}

/**
 * Update bulk action bar visibility and count
 */
function updateBulkActionBar() {
    const bar = document.getElementById('bulkActionBar');
    const count = document.getElementById('bulkSelectedCount');

    if (bar && count) {
        count.textContent = bulkSelectedItems.size;

        if (bulkSelectedItems.size > 0) {
            bar.classList.add('visible');
            bulkActionBarVisible = true;
        } else {
            bar.classList.remove('visible');
            bulkActionBarVisible = false;
        }
    }

    // Update select all checkbox state
    const selectAllCb = document.getElementById('selectAllCheckbox');
    const allCheckboxes = document.querySelectorAll('tbody .bulk-select-checkbox');
    if (selectAllCb && allCheckboxes.length > 0) {
        const allSelected = Array.from(allCheckboxes).every(cb => cb.checked);
        const someSelected = Array.from(allCheckboxes).some(cb => cb.checked);
        selectAllCb.checked = allSelected;
        selectAllCb.indeterminate = someSelected && !allSelected;
    }
}

/**
 * Toggle bulk dropdown menu
 */
function toggleBulkDropdown() {
    const menu = document.getElementById('bulkDropdownMenu');
    if (menu) {
        menu.classList.toggle('visible');
    }
}

/**
 * Bulk export selected items
 */
async function bulkExport(format) {
    if (bulkSelectedItems.size === 0) {
        showToast('No items selected', 'warning');
        return;
    }

    showToast(`Exporting ${bulkSelectedItems.size} items to ${format.toUpperCase()}...`, 'info');

    try {
        const ids = Array.from(bulkSelectedItems);
        const response = await fetch(`${API_BASE}/api/competitors/export`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({ ids, format })
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `competitors_export_${new Date().toISOString().split('T')[0]}.${format === 'excel' ? 'xlsx' : format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            showToast(`Exported ${bulkSelectedItems.size} items successfully!`, 'success');
        } else {
            // Try to get error details from response
            let errorMsg = `Export failed (${response.status})`;
            try {
                const errorData = await response.json();
                if (errorData.detail) errorMsg = `Export failed: ${errorData.detail}`;
            } catch (e) { /* ignore parse errors */ }
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        console.error('Bulk export error:', error);
        showToast('Export failed: ' + (error.message || 'Unknown error'), 'error');
    }
}

// ==============================================================================
// Reusable Export Dropdown & Download Helper
// ==============================================================================

/**
 * Create a reusable export dropdown button.
 * @param {string} containerId - ID of the container element to inject into
 * @param {Array<{label: string, format: string, handler: Function}>} exportOptions
 */
function createExportDropdown(containerId, exportOptions) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Clear existing dropdown if present
    container.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.className = 'export-dropdown-wrapper';

    const btn = document.createElement('button');
    btn.className = 'btn btn-secondary export-dropdown-toggle';
    btn.innerHTML = '<span>Export</span> <span class="export-chevron">&#9662;</span>';

    const menu = document.createElement('div');
    menu.className = 'export-dropdown-menu';

    exportOptions.forEach(opt => {
        const item = document.createElement('button');
        item.className = 'export-dropdown-item';
        item.textContent = opt.label;
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.remove('open');
            btn.classList.remove('active');
            if (typeof opt.handler === 'function') {
                opt.handler(opt.format);
            }
        });
        menu.appendChild(item);
    });

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = menu.classList.contains('open');
        // Close all other open export dropdowns first
        document.querySelectorAll('.export-dropdown-menu.open').forEach(m => m.classList.remove('open'));
        document.querySelectorAll('.export-dropdown-toggle.active').forEach(b => b.classList.remove('active'));
        if (!isOpen) {
            menu.classList.add('open');
            btn.classList.add('active');
        }
    });

    wrapper.appendChild(btn);
    wrapper.appendChild(menu);
    container.appendChild(wrapper);
}

// Close export dropdowns on outside click
document.addEventListener('click', () => {
    document.querySelectorAll('.export-dropdown-menu.open').forEach(m => m.classList.remove('open'));
    document.querySelectorAll('.export-dropdown-toggle.active').forEach(b => b.classList.remove('active'));
});

/**
 * Download a blob response from an API endpoint.
 * @param {string} endpoint - API path (without API_BASE)
 * @param {Object|null} body - POST body (null for GET)
 * @param {string} filename - Download filename
 * @param {string} method - HTTP method (default POST)
 */
async function downloadExport(endpoint, body, filename, method = 'POST') {
    showToast('Preparing export...', 'info');
    try {
        const options = {
            method,
            headers: {
                ...getAuthHeaders()
            }
        };
        if (body && method === 'POST') {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, options);

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
            showToast('Export downloaded successfully', 'success');
        } else {
            let errorMsg = 'Export failed';
            try {
                const errorData = await response.json();
                if (errorData.detail) errorMsg = errorData.detail;
            } catch (e) { /* ignore parse errors */ }
            showToast(errorMsg, 'error');
        }
    } catch (error) {
        console.error('Download export error:', error);
        showToast('Export failed. Please try again.', 'error');
    }
}

/**
 * Initialize export dropdown for Records (Competitors) page
 */
function initRecordsExport() {
    const allCompetitorIds = () => (competitors || []).map(c => c.id);
    const dateStr = () => new Date().toISOString().split('T')[0];

    createExportDropdown('recordsExportContainer', [
        {
            label: 'Competitors (Excel)',
            format: 'excel',
            handler: () => downloadExport('/api/competitors/export', { ids: allCompetitorIds(), format: 'excel' }, `competitors_${dateStr()}.xlsx`)
        },
        {
            label: 'Competitors (CSV)',
            format: 'csv',
            handler: () => downloadExport('/api/competitors/export', { ids: allCompetitorIds(), format: 'csv' }, `competitors_${dateStr()}.csv`)
        },
        {
            label: 'Competitors (JSON)',
            format: 'json',
            handler: () => downloadExport('/api/competitors/export', { ids: allCompetitorIds(), format: 'json' }, `competitors_${dateStr()}.json`)
        },
        {
            label: 'Change Log (CSV)',
            format: 'csv',
            handler: () => downloadExport('/api/changes/export?format=csv', null, `changelog_${dateStr()}.csv`, 'GET')
        }
    ]);
}

/**
 * Initialize export dropdown for Battlecards page
 */
function initBattlecardsExport() {
    const allCompetitorIds = () => (competitors || []).map(c => c.id);
    const dateStr = () => new Date().toISOString().split('T')[0];

    createExportDropdown('battlecardsExportContainer', [
        {
            label: 'Battlecards (Excel)',
            format: 'excel',
            handler: () => downloadExport('/api/competitors/export', { ids: allCompetitorIds(), format: 'excel' }, `battlecards_${dateStr()}.xlsx`)
        },
        {
            label: 'Battlecards (CSV)',
            format: 'csv',
            handler: () => downloadExport('/api/competitors/export', { ids: allCompetitorIds(), format: 'csv' }, `battlecards_${dateStr()}.csv`)
        },
        {
            label: 'Battlecards (JSON)',
            format: 'json',
            handler: () => downloadExport('/api/competitors/export', { ids: allCompetitorIds(), format: 'json' }, `battlecards_${dateStr()}.json`)
        }
    ]);
}

/**
 * Initialize export dropdown for Analytics page
 */
function initAnalyticsExport() {
    const dateStr = () => new Date().toISOString().split('T')[0];

    createExportDropdown('analyticsExportContainer', [
        {
            label: 'Full Report (Excel)',
            format: 'excel',
            handler: () => {
                window.open(`${API_BASE}/api/export/excel`, '_blank');
                showToast('Excel report download started', 'success');
            }
        },
        {
            label: 'Competitor Data (CSV)',
            format: 'csv',
            handler: () => {
                const ids = (competitors || []).map(c => c.id);
                downloadExport('/api/competitors/export', { ids, format: 'csv' }, `analytics_${dateStr()}.csv`);
            }
        },
        {
            label: 'Charts (PNG)',
            format: 'png',
            handler: () => exportAllCharts('png')
        }
    ]);
}

/**
 * Initialize export dropdown for Dashboard page (client-side PDF with charts)
 */
function initDashboardExport() {
    createExportDropdown('dashboardExportContainer', [
        {
            label: 'Dashboard (PDF)',
            format: 'pdf',
            handler: () => {
                try {
                    const charts = [];
                    const canvasIds = ['threatDistChart', 'threatTrendChart', 'coverageChart'];
                    canvasIds.forEach(id => {
                        const el = document.querySelector('#dashboardPage canvas[id="' + id + '"], #dashboardPage canvas');
                        if (el) charts.push(el);
                    });
                    // Collect all canvases from dashboard if specific IDs not found
                    if (charts.length === 0) {
                        document.querySelectorAll('#dashboardPage canvas').forEach(c => charts.push(c));
                    }
                    const dateStr = new Date().toISOString().split('T')[0];
                    window.pdfExporter.exportWithCharts(
                        'Certify Intel - Dashboard Report',
                        charts.slice(0, 4),
                        null,
                        'dashboard_report_' + dateStr + '.pdf'
                    );
                    showToast('Dashboard PDF exported', 'success');
                } catch (err) {
                    console.error('[Export] Dashboard PDF failed:', err);
                    showToast('PDF export failed. Ensure the page has loaded.', 'error');
                }
            }
        },
        {
            label: 'Full Report (Excel)',
            format: 'excel',
            handler: () => {
                window.open(API_BASE + '/api/export/excel', '_blank');
                showToast('Excel report download started', 'success');
            }
        }
    ]);
}

/**
 * Initialize export dropdown for News page (client-side Excel)
 */
function initNewsExport() {
    createExportDropdown('newsExportContainer', [
        {
            label: 'News Articles (Excel)',
            format: 'excel',
            handler: async () => {
                try {
                    showToast('Preparing news export...', 'info');
                    const data = await fetchAPI('/api/news-feed', { silent: true });
                    const articles = Array.isArray(data) ? data : (data && data.articles ? data.articles : []);
                    if (!articles.length) {
                        showToast('No news articles to export', 'warning');
                        return;
                    }
                    const headers = ['Title', 'Source', 'Competitor', 'Published', 'Sentiment', 'URL'];
                    const rows = articles.map(a => [
                        a.title || '',
                        a.source || '',
                        a.competitor_name || '',
                        a.published_at || a.created_at || '',
                        a.sentiment || '',
                        a.url || ''
                    ]);
                    const dateStr = new Date().toISOString().split('T')[0];
                    window.excelExporter.exportTable('News Articles', headers, rows, 'news_articles_' + dateStr + '.xlsx');
                    showToast('News articles exported to Excel', 'success');
                } catch (err) {
                    console.error('[Export] News Excel failed:', err);
                    showToast('Export failed. Please try again.', 'error');
                }
            }
        },
        {
            label: 'News Articles (PDF)',
            format: 'pdf',
            handler: async () => {
                try {
                    showToast('Preparing news PDF...', 'info');
                    const data = await fetchAPI('/api/news-feed', { silent: true });
                    const articles = Array.isArray(data) ? data : (data && data.articles ? data.articles : []);
                    if (!articles.length) {
                        showToast('No news articles to export', 'warning');
                        return;
                    }
                    const headers = ['Title', 'Source', 'Competitor', 'Published', 'Sentiment'];
                    const rows = articles.slice(0, 100).map(a => [
                        (a.title || '').substring(0, 60),
                        a.source || '',
                        a.competitor_name || '',
                        a.published_at || '',
                        a.sentiment || ''
                    ]);
                    const dateStr = new Date().toISOString().split('T')[0];
                    window.pdfExporter.exportTable('Certify Intel - News Articles', headers, rows, 'news_articles_' + dateStr + '.pdf');
                    showToast('News articles exported to PDF', 'success');
                } catch (err) {
                    console.error('[Export] News PDF failed:', err);
                    showToast('PDF export failed. Please try again.', 'error');
                }
            }
        }
    ]);
}

// Export to window for global access
window.createExportDropdown = createExportDropdown;
window.downloadExport = downloadExport;
window.initRecordsExport = initRecordsExport;
window.initBattlecardsExport = initBattlecardsExport;
window.initAnalyticsExport = initAnalyticsExport;
window.initDashboardExport = initDashboardExport;
window.initNewsExport = initNewsExport;

/**
 * Bulk update threat level
 */
async function bulkUpdateThreatLevel() {
    if (bulkSelectedItems.size === 0) {
        showToast('No items selected', 'warning');
        return;
    }

    const threatLevel = prompt('Enter new threat level (Critical, High, Medium, Low):');
    if (!threatLevel || !['Critical', 'High', 'Medium', 'Low'].includes(threatLevel)) {
        showToast('Invalid threat level', 'warning');
        return;
    }

    showToast(`Updating ${bulkSelectedItems.size} items...`, 'info');

    try {
        const ids = Array.from(bulkSelectedItems);
        const response = await fetch(`${API_BASE}/api/competitors/bulk-update`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({ ids, updates: { threat_level: threatLevel } })
        });

        if (response.ok) {
            showToast(`Updated ${bulkSelectedItems.size} items successfully!`, 'success');
            clearBulkSelection();
            // Refresh the data
            if (typeof loadCompetitors === 'function') {
                loadCompetitors();
            }
        } else {
            showToast('Bulk update failed', 'error');
        }
    } catch (error) {
        console.error('Bulk update error:', error);
        showToast('Bulk update failed: ' + error.message, 'error');
    }

    toggleBulkDropdown();
}

/**
 * Bulk compare selected items
 */
function bulkCompare() {
    if (bulkSelectedItems.size < 2) {
        showToast('Select at least 2 items to compare', 'warning');
        return;
    }

    if (bulkSelectedItems.size > 4) {
        showToast('Maximum 4 items can be compared at once', 'warning');
        return;
    }

    const ids = Array.from(bulkSelectedItems).join(',');
    window.location.hash = `compare?ids=${ids}`;
    toggleBulkDropdown();
}

/**
 * Bulk refresh selected items
 */
async function bulkRefresh() {
    if (bulkSelectedItems.size === 0) {
        showToast('No items selected', 'warning');
        return;
    }

    showToast(`Refreshing ${bulkSelectedItems.size} items...`, 'info');

    try {
        const ids = Array.from(bulkSelectedItems);
        const response = await fetch(`${API_BASE}/api/competitors/bulk-refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({ ids })
        });

        if (response.ok) {
            showToast(`Refresh started for ${bulkSelectedItems.size} items!`, 'success');
        } else {
            showToast('Bulk refresh failed', 'error');
        }
    } catch (error) {
        console.error('Bulk refresh error:', error);
        showToast('Bulk refresh failed: ' + error.message, 'error');
    }

    toggleBulkDropdown();
}

/**
 * Bulk delete selected items
 */
async function bulkDelete() {
    if (bulkSelectedItems.size === 0) {
        showToast('No items selected', 'warning');
        return;
    }

    const confirmed = confirm(`Are you sure you want to delete ${bulkSelectedItems.size} items? This action cannot be undone.`);
    if (!confirmed) return;

    showToast(`Deleting ${bulkSelectedItems.size} items...`, 'info');

    try {
        const ids = Array.from(bulkSelectedItems);
        const response = await fetch(`${API_BASE}/api/competitors/bulk-delete`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify({ ids })
        });

        if (response.ok) {
            showToast(`Deleted ${bulkSelectedItems.size} items successfully!`, 'success');
            clearBulkSelection();
            // Refresh the data
            if (typeof loadCompetitors === 'function') {
                loadCompetitors();
            }
        } else {
            showToast('Bulk delete failed', 'error');
        }
    } catch (error) {
        console.error('Bulk delete error:', error);
        showToast('Bulk delete failed: ' + error.message, 'error');
    }

    toggleBulkDropdown();
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const dropdown = document.querySelector('.bulk-dropdown');
    const menu = document.getElementById('bulkDropdownMenu');
    if (dropdown && menu && !dropdown.contains(e.target)) {
        menu.classList.remove('visible');
    }
});

// Initialize WebSocket when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Initialize dark mode toggle button
    initDarkMode();

    // Only connect WebSocket if authenticated
    if (localStorage.getItem('access_token')) {
        setTimeout(initWebSocket, 1000); // Delay to let page load
    }
});

// ============== Authentication ==============

/**
 * Check if user is authenticated, redirect to login if not
 */
function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}

/**
 * Logout user - revoke refresh token, clear storage, redirect
 */
function logout() {
    if (window._notificationIntervalId) {
        clearInterval(window._notificationIntervalId);
        window._notificationIntervalId = null;
    }
    if (window._tokenRefreshTimer) {
        clearTimeout(window._tokenRefreshTimer);
        window._tokenRefreshTimer = null;
    }
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
        fetch(`${API_BASE}/api/auth/logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        }).catch(() => {});
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expires_at');
    window.location.href = '/login.html';
}

/**
 * Get authorization headers for API calls
 */
function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * Refresh the access token using the stored refresh token.
 * Returns true if refresh succeeded, false otherwise.
 */
let _refreshInProgress = null;
async function refreshAccessToken() {
    // Deduplicate concurrent refresh attempts
    if (_refreshInProgress) return _refreshInProgress;

    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;

    _refreshInProgress = (async () => {
        try {
            const response = await fetch(`${API_BASE}/api/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken })
            });

            if (!response.ok) return false;

            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            if (data.refresh_token) {
                localStorage.setItem('refresh_token', data.refresh_token);
            }
            if (data.expires_in) {
                const expiresAt = Date.now() + (data.expires_in * 1000);
                localStorage.setItem('token_expires_at', expiresAt.toString());
            }
            scheduleTokenRefresh();
            return true;
        } catch {
            return false;
        } finally {
            _refreshInProgress = null;
        }
    })();

    return _refreshInProgress;
}

/**
 * Schedule a proactive token refresh 1 minute before expiry
 */
function scheduleTokenRefresh() {
    if (window._tokenRefreshTimer) {
        clearTimeout(window._tokenRefreshTimer);
    }
    const expiresAt = parseInt(localStorage.getItem('token_expires_at'), 10);
    if (!expiresAt || isNaN(expiresAt)) return;

    // Refresh 60 seconds before expiry, minimum 10 seconds from now
    const refreshIn = Math.max((expiresAt - Date.now()) - 60000, 10000);
    window._tokenRefreshTimer = setTimeout(async () => {
        const success = await refreshAccessToken();
        if (!success) {
            logout();
        }
    }, refreshIn);
}

// Start the refresh scheduler on page load if we have tokens
if (localStorage.getItem('access_token') && localStorage.getItem('refresh_token')) {
    scheduleTokenRefresh();
}

/**
 * Setup user menu info and toggle logic
 */
async function setupUserMenu() {
    const avatar = document.getElementById('userAvatar');
    const dropdown = document.getElementById('userDropdown');
    const userNameEl = document.getElementById('userName');
    const userEmailEl = document.getElementById('userEmail');
    const userRoleEl = document.getElementById('userRole');

    if (!avatar || !dropdown) return;

    try {
        const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const user = await response.json();

            // Update initials (as tooltip)
            const initials = user.full_name ?
                user.full_name.split(' ').map(n => n[0]).join('').toUpperCase() :
                user.email[0].toUpperCase();
            avatar.title = initials;

            // Update dropdown info
            userNameEl.textContent = user.full_name || 'User';
            userEmailEl.textContent = user.email;
            userRoleEl.textContent = user.role || 'Analyst';

            // Show invite link for admins
            if (user.role === 'admin') {
                const inviteLink = document.getElementById('inviteUserLink');
                if (inviteLink) {
                    inviteLink.style.display = 'flex';
                }
            }
        }
    } catch (e) {
        console.error('Error fetching user info:', e);
    }

    // Close dropdown on click outside
    document.addEventListener('click', (e) => {
        if (!avatar.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });
}

/**
 * Toggle the user profile dropdown
 */
function toggleUserDropdown() {
    const dropdown = document.getElementById('userDropdown');
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
}


// ============== Source Attribution Helpers ==============

/**
 * Get company logo URL from Clearbit via Backend Proxy
 */
function getLogoUrl(website) {
    if (!website) return null;
    const domain = website.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0];
    // Route through backend proxy to bypass CORS/Network blocks
    return `${API_BASE}/api/logo-proxy?url=` + encodeURIComponent(`https://logo.clearbit.com/${domain}`);
}

/**
 * Create logo image element with fallback
 * PERF-006: Added lazy loading for images
 */
function createLogoImg(website, name, size = 32) {
    if (!website) {
        return `<div class="company-logo-placeholder" style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;background:#e2e8f0;border-radius:4px;font-weight:bold;color:#64748b;font-size:${size / 2}px;">${(name || '?')[0].toUpperCase()}</div>`;
    }
    const logoUrl = getLogoUrl(website);
    // PERF-006: Use loading="lazy" and decoding="async" for better performance
    return `<img src="${logoUrl}" alt="${name}" class="company-logo" loading="lazy" decoding="async" style="width:${size}px;height:${size}px;border-radius:4px;object-fit:contain;" onerror="this.nextElementSibling.style.display='flex';this.style.display='none'"/><div class="company-logo-placeholder" style="display:none;width:${size}px;height:${size}px;align-items:center;justify-content:center;background:#e2e8f0;border-radius:4px;font-weight:bold;color:#64748b;font-size:${size / 2}px;">${(name || '?')[0].toUpperCase()}</div>`;
}

/**
 * Source attribution icons with links
 */
const SOURCE_CONFIGS = {
    clearbit: { icon: '🖼️', name: 'Clearbit', baseUrl: 'https://clearbit.com/logo' },
    sec: { icon: '📊', name: 'SEC EDGAR', baseUrl: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=' },
    hunter: { icon: '📧', name: 'Hunter.io', baseUrl: 'https://hunter.io/search/' },
    google: { icon: '🔍', name: 'Google', baseUrl: 'https://www.google.com/search?q=' },
    newsapi: { icon: '📰', name: 'NewsAPI', baseUrl: 'https://newsapi.org' },
    linkedin: { icon: '💼', name: 'LinkedIn', baseUrl: 'https://www.linkedin.com/company/' },
    website: { icon: '🌐', name: 'Website', baseUrl: '' },
    manual: { icon: '✏️', name: 'Manual Entry', baseUrl: '' }
};

/**
 * Create source attribution link icon
 */
function createSourceLink(source, identifier = '', highlight = '') {
    const config = SOURCE_CONFIGS[source] || { icon: '📌', name: source, baseUrl: '' };
    let url = config.baseUrl + encodeURIComponent(identifier);
    let title = `Source: ${config.name}`;

    // Website: verification via Google Search ("Company customer count")
    if (source === 'website' && highlight) {
        url = `https://www.google.com/search?q=${encodeURIComponent(identifier ? new URL(identifier).hostname : '')}+${encodeURIComponent(highlight)}+verification`;
        title = "Verify this figure on Google";
    } else if (source === 'website') {
        url = identifier; // Direct link
    }

    // Google: Specific search with highlight
    if (highlight && source === 'google') {
        url = `https://www.google.com/search?q=${encodeURIComponent(identifier)}"+"${encodeURIComponent(highlight)}"`;
    }

    // SEC-specific URL with CIK
    if (source === 'sec' && identifier) {
        url = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${identifier}&type=10-K&dateb=&owner=include&count=10`;
    }

    // Hunter.io search
    if (source === 'hunter' && identifier) {
        url = `https://hunter.io/search/${identifier.replace('https://', '').replace('http://', '').split('/')[0]}`;
    }

    return `<a href="${url}" target="_blank" class="source-link" title="${title}" style="cursor:pointer;text-decoration:none;margin-left:4px;opacity:0.7;font-size:12px;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.7'">${config.icon}</a>`;
}

/**
 * Create a value with source attribution
 */

/**
 * Format SEC filings into displayable HTML
 */

function formatSecFilings(filingsJson, cik) {
    if (!filingsJson) return '';
    try {
        const filings = typeof filingsJson === 'string' ? JSON.parse(filingsJson) : filingsJson;
        return filings.slice(0, 3).map(f =>
            `<a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}&type=${f.form}" target="_blank" class="sec-filing-link" style="display:inline-block;margin:2px 4px;padding:2px 8px;background:#e0f2fe;border-radius:4px;font-size:11px;text-decoration:none;color:#0369a1;">${f.form} (${f.filed})</a>`
        ).join('');
    } catch (e) {
        return '';
    }
}

/**
 * Format key contacts into displayable HTML
 */
function formatKeyContacts(contactsJson, website) {
    if (!contactsJson) return '';
    try {
        const contacts = typeof contactsJson === 'string' ? JSON.parse(contactsJson) : contactsJson;
        const domain = website?.replace('https://', '').replace('http://', '').split('/')[0] || '';
        return contacts.slice(0, 5).map(c =>
            `<div class="contact-item" style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid #f1f5f9;">
                <span style="font-weight:500;">${escapeHtml(c.name)}</span>
                <span style="color:#64748b;font-size:12px;">${c.position || ''}</span>
                <a href="mailto:${c.email}" style="margin-left:auto;color:#0ea5e9;font-size:12px;">${c.email}</a>
            </div>`
        ).join('') + (domain ? `<div style="margin-top:8px;text-align:right;"><a href="https://hunter.io/search/${domain}" target="_blank" style="color:#ff6b35;font-size:11px;">View all on Hunter.io →</a></div>` : '');
    } catch (e) {
        return '';
    }
}

// ============== Initialization ==============

// P3-4: Navigation State Preservation
const NAV_STATE_KEY = 'certify_intel_nav_state';

/**
 * Save navigation state to localStorage
 * Preserves current page, filters, and scroll position
 */
function saveNavigationState(pageName, additionalState = {}) {
    const state = {
        page: pageName,
        timestamp: Date.now(),
        filters: {
            threat: document.getElementById('filterThreat')?.value || 'all',
            status: document.getElementById('filterStatus')?.value || 'all',
            severity: document.getElementById('filterSeverity')?.value || 'all',
            days: document.getElementById('filterDays')?.value || '30'
        },
        scroll: {
            x: window.scrollX,
            y: window.scrollY
        },
        ...additionalState
    };
    localStorage.setItem(NAV_STATE_KEY, JSON.stringify(state));

    // P3-6: Update URL hash for shareable links
    updateUrlHash(pageName, additionalState);
}

/**
 * Restore navigation state from localStorage
 */
function restoreNavigationState() {
    // P3-6: First check URL hash for shared links
    const hashState = parseUrlHash();
    if (hashState.page) {
        return hashState;
    }

    // Fall back to localStorage
    try {
        const saved = localStorage.getItem(NAV_STATE_KEY);
        if (saved) {
            const state = JSON.parse(saved);
            // Only restore if less than 24 hours old
            if (Date.now() - state.timestamp < 24 * 60 * 60 * 1000) {
                return state;
            }
        }
    } catch (e) {
        console.warn('Could not restore navigation state:', e);
    }
    return null;
}

/**
 * P3-6: Update URL hash for shareable links
 */
function updateUrlHash(pageName, additionalState = {}) {
    let hash = `#${pageName}`;

    // Add comparison IDs if on comparison page
    if (pageName === 'comparison' && additionalState.compareIds) {
        hash += `?compare=${additionalState.compareIds.join(',')}`;
    }

    // Add competitor ID if viewing a specific competitor
    if (additionalState.competitorId) {
        hash += `${hash.includes('?') ? '&' : '?'}competitor=${additionalState.competitorId}`;
    }

    // Update URL without triggering navigation
    if (window.location.hash !== hash) {
        history.replaceState(null, '', hash);
    }
}

/**
 * P3-6: Parse URL hash for shared links
 */
function parseUrlHash() {
    const hash = window.location.hash;
    if (!hash || hash === '#') return {};

    const [pagePart, queryPart] = hash.substring(1).split('?');
    const result = { page: pagePart };

    if (queryPart) {
        const params = new URLSearchParams(queryPart);
        if (params.has('compare')) {
            result.compareIds = params.get('compare').split(',').map(Number).filter(n => !isNaN(n));
        }
        if (params.has('competitor')) {
            result.competitorId = parseInt(params.get('competitor'));
        }
    }

    return result;
}

/**
 * P3-6: Generate shareable comparison link
 */
function generateComparisonLink(competitorIds) {
    const baseUrl = window.location.origin + window.location.pathname;
    return `${baseUrl}#comparison?compare=${competitorIds.join(',')}`;
}

/**
 * P3-6: Copy comparison link to clipboard
 */
async function copyComparisonLink() {
    const selectedIds = Array.from(document.querySelectorAll('.comparison-checkbox:checked'))
        .map(cb => parseInt(cb.dataset.id))
        .filter(id => !isNaN(id));

    if (selectedIds.length < 2) {
        showToast('Select at least 2 competitors to share', 'warning');
        return;
    }

    const link = generateComparisonLink(selectedIds);

    try {
        await navigator.clipboard.writeText(link);
        showToast('Comparison link copied to clipboard!', 'success');
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = link;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showToast('Comparison link copied!', 'success');
    }
}

// Make functions globally available
window.copyComparisonLink = copyComparisonLink;
window.generateComparisonLink = generateComparisonLink;

document.addEventListener('DOMContentLoaded', () => {
    // Check authentication first
    if (!checkAuth()) return;

    initNavigation();

    // P3-4: Restore saved navigation state
    const savedState = restoreNavigationState();
    if (savedState && savedState.page) {
        // Restore filters before loading page
        if (savedState.filters) {
            const threatFilter = document.getElementById('filterThreat');
            const statusFilter = document.getElementById('filterStatus');
            const severityFilter = document.getElementById('filterSeverity');
            const daysFilter = document.getElementById('filterDays');

            if (threatFilter && savedState.filters.threat) threatFilter.value = savedState.filters.threat;
            if (statusFilter && savedState.filters.status) statusFilter.value = savedState.filters.status;
            if (severityFilter && savedState.filters.severity) severityFilter.value = savedState.filters.severity;
            if (daysFilter && savedState.filters.days) daysFilter.value = savedState.filters.days;
        }

        // Show the saved page
        showPage(savedState.page);

        // P3-6: Handle comparison links with pre-selected competitors
        if (savedState.compareIds && savedState.compareIds.length > 0) {
            setTimeout(() => {
                loadComparisonFromIds(savedState.compareIds);
            }, 500);
        }

        // Restore scroll position after page loads
        if (savedState.scroll) {
            setTimeout(() => {
                window.scrollTo(savedState.scroll.x, savedState.scroll.y);
            }, 100);
        }
    } else {
        loadDashboard();
    }

    setupUserMenu();
    preloadPrompts(); // Preload AI prompts for instant access
    loadApprovedFieldsCache(); // Load approved manual edits cache for green styling

    // P3-4: Listen for hash changes (browser back/forward)
    window.addEventListener('hashchange', () => {
        const hashState = parseUrlHash();
        if (hashState.page) {
            showPage(hashState.page);
            if (hashState.compareIds) {
                setTimeout(() => loadComparisonFromIds(hashState.compareIds), 300);
            }
        }
    });
});

function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            showPage(page);
        });
    });

    // Filter event listeners
    document.getElementById('filterThreat')?.addEventListener('change', filterCompetitors);
    document.getElementById('filterStatus')?.addEventListener('change', filterCompetitors);
    document.getElementById('filterSeverity')?.addEventListener('change', loadChanges);
    document.getElementById('filterDays')?.addEventListener('change', loadChanges);
    document.getElementById('filterCompany')?.addEventListener('change', loadChanges);

    // Search
    document.getElementById('globalSearch')?.addEventListener('input', debounce(handleSearch, 300));
}

function showPageError(pageId, message) {
    const page = document.getElementById(pageId);
    if (page) {
        const existing = page.querySelector('.page-error');
        if (existing) existing.remove();
        const errorDiv = document.createElement('div');
        errorDiv.className = 'page-error';
        errorDiv.style.cssText = 'padding:40px;text-align:center;color:#e0e0e0;';
        const heading = document.createElement('h3');
        heading.style.cssText = 'color:#F44336;margin-bottom:8px;';
        heading.textContent = 'Failed to load page';
        const desc = document.createElement('p');
        desc.style.cssText = 'color:#aaa;margin-bottom:16px;';
        desc.textContent = message || 'An unexpected error occurred';
        const retryBtn = document.createElement('button');
        retryBtn.style.cssText = 'padding:8px 24px;background:#6C63FF;color:white;border:none;border-radius:6px;cursor:pointer;';
        retryBtn.textContent = 'Retry';
        const retryPage = pageId.replace('Page', '');
        retryBtn.addEventListener('click', function() { showPage(retryPage); });
        errorDiv.appendChild(heading);
        errorDiv.appendChild(desc);
        errorDiv.appendChild(retryBtn);
        page.prepend(errorDiv);
    }
}

function showPage(pageName) {
    // PERF-002: Destroy all Chart.js instances to prevent memory leaks on navigation
    destroyAllCharts();

    // FIX v6.3.7: More robust navigation highlighting
    // Step 1: Remove 'active' from ALL nav items first
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    // Step 2: Add 'active' to the matching nav item
    const activeNav = document.querySelector(`.nav-item[data-page="${pageName}"]`);
    if (activeNav) {
        activeNav.classList.add('active');
    }

    // WCAG 2.1 AA: Update aria-current and announce page change
    if (typeof updateNavAriaState === 'function') {
        updateNavAriaState(pageName);
    }
    if (typeof announceToScreenReader === 'function') {
        const pageLabel = activeNav ? activeNav.textContent.trim() : pageName;
        announceToScreenReader(`Navigated to ${pageLabel}`);
    }

    // Step 3: Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    // Step 4: Show the target page
    const targetPage = document.getElementById(`${pageName}Page`);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    // P3-4: Save navigation state
    if (typeof saveNavigationState === 'function') {
        saveNavigationState(pageName);
    }

    // Clear any previous page errors on navigation
    if (targetPage) {
        const prevError = targetPage.querySelector('.page-error');
        if (prevError) prevError.remove();
    }

    // Load page-specific data with error boundaries (async-safe)
    switch (pageName) {
        case 'dashboard':
            try {
                loadDashboard().catch(err => { console.error('[showPage] Dashboard load failed:', err); showPageError('dashboardPage', err.message); });
                if (typeof initPromptSelector === 'function') initPromptSelector('dashboard', 'dashboardPromptSelect');
                initDashboardExport();
            } catch (error) {
                console.error('[showPage] Dashboard load failed:', error);
                showPageError('dashboardPage', error.message);
            }
            break;
        case 'competitors':
            try {
                loadCompetitors().catch(err => { console.error('[showPage] Competitors load failed:', err); showPageError('competitorsPage', err.message); });
                initRecordsExport();
            } catch (error) {
                console.error('[showPage] Competitors load failed:', error);
                showPageError('competitorsPage', error.message);
            }
            break;
        case 'changes':
            try {
                loadChanges().catch(err => { console.error('[showPage] Changes load failed:', err); showPageError('changesPage', err.message); });
            } catch (error) {
                console.error('[showPage] Changes load failed:', error);
                showPageError('changesPage', error.message);
            }
            break;
        case 'comparison':
            try {
                loadComparisonOptions().catch(err => { console.error('[showPage] Comparison load failed:', err); showPageError('comparisonPage', err.message); });
            } catch (error) {
                console.error('[showPage] Comparison load failed:', error);
                showPageError('comparisonPage', error.message);
            }
            break;
        case 'analytics':
            try {
                loadAnalytics().catch(err => { console.error('[showPage] Analytics load failed:', err); showPageError('analyticsPage', err.message); });
                if (typeof initPromptSelector === 'function') initPromptSelector('competitor', 'competitorPromptSelect');
                initAnalyticsExport();
            } catch (error) {
                console.error('[showPage] Analytics load failed:', error);
                showPageError('analyticsPage', error.message);
            }
            break;
        case 'marketmap':
            try {
                loadMarketMap();
            } catch (error) {
                console.error('[showPage] MarketMap load failed:', error);
                showPageError('marketmapPage', error.message);
            }
            break;
        case 'battlecards':
            try {
                loadBattlecards().catch(err => { console.error('[showPage] Battlecards load failed:', err); showPageError('battlecardsPage', err.message); });
                if (typeof initPromptSelector === 'function') initPromptSelector('battlecards', 'battlecardPromptSelect');
                resumeVerificationIfRunning();
                initBattlecardsExport();
            } catch (error) {
                console.error('[showPage] Battlecards load failed:', error);
                showPageError('battlecardsPage', error.message);
            }
            break;
        case 'discovered':
            try {
                loadDiscovered().catch(err => { console.error('[showPage] Discovery load failed:', err); showPageError('discoveredPage', err.message); });
                if (typeof initPromptSelector === 'function') initPromptSelector('discovery', 'discoveryPromptSelect');
                if (typeof createChatWidget === 'function') {
                    createChatWidget('discoveryChatContainer', {
                        endpoint: '/api/analytics/chat',
                        pageContext: 'discovery',
                        placeholder: 'Ask about discovery results...',
                        systemContext: 'Discovery Scout - competitor discovery and qualification'
                    });
                }
            } catch (error) {
                console.error('[showPage] Discovery load failed:', error);
                showPageError('discoveredPage', error.message);
            }
            break;
        case 'dataquality':
            try {
                loadDataQuality().catch(err => { console.error('[showPage] DataQuality load failed:', err); showPageError('dataqualityPage', err.message); });
                loadDataConflicts().catch(err => { console.error('[showPage] DataConflicts load failed:', err); });
            } catch (error) {
                console.error('[showPage] DataQuality load failed:', error);
                showPageError('dataqualityPage', error.message);
            }
            break;
        case 'newsfeed':
            try {
                initNewsFeedPage().catch(err => { console.error('[showPage] NewsFeed load failed:', err); showPageError('newsfeedPage', err.message); });
                if (typeof initPromptSelector === 'function') initPromptSelector('news', 'newsPromptSelect');
                initNewsExport();
            } catch (error) {
                console.error('[showPage] NewsFeed load failed:', error);
                showPageError('newsfeedPage', error.message);
            }
            break;
        case 'salesmarketing':
            try {
                if (typeof initSalesMarketingModule === 'function') {
                    initSalesMarketingModule();
                }
                if (typeof initPromptSelector === 'function') initPromptSelector('battlecards', 'battlecardPromptSelect');
            } catch (error) {
                console.error('[showPage] SalesMarketing load failed:', error);
                showPageError('salesmarketingPage', error.message);
            }
            break;
        case 'settings':
            try {
                loadSettings().catch(err => { console.error('[showPage] Settings load failed:', err); showPageError('settingsPage', err.message); });
                initKnowledgeBaseStatus().catch(err => { console.error('[showPage] KB status load failed:', err); });
                if (typeof initPromptSelector === 'function') initPromptSelector('knowledge_base', 'kbPromptSelect');
            } catch (error) {
                console.error('[showPage] Settings load failed:', error);
                showPageError('settingsPage', error.message);
            }
            break;
        case 'verification':
            try {
                loadVerificationQueue().catch(err => { console.error('[showPage] Verification load failed:', err); showPageError('verificationPage', err.message); });
            } catch (error) {
                console.error('[showPage] Verification load failed:', error);
                showPageError('verificationPage', error.message);
            }
            break;
    }
}

// ============== API Functions ==============

/**
 * Custom API Error class for better error handling
 */
class APIError extends Error {
    constructor(status, message, endpoint) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.endpoint = endpoint;
    }
}

/**
 * Get user-friendly error message based on HTTP status code
 */
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

/**
 * Enhanced API fetch wrapper with better error handling
 */
async function fetchAPI(endpoint, options = {}) {
    const { retries = 0, retryDelay = 1000, silent = false } = options;

    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...getAuthHeaders()
                },
                ...options
            });

            // Handle 401 Unauthorized - attempt token refresh before redirecting
            if (response.status === 401) {
                console.warn(`[fetchAPI] 401 on ${endpoint} - attempting token refresh`);
                if (!window._handling401) {
                    window._handling401 = true;
                    const refreshed = await refreshAccessToken();
                    window._handling401 = false;
                    if (refreshed) {
                        // Retry the original request with the new token
                        const retryResponse = await fetch(`${API_BASE}${endpoint}`, {
                            headers: {
                                'Content-Type': 'application/json',
                                ...getAuthHeaders()
                            },
                            ...options
                        });
                        if (retryResponse.ok) {
                            return await retryResponse.json();
                        }
                    }
                    // Refresh failed or retry failed - redirect to login
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');
                    localStorage.removeItem('token_expires_at');
                    window.location.href = '/login.html';
                }
                return null;
            }

            // Handle other error responses
            if (!response.ok) {
                const errorMessage = getErrorMessage(response.status, endpoint);
                throw new APIError(response.status, errorMessage, endpoint);
            }

            return await response.json();
        } catch (error) {
            // Don't show toast for intentional aborts (timeouts)
            if (error.name === 'AbortError') {
                return null;
            }

            // Retry logic for network errors
            if (attempt < retries && (error.name === 'TypeError' || error.status >= 500)) {
                await new Promise(resolve => setTimeout(resolve, retryDelay * (attempt + 1)));
                continue;
            }

            console.error(`API Error: ${endpoint}`, error);

            // Only show toast if not silent mode
            if (!silent) {
                const message = error instanceof APIError ? error.message : 'Network error. Please check your connection.';
                showToast(message, 'error');
            }

            return null;
        }
    }
}

/**
 * Show persistent error banner at top of page
 */
function showErrorBanner(message, options = {}) {
    const { action = null, dismissible = true } = options;

    // Remove existing banner
    const existing = document.getElementById('errorBanner');
    if (existing) existing.remove();

    const banner = document.createElement('div');
    banner.id = 'errorBanner';
    banner.className = 'error-banner';
    banner.innerHTML = `
        <div class="error-banner-content">
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
            ${action ? `<button class="btn btn-sm" onclick="${action.onClick}">${action.text}</button>` : ''}
        </div>
        ${dismissible ? '<button class="error-banner-close" onclick="this.parentElement.remove()">&times;</button>' : ''}
    `;

    document.body.insertBefore(banner, document.body.firstChild);
}

/**
 * Hide error banner
 */
function hideErrorBanner() {
    const banner = document.getElementById('errorBanner');
    if (banner) banner.remove();
}

// ============== Dashboard ==============

// Track last refresh time
let lastDataRefresh = null;

function updateRefreshTimestamp() {
    lastDataRefresh = new Date();
    const timeElement = document.getElementById('lastRefreshTime');
    if (timeElement) {
        // Format: "Sun, Jan 25, 2026, 03:08 PM EST"
        const dateOptions = {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        };
        const timeOptions = {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
            timeZoneName: 'short'
        };
        const datePart = lastDataRefresh.toLocaleDateString('en-US', dateOptions);
        const timePart = lastDataRefresh.toLocaleTimeString('en-US', timeOptions);
        timeElement.textContent = `${datePart}, ${timePart}`;
    }
}

async function loadDashboard() {

    // Resume any in-progress data refresh
    resumeRefreshIfRunning();

    // Initialize dashboard controls (date range picker, threat count)
    initDashboardControls();

    try {
        // Stats - independent
        try {
            stats = await fetchAPI('/api/dashboard/stats') || {};
            updateStatsCards();
        } catch (e) { console.error('[Dashboard] Stats failed:', e); }

        // Competitors - independent
        try {
            competitors = await fetchAPI('/api/competitors') || [];
            renderTopThreats();
        } catch (e) { console.error('[Dashboard] Competitors failed:', e); }

        // Changes - independent
        try {
            changes = (await fetchAPI('/api/changes?days=7'))?.changes || [];
            renderRecentChanges();
        } catch (e) { console.error('[Dashboard] Changes failed:', e); }

        // Charts - independent
        try {
            if (document.getElementById('threatChart')) {
                renderThreatChart();
            }
        } catch (e) { console.error('[Dashboard] Threat chart failed:', e); }

        try {
            if (document.getElementById('topThreatsChart')) {
                renderTopThreatsChart();
            }
        } catch (e) { console.error('[Dashboard] Top threats chart failed:', e); }

        try {
            if (document.getElementById('threatTrendChart')) {
                renderThreatTrendChart();
            }
        } catch (e) { console.error('[Dashboard] Threat trend chart failed:', e); }

        // Mini widgets
        try {
            loadDashboardMiniWidgets();
        } catch (e) { console.error('[Dashboard] Mini widgets failed:', e); }

        // v8.0.8: Load saved AI summary from DB (survives server restart)
        try {
            const savedSummary = await fetchAPI('/api/analytics/summary/saved', { silent: true });
            if (savedSummary && savedSummary.summary) {
                const contentDiv = document.getElementById('aiSummaryContent');
                const summaryCard = document.getElementById('aiSummaryCard');
                const metaDiv = document.getElementById('aiSummaryMeta');
                const modelBadge = document.getElementById('aiModelBadge');
                if (contentDiv && summaryCard) {
                    summaryCard.style.display = 'block';
                    let html = escapeHtml(savedSummary.summary);
                    html = html
                        .replace(/^# (.*$)/gim, '<h2>$1</h2>')
                        .replace(/^## (.*$)/gim, '<h3>$1</h3>')
                        .replace(/^### (.*$)/gim, '<h4>$1</h4>')
                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                        .replace(/^\s*-\s(.*?)$/gm, '<li>$1</li>')
                        .replace(/^\s*\d+\.\s(.*?)$/gm, '<li>$1</li>');
                    if (html.includes('<li>')) {
                        html = html.replace(/((<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
                    }
                    html = html.replace(/\n\n/g, '<br>');
                    contentDiv.innerHTML = html;
                    if (metaDiv && savedSummary.data_points_analyzed) {
                        metaDiv.innerHTML = `<span>📊 Analyzed ${parseInt(savedSummary.data_points_analyzed) || 0} competitors</span> |
                            <span>🕐 Generated: ${new Date(savedSummary.generated_at).toLocaleTimeString()}</span> |
                            <span>🤖 Model: ${escapeHtml(savedSummary.provider || '')} ${escapeHtml(savedSummary.model || 'Automated')}</span>`;
                    }
                    if (modelBadge && savedSummary.model) {
                        modelBadge.textContent = savedSummary.model.toUpperCase();
                    }
                }
                initDashboardChatWidget(savedSummary.summary);
            } else {
                initDashboardChatWidget('');
            }
        } catch (e) {
            console.error('[Dashboard] Saved summary load failed:', e);
            try { initDashboardChatWidget(''); } catch (e2) {}
        }
    } catch (error) {
        console.error('[Dashboard] Error loading dashboard:', error);
    } finally {
        // ALWAYS update refresh timestamp, even on partial failure
        updateRefreshTimestamp();
    }
}


// Make functions global for button clicks
window.clearAISummary = function () {
    const contentDiv = document.getElementById('aiSummaryContent');
    const metaDiv = document.getElementById('aiSummaryMeta');

    if (contentDiv) {
        contentDiv.innerHTML = '<div class="ai-empty-state">Ready to generate insights. Click "Generate Summary" to start.</div>';
    } else {
        console.error('aiSummaryContent not found');
    }

    if (metaDiv) metaDiv.innerHTML = '';

    // v8.0.8: Clear saved summary from DB
    fetchAPI('/api/analytics/summary/saved', { method: 'DELETE', silent: true }).catch(() => {});
};

// Toggle AI Summary expand/collapse
window.toggleAISummary = function() {
    const summaryCard = document.getElementById('aiSummaryCard');
    if (summaryCard) {
        summaryCard.classList.toggle('collapsed');
    }
};

// Toggle Sidebar collapse/expand
window.toggleSidebarCollapse = function() {
    const sidebar = document.getElementById('mainSidebar');
    const mainContent = document.querySelector('.main-content');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
        if (mainContent) {
            mainContent.classList.toggle('sidebar-collapsed');
        }
    }
};

// Make accessible to onclick
window.startAISummary = startAISummary;

// AI Summary progress tracking
let aiProgressInterval = null;
let aiProgressStartTime = null;

function showAISummaryProgressModal() {
    const modal = document.getElementById('aiSummaryProgressModal');
    if (modal) {
        modal.style.display = 'flex';
        aiProgressStartTime = Date.now();
        // Reset progress display
        document.getElementById('aiSummaryProgressBar').style.width = '0%';
        document.getElementById('aiProgressPercent').textContent = '0%';
        document.getElementById('aiProgressStepText').textContent = 'Initializing...';
        document.getElementById('aiProgressElapsed').textContent = 'Elapsed: 0s';
        // Reset step indicators
        for (let i = 1; i <= 5; i++) {
            const step = document.getElementById(`step${i}`);
            if (step) {
                step.style.color = '#64748b';
                step.style.fontWeight = 'normal';
            }
        }
    }
}

function hideAISummaryProgressModal() {
    const modal = document.getElementById('aiSummaryProgressModal');
    if (modal) {
        modal.style.display = 'none';
    }
    if (aiProgressInterval) {
        clearInterval(aiProgressInterval);
        aiProgressInterval = null;
    }
}

function updateAISummaryProgress(progress) {
    const progressBar = document.getElementById('aiSummaryProgressBar');
    const percentText = document.getElementById('aiProgressPercent');
    const stepText = document.getElementById('aiProgressStepText');
    const elapsedText = document.getElementById('aiProgressElapsed');

    if (progressBar) progressBar.style.width = `${progress.progress}%`;
    if (percentText) percentText.textContent = `${progress.progress}%`;
    if (stepText) stepText.textContent = progress.step_description || 'Processing...';

    // Update elapsed time
    if (elapsedText && aiProgressStartTime) {
        const elapsed = Math.floor((Date.now() - aiProgressStartTime) / 1000);
        elapsedText.textContent = `Elapsed: ${elapsed}s`;
    }

    // Highlight current step
    const currentStep = progress.step || 0;
    for (let i = 1; i <= 5; i++) {
        const stepEl = document.getElementById(`step${i}`);
        if (stepEl) {
            if (i < currentStep) {
                stepEl.style.color = '#10B981';
                stepEl.style.fontWeight = '500';
            } else if (i === currentStep) {
                stepEl.style.color = '#059669';
                stepEl.style.fontWeight = '600';
            } else {
                stepEl.style.color = '#94a3b8';
                stepEl.style.fontWeight = 'normal';
            }
        }
    }
}

async function pollAISummaryProgress() {
    try {
        const progress = await fetchAPI('/api/analytics/summary/progress');
        if (progress) {
            updateAISummaryProgress(progress);
            if (!progress.active && progress.progress >= 100) {
                // Complete - stop polling
                if (aiProgressInterval) {
                    clearInterval(aiProgressInterval);
                    aiProgressInterval = null;
                }
            }
        }
    } catch (e) {
        console.error('Error polling AI progress:', e);
    }
}

async function startAISummary() {
    const summaryCard = document.getElementById('aiSummaryCard');
    const contentDiv = document.getElementById('aiSummaryContent');
    const modelBadge = document.getElementById('aiModelBadge');
    const providerLogo = document.getElementById('aiProviderLogo');
    const metaDiv = document.getElementById('aiSummaryMeta');

    if (!summaryCard || !contentDiv) return;

    summaryCard.style.display = 'block';
    contentDiv.innerHTML = '<div class="ai-loading"><span class="ai-spinner">⏳</span> Generating comprehensive strategic insights...</div>';

    // Show progress modal and start polling
    showAISummaryProgressModal();
    aiProgressInterval = setInterval(pollAISummaryProgress, 500);

    // Read selected prompt from the dashboard prompt selector
    let summaryUrl = '/api/analytics/summary';
    const promptSelect = document.getElementById('dashboardPromptSelect');
    if (promptSelect && promptSelect.value) {
        summaryUrl += `?prompt_key=${encodeURIComponent(promptSelect.value)}`;
    }
    const data = await fetchAPI(summaryUrl);

    // Hide progress modal
    hideAISummaryProgressModal();

    if (data) {
        let html = escapeHtml(data.summary || String(data));
        if (typeof html === 'object') html = escapeHtml(html.summary);

        // Null check for html content
        if (!html || typeof html !== 'string') {
            contentDiv.innerHTML = '<div class="ai-empty-state">No summary content available. Please try again.</div>';
            showToast('AI Summary returned empty content', 'warning');
            return;
        }

        // Format markdown to HTML
        html = html
            .replace(/^# (.*$)/gim, '<h2>$1</h2>')
            .replace(/^## (.*$)/gim, '<h3>$1</h3>')
            .replace(/^### (.*$)/gim, '<h4>$1</h4>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/^\s*-\s(.*?)$/gm, '<li>$1</li>')
            .replace(/^\s*\d+\.\s(.*?)$/gm, '<li>$1</li>');

        // Wrap consecutive li tags in ul
        if (html.includes('<li>')) {
            html = html.replace(/((<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
        }

        html = html.replace(/\n\n/g, '<br>');
        contentDiv.innerHTML = html;

        // Update model badge
        if (modelBadge && data.model) {
            modelBadge.textContent = data.model.toUpperCase().replace('GPT-4-TURBO', 'GPT-4');
            modelBadge.style.background = data.type === 'ai' ?
                'linear-gradient(135deg, #10b981 0%, #059669 100%)' :
                'linear-gradient(135deg, #64748b 0%, #475569 100%)';
        }

        // Update provider logo
        if (providerLogo && data.provider) {
            if (data.provider === 'OpenAI') {
                providerLogo.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23000"%3E%3Cpath d="M22.28 9.9c.5-1.47.73-3.02.68-4.55A5.38 5.38 0 0 0 17.73.42a5.29 5.29 0 0 0-5.14 1.24A5.29 5.29 0 0 0 4.63.68 5.38 5.38 0 0 0 .88 6.75c-.2 1.52.05 3.05.72 4.44a5.35 5.35 0 0 0 .68 8.3 5.28 5.28 0 0 0 5.14.12 5.29 5.29 0 0 0 7.96.98 5.38 5.38 0 0 0 3.75-6.07c.68-1.3.98-2.76.88-4.22l-.73.6z"/%3E%3C/svg%3E';
                providerLogo.alt = 'OpenAI';
            }
        }

        // Update meta info
        if (metaDiv && data.data_points_analyzed) {
            metaDiv.innerHTML = `<span>📊 Analyzed ${parseInt(data.data_points_analyzed) || 0} competitors</span> |
                <span>🕐 Generated: ${new Date(data.generated_at).toLocaleTimeString()}</span> |
                <span>🤖 Model: ${escapeHtml(data.provider || '')} ${escapeHtml(data.model || 'Automated')}</span>`;
        }

        // Update badge style based on type
        const badge = summaryCard.querySelector('.ai-badge');
        if (data.type === 'fallback' && badge) {
            badge.textContent = 'Automated Insight';
            badge.style.background = '#f1f5f9';
            badge.style.color = '#64748b';
        } else if (badge) {
            badge.textContent = 'AI Generated';
            badge.style.background = '#e0e7ff';
            badge.style.color = '#3730a3';
        }

        showToast('AI Summary generated successfully!', 'success');

        // Initialize conversational chat widget below the summary
        initDashboardChatWidget(data.summary || String(data));
    } else {
        contentDiv.innerHTML = '<div class="ai-empty-state">Failed to generate summary. Please try again.</div>';
    }
}

/**
 * Initialize the dashboard chat widget with the executive summary as first message.
 * Converts the old one-shot sendAIChat into a persistent conversational widget.
 */
function initDashboardChatWidget(summaryText) {
    const chatContainer = document.getElementById('aiChatMessages');
    if (!chatContainer) return;

    // Clear old static chatbox markup; the widget replaces it
    const oldInput = document.getElementById('aiChatInput');
    if (oldInput) {
        const inputContainer = oldInput.closest('.ai-chat-input-container');
        if (inputContainer) inputContainer.style.display = 'none';
    }
    // Hide old chatbox header since widget has its own
    const oldHeader = chatContainer.closest('.ai-chatbox')?.querySelector('.ai-chatbox-header');
    if (oldHeader) oldHeader.style.display = 'none';

    createChatWidget('aiChatMessages', {
        pageContext: 'dashboard',
        placeholder: 'Ask about competitors, pricing, threats...',
        endpoint: '/api/analytics/chat',
        promptSelectorId: 'dashboardPromptSelect'
    });
}

// Legacy sendAIChat - redirects to the chat widget
async function sendAIChat() {
    const widget = _chatWidgetRegistry['aiChatMessages'];
    if (widget) {
        const input = document.getElementById('aiChatInput');
        if (input && input.value.trim()) {
            widget.sendMessage(input.value.trim());
            input.value = '';
        }
        return;
    }
    // Fallback: initialize widget on first send if summary wasn't generated yet
    initDashboardChatWidget('');
    const input = document.getElementById('aiChatInput');
    if (input && input.value.trim()) {
        const w = _chatWidgetRegistry['aiChatMessages'];
        if (w) {
            w.sendMessage(input.value.trim());
            input.value = '';
        }
    }
}

// ==============================================================================
// REUSABLE CHAT WIDGET COMPONENT (v7.2.0)
// ==============================================================================

/**
 * Registry of active chat widgets, keyed by containerId.
 * Prevents duplicate initialization and enables cleanup.
 */
const _chatWidgetRegistry = {};

/**
 * Creates a reusable conversational chat widget inside a container element.
 * @param {string} containerId - The DOM id of the container element
 * @param {Object} config - Configuration object
 * @param {string} config.pageContext - Unique context key for session isolation
 * @param {number} [config.competitorId] - Optional competitor id for context
 * @param {string} config.placeholder - Input placeholder text
 * @param {string} config.endpoint - API endpoint for sending messages
 * @param {Function} [config.onResponse] - Optional callback after AI response
 * @returns {{ sendMessage: Function, loadHistory: Function, clearHistory: Function, destroy: Function }}
 */
function createChatWidget(containerId, config) {
    // Destroy any previous widget in this container
    if (_chatWidgetRegistry[containerId]) {
        _chatWidgetRegistry[containerId].destroy();
    }

    const container = document.getElementById(containerId);
    if (!container) {
        console.warn('[ChatWidget] Container not found:', containerId);
        return null;
    }

    let sessionId = null;
    let conversationHistory = [];

    // Build DOM
    container.innerHTML = '';
    container.classList.add('chat-widget');

    // Header with clear button
    const header = document.createElement('div');
    header.className = 'chat-widget-header';
    const headerLabel = document.createElement('span');
    headerLabel.textContent = 'Ask follow-up questions';
    const clearBtn = document.createElement('button');
    clearBtn.className = 'chat-clear-btn';
    clearBtn.textContent = 'Clear Chat';
    clearBtn.addEventListener('click', () => clearHistory());
    header.appendChild(headerLabel);
    header.appendChild(clearBtn);
    container.appendChild(header);

    // Messages area
    const messagesArea = document.createElement('div');
    messagesArea.className = 'chat-messages';
    container.appendChild(messagesArea);

    // Input area
    const inputArea = document.createElement('div');
    inputArea.className = 'chat-input-area';
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'chat-input';
    input.placeholder = config.placeholder || 'Ask a follow-up question...';
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(input.value.trim());
        }
    });
    const sendBtn = document.createElement('button');
    sendBtn.className = 'chat-send-btn';
    sendBtn.textContent = 'Send';
    sendBtn.addEventListener('click', () => sendMessage(input.value.trim()));
    inputArea.appendChild(input);
    inputArea.appendChild(sendBtn);
    container.appendChild(inputArea);

    // Show empty state initially
    showEmptyState();

    // Load existing history on mount
    loadHistory();

    function showEmptyState() {
        const existing = messagesArea.querySelector('.chat-empty-state');
        if (!existing && messagesArea.children.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'chat-empty-state';
            empty.textContent = 'Ask a question to start a conversation...';
            messagesArea.appendChild(empty);
        }
    }

    function removeEmptyState() {
        const empty = messagesArea.querySelector('.chat-empty-state');
        if (empty) empty.remove();
    }

    function appendMessage(role, content, timestamp) {
        removeEmptyState();
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-msg ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'chat-avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';

        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';

        // Use textContent for user messages, escaped HTML for AI (allows line breaks)
        if (role === 'user') {
            bubble.textContent = content;
        } else {
            // AI content: escape then allow line breaks
            const escaped = escapeHtml(content);
            bubble.innerHTML = escaped.replace(/\n/g, '<br>');
        }

        if (timestamp) {
            const ts = document.createElement('span');
            ts.className = 'chat-timestamp';
            ts.textContent = new Date(timestamp).toLocaleTimeString();
            bubble.appendChild(ts);
        }

        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubble);
        messagesArea.appendChild(msgDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    function showLoading() {
        removeEmptyState();
        const loadDiv = document.createElement('div');
        loadDiv.className = 'chat-loading';
        loadDiv.id = `chat-loading-${containerId}`;
        loadDiv.textContent = 'AI is thinking...';
        messagesArea.appendChild(loadDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    function hideLoading() {
        const el = document.getElementById(`chat-loading-${containerId}`);
        if (el) el.remove();
    }

    async function loadHistory() {
        try {
            const data = await fetchAPI(`/api/chat/sessions/by-context/${encodeURIComponent(config.pageContext)}`, { silent: true });
            // API returns {session: {id, messages, ...}} - unwrap it
            const session = data?.session || data;
            if (session && session.id && session.messages && session.messages.length > 0) {
                sessionId = session.id;
                conversationHistory = session.messages.map(m => ({
                    role: m.role,
                    content: m.content
                }));
                // Clear and render all messages
                messagesArea.innerHTML = '';
                session.messages.forEach(m => {
                    appendMessage(m.role, m.content, m.created_at);
                });
            }
        } catch (e) {
            // No existing session, that's fine
        }
    }

    async function sendMessage(text) {
        if (!text) return;
        input.value = '';
        sendBtn.disabled = true;

        // Display user message immediately
        appendMessage('user', text);
        conversationHistory.push({ role: 'user', content: text });

        showLoading();

        try {
            // Create session if needed
            if (!sessionId) {
                const sessionData = await fetchAPI('/api/chat/sessions', {
                    method: 'POST',
                    body: JSON.stringify({
                        page_context: config.pageContext,
                        competitor_id: config.competitorId || null
                    })
                });
                if (sessionData && sessionData.id) {
                    sessionId = sessionData.id;
                }
            }

            // Send to AI endpoint with conversation history
            const payload = {
                message: text,
                session_id: sessionId,
                conversation_history: conversationHistory
            };
            if (config.competitorId) {
                payload.competitor_id = config.competitorId;
            }
            // Pass selected prompt key if a prompt selector is configured
            if (config.promptSelectorId) {
                const promptSelect = document.getElementById(config.promptSelectorId);
                if (promptSelect && promptSelect.value) {
                    payload.prompt_key = promptSelect.value;
                }
            }

            const response = await fetchAPI(config.endpoint, {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            hideLoading();

            if (!response) {
                appendMessage('assistant', 'Failed to get a response. Please try again.');
                conversationHistory.push({ role: 'assistant', content: 'Failed to get a response. Please try again.' });
                sendBtn.disabled = false;
                input.focus();
                return;
            }

            const aiContent = response?.response || response?.content || response?.summary ||
                (typeof response === 'string' ? response : 'No response received.');

            appendMessage('assistant', aiContent);
            conversationHistory.push({ role: 'assistant', content: aiContent });

            // Persist both messages to the session
            if (sessionId) {
                fetchAPI(`/api/chat/sessions/${sessionId}/messages`, {
                    method: 'POST',
                    body: JSON.stringify({ role: 'user', content: text })
                }).catch(e => console.warn('[ChatWidget] Failed to persist user message:', e));

                fetchAPI(`/api/chat/sessions/${sessionId}/messages`, {
                    method: 'POST',
                    body: JSON.stringify({ role: 'assistant', content: aiContent })
                }).catch(e => console.warn('[ChatWidget] Failed to persist AI message:', e));
            }

            if (config.onResponse) {
                config.onResponse(aiContent, response);
            }
        } catch (err) {
            hideLoading();
            appendMessage('assistant', 'Error: ' + (err.message || 'Failed to get response. Please try again.'));
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    }

    async function clearHistory() {
        if (sessionId) {
            try {
                await fetchAPI(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
            } catch (e) {
                console.warn('[ChatWidget] Failed to delete session:', e);
            }
        }
        sessionId = null;
        conversationHistory = [];
        messagesArea.innerHTML = '';
        showEmptyState();
        showToast('Chat history cleared', 'info');
    }

    function destroy() {
        container.innerHTML = '';
        container.classList.remove('chat-widget');
        delete _chatWidgetRegistry[containerId];
    }

    const widget = { sendMessage, loadHistory, clearHistory, destroy };
    _chatWidgetRegistry[containerId] = widget;
    return widget;
}

window.createChatWidget = createChatWidget;

// Enhanced triggerScrapeAll with progress modal and live progress tracking
async function triggerScrapeAll() {
    const btn = document.querySelector('.btn-primary[onclick*="triggerScrapeAll"]') ||
        document.querySelector('button:contains("Refresh")') ||
        event?.target;

    if (btn) {
        btn.classList.add('btn-loading');
        btn.disabled = true;
    }

    // Show inline progress on Dashboard (Phase 1: Task 5.0.1-025)
    showInlineRefreshProgress();

    try {
        const result = await fetchAPI('/api/scrape/all', { method: 'POST' });

        if (result && result.total) {
            // Start polling for inline progress
            pollInlineRefreshProgress(result.total);
        } else {
            hideInlineRefreshProgress();
            showToast('Error starting refresh', 'error');
            if (btn) {
                btn.classList.remove('btn-loading');
                btn.disabled = false;
            }
        }
    } catch (e) {
        hideInlineRefreshProgress();
        showToast('Error refreshing data: ' + e.message, 'error');
        if (btn) {
            btn.classList.remove('btn-loading');
            btn.disabled = false;
        }
    }
}

// Progress modal functions
function showRefreshProgressModal() {
    const modal = document.getElementById('refreshProgressModal');
    if (modal) {
        modal.style.display = 'flex';
        document.getElementById('progressCurrentText').textContent = 'Starting refresh...';
        document.getElementById('refreshProgressBar').style.width = '0%';
        document.getElementById('progressPercent').textContent = '0%';
        document.getElementById('progressCount').textContent = '0 of 0 competitors';
        document.getElementById('progressCompletedList').innerHTML = '';
    }
}

function hideRefreshProgressModal() {
    const modal = document.getElementById('refreshProgressModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function updateRefreshProgress(progress) {
    const percent = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;

    document.getElementById('refreshProgressBar').style.width = `${percent}%`;
    document.getElementById('progressPercent').textContent = `${percent}%`;
    document.getElementById('progressCount').textContent = `${progress.completed} of ${progress.total} competitors`;

    if (progress.current_competitor) {
        const statusText = progress.enrichment_active ? progress.current_competitor : `Scraping: ${progress.current_competitor}`;
        document.getElementById('progressCurrentText').textContent = statusText;
    }

    // Update completed list
    const listEl = document.getElementById('progressCompletedList');
    let html = '';

    // Show last 5 completed items
    const recentDone = progress.competitors_done.slice(-5);
    recentDone.forEach(name => {
        html += `<div class="progress-completed-item"><span class="check-icon">&#10003;</span> ${escapeHtml(name)}</div>`;
    });

    // Show current item if active
    if (progress.current_competitor && progress.active) {
        html += `<div class="progress-completed-item current"><span class="check-icon">&#8594;</span> ${escapeHtml(progress.current_competitor)}</div>`;
    }

    listEl.innerHTML = html;
}

async function showRefreshCompleteModal(progress) {
    const modal = document.getElementById('refreshCompleteModal');
    if (!modal) return;

    // Update stats
    document.getElementById('completeTotal').textContent = progress.total || 0;
    document.getElementById('completeChanges').textContent = progress.changes_detected || 0;
    document.getElementById('completeNewValues').textContent = progress.new_values_added || 0;

    // v7.1.0: Show enrichment stats (news + stock)
    const enrichmentStatsEl = document.getElementById('enrichmentStats');
    if (enrichmentStatsEl) {
        const newsCount = progress.news_articles_fetched || 0;
        const stockCount = progress.stock_prices_updated || 0;
        enrichmentStatsEl.innerHTML = `
            <div style="display: flex; gap: 16px; margin-top: 8px;">
                <div style="flex: 1; text-align: center; padding: 8px; background: var(--bg-secondary); border-radius: 8px;">
                    <div style="font-size: 20px; font-weight: 700; color: var(--primary-color);">${newsCount}</div>
                    <div style="font-size: 11px; color: var(--text-secondary);">News Articles Fetched</div>
                </div>
                <div style="flex: 1; text-align: center; padding: 8px; background: var(--bg-secondary); border-radius: 8px;">
                    <div style="font-size: 20px; font-weight: 700; color: var(--primary-color);">${stockCount}</div>
                    <div style="font-size: 11px; color: var(--text-secondary);">Stock Prices Updated</div>
                </div>
            </div>
        `;
        enrichmentStatsEl.style.display = 'block';
    }

    // Show modal
    modal.style.display = 'flex';

    // Reset AI summary section
    const summaryContent = document.getElementById('refreshAISummaryContent');
    if (summaryContent) {
        summaryContent.innerHTML = '<span class="loading-text">🤖 Analyzing changes across your data...</span>';
    }

    // Reset categorized changes section
    const categorizedSection = document.getElementById('categorizedChangesSection');
    const categorizedList = document.getElementById('categorizedChangesList');
    if (categorizedSection) categorizedSection.style.display = 'none';
    if (categorizedList) categorizedList.innerHTML = '';

    // Fetch AI summary (Phase 3: Task 5.0.1-030)
    try {
        const summaryResult = await fetchAPI('/api/scrape/generate-summary', { method: 'POST' });

        if (summaryResult && summaryResult.summary) {
            const summaryHtml = `
                <p style="margin: 0; line-height: 1.6;">${escapeHtml(summaryResult.summary)}</p>
                <div class="summary-meta" style="margin-top: 12px; font-size: 11px; color: var(--text-secondary); border-top: 1px solid var(--border-color); padding-top: 8px;">
                    ${summaryResult.type === 'ai' ? `<span style="color: var(--primary-color);">✨ Generated by ${summaryResult.model || 'AI'}</span>` : '<span>📊 Auto-generated summary</span>'}
                    &nbsp;•&nbsp; ${new Date().toLocaleTimeString()}
                </div>
            `;
            if (summaryContent) {
                summaryContent.innerHTML = summaryHtml;
            }
        } else if (summaryResult && summaryResult.error) {
            if (summaryContent) {
                summaryContent.innerHTML = `<p style="color: var(--text-secondary); font-style: italic;">Summary: ${escapeHtml(summaryResult.summary || 'No significant changes detected during this refresh.')}</p>`;
            }
        }
    } catch (e) {
        console.error('Error fetching AI summary:', e);
        if (summaryContent) {
            summaryContent.innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">Could not generate AI summary. Check change details below.</p>';
        }
    }

    // Populate change details and categorized changes
    await populateChangeDetails();
    await populateCategorizedChanges();

    // Initialize chat widget for follow-up questions about refresh changes
    try {
        const chatSection = document.getElementById('refreshChatWidget');
        if (chatSection) {
            createChatWidget('refreshChatWidget', {
                pageContext: 'refresh_summary',
                placeholder: 'Ask about the changes (e.g., "What pricing changes happened?")',
                endpoint: '/api/analytics/chat'
            });
        }
    } catch (e) {
        console.error('[Refresh] Chat widget init failed:', e);
    }
}

/**
 * Populate categorized changes summary
 */
async function populateCategorizedChanges() {
    const categorizedSection = document.getElementById('categorizedChangesSection');
    const categorizedList = document.getElementById('categorizedChangesList');
    if (!categorizedSection || !categorizedList) return;

    try {
        const session = await fetchAPI('/api/scrape/session');

        if (session && session.change_details && session.change_details.length > 0) {
            // Categorize changes
            const categories = {
                pricing: { icon: '💰', label: 'Pricing Changes', changes: [] },
                product: { icon: '📦', label: 'Product Updates', changes: [] },
                company: { icon: '🏢', label: 'Company Info', changes: [] },
                threat: { icon: '⚠️', label: 'Threat Level Changes', changes: [] },
                other: { icon: '📝', label: 'Other Changes', changes: [] }
            };

            session.change_details.forEach(change => {
                const field = (change.field || '').toLowerCase();
                if (field.includes('price') || field.includes('pricing') || field.includes('cost')) {
                    categories.pricing.changes.push(change);
                } else if (field.includes('product') || field.includes('feature') || field.includes('service')) {
                    categories.product.changes.push(change);
                } else if (field.includes('threat') || field.includes('risk')) {
                    categories.threat.changes.push(change);
                } else if (field.includes('employee') || field.includes('customer') || field.includes('funding') || field.includes('revenue') || field.includes('headquarters')) {
                    categories.company.changes.push(change);
                } else {
                    categories.other.changes.push(change);
                }
            });

            // Build HTML for categories with changes
            let html = '';
            Object.entries(categories).forEach(([key, cat]) => {
                if (cat.changes.length > 0) {
                    const uniqueCompetitors = [...new Set(cat.changes.map(c => c.competitor))];
                    const competitorList = uniqueCompetitors.slice(0, 3).join(', ');
                    const moreCount = uniqueCompetitors.length > 3 ? ` +${uniqueCompetitors.length - 3} more` : '';

                    html += `
                        <li class="change-category-item ${key}">
                            <span class="change-category-icon">${cat.icon}</span>
                            <span class="change-category-text">
                                <strong>${cat.changes.length} ${cat.label}</strong>
                                <span style="display: block; font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
                                    ${competitorList}${moreCount}
                                </span>
                            </span>
                        </li>
                    `;
                }
            });

            if (html) {
                categorizedList.innerHTML = html;
                categorizedSection.style.display = 'block';
            }
        }
    } catch (e) {
        console.error('Error loading categorized changes:', e);
    }
}

async function populateChangeDetails() {
    const detailsEl = document.getElementById('changeDetailsContent');
    if (!detailsEl) return;

    try {
        const session = await fetchAPI('/api/scrape/session');

        if (session && session.change_details && session.change_details.length > 0) {
            detailsEl.innerHTML = session.change_details.map(change => `
                <div class="change-detail-item ${change.type || 'change'}">
                    <div class="change-competitor">${escapeHtml(change.competitor || 'Unknown')}</div>
                    <div class="change-field">${escapeHtml(formatFieldName(change.field || ''))}</div>
                    <div class="change-values">
                        ${change.old_value ? `<span class="old-value">${escapeHtml(change.old_value)}</span> →` : ''}
                        <span class="new-value">${escapeHtml(change.new_value || 'N/A')}</span>
                    </div>
                </div>
            `).join('');
        } else {
            detailsEl.innerHTML = '<p style="color: #94a3b8; padding: 12px; text-align: center;">No detailed changes recorded for this refresh.</p>';
        }
    } catch (e) {
        console.error('Error loading change details:', e);
        detailsEl.innerHTML = '<p style="color: #94a3b8; padding: 12px;">Could not load change details.</p>';
    }
}

function toggleChangeDetails() {
    const content = document.getElementById('changeDetailsContent');
    const button = document.querySelector('.accordion-toggle');
    const arrow = document.querySelector('.toggle-arrow');

    if (!content) return;

    if (content.style.display === 'none') {
        content.style.display = 'block';
        if (button) button.classList.add('expanded');
        if (arrow) arrow.textContent = '▲';
    } else {
        content.style.display = 'none';
        if (button) button.classList.remove('expanded');
        if (arrow) arrow.textContent = '▼';
    }
}

function closeRefreshCompleteModal() {
    const modal = document.getElementById('refreshCompleteModal');
    if (modal) {
        modal.style.display = 'none';
    }

    // Reset accordion state
    const content = document.getElementById('changeDetailsContent');
    const button = document.querySelector('.accordion-toggle');
    const arrow = document.querySelector('.toggle-arrow');
    if (content) content.style.display = 'none';
    if (button) button.classList.remove('expanded');
    if (arrow) arrow.textContent = '▼';
}

// ============================================
// Inline Refresh Progress - Phase 1: Task 5.0.1-025
// ============================================

function showInlineRefreshProgress() {
    // Hide the data refresh indicator
    const indicator = document.getElementById('dataRefreshIndicator');
    if (indicator) {
        indicator.style.display = 'none';
    }

    // Show inline progress
    const inlineProgress = document.getElementById('inlineRefreshProgress');
    if (inlineProgress) {
        inlineProgress.style.display = 'block';
        document.getElementById('inlineProgressBar').style.width = '0%';
        document.getElementById('inlineProgressPercent').textContent = '0%';
        document.getElementById('inlineProgressText').textContent = 'Starting...';
        document.getElementById('inlineProgressCount').textContent = '0 / 0 competitors';
        document.getElementById('inlineProgressLive').innerHTML = '';
    }
}

function hideInlineRefreshProgress() {
    // Hide inline progress
    const inlineProgress = document.getElementById('inlineRefreshProgress');
    if (inlineProgress) {
        inlineProgress.style.display = 'none';
    }

    // Show the data refresh indicator again
    const indicator = document.getElementById('dataRefreshIndicator');
    if (indicator) {
        indicator.style.display = 'flex';
    }
}

function updateInlineProgress(progress) {
    const percent = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;

    const progressBar = document.getElementById('inlineProgressBar');
    const percentEl = document.getElementById('inlineProgressPercent');
    const countEl = document.getElementById('inlineProgressCount');
    const textEl = document.getElementById('inlineProgressText');
    const liveEl = document.getElementById('inlineProgressLive');

    if (progressBar) progressBar.style.width = `${percent}%`;
    if (percentEl) percentEl.textContent = `${percent}%`;
    if (countEl) countEl.textContent = `${progress.completed} / ${progress.total} competitors`;

    if (progress.current_competitor && textEl) {
        // v7.1.0: During enrichment phase, backend provides full status text
        textEl.textContent = progress.enrichment_active ? progress.current_competitor : `Scanning: ${progress.current_competitor}`;
    }

    // Update live feed with recent changes (if available from enhanced backend)
    if (progress.recent_changes && progress.recent_changes.length > 0 && liveEl) {
        liveEl.innerHTML = progress.recent_changes.slice(-5).map(change => `
            <div class="live-update-item ${change.type || 'change'}">
                <span class="change-icon">${change.type === 'new' ? '✨' : '📝'}</span>
                <span><strong>${escapeHtml(change.competitor || '')}</strong>: ${escapeHtml(change.field || '')} ${change.type === 'new' ? 'discovered' : 'updated'}</span>
            </div>
        `).join('');
    } else if (progress.competitors_done && progress.competitors_done.length > 0 && liveEl) {
        // Fallback: Show completed competitors as live updates
        const recentDone = progress.competitors_done.slice(-5);
        liveEl.innerHTML = recentDone.map(name => `
            <div class="live-update-item new">
                <span class="change-icon">✓</span>
                <span><strong>${name}</strong> data refreshed</span>
            </div>
        `).join('');
    }
}

// Global refresh polling state — survives page navigation
let _refreshPolling = false;
let _refreshPollInterval = null;

async function pollInlineRefreshProgress(total) {
    _refreshPolling = true;

    if (_refreshPollInterval) clearInterval(_refreshPollInterval);

    _refreshPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/scrape/progress`);
            if (!response.ok) throw new Error('Request failed');
            const progress = await response.json();

            // Update inline progress display only if DOM exists
            const inlineEl = document.getElementById('inlineRefreshProgress');
            if (inlineEl) {
                updateInlineProgress(progress);
            }

            // Also update the modal progress in case it's visible
            updateRefreshProgress(progress);

            // Check if complete (v7.1.0: also wait for enrichment phase to finish)
            if (!progress.active && !progress.enrichment_active && progress.completed >= progress.total && progress.total > 0) {
                clearInterval(_refreshPollInterval);
                _refreshPollInterval = null;
                _refreshPolling = false;

                // Ensure progress bar shows 100% before transitioning (only if DOM exists)
                const progressBar = document.getElementById('inlineProgressBar');
                const percentEl = document.getElementById('inlineProgressPercent');
                if (progressBar) progressBar.style.width = '100%';
                if (percentEl) percentEl.textContent = '100%';
                const textEl = document.getElementById('inlineProgressText');
                if (textEl) textEl.textContent = 'Refresh complete!';

                // Re-enable button if it exists
                const btn = document.querySelector('.btn-primary[onclick*="triggerScrapeAll"]');
                if (btn) {
                    btn.classList.remove('btn-loading');
                    btn.disabled = false;
                }

                // Brief delay to show 100% before hiding
                await new Promise(r => setTimeout(r, 1200));
                hideInlineRefreshProgress();

                // Only reload dashboard and show modal if dashboard DOM exists
                if (document.getElementById('dashboardPage')) {
                    try {
                        await loadDashboard();
                    } catch (e) {
                        console.error('[Refresh] Dashboard reload failed:', e);
                    }

                    try {
                        await showRefreshCompleteModal(progress);
                    } catch (e) {
                        console.error('[Refresh] Completion modal failed:', e);
                        showToast('Refresh complete! Check the dashboard for updated data.', 'success');
                    }
                } else {
                    showToast('Data refresh complete! Return to Dashboard to see updated data.', 'success');
                }

                // Update last refresh time
                updateLastRefreshTime();
            }
        } catch (e) {
            console.error('Error polling inline progress:', e);
        }
    }, 500);

    // Safety timeout after 10 minutes
    setTimeout(() => {
        if (_refreshPollInterval) {
            clearInterval(_refreshPollInterval);
            _refreshPollInterval = null;
            _refreshPolling = false;
            hideInlineRefreshProgress();
            const btn = document.querySelector('.btn-primary[onclick*="triggerScrapeAll"]');
            if (btn) {
                btn.classList.remove('btn-loading');
                btn.disabled = false;
            }
            showToast('Refresh timed out - check Change Log for any completed updates', 'warning');
        }
    }, 600000);
}

/**
 * Resume refresh progress UI when user returns to the dashboard.
 * Returns true if refresh is currently in progress.
 */
function resumeRefreshIfRunning() {
    if (!_refreshPolling) return false;

    const inlineProgress = document.getElementById('inlineRefreshProgress');
    if (inlineProgress) {
        inlineProgress.style.display = 'block';
    }

    const btn = document.querySelector('.btn-primary[onclick*="triggerScrapeAll"]');
    if (btn) {
        btn.classList.add('btn-loading');
        btn.disabled = true;
    }

    return true;
}

function updateLastRefreshTime() {
    const timeEl = document.getElementById('lastRefreshTime');
    if (timeEl) {
        const now = new Date();
        const options = {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short'
        };
        timeEl.textContent = now.toLocaleString('en-US', options);
    }
}

// ============================================
// End Inline Refresh Progress
// ============================================

async function pollRefreshProgress(total) {
    const btn = document.querySelector('.btn-primary[onclick*="triggerScrapeAll"]');
    let pollInterval = null;

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/scrape/progress`);
            if (!response.ok) throw new Error('Request failed');
            const progress = await response.json();

            updateRefreshProgress(progress);

            // Check if complete (v7.1.0: also wait for enrichment phase to finish)
            if (!progress.active && !progress.enrichment_active && progress.completed >= progress.total && progress.total > 0) {
                clearInterval(pollInterval);
                hideRefreshProgressModal();

                // Show completion modal
                showRefreshCompleteModal(progress);

                // Re-enable button
                if (btn) {
                    btn.classList.remove('btn-loading');
                    btn.disabled = false;
                }

                // Reload dashboard data
                await loadDashboard();
            }
        } catch (e) {
            console.error('Error polling progress:', e);
        }
    }, 500);

    // Safety timeout after 10 minutes
    setTimeout(() => {
        if (pollInterval) {
            clearInterval(pollInterval);
            hideRefreshProgressModal();
            if (btn) {
                btn.classList.remove('btn-loading');
                btn.disabled = false;
            }
            showToast('Refresh timed out - check Change Log for any completed updates', 'warning');
        }
    }, 600000);
}

function updateStatsCards() {
    // Ensure stats object exists before accessing properties
    if (!stats || typeof stats !== 'object') {
        console.warn('Stats object is empty or invalid:', stats);
        stats = {};
    }

    const totalEl = document.getElementById('totalCompetitors');
    const highEl = document.getElementById('highThreat');
    const mediumEl = document.getElementById('mediumThreat');
    const lowEl = document.getElementById('lowThreat');

    if (totalEl) totalEl.textContent = stats.total_competitors ?? 0;
    if (highEl) highEl.textContent = stats.high_threat ?? 0;
    if (mediumEl) mediumEl.textContent = stats.medium_threat ?? 0;
    if (lowEl) lowEl.textContent = stats.low_threat ?? 0;

}

function showCompanyList(threatLevel) {
    let filteredCompetitors = competitors;
    let title = 'All Competitors';
    let color = '#3A95ED';

    if (threatLevel !== 'all') {
        filteredCompetitors = competitors.filter(c => c.threat_level === threatLevel);
        title = `${threatLevel} Threat Competitors`;
        color = threatLevel === 'High' ? '#dc3545' : threatLevel === 'Medium' ? '#f59e0b' : '#22c55e';
    }

    const companiesList = filteredCompetitors.map((c, idx) => {
        const publicBadge = c.is_public ?
            `<span style="background: #22c55e; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.7em; margin-left: 8px;">PUBLIC ${c.ticker_symbol || ''}</span>` :
            `<span style="background: #64748b; color: white; padding: 1px 6px; border-radius: 3px; font-size: 0.7em; margin-left: 8px;">PRIVATE</span>`;
        return `<div style="padding: 16px 0; border-bottom: 1px solid #e2e8f0;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <span style="font-size: 1.1em;"><strong>${idx + 1}.</strong> ${escapeHtml(c.name)} ${publicBadge}</span>
                <button class="btn btn-sm btn-secondary" onclick="viewCompetitor(${c.id})" style="padding: 2px 8px; font-size: 0.8em;">View Profile</button>
            </div>
            
            <div style="display: flex; gap: 16px; flex-wrap: wrap; margin-left: 20px;">
                ${createEditableDataField('Pricing', c.pricing_model, c.id, 'pricing_model')}
                ${createEditableDataField('Customers', c.customer_count, c.id, 'customer_count')}
                ${createEditableDataField('Founded', c.year_founded, c.id, 'year_founded')}
            </div>
        </div>`;
    }).join('');

    const modalContent = `
        <div style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center;" onclick="this.remove()">
            <div style="background: white; border-radius: 12px; max-width: 600px; width: 90%; max-height: 80vh; overflow: hidden;" onclick="event.stopPropagation()">
                <div style="background: ${color}; color: white; padding: 20px; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0;">${title} (${filteredCompetitors.length})</h3>
                    <button onclick="this.closest('.company-list-modal').remove()" style="background: none; border: none; color: white; font-size: 24px; cursor: pointer;">×</button>
                </div>
                <div style="padding: 20px; max-height: 60vh; overflow-y: auto;">
                    ${companiesList || '<p style="color: #64748b;">No competitors found in this category.</p>'}
                </div>
            </div>
        </div>
    `;

    const modal = document.createElement('div');
    modal.className = 'company-list-modal';
    modal.innerHTML = modalContent;
    document.body.appendChild(modal);
}

function renderTopThreats() {
    const tbody = document.getElementById('topThreatsBody');
    if (!tbody) return;

    const highThreats = competitors.filter(c => c.threat_level === 'High');

    tbody.innerHTML = highThreats.slice(0, 5).map(comp => `
        <tr>
            <td>
                <div style="display:flex;align-items:center;gap:10px;">
                    ${createLogoImg(comp.website, comp.name, 32)}
                    <div>
                        <strong>${escapeHtml(comp.name)}</strong><br>
                        <a href="${comp.website}" target="_blank" class="competitor-website" style="font-size:12px;color:#64748b;">${comp.website ? new URL(comp.website).hostname : '—'}</a>
                    </div>
                </div>
            </td>
            <td><span class="threat-badge ${(comp.threat_level || 'medium').toLowerCase()}">${comp.threat_level || 'Medium'}</span></td>
            <td><span style="display:flex;align-items:center;gap:4px;">${renderSourceDot(comp.id, 'customer_count', comp.customer_count)} ${createSourcedValue(comp.customer_count, comp.id, 'customer_count')}</span></td>
            <td><span style="display:flex;align-items:center;gap:4px;">${renderSourceDot(comp.id, 'base_price', comp.base_price)} ${createSourcedValue(comp.base_price, comp.id, 'base_price')}</span></td>
            <td>${formatDate(comp.last_updated)}</td>
            <td style="display: flex; gap: 6px;">
                <button class="btn btn-secondary" onclick="viewCompetitor(${comp.id})">View</button>
                <button class="btn-view-sources" onclick="viewDataSources(${comp.id})" title="View Data Sources">📋</button>
            </td>
        </tr>
    `).join('');
}

function renderRecentChanges() {
    const container = document.getElementById('recentChanges');
    if (!container) return;

    container.innerHTML = changes.slice(0, 5).map(change => `
        <div class="change-item">
            <div class="change-icon ${change.severity.toLowerCase()}">
                ${change.severity === 'High' ? '🔴' : change.severity === 'Medium' ? '🟡' : '🔵'}
            </div>
            <div class="change-content">
                <div class="change-title">${escapeHtml(change.competitor_name || '')}: ${escapeHtml(change.change_type || '')}</div>
                <div class="change-details">
                    ${change.previous_value ? `Changed from "${escapeHtml(change.previous_value)}" to ` : 'Set to '}
                    "${escapeHtml(change.new_value || '')}"
                </div>
            </div>
            <div class="change-time">${formatDate(change.detected_at)}</div>
        </div>
    `).join('') || '<p class="empty-state">No recent changes</p>';
}

function renderThreatChart() {
    const ctx = document.getElementById('threatChart')?.getContext('2d');
    if (!ctx) return;

    if (threatChart) threatChart.destroy();

    threatChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['High', 'Medium', 'Low'],
            datasets: [{
                data: [stats.high_threat || 0, stats.medium_threat || 0, stats.low_threat || 0],
                backgroundColor: ['#DC3545', '#FFC107', '#28A745'],
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    const threatLevel = ['High', 'Medium', 'Low'][idx];
                    drillDownToCompetitors(threatLevel);
                }
            }
        }
    });
}

async function renderTopThreatsChart(limit) {
    const ctx = document.getElementById('topThreatsChart')?.getContext('2d');
    if (!ctx) return;

    if (topThreatsChart) topThreatsChart.destroy();

    const threatLimit = limit || parseInt(document.getElementById('threatCountSelect')?.value) || 5;

    try {
        const rawData = await fetchAPI(`/api/dashboard/top-threats?limit=${threatLimit}`);
        let data = rawData?.top_threats || (Array.isArray(rawData) ? rawData : null);

        // Fallback: use top N competitors sorted by threat level from local data
        if (!data || data.length === 0) {
            const threatOrder = { 'High': 3, 'Medium': 2, 'Low': 1 };
            data = [...competitors]
                .sort((a, b) => (threatOrder[b.threat_level] || 0) - (threatOrder[a.threat_level] || 0))
                .slice(0, threatLimit);
        }

        // If still no data, show placeholder
        if (!data || data.length === 0) {
            const canvas = document.getElementById('topThreatsChart');
            if (canvas && canvas.parentElement) {
                canvas.parentElement.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-secondary);">No competitor data available yet. Run a data refresh to populate threats.</div>';
            }
            return;
        }

        const labels = data.map(t => t.name || 'Unknown');
        // Use product_overlap_score, falling back to threat level numeric value
        const threatNumeric = { 'High': 85, 'Medium': 55, 'Low': 25 };
        const scores = data.map(t => {
            const overlap = t.product_overlap_score || 0;
            return overlap > 0 ? overlap : (threatNumeric[t.threat_level] || 10);
        });
        const colors = data.map(t => {
            const level = t.threat_level || 'Low';
            return level === 'High' ? '#DC3545' : level === 'Medium' ? '#FFC107' : '#28A745';
        });

        topThreatsChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Threat Score',
                    data: scores,
                    backgroundColor: colors,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, max: 100, title: { display: true, text: 'Threat Score' } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const compName = labels[idx];
                        const comp = competitors.find(c => c.name === compName);
                        if (comp) {
                            showPage('competitors');
                            setTimeout(() => viewCompetitor(comp.id), 200);
                        }
                    }
                }
            }
        });
    } catch (e) {
        console.error('Error rendering top threats chart:', e);
    }
}

/**
 * Render threat level trend line chart on Dashboard.
 * Fetches from GET /api/dashboard/threat-trends and draws 3 lines (High, Medium, Low).
 */
async function renderThreatTrendChart(days) {
    const container = document.getElementById('threatTrendChartContainer');
    const canvas = document.getElementById('threatTrendChart');
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (threatTrendChart) threatTrendChart.destroy();

    const trendDays = days || 90;

    // Loading state
    container.style.position = 'relative';
    const loader = document.createElement('div');
    loader.id = 'threatTrendLoader';
    loader.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:var(--bg-secondary);border-radius:8px;z-index:2;';
    loader.innerHTML = '<div class="spinner" style="margin:0 auto;"></div>';
    container.appendChild(loader);

    try {
        const data = await fetchAPI(`/api/dashboard/threat-trends?days=${trendDays}`, { silent: true });

        // Remove loader
        const loaderEl = document.getElementById('threatTrendLoader');
        if (loaderEl) loaderEl.remove();

        if (!data || !data.labels || !data.labels.length) {
            container.innerHTML = '<canvas id="threatTrendChart"></canvas><div style="text-align:center;padding:40px;color:var(--text-secondary);">No trend data available yet. Run data refreshes to build trend history.</div>';
            return;
        }

        // Backend returns datasets nested: { labels, datasets: { high, medium, low } }
        const ds = data.datasets || data;

        threatTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'High Threat',
                        data: ds.high || [],
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointBackgroundColor: '#ef4444',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Medium Threat',
                        data: ds.medium || [],
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointBackgroundColor: '#f59e0b',
                        tension: 0.3,
                        fill: true
                    },
                    {
                        label: 'Low Threat',
                        data: ds.low || [],
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointBackgroundColor: '#22c55e',
                        tension: 0.3,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: '#e2e8f0',
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 16,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(15, 23, 42, 0.9)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#e2e8f0',
                        borderColor: 'rgba(148, 163, 184, 0.2)',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        ticks: { color: '#94a3b8', font: { size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 11 },
                            stepSize: 1,
                            precision: 0
                        },
                        title: {
                            display: true,
                            text: 'Number of Competitors',
                            color: '#94a3b8',
                            font: { size: 12 }
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    } catch (e) {
        // Remove loader on error
        const loaderEl = document.getElementById('threatTrendLoader');
        if (loaderEl) loaderEl.remove();

        console.error('[Dashboard] Threat trend chart failed:', e);
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = 'text-align:center;padding:40px;color:var(--text-secondary);';
        errorDiv.textContent = 'Unable to load threat trend data.';
        container.appendChild(errorDiv);
    }
}

// ==============================================================================
// Dashboard: Date Range Picker + Threat Count Select
// ==============================================================================

function initDashboardControls() {
    // Date range picker for threat trends
    const picker = document.getElementById('trendDateRangePicker');
    if (picker) {
        picker.addEventListener('click', (e) => {
            const btn = e.target.closest('.range-btn');
            if (!btn) return;
            picker.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const days = parseInt(btn.dataset.days) || 90;
            renderThreatTrendChart(days);
        });
    }

    // Threat count select for top threats chart
    const threatSelect = document.getElementById('threatCountSelect');
    if (threatSelect) {
        threatSelect.addEventListener('change', () => {
            const limit = parseInt(threatSelect.value) || 5;
            renderTopThreatsChart(limit);
        });
    }
}

// ==============================================================================
// Competitors: View Toggle (Grid/List) + Sort
// ==============================================================================

let currentCompetitorView = localStorage.getItem('competitorView') || 'grid';
let currentCompetitorSort = localStorage.getItem('competitorSort') || '';

function setCompetitorView(view) {
    currentCompetitorView = view;
    localStorage.setItem('competitorView', view);

    // Update toggle button state
    const toggle = document.getElementById('competitorViewToggle');
    if (toggle) {
        toggle.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === view);
        });
    }

    applyCompetitorFilters();
}

function sortCompetitorData(comps, sortBy) {
    if (!sortBy) return comps;
    return [...comps].sort((a, b) => {
        switch (sortBy) {
            case 'name-asc': return (a.name || '').localeCompare(b.name || '');
            case 'name-desc': return (b.name || '').localeCompare(a.name || '');
            case 'threat': {
                const order = { 'High': 3, 'Medium': 2, 'Low': 1 };
                return (order[b.threat_level] || 0) - (order[a.threat_level] || 0);
            }
            case 'employees': return (b.employee_count || 0) - (a.employee_count || 0);
            default: return 0;
        }
    });
}

function applyCompetitorFilters() {
    const threatFilter = document.getElementById('filterThreat')?.value || '';
    const statusFilter = document.getElementById('filterStatus')?.value || '';
    const sortBy = document.getElementById('sortCompetitors')?.value || currentCompetitorSort;

    let filtered = competitors.filter(c => {
        if (threatFilter && c.threat_level !== threatFilter) return false;
        if (statusFilter && c.status !== statusFilter) return false;
        return true;
    });

    filtered = sortCompetitorData(filtered, sortBy);

    if (currentCompetitorView === 'list') {
        renderCompetitorsList(filtered);
    } else {
        renderCompetitorsGrid(filtered);
    }
}

function renderCompetitorsList(comps = competitors) {
    const grid = document.getElementById('competitorsGrid');
    if (!grid) return;

    if (comps.length === 0) {
        grid.innerHTML = '<div class="empty-state" style="text-align:center;padding:60px 20px;"><h4 style="color:var(--text-primary);">No competitors match your filters</h4></div>';
        return;
    }

    grid.innerHTML = `<table class="competitor-list-table">
        <thead>
            <tr>
                <th>Company</th>
                <th>Threat Level</th>
                <th>Customers</th>
                <th>Employees</th>
                <th>G2 Rating</th>
                <th>Last Updated</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            ${comps.map(comp => `<tr>
                <td>
                    <div style="display:flex;align-items:center;gap:10px;">
                        ${createLogoImg(comp.website, comp.name, 28)}
                        <div>
                            <strong>${escapeHtml(comp.name)}</strong>
                            <div style="font-size:11px;color:var(--text-muted);">${comp.website ? comp.website.replace('https://', '').replace('www.', '') : ''}</div>
                        </div>
                    </div>
                </td>
                <td><span class="threat-badge ${(comp.threat_level || 'medium').toLowerCase()}">${escapeHtml(comp.threat_level || 'N/A')}</span></td>
                <td>${comp.customer_count || 'N/A'}</td>
                <td>${comp.employee_count || 'N/A'}</td>
                <td>${comp.g2_rating || 'N/A'}</td>
                <td>${formatDate(comp.last_updated)}</td>
                <td style="display:flex;gap:6px;">
                    <button class="btn btn-primary btn-sm" onclick="viewBattlecard(${comp.id})" title="Battlecard">Battlecard</button>
                    <button class="btn btn-secondary btn-sm" onclick="viewCompetitor(${comp.id})" title="View Details">View</button>
                </td>
            </tr>`).join('')}
        </tbody>
    </table>`;
}

// Wire up sort change
function initCompetitorControls() {
    const sortSelect = document.getElementById('sortCompetitors');
    if (sortSelect) {
        // Restore saved sort
        if (currentCompetitorSort) {
            sortSelect.value = currentCompetitorSort;
        }
        sortSelect.addEventListener('change', () => {
            currentCompetitorSort = sortSelect.value;
            localStorage.setItem('competitorSort', currentCompetitorSort);
            applyCompetitorFilters();
        });
    }

    // Restore saved view toggle state
    const toggle = document.getElementById('competitorViewToggle');
    if (toggle) {
        toggle.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === currentCompetitorView);
        });
    }
}

window.setCompetitorView = setCompetitorView;
window.applyCompetitorFilters = applyCompetitorFilters;

function drillDownToCompetitors(threatLevel) {
    showPage('competitors');
    setTimeout(() => {
        const filterSelect = document.getElementById('filterThreat');
        if (filterSelect) {
            filterSelect.value = threatLevel;
            applyCompetitorFilters();
        }
    }, 200);
}
window.drillDownToCompetitors = drillDownToCompetitors;

// ==============================================================================
// Dashboard Mini Widgets
// ==============================================================================

async function loadDashboardMiniWidgets() {
    // 1. Activity Trend
    try {
        const trend = await fetchAPI('/api/analytics/activity-trend?days=30', { silent: true });
        const el = document.getElementById('miniActivityTrend');
        if (el && trend) {
            const totalNews = (trend.news_activity || []).reduce((s, v) => s + v, 0);
            const totalProducts = (trend.product_updates || []).reduce((s, v) => s + v, 0);
            el.textContent = totalNews + totalProducts;

            // Draw tiny sparkline
            const sparkContainer = document.getElementById('miniActivitySparkline');
            if (sparkContainer && trend.news_activity && trend.news_activity.length > 0) {
                const canvas = document.createElement('canvas');
                canvas.width = 60;
                canvas.height = 24;
                sparkContainer.innerHTML = '';
                sparkContainer.appendChild(canvas);
                const ctx = canvas.getContext('2d');
                const data = trend.news_activity.slice(-14);
                const max = Math.max(...data, 1);
                const step = 60 / Math.max(data.length - 1, 1);
                ctx.beginPath();
                ctx.strokeStyle = '#3b82f6';
                ctx.lineWidth = 1.5;
                data.forEach((v, i) => {
                    const x = i * step;
                    const y = 22 - (v / max) * 20;
                    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                });
                ctx.stroke();
            }
        }
    } catch (e) { /* silent */ }

    // 2. Data Freshness
    try {
        const el = document.getElementById('miniDataFreshness');
        if (el && competitors && competitors.length > 0) {
            const now = Date.now();
            const recentUpdate = competitors.reduce((latest, c) => {
                const t = c.last_updated ? new Date(c.last_updated).getTime() : 0;
                return t > latest ? t : latest;
            }, 0);
            if (recentUpdate > 0) {
                const hoursAgo = Math.round((now - recentUpdate) / (1000 * 60 * 60));
                if (hoursAgo < 1) {
                    el.textContent = 'Just now';
                    el.style.color = '#10b981';
                } else if (hoursAgo < 24) {
                    el.textContent = hoursAgo + 'h ago';
                    el.style.color = '#10b981';
                } else {
                    const daysAgo = Math.round(hoursAgo / 24);
                    el.textContent = daysAgo + 'd ago';
                    el.style.color = daysAgo > 7 ? '#f59e0b' : '#10b981';
                }
            } else {
                el.textContent = 'N/A';
            }
        }
    } catch (e) { /* silent */ }

    // 3. Win Rate
    try {
        const dealStats = await fetchAPI('/api/deals/stats', { silent: true });
        const el = document.getElementById('miniWinRate');
        if (el && dealStats && !dealStats.error) {
            const wins = dealStats.total_wins || dealStats.wins || 0;
            const losses = dealStats.total_losses || dealStats.losses || 0;
            const total = wins + losses;
            if (total > 0) {
                const rate = Math.round((wins / total) * 100);
                el.textContent = rate + '%';
                el.style.color = rate >= 50 ? '#10b981' : '#f59e0b';
            } else {
                el.textContent = 'No data';
            }
        }
    } catch (e) { /* silent */ }

    // 4. Active Users
    try {
        const summary = await fetchAPI('/api/activity-logs/summary?days=7', { silent: true });
        const el = document.getElementById('miniActiveUsers');
        if (el && summary) {
            const userCount = (summary.by_user || []).length;
            el.textContent = userCount;
        }
    } catch (e) { /* silent */ }
}

// ============== Competitors ==============

async function loadCompetitors() {
    // Show skeleton loading state
    const grid = document.getElementById('competitorsGrid');
    if (grid) {
        showSkeleton('competitorsGrid', 'cards', 6);
    }

    try {
        competitors = await fetchAPI('/api/competitors') || [];
        populateCompanyFilter();
        initCompetitorControls();
        applyCompetitorFilters();
    } catch (error) {
        console.error('Failed to load competitors:', error);
        if (grid) {
            grid.innerHTML = `
                <div class="empty-state" style="text-align: center; padding: 60px 20px; grid-column: 1/-1;">
                    <i class="fas fa-exclamation-circle" style="font-size: 3rem; color: var(--danger); opacity: 0.5; margin-bottom: 20px; display: block;"></i>
                    <h4 style="color: var(--text-primary); margin-bottom: 10px;">Failed to Load Competitors</h4>
                    <p style="color: var(--text-muted); max-width: 400px; margin: 0 auto 20px;">
                        Unable to fetch competitor data. Please check your connection and try again.
                    </p>
                    <button class="btn btn-primary" onclick="loadCompetitors()">
                        <i class="fas fa-sync"></i> Retry
                    </button>
                </div>
            `;
        }
    }
}

function populateCompanyFilter() {
    const select = document.getElementById('filterCompany');
    if (!select) return;

    // Save current selection if re-populating
    const currentVal = select.value;

    select.innerHTML = '<option value="">All Companies</option>' +
        competitors.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');

    select.value = currentVal;
}

function filterCompetitors() {
    applyCompetitorFilters();
}

function renderCompetitorsGrid(comps = competitors) {
    const grid = document.getElementById('competitorsGrid');
    if (!grid) return;

    grid.innerHTML = comps.map(comp => {
        // Determine public/private status block
        const isPublic = comp.is_public;
        const ticker = comp.ticker_symbol || '';
        const exchange = comp.stock_exchange || '';

        let statusBlock = '';
        if (isPublic && ticker) {
            statusBlock = `
                <div class="stock-info-block" data-ticker="${ticker}" style="margin-top: 4px;">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: nowrap;">
                        <span style="background: #22c55e; color: white; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 700;">PUBLIC</span>
                        <span style="font-weight: 700; color: #122753; font-size: 12px;">${ticker} <small style="color: #64748b; font-weight: 400;">(${exchange})</small></span>
                        <span id="price-${comp.id}" style="font-weight: 700; color: #122753; font-size: 13px;">---</span>
                    </div>
                </div>
            `;
        } else {
            statusBlock = `
                <div style="margin-top: 6px;">
                    <span style="background: #64748b; color: white; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 700;">PRIVATE</span>
                </div>
            `;
        }

        // P2-1: Calculate data freshness badge
        const freshness = getDataFreshnessBadge(comp.last_updated);

        return `
        <div class="competitor-card" data-id="${comp.id}">
            <div class="competitor-header">
                <div style="display:flex;align-items:flex-start;gap:12px; width: 100%;">
                    ${createLogoImg(comp.website, comp.name, 40)}
                    <div style="flex: 1; min-width: 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
                            <div class="competitor-name" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(comp.name)}</div>
                            <div style="display: flex; gap: 6px; align-items: center; flex-shrink: 0;">
                                ${freshness.badge}
                                <span class="threat-badge ${(comp.threat_level || 'medium').toLowerCase()}" style="font-size: 0.8em;">${comp.threat_level || 'Medium'}</span>
                            </div>
                        </div>
                        <a href="${comp.website}" target="_blank" class="competitor-website" style="display: block; margin-top: 0px;">${comp.website.replace('https://', '').replace('www.', '')}</a>
                        ${statusBlock}
                    </div>
                </div>
            </div>
            
            <div class="competitor-details">
                <div class="detail-item">
                    <span class="detail-icon">👥</span>
                    <span class="detail-label">Customers</span>
                    <div class="detail-value">${createSourcedValue(comp.customer_count, comp.id, 'customer_count')}</div>
                </div>
                <div class="detail-item">
                    <span class="detail-icon">💰</span>
                    <span class="detail-label">Pricing</span>
                    <div class="detail-value">${createSourcedValue(comp.base_price, comp.id, 'base_price')}</div>
                </div>
                <div class="detail-item">
                    <span class="detail-icon">👔</span>
                    <span class="detail-label">Employees</span>
                    <div class="detail-value">${createSourcedValue(comp.employee_count, comp.id, 'employee_count')}</div>
                </div>
                <div class="detail-item">
                    <span class="detail-icon">⭐</span>
                    <span class="detail-label">G2 Rating</span>
                    <div class="detail-value">${createSourcedValue(comp.g2_rating ? comp.g2_rating : null, comp.id, 'g2_rating')}</div>
                </div>
            </div>

            <div id="verif-bar-${comp.id}" style="padding: 0 16px;">
                <div style="display:flex;align-items:center;gap:6px;font-size:10px;color:#94a3b8;">
                    <span class="confidence-dot confidence-unknown" style="width:6px;height:6px;"></span> Loading verification...
                </div>
            </div>

            <div class="competitor-actions">
                <button class="btn btn-primary" onclick="viewBattlecard(${comp.id})" title="View Battlecard">
                    📄 Battlecard
                </button>
                <button class="btn btn-secondary" onclick="showCompetitorInsights(${comp.id})" title="AI Analysis">
                    🧠 Insights
                </button>
                <button class="btn btn-secondary" onclick="toggleCompetitorMenu(event, ${comp.id})" title="More Actions">
                    ⋯
                </button>
            </div>
        </div>
    `}).join('');

    // Fetch live stock prices for public companies
    comps.filter(c => c.is_public && c.ticker_symbol).forEach(comp => {
        fetchLiveStockPrice(comp.id, comp.name);
    });

    // v7.2: Load verification summaries for competitor cards
    _loadCompetitorVerificationBars(comps);

    // Add bulk selection checkboxes to cards
    addBulkCheckboxesToCards();
}

async function fetchLiveStockPrice(competitorId, companyName) {
    try {
        const response = await fetch(`${API_BASE}/api/stock/${encodeURIComponent(companyName)}`);
        if (!response.ok) throw new Error('Request failed');
        const data = await response.json();

        const priceEl = document.getElementById(`price-${competitorId}`);
        if (priceEl && data.is_public && data.price) {
            // Apply navy color for price, green/red for change only
            const changeColor = data.change >= 0 ? '#22c55e' : '#dc3545';
            const changeSign = data.change >= 0 ? '+' : '';
            priceEl.innerHTML = `
                <span style="color: #122753;">$${data.price.toFixed(2)}</span> 
                <span style="color: ${changeColor}; font-size: 0.9em; margin-left: 4px;">(${changeSign}${data.change_percent?.toFixed(1)}%)</span>
            `;
        }
    } catch (e) {
        // Silent fail for stock price fetch
    }
}

function viewCompetitor(id) {
    const comp = competitors.find(c => c.id === id);
    if (!comp) return;

    // Build SEC section if public company
    const secSection = comp.is_public && comp.sec_cik ? `
        <div style="background:#f0f9ff;border-radius:8px;padding:12px;margin-top:16px;">
            <h4 style="margin:0 0 8px 0;display:flex;align-items:center;gap:6px;">
                📊 SEC EDGAR Filings ${createSourceLink('sec', comp.sec_cik)}
            </h4>
            <div style="font-size:13px;color:#0369a1;">
                <strong>CIK:</strong> ${comp.sec_cik} | 
                <strong>Fiscal Year End:</strong> ${comp.fiscal_year_end || '—'}
            </div>
            <div style="margin-top:8px;">
                ${formatSecFilings(comp.recent_sec_filings, comp.sec_cik) || '<span style="color:#64748b;">No recent filings</span>'}
            </div>
            ${comp.annual_revenue ? `<div style="margin-top:8px;"><strong>Revenue:</strong> ${comp.annual_revenue}</div>` : ''}
        </div>
    ` : '';

    // Build contacts section if available
    const contactsSection = comp.key_contacts || comp.email_pattern ? `
        <div style="background:#fef3c7;border-radius:8px;padding:12px;margin-top:16px;">
            <h4 style="margin:0 0 8px 0;display:flex;align-items:center;gap:6px;">
                📧 Key Contacts ${createSourceLink('hunter', comp.website)}
            </h4>
            ${comp.email_pattern ? `<div style="font-size:12px;color:#92400e;margin-bottom:8px;">Email Pattern: <code style="background:#fef3c7;padding:2px 6px;border-radius:3px;">${comp.email_pattern}@${comp.website?.replace('https://', '').replace('http://', '').split('/')[0] || 'company.com'}</code></div>` : ''}
            ${formatKeyContacts(comp.key_contacts, comp.website) || '<span style="color:#64748b;">No contacts found</span>'}
        </div>
    ` : '';

    const content = `
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
            ${createLogoImg(comp.website, comp.name, 64)}
            <div style="flex:1;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <h2 style="margin:0;">${escapeHtml(comp.name)}</h2>
                    <span class="threat-badge ${(comp.threat_level || '').toLowerCase()}" style="font-size:0.9em; padding:4px 12px;">${comp.threat_level || '—'} Threat</span>
                </div>
                <p style="margin:4px 0;">
                    <a href="${comp.website}" target="_blank" style="color:#0ea5e9;">${comp.website}</a>
                    ${createSourceLink('website', comp.website)}
                </p>
            </div>
        </div>
        
        <div id="stockSection">
            <!-- Stock data loaded here via loadCompanyStockData -->
        </div>

        <hr>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            ${createEditableDataField('Status', comp.status, comp.id, 'status')}
            ${createEditableDataField('Pricing Model', comp.pricing_model, comp.id, 'pricing_model')}
            ${createEditableDataField('Base Price', comp.base_price, comp.id, 'base_price')}
            ${createEditableDataField('Customers', comp.customer_count, comp.id, 'customer_count')}
            ${createEditableDataField('Employees', comp.employee_count, comp.id, 'employee_count')}
            ${createEditableDataField('G2 Rating', comp.g2_rating, comp.id, 'g2_rating')}
            ${createEditableDataField('Founded', comp.year_founded, comp.id, 'year_founded')}
            ${createEditableDataField('Headquarters', comp.headquarters, comp.id, 'headquarters')}
            ${createEditableDataField('Funding', comp.funding_total, comp.id, 'funding_total')}
        </div>
        ${secSection}
        ${contactsSection}
        <hr>
        <h4>Products ${createSourceLink('website', comp.website)}</h4>
        <p>${createSourcedValue(comp.product_categories, 'website', comp.website, 'products')}</p>
        <h4>Key Features</h4>
        <p>${createSourcedValue(comp.key_features, 'website', comp.website, 'features')}</p>
        <h4>Integrations</h4>
        <p>${createSourcedValue(comp.integration_partners, 'website', comp.website, 'integrations')}</p>
    `;

    showModal(content);

    // Load stock data if company is public or we have a ticker
    if (comp.ticker || comp.is_public) {
        loadCompanyStockData(comp.name);
    }
}

function editCompetitor(id) {
    const comp = competitors.find(c => c.id === id);
    if (!comp) return;

    const content = `
        <h2>Edit ${escapeHtml(comp.name)}</h2>
        <form id="editCompetitorForm" onsubmit="saveCompetitor(event, ${id})">
            <div class="form-group">
                <label>Name</label>
                <input type="text" name="name" value="${escapeHtml(comp.name)}" required>
            </div>
            <div class="form-group">
                <label>Website</label>
                <input type="url" name="website" value="${comp.website}" required>
            </div>
            <div class="form-group">
                <label>Threat Level</label>
                <select name="threat_level">
                    <option value="High" ${comp.threat_level === 'High' ? 'selected' : ''}>High</option>
                    <option value="Medium" ${comp.threat_level === 'Medium' ? 'selected' : ''}>Medium</option>
                    <option value="Low" ${comp.threat_level === 'Low' ? 'selected' : ''}>Low</option>
                </select>
            </div>
            <div class="form-group">
                <label>Pricing Model</label>
                <input type="text" name="pricing_model" value="${comp.pricing_model || ''}">
            </div>
            <div class="form-group">
                <label>Base Price</label>
                <input type="text" name="base_price" value="${comp.base_price || ''}">
            </div>
            <div class="form-group">
                <label>Notes</label>
                <textarea name="notes" rows="3">${comp.notes || ''}</textarea>
            </div>
            <button type="submit" class="btn btn-primary">Save Changes</button>
        </form>
    `;

    showModal(content);
}

async function saveCompetitor(event, id) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    const result = await fetchAPI(`/api/competitors/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data)
    });

    if (result) {
        showToast('Competitor updated successfully', 'success');
        closeModal();
        loadCompetitors();
    }
}

function showAddCompetitorModal() {
    const content = `
        <h2>Add New Competitor</h2>
        <form id="addCompetitorForm" onsubmit="createCompetitor(event)">
            <div class="form-group">
                <label>Name *</label>
                <input type="text" name="name" placeholder="Enter competitor name">
            </div>
            <div class="form-group">
                <label>Website *</label>
                <input type="text" name="website" placeholder="https://example.com">
            </div>
            <div class="form-group">
                <label>Threat Level</label>
                <select name="threat_level">
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Low">Low</option>
                </select>
            </div>
            <div class="form-group">
                <label>Pricing Model</label>
                <input type="text" name="pricing_model" placeholder="e.g., Per user/month">
            </div>
            <div class="form-group">
                <label>Base Price</label>
                <input type="text" name="base_price" placeholder="e.g., $99">
            </div>
            <button type="submit" class="btn btn-primary">Add Competitor</button>
        </form>
    `;

    showModal(content);

    // Setup real-time validation after modal is shown
    setTimeout(() => {
        const form = document.getElementById('addCompetitorForm');
        if (form) {
            const rules = {
                name: [validationRules.required, validationRules.minLength(2)],
                website: [validationRules.required, validationRules.url]
            };
            setupRealtimeValidation(form, rules);
        }
    }, 100);
}

async function createCompetitor(event) {
    event.preventDefault();
    const form = event.target;

    // Validate form before submission
    const rules = {
        name: [validationRules.required, validationRules.minLength(2)],
        website: [validationRules.required, validationRules.url]
    };

    if (!validateForm(form, rules)) {
        showToast('Please fix the validation errors before submitting', 'error');
        return;
    }

    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    const result = await fetchAPI('/api/competitors', {
        method: 'POST',
        body: JSON.stringify(data)
    });

    if (result) {
        showToast('Competitor added successfully', 'success');
        closeModal();
        loadCompetitors();
    }
}

async function deleteCompetitor(id) {
    if (!confirm('Are you sure you want to delete this competitor? This action cannot be undone.')) return;

    const result = await fetchAPI(`/api/competitors/${id}`, {
        method: 'DELETE'
    });

    if (result) {
        showToast('Competitor deleted successfully', 'success');
        loadCompetitors();
    }
}

// ============== Changes ==============

/**
 * Load approved manual edits cache for styling
 */
async function loadApprovedFieldsCache() {
    try {
        const response = await fetchAPI('/api/data-changes/approved-fields', { silent: true });
        if (response?.approved_fields) {
            Object.entries(response.approved_fields).forEach(([key, data]) => {
                manualEditCache[key] = data;
            });
        }
    } catch (e) {
    }
}

/**
 * Load pending data changes for admin review
 */
async function loadPendingChanges() {
    try {
        const response = await fetchAPI('/api/data-changes/pending');
        return response?.changes || [];
    } catch (e) {
        return [];
    }
}

/**
 * Approve a pending data change (admin only)
 */
async function approveDataChange(changeId) {
    try {
        const response = await fetchAPI(`/api/data-changes/${changeId}/approve`, {
            method: 'POST'
        });
        if (response?.success) {
            showToast('Change approved and applied', 'success');
            loadChanges(); // Refresh the list
        } else {
            showToast(response?.message || 'Failed to approve change', 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

/**
 * Reject a pending data change (admin only)
 */
async function rejectDataChange(changeId) {
    const reason = prompt('Reason for rejection (optional):');
    try {
        const response = await fetchAPI(`/api/data-changes/${changeId}/reject?reason=${encodeURIComponent(reason || '')}`, {
            method: 'POST'
        });
        if (response?.success) {
            showToast('Change rejected', 'info');
            loadChanges(); // Refresh the list
        } else {
            showToast(response?.message || 'Failed to reject change', 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

async function loadChanges() {
    const severity = document.getElementById('filterSeverity')?.value || '';
    const days = document.getElementById('filterDays')?.value || 7;
    const competitorId = document.getElementById('filterCompany')?.value || '';

    let url = `/api/changes?days=${days}`;
    if (severity) url += `&severity=${severity}`;
    if (competitorId) url += `&competitor_id=${competitorId}`;

    // Load both regular changes and pending changes
    const [result, pendingChanges] = await Promise.all([
        fetchAPI(url),
        loadPendingChanges()
    ]);

    changes = result?.changes || [];

    const container = document.getElementById('changesList');
    if (!container) return;

    // Render pending changes section (for admins)
    let pendingHtml = '';
    if (pendingChanges.length > 0) {
        pendingHtml = `
            <div class="pending-changes-section" style="margin-bottom: 24px; background: #fef3c7; border-radius: 12px; padding: 16px;">
                <h4 style="margin: 0 0 12px 0; color: #92400e; display: flex; align-items: center; gap: 8px;">
                    <span>⏳</span> Pending Approval (${pendingChanges.length})
                </h4>
                ${pendingChanges.map(p => `
                    <div class="pending-change-item" style="background: white; border-radius: 8px; padding: 12px; margin-bottom: 8px; border: 1px solid #f59e0b;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <div style="font-weight: 600; color: #1e293b; margin-bottom: 4px;">
                                    ${p.competitor_name}: <span class="clickable-label" onclick="openDataFieldPopup(${p.competitor_id}, '${p.field_name}', '${p.field_name}', '${p.new_value || ''}')">${p.field_name}</span>
                                </div>
                                <div style="font-size: 13px; color: #64748b;">
                                    ${p.old_value ? `"${p.old_value}"` : 'N/A'} → "${p.new_value}"
                                </div>
                                ${p.source_url ? `<div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">Source: <a href="${p.source_url}" target="_blank" style="color: #3b82f6;">${p.source_url.substring(0, 40)}...</a></div>` : ''}
                                ${p.notes ? `<div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">Notes: ${p.notes}</div>` : ''}
                                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">By ${p.submitted_by} • ${formatDate(p.submitted_at)}</div>
                            </div>
                            <div style="display: flex; gap: 6px;">
                                <button class="approve-btn" onclick="approveDataChange(${p.id})">✓ Approve</button>
                                <button class="reject-btn" onclick="rejectDataChange(${p.id})">✗ Reject</button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    if (changes.length === 0 && pendingChanges.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="text-align: center; padding: 60px 20px;">
                <i class="fas fa-history" style="font-size: 3rem; color: var(--text-muted); opacity: 0.5; margin-bottom: 20px; display: block;"></i>
                <h4 style="color: var(--text-primary); margin-bottom: 10px;">No Changes Detected</h4>
                <p style="color: var(--text-muted); max-width: 400px; margin: 0 auto 20px;">
                    No competitor changes have been detected in the selected time period.
                    Changes are tracked automatically when competitor data is refreshed.
                </p>
                <button class="btn btn-primary" onclick="document.getElementById('filterDays').value = '30'; loadChanges();">
                    <i class="fas fa-search"></i> Search Last 30 Days
                </button>
            </div>
        `;
        return;
    }

    const changesHtml = changes.map(change => `
        <div class="change-item">
            <div class="change-icon ${change.severity.toLowerCase()}">
                ${change.severity === 'High' ? '🔴' : change.severity === 'Medium' ? '🟡' : '🔵'}
            </div>
            <div class="change-content">
                <div class="change-title">${escapeHtml(change.competitor_name || '')}: ${escapeHtml(change.change_type || '')}</div>
                <div class="change-details">
                    ${change.previous_value ? `Changed from "${escapeHtml(change.previous_value)}" to ` : 'Set to '}
                    "${escapeHtml(change.new_value || '')}"
                </div>
                <div class="change-meta">Source: ${change.source || 'Unknown'}</div>
            </div>
            <div class="change-time">${formatDate(change.detected_at)}</div>
        </div>
    `).join('');

    container.innerHTML = pendingHtml + changesHtml;
}

// ============== Comparison ==============

async function loadComparisonOptions() {
    const container = document.getElementById('comparisonChecklist');
    if (!container) return;

    // Show skeleton while loading
    container.innerHTML = `
        <div class="comparison-loading">
            <div class="skeleton-checkbox"></div>
            <div class="skeleton-checkbox"></div>
            <div class="skeleton-checkbox"></div>
            <div class="skeleton-checkbox"></div>
            <div class="skeleton-checkbox"></div>
            <div class="skeleton-checkbox"></div>
        </div>
    `;

    try {
        // Fetch from API if global array is empty
        let comps = competitors;
        if (!comps || comps.length === 0) {
            const response = await fetch(API_BASE + '/api/competitors', {
                headers: getAuthHeaders()
            });
            if (response.ok) {
                comps = await response.json();
                competitors = comps;  // Update global cache
            }
        }

        if (!comps || comps.length === 0) {
            container.innerHTML = `
                <div class="empty-state-inline" style="text-align: center; padding: 20px;">
                    <i class="fas fa-users" style="font-size: 2rem; color: var(--text-muted); margin-bottom: 10px; display: block;"></i>
                    <p style="color: var(--text-muted);">No competitors found. <a href="#" onclick="showPage('competitors'); return false;" style="color: var(--accent-blue);">Add competitors</a> to compare.</p>
                </div>
            `;
            return;
        }

        // Sort alphabetically for easier selection
        const sortedComps = [...comps].sort((a, b) => a.name.localeCompare(b.name));

        container.innerHTML = sortedComps.map(comp => `
            <label class="comparison-checkbox">
                <input type="checkbox" value="${comp.id}" name="compareCompetitor" onchange="updateComparisonSelection()">
                <span class="checkbox-label">
                    <span class="competitor-name">${escapeHtml(comp.name)}</span>
                    ${comp.threat_level ? `<span class="threat-badge threat-${comp.threat_level.toLowerCase()}">${comp.threat_level}</span>` : ''}
                </span>
            </label>
        `).join('');

    } catch (error) {
        console.error('Error loading comparison options:', error);
        container.innerHTML = `
            <div class="error-state-inline" style="text-align: center; padding: 20px;">
                <i class="fas fa-exclamation-circle" style="font-size: 2rem; color: var(--accent-red); margin-bottom: 10px; display: block;"></i>
                <p style="color: var(--text-muted);">Failed to load competitors. <a href="#" onclick="loadComparisonOptions(); return false;" style="color: var(--accent-blue);">Try again</a></p>
            </div>
        `;
    }
}

function runComparison() {
    const selected = Array.from(document.querySelectorAll('input[name="compareCompetitor"]:checked'))
        .map(cb => parseInt(cb.value));

    if (selected.length < 2) {
        showToast('Please select at least 2 competitors to compare', 'warning');
        return;
    }

    const selectedComps = competitors.filter(c => selected.includes(c.id));

    const attributes = [
        { label: 'Threat Level', key: 'threat_level' },
        { label: 'Pricing Model', key: 'pricing_model' },
        { label: 'Base Price', key: 'base_price' },
        { label: 'Customers', key: 'customer_count' },
        { label: 'Employees', key: 'employee_count' },
        { label: 'G2 Rating', key: 'g2_rating' },
        { label: 'Target Segments', key: 'target_segments' },
        { label: 'Funding', key: 'funding_total' },
        { label: 'Products', key: 'product_categories' },
    ];

    const container = document.getElementById('comparisonResults');

    // Store selected IDs for verification
    _comparisonSelectedIds = selected;

    container.innerHTML = `
        <div class="comparison-table">
            <table id="comparisonTable">
                <thead>
                    <tr>
                        <th>Attribute</th>
                        ${selectedComps.map(c => `<th>${escapeHtml(c.name)}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${attributes.map(attr => `
                        <tr data-attr="${attr.key}">
                            <td><strong>${attr.label}</strong></td>
                            ${selectedComps.map(c => `<td id="comp-cell-${c.id}-${attr.key}"><span style="display:flex;align-items:center;gap:4px;">${renderSourceDot(c.id, attr.key, c[attr.key])} ${createSourcedValue(c[attr.key], c.id, attr.key, 'external')}</span></td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        <div style="display: flex; gap: 8px; margin-top: 12px; align-items: center; flex-wrap: wrap;">
            <button class="btn btn-secondary btn-sm" id="verifyComparisonBtn" onclick="verifyComparisonData()">Verify Data</button>
            <span id="verifyComparisonStatus" style="font-size: 0.82em; color: var(--text-secondary);"></span>
        </div>
        <div id="comparisonVerificationResults" style="display: none; margin-top: 12px;"></div>
    `;
}

// ============== Comparison Data Verification (v8.3.0) ==============

let _comparisonSelectedIds = [];

async function verifyComparisonData() {
    const btn = document.getElementById('verifyComparisonBtn');
    const statusEl = document.getElementById('verifyComparisonStatus');
    const resultsEl = document.getElementById('comparisonVerificationResults');

    if (!_comparisonSelectedIds || _comparisonSelectedIds.length === 0) {
        showToast('No competitors selected for verification', 'warning');
        return;
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Verifying...'; }
    if (statusEl) statusEl.textContent = 'Running AI verification on displayed fields...';

    const fields = ['pricing_model', 'base_price', 'customer_count', 'employee_count', 'g2_rating', 'target_segments', 'funding_total', 'product_categories'];

    try {
        // Verify each competitor in parallel
        const results = await Promise.all(
            _comparisonSelectedIds.map(compId =>
                fetchAPI(`/api/verification/run/${compId}`, { method: 'POST', silent: true })
                    .catch(() => ({ competitor_id: compId, status: 'error' }))
            )
        );

        // Fetch updated competitor data to show corrections
        const updatedComps = await Promise.all(
            _comparisonSelectedIds.map(compId =>
                fetchAPI(`/api/competitors/${compId}`, { silent: true }).catch(() => null)
            )
        );

        let discrepancies = [];
        updatedComps.forEach((updatedComp, idx) => {
            if (!updatedComp) return;
            const compId = _comparisonSelectedIds[idx];
            const originalComp = competitors.find(c => c.id === compId);
            if (!originalComp) return;

            fields.forEach(field => {
                const oldVal = String(originalComp[field] || '');
                const newVal = String(updatedComp[field] || '');
                if (oldVal !== newVal && newVal && newVal !== 'null' && newVal !== 'Unknown') {
                    discrepancies.push({
                        competitorId: compId,
                        competitorName: originalComp.name,
                        field: field,
                        oldValue: oldVal || 'N/A',
                        newValue: newVal
                    });
                }
            });

            // Update local cache with fresh data
            Object.assign(originalComp, updatedComp);
        });

        // Highlight cells with discrepancies
        discrepancies.forEach(d => {
            const cell = document.getElementById(`comp-cell-${d.competitorId}-${d.field}`);
            if (cell) {
                cell.style.background = 'rgba(234, 179, 8, 0.15)';
                cell.style.borderLeft = '3px solid #eab308';
            }
        });

        // Show results
        if (resultsEl) {
            resultsEl.style.display = 'block';
            if (discrepancies.length === 0) {
                resultsEl.innerHTML = '<div style="padding: 10px; background: rgba(34, 197, 94, 0.1); border-radius: 6px; border-left: 3px solid #22c55e; color: var(--text-primary); font-size: 0.88em;">All displayed data verified - no discrepancies found.</div>';
            } else {
                let html = `<div style="padding: 10px; background: rgba(234, 179, 8, 0.1); border-radius: 6px; border-left: 3px solid #eab308; font-size: 0.88em;">
                    <strong>${discrepancies.length} discrepanc${discrepancies.length === 1 ? 'y' : 'ies'} found:</strong>
                    <div style="margin-top: 8px;">`;
                discrepancies.forEach(d => {
                    const fieldLabel = fields.find(f => f === d.field) ? d.field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : d.field;
                    html += `<div style="display: flex; align-items: center; gap: 8px; padding: 4px 0; flex-wrap: wrap;">
                        <span style="font-weight: 600; min-width: 100px;">${escapeHtml(d.competitorName)}</span>
                        <span style="color: var(--text-secondary);">${escapeHtml(fieldLabel)}:</span>
                        <span style="text-decoration: line-through; color: var(--danger-color);">${escapeHtml(d.oldValue)}</span>
                        <span style="color: var(--text-secondary);">-></span>
                        <span style="color: var(--success-color); font-weight: 600;">${escapeHtml(d.newValue)}</span>
                        <button class="btn btn-sm" style="padding:2px 8px;font-size:11px;background:var(--success-color);color:#fff;border:none;border-radius:3px;cursor:pointer;" onclick="acceptVerifiedValue(${d.competitorId}, '${escapeHtml(d.field)}', '${escapeHtml(d.newValue.replace(/'/g, "\\'"))}')">Accept</button>
                    </div>`;
                });
                html += '</div></div>';
                resultsEl.innerHTML = html;
            }
        }

        if (statusEl) statusEl.textContent = `Verification complete. ${discrepancies.length} discrepanc${discrepancies.length === 1 ? 'y' : 'ies'} found.`;
        showToast('Data verification complete', 'success');
    } catch (error) {
        console.error('Comparison verification error:', error);
        if (statusEl) statusEl.textContent = 'Verification failed.';
        showToast('Data verification failed', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Verify Data'; }
    }
}

async function acceptVerifiedValue(competitorId, field, newValue) {
    try {
        await fetchAPI(`/api/competitors/${competitorId}/correct`, {
            method: 'POST',
            body: JSON.stringify({
                field: field,
                new_value: newValue,
                reason: 'AI Verification - Accepted Corrected Value'
            })
        });
        showToast('Value updated successfully', 'success');

        // Refresh the comparison table
        runComparison();
    } catch (error) {
        console.error('Accept verified value error:', error);
        showToast('Failed to update value', 'error');
    }
}

window.verifyComparisonData = verifyComparisonData;
window.acceptVerifiedValue = acceptVerifiedValue;

// P3-4/P3-6: Load comparison from URL hash or shared link
async function loadComparisonFromIds(competitorIds) {
    if (!competitorIds || competitorIds.length < 2) {
        showToast('At least 2 competitors are required for comparison', 'warning');
        return;
    }

    // Ensure competitors are loaded
    if (!competitors || competitors.length === 0) {
        try {
            const response = await fetch(API_BASE + '/api/competitors', {
                headers: getAuthHeaders()
            });
            if (response.ok) {
                competitors = await response.json();
            }
        } catch (error) {
            console.error('Error loading competitors for comparison:', error);
            showToast('Failed to load competitors', 'error');
            return;
        }
    }

    // Find matching competitors
    const validIds = competitorIds.filter(id => competitors.some(c => c.id === id));
    if (validIds.length < 2) {
        showToast('Some competitors in the link no longer exist', 'warning');
        return;
    }

    // Check the checkboxes
    const checkboxes = document.querySelectorAll('input[name="compareCompetitor"]');
    checkboxes.forEach(cb => {
        const cbId = parseInt(cb.value);
        cb.checked = validIds.includes(cbId);
    });

    // Update selection count
    updateComparisonSelection();

    // Run the comparison
    runComparison();

    // Save to navigation state
    saveNavigationState('comparison', { compareIds: validIds });
}

// ============== Analytics ==============

function renderMarketShareChart() {
    const ctx = document.getElementById('marketShareChart')?.getContext('2d');
    if (!ctx) return;

    if (marketShareChart) marketShareChart.destroy();

    // Sort by customer count descending, take top 8 with real data
    const sorted = [...competitors]
        .map(c => ({
            name: c.name,
            count: parseInt((c.customer_count || '0').replace(/\D/g, '')) || 0,
            website: c.website || null
        }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);

    // Exclude competitors with 0 customers if enough have data
    const withData = sorted.filter(d => d.count > 0);
    const shareData = withData.length >= 3 ? withData : sorted;

    const total = shareData.reduce((sum, d) => sum + d.count, 0);
    shareData.forEach(d => d.share = total > 0 ? Math.round(d.count / total * 100) : 0);

    marketShareChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: shareData.map(d => d.name),
            datasets: [{
                data: shareData.map(d => d.share),
                backgroundColor: [
                    '#2F5496', '#00B4D8', '#28A745', '#FFC107',
                    '#DC3545', '#6C757D', '#17A2B8', '#6610f2'
                ],
                borderWidth: 2,
                borderColor: '#1e293b'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#e2e8f0',
                        padding: 12,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const d = shareData[idx];
                            return `${d.name}: ${d.share}% (~${d.count.toLocaleString()} customers)`;
                        },
                        afterLabel: function(context) {
                            const idx = context.dataIndex;
                            const d = shareData[idx];
                            return d.website ? `Source: ${d.website}` : '';
                        }
                    }
                }
            },
            onClick: function(evt, elements) {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    const url = shareData[idx].website;
                    if (url) window.open(url, '_blank', 'noopener');
                }
            }
        }
    });
}

// P3-7: LIVE Competitive Heatmap Implementation
function renderHeatmap() {
    const container = document.getElementById('heatmapContainer');
    if (!container) return;

    const sizeBy = document.getElementById('heatmapSizeBy')?.value || 'employees';
    const colorBy = document.getElementById('heatmapColorBy')?.value || 'threat_level';

    // Build heatmap data with real metrics
    const heatmapData = competitors.map(comp => {
        // Calculate size metric
        let sizeValue = 0;
        let sizeLabel = '';
        switch (sizeBy) {
            case 'employees':
                sizeValue = parseInt((comp.employee_count || '0').replace(/\D/g, '')) || 0;
                sizeLabel = sizeValue > 0 ? `${sizeValue.toLocaleString()} employees` : 'Unknown';
                break;
            case 'customers':
                sizeValue = parseInt((comp.customer_count || '0').replace(/\D/g, '')) || 0;
                sizeLabel = sizeValue > 0 ? `${sizeValue.toLocaleString()} customers` : 'Unknown';
                break;
            case 'products':
                sizeValue = comp.product_count || (comp.product_categories ? comp.product_categories.split(',').length : 0);
                sizeLabel = sizeValue > 0 ? `${sizeValue} products` : 'Unknown';
                break;
        }

        // Determine tile size class
        let sizeClass = 'size-sm';
        const maxSize = Math.max(...competitors.map(c => {
            switch (sizeBy) {
                case 'employees': return parseInt((c.employee_count || '0').replace(/\D/g, '')) || 0;
                case 'customers': return parseInt((c.customer_count || '0').replace(/\D/g, '')) || 0;
                case 'products': return c.product_count || (c.product_categories ? c.product_categories.split(',').length : 0);
                default: return 0;
            }
        }));
        const sizeRatio = maxSize > 0 ? sizeValue / maxSize : 0;
        if (sizeRatio >= 0.75) sizeClass = 'size-xl';
        else if (sizeRatio >= 0.5) sizeClass = 'size-lg';
        else if (sizeRatio >= 0.25) sizeClass = 'size-md';

        // Determine color class
        let colorClass = 'threat-unknown';
        let colorLabel = '';
        switch (colorBy) {
            case 'threat_level':
                colorClass = `threat-${(comp.threat_level || 'unknown').toLowerCase()}`;
                colorLabel = comp.threat_level || 'Unknown';
                break;
            case 'status':
                colorClass = comp.status === 'Active' ? 'threat-high' : 'threat-low';
                colorLabel = comp.status || 'Unknown';
                break;
            case 'sentiment':
                // Use g2_rating as proxy for sentiment
                const rating = parseFloat(comp.g2_rating) || 0;
                if (rating >= 4) colorClass = 'threat-low';
                else if (rating >= 3) colorClass = 'threat-medium';
                else if (rating > 0) colorClass = 'threat-high';
                colorLabel = rating > 0 ? `${rating}/5 rating` : 'No rating';
                break;
        }

        return {
            id: comp.id,
            name: comp.name,
            sizeValue,
            sizeLabel,
            sizeClass,
            colorClass,
            colorLabel,
            threatLevel: comp.threat_level || 'Unknown',
            website: comp.website,
            pricing: comp.pricing_model,
            g2Rating: comp.g2_rating
        };
    });

    // Sort by size value (largest first)
    heatmapData.sort((a, b) => b.sizeValue - a.sizeValue);

    // Update stats
    updateHeatmapStats(heatmapData);

    // Render tiles with source links
    container.innerHTML = `
        <div class="heatmap-grid">
            ${heatmapData.map(tile => `
                <div class="heatmap-tile ${tile.sizeClass} ${tile.colorClass}"
                     onclick="showCompetitorDetail(${tile.id})"
                     data-competitor-id="${tile.id}"
                     title="${tile.name}: ${tile.sizeLabel} | ${tile.colorLabel}">
                    <div class="heatmap-tile-indicator"></div>
                    <div class="heatmap-tile-name">${tile.name}</div>
                    <div class="heatmap-tile-metric">${tile.sizeLabel}</div>
                    ${tile.website ? `<a href="${tile.website}" target="_blank" rel="noopener" onclick="event.stopPropagation();" class="heatmap-tile-source" style="font-size:0.7em;color:#94a3b8;text-decoration:underline;display:block;margin-top:2px;">Source</a>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

function updateHeatmapStats(data) {
    // Update stats cards
    const totalEl = document.getElementById('heatmapTotalCompetitors');
    const highEl = document.getElementById('heatmapHighThreat');
    const mediumEl = document.getElementById('heatmapMediumThreat');
    const lowEl = document.getElementById('heatmapLowThreat');

    if (totalEl) totalEl.textContent = data.length;
    if (highEl) highEl.textContent = data.filter(d => d.threatLevel === 'High').length;
    if (mediumEl) mediumEl.textContent = data.filter(d => d.threatLevel === 'Medium').length;
    if (lowEl) lowEl.textContent = data.filter(d => d.threatLevel === 'Low').length;
}

function updateHeatmap() {
    // Called when controls change
    renderHeatmap();
}

async function refreshHeatmapData() {
    showLoading('Refreshing competitive data...');
    try {
        // Refresh competitors from API
        const response = await fetch(API_BASE + '/api/competitors', {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            competitors = await response.json();
            renderHeatmap();
            showToast('Heatmap data refreshed', 'success');
        }
    } catch (error) {
        console.error('Error refreshing heatmap:', error);
        showToast('Failed to refresh data', 'error');
    } finally {
        hideLoading();
    }
}

function showCompetitorDetail(competitorId) {
    const comp = competitors.find(c => c.id === competitorId);
    if (!comp) return;

    const modal = document.getElementById('competitorDetailModal');
    const nameEl = document.getElementById('detailCompetitorName');
    const contentEl = document.getElementById('competitorDetailContent');

    if (!modal || !nameEl || !contentEl) return;

    nameEl.textContent = comp.name;

    // Helper: wrap a data value with a clickable source link
    const srcUrl = comp.website || '';
    const linkedVal = (val, fallback) => {
        const display = val || fallback;
        if (srcUrl && val) {
            return `<a href="${srcUrl}" target="_blank" rel="noopener" title="Source: ${srcUrl}" style="color:inherit;text-decoration:underline dotted;cursor:pointer;">${display}</a>`;
        }
        return display;
    };

    contentEl.innerHTML = `
        <div class="competitor-detail-grid">
            <div class="detail-section">
                <h4>Overview</h4>
                <div class="detail-row">
                    <span class="detail-label">Website:</span>
                    <span class="detail-value">${comp.website ? `<a href="${comp.website}" target="_blank">${comp.website}</a>` : 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Threat Level:</span>
                    <span class="detail-value threat-badge threat-${(comp.threat_level || 'unknown').toLowerCase()}">${comp.threat_level || 'Unknown'}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="detail-value">${comp.status || 'Active'}</span>
                </div>
            </div>

            <div class="detail-section">
                <h4>Metrics</h4>
                <div class="detail-row">
                    <span class="detail-label">Employees:</span>
                    <span class="detail-value">${linkedVal(comp.employee_count, 'Unknown')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Customers:</span>
                    <span class="detail-value">${linkedVal(comp.customer_count, 'Unknown')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">G2 Rating:</span>
                    <span class="detail-value">${comp.g2_rating ? linkedVal(`${comp.g2_rating}/5`, 'N/A') : 'N/A'}</span>
                </div>
            </div>

            <div class="detail-section">
                <h4>Business</h4>
                <div class="detail-row">
                    <span class="detail-label">Pricing:</span>
                    <span class="detail-value">${linkedVal(comp.pricing_model, 'Unknown')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Funding:</span>
                    <span class="detail-value">${linkedVal(comp.funding_total, 'Unknown')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Founded:</span>
                    <span class="detail-value">${linkedVal(comp.year_founded, 'Unknown')}</span>
                </div>
            </div>

            ${comp.key_features ? `
            <div class="detail-section full-width">
                <h4>Key Features</h4>
                <p class="detail-features">${escapeHtml(comp.key_features || '')}</p>
            </div>
            ` : ''}
        </div>
    `;

    // Store current competitor ID for "View Full Profile" button
    modal.dataset.competitorId = competitorId;
    modal.style.display = 'flex';

    // Reset to overview tab
    switchCompDetailTab('overview');

    // Load annotations for the annotations tab (preload count)
    loadCompDetailAnnotations(competitorId);
}

function closeCompetitorDetail() {
    const modal = document.getElementById('competitorDetailModal');
    if (modal) modal.style.display = 'none';
}

function viewFullCompetitorProfile() {
    const modal = document.getElementById('competitorDetailModal');
    const competitorId = modal?.dataset.competitorId;
    if (competitorId) {
        closeCompetitorDetail();
        showPage('battlecards');
        // Find and open the battlecard for this competitor
        setTimeout(() => {
            const comp = competitors.find(c => c.id === parseInt(competitorId));
            if (comp && typeof openBattlecardModal === 'function') {
                openBattlecardModal(comp);
            }
        }, 300);
    }
}

function renderFeatureGaps() {
    const container = document.getElementById('featureGapContainer');
    if (!container) return;

    // Feature definitions with keywords to detect from competitor data
    const features = [
        { name: 'Patient Intake', certify: true, keywords: ['intake', 'registration', 'check-in', 'checkin'] },
        { name: 'Eligibility Verification', certify: true, keywords: ['eligibility', 'insurance verification', 'verification'] },
        { name: 'Patient Payments', certify: true, keywords: ['payment', 'billing', 'collect', 'pay'] },
        { name: 'Telehealth', certify: false, keywords: ['telehealth', 'telemedicine', 'virtual care', 'video visit'] },
        { name: 'Full EHR', certify: false, keywords: ['ehr', 'electronic health record', 'emr', 'clinical documentation'] },
        { name: 'AI Scheduling', certify: false, keywords: ['ai schedul', 'smart schedul', 'intelligent schedul', 'ai-powered schedul'] },
        { name: 'Practice Management', certify: false, keywords: ['practice management', 'pm system'] },
        { name: 'Patient Portal', certify: true, keywords: ['patient portal', 'patient access'] },
        { name: 'Kiosk / Self-Service', certify: true, keywords: ['kiosk', 'self-service', 'self service'] },
        { name: 'Revenue Cycle (RCM)', certify: false, keywords: ['rcm', 'revenue cycle', 'claims management', 'denial management'] },
    ];

    // Detect if competitor has a feature based on key_features + product_categories
    function competitorHasFeature(comp, feature) {
        const combined = ((comp.key_features || '') + ' ' + (comp.product_categories || '')).toLowerCase();
        return feature.keywords.some(kw => combined.includes(kw));
    }

    const topComps = competitors.slice(0, 5);

    container.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Feature</th>
                    <th>Certify Health</th>
                    ${topComps.map(c => `<th>${escapeHtml(c.name)}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
                ${features.map(f => `
                    <tr>
                        <td>${escapeHtml(f.name)}</td>
                        <td style="text-align:center;">${f.certify ? '<span style="color:#16a34a;">Yes</span>' : '<span style="color:#94a3b8;">No</span>'}</td>
                        ${topComps.map(c => {
                            const has = competitorHasFeature(c, f);
                            const sourceUrl = c.website || '#';
                            return `<td style="text-align:center;">
                                <a href="${sourceUrl}" target="_blank" rel="noopener" title="Source: ${escapeHtml(c.website || 'N/A')}" style="text-decoration:none;">
                                    ${has ? '<span style="color:#16a34a;">Yes</span>' : '<span style="color:#94a3b8;">No</span>'}
                                </a>
                            </td>`;
                        }).join('')}
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <p style="font-size:0.8em; color:#94a3b8; margin-top:8px;">Feature detection based on competitor product categories and key features. Click values to visit source.</p>
    `;
}

// ============== Battlecards ==============

let corporateProfile = null;
// Cache for AI strategy content (persists across navigation until user clears)
const _battlecardStrategyCache = {};

async function loadBattlecards() {
    const grid = document.getElementById('battlecardsGrid');
    if (!grid) return;

    // v8.3.0: Load source quality stats on battlecards page
    loadSourceQualityStats();

    // FIX v6.3.7: Always fetch competitors if array is empty
    // This ensures battlecards load even when navigating directly to this page
    if (!competitors || competitors.length === 0) {
        try {
            competitors = await fetchAPI('/api/competitors') || [];
        } catch (error) {
            console.error('[Battlecards] Failed to load competitors:', error);
            grid.innerHTML = '<div class="empty-state"><p>Failed to load competitors. Please refresh the page.</p></div>';
            return;
        }
    }

    // Fetch corporate profile (Certify Health) if not already loaded
    if (!corporateProfile) {
        try {
            corporateProfile = await fetchAPI('/api/corporate-profile', { silent: true });
        } catch (e) {
        }
    }

    // Build corporate battlecard HTML (displayed first)
    const corporateCard = corporateProfile ? `
        <div class="battlecard-preview corporate" onclick="viewCorporateBattlecard()" style="position: relative; padding-bottom: 52px;">
            <span class="company-badge">🏢 Our Company</span>
            <h4>${corporateProfile.name}</h4>
            <p class="battlecard-summary">
                ${corporateProfile.tagline}
            </p>
            <button class="btn btn-secondary">View Reference Profile</button>
            <img src="certify_health_logo.png" alt="Certify Health" style="position: absolute; bottom: 12px; left: 14px; height: 26px; object-fit: contain; opacity: 0.85;">
        </div>
    ` : '';

    // Build competitor battlecards (Enhanced v6.1.2)
    const competitorCards = competitors.map(comp => `
        <div class="battlecard-preview threat-${(comp.threat_level || 'medium').toLowerCase()}" onclick="viewBattlecard(${comp.id})" style="position: relative;">
            <div style="position: absolute; top: 12px; right: 12px;">
                ${createLogoImg(comp.website, comp.name, 40)}
            </div>
            <h4 style="padding-right: 56px;">
                ${escapeHtml(comp.name)}
                ${comp.is_public ? '<span style="font-size: 11px; background: var(--info-light); color: var(--info-color); padding: 2px 6px; border-radius: 4px; margin-left: 8px;">PUBLIC</span>' : ''}
            </h4>
            <span class="threat-badge ${(comp.threat_level || 'medium').toLowerCase()}">${comp.threat_level || 'Medium'} Threat</span>
            <div id="battlecard-summary-${comp.id}" style="font-size: 13px; line-height: 1.5; color: var(--text-secondary); position: relative;">
                ${comp.ai_threat_summary ? `
                    <p class="battlecard-summary-text" id="summary-text-${comp.id}" style="margin: 8px 0 4px; overflow: hidden; max-height: 3.2em; transition: max-height 0.3s ease;">${escapeHtml(comp.ai_threat_summary)}</p>
                    <span class="expand-summary-btn" onclick="event.stopPropagation(); toggleSummary(${comp.id})" style="color: var(--primary-color); cursor: pointer; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 4px;">Show more</span>
                ` : '<p style="color: var(--text-muted); font-style: italic; margin: 8px 0;">Generating threat summary...</p>'}
            </div>
            <div class="btn-container">
                <button class="btn btn-secondary" onclick="event.stopPropagation(); viewBattlecard(${comp.id})">
                    📋 View Details
                </button>
                <button class="btn btn-secondary" onclick="event.stopPropagation(); downloadBattlecardPDF(${comp.id})">
                    📄 PDF
                </button>
            </div>
        </div>
    `).join('');

    grid.innerHTML = corporateCard + competitorCards;

    // Auto-generate AI threat summaries if any are missing
    const missingCount = competitors.filter(c => !c.ai_threat_summary).length;
    if (missingCount > 0) {
        generateThreatSummaries();
    }
}

async function generateThreatSummaries() {
    try {
        const resp = await fetchAPI('/api/battlecards/generate-summaries', {
            method: 'POST',
            body: JSON.stringify({})
        });
        if (resp && resp.status === 'running') {
            showToast(`Generating AI threat summaries for ${resp.count} competitors...`, 'info');
            // Poll for completion - check every 5 seconds for up to 2 minutes
            let attempts = 0;
            const maxAttempts = 24;
            const pollInterval = setInterval(async () => {
                attempts++;
                try {
                    const updated = await fetchAPI('/api/competitors', { silent: true });
                    if (updated && updated.length > 0) {
                        const withSummary = updated.filter(c => c.ai_threat_summary);
                        if (withSummary.length > 0) {
                            competitors = updated;
                            // Update summary text on existing cards
                            competitors.forEach(comp => {
                                const summaryEl = document.getElementById(`battlecard-summary-${comp.id}`);
                                if (summaryEl && comp.ai_threat_summary) {
                                    const escaped = escapeHtml(comp.ai_threat_summary);
                                    summaryEl.innerHTML = `
                                        <p class="battlecard-summary-text" id="summary-text-${comp.id}" style="margin: 8px 0 4px; overflow: hidden; max-height: 3.2em; transition: max-height 0.3s ease;">${escaped}</p>
                                        <span class="expand-summary-btn" onclick="event.stopPropagation(); toggleSummary(${comp.id})" style="color: var(--primary-color); cursor: pointer; font-size: 12px; font-weight: 600; display: inline-block; margin-bottom: 4px;">Show more</span>
                                    `;
                                }
                            });
                        }
                        // Stop polling when all have summaries or max attempts reached
                        const missingCount = updated.filter(c => !c.ai_threat_summary).length;
                        if (missingCount === 0 || attempts >= maxAttempts) {
                            clearInterval(pollInterval);
                            if (missingCount === 0) {
                                showToast(`AI threat summaries generated for all ${withSummary.length} competitors`, 'success');
                            } else {
                                showToast(`Generated ${withSummary.length} summaries (${missingCount} pending)`, 'info');
                            }
                        }
                    }
                } catch (pollErr) {
                    console.error('[Battlecards] Poll error:', pollErr);
                }
                if (attempts >= maxAttempts) {
                    clearInterval(pollInterval);
                }
            }, 5000);
        } else if (resp && resp.generated === 0) {
        }
    } catch (error) {
        console.error('[Battlecards] Failed to generate threat summaries:', error);
        // Update loading placeholders to show fallback text
        competitors.forEach(comp => {
            if (!comp.ai_threat_summary) {
                const summaryEl = document.getElementById(`battlecard-summary-${comp.id}`);
                if (summaryEl) {
                    summaryEl.textContent = comp.product_categories || comp.key_features || 'Healthcare technology solution';
                    summaryEl.style.fontStyle = 'normal';
                }
            }
        });
    }
}
window.generateThreatSummaries = generateThreatSummaries;

function toggleSummary(compId) {
    const textEl = document.getElementById(`summary-text-${compId}`);
    const btn = textEl ? textEl.nextElementSibling : null;
    if (!textEl || !btn) return;
    const isExpanded = textEl.style.maxHeight !== '3.2em';
    if (isExpanded) {
        textEl.style.maxHeight = '3.2em';
        btn.textContent = 'Show more';
    } else {
        textEl.style.maxHeight = textEl.scrollHeight + 'px';
        btn.textContent = 'Show less';
    }
}
window.toggleSummary = toggleSummary;

async function viewCorporateBattlecard() {
    // Fetch fresh corporate profile data
    let profile = corporateProfile;
    if (!profile) {
        try {
            const response = await fetch(`${API_BASE}/api/corporate-profile`);
            if (response.ok) {
                profile = await response.json();
                corporateProfile = profile;
            }
        } catch (e) {
            showToast('Error loading corporate profile', 'error');
            return;
        }
    }

    if (!profile) {
        showToast('Corporate profile not available', 'error');
        return;
    }

    // Build products HTML
    const productsHtml = Object.values(profile.products).map(p => `
        <div class="product-card">
            <h5>${p.name}</h5>
            <p>${p.description}</p>
        </div>
    `).join('');

    // Build metrics HTML
    const metricsHtml = `
        <div class="metric-card">
            <div class="metric-value">${profile.claimed_outcomes.no_show_reduction.replace('% fewer no-shows', '%')}</div>
            <div class="metric-label">Fewer No-Shows</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${profile.claimed_outcomes.revenue_increase.replace('% more revenue collected', '%')}</div>
            <div class="metric-label">More Revenue</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">${profile.claimed_outcomes.claim_denial_reduction.replace('% reduction in claim denials', '%')}</div>
            <div class="metric-label">Fewer Denials</div>
        </div>
    `;

    // Build differentiators list
    const diffHtml = profile.key_differentiators.map(d => `<li>${d}</li>`).join('');

    // Build markets list
    const marketsHtml = profile.markets.map(m => `<span class="tag">${m}</span>`).join(' ');

    const content = `
        <div class="battlecard-full corporate">
            <h2 style="display: flex; align-items: center; gap: 12px;">
                <img src="certify_health_logo.png" alt="Certify Health" style="height: 40px; object-fit: contain;">
                ${profile.name}
                <span class="corporate-header-badge">Reference Profile</span>
            </h2>
            
            <p style="font-size: 16px; color: #465D8B; margin: 16px 0;">
                <em>"${profile.mission}"</em>
            </p>
            
            <h3>📊 Key Metrics</h3>
            <div class="metrics-grid">
                ${metricsHtml}
            </div>
            
            <h3>🏗️ Our Products (7 Platforms)</h3>
            <div class="product-grid">
                ${productsHtml}
            </div>
            
            <h3>🎯 Key Differentiators</h3>
            <ul class="differentiator-list">
                ${diffHtml}
            </ul>
            
            <h3>🏥 Markets We Serve (11 Verticals)</h3>
            <div style="margin: 12px 0; line-height: 2;">
                ${marketsHtml}
            </div>
            
            <h3>Quick Facts</h3>
            <table class="data-table" style="margin-bottom: 20px;">
                <tr><td>Founded</td><td>${profile.year_founded}</td></tr>
                <tr><td>Headquarters</td><td>${profile.headquarters}</td></tr>
                <tr><td>Employees</td><td>${profile.employee_count}</td></tr>
                <tr><td>Funding</td><td>${profile.funding_total}</td></tr>
                <tr><td>Investors</td><td>${profile.investors.join(', ')}</td></tr>
                <tr><td>Certifications</td><td>${profile.certifications.join(', ')}</td></tr>
            </table>
            
            <h3>🏆 Awards</h3>
            <p>${profile.awards.join(', ')}</p>
            
            <div style="margin-top: 24px; display: flex; gap: 12px;">
                <a href="${profile.website}" target="_blank" class="btn btn-primary">🌐 Visit Website</a>
                <a href="${profile.contact.demo_url}" target="_blank" class="btn btn-secondary">📅 Request Demo</a>
            </div>
        </div>
    `;

    showModal(content);
}

/**
 * Create a battlecard data row with editable value (click to edit)
 * @param {string} label - The field label (e.g., "Customers")
 * @param {string|number} value - The data value
 * @param {number} competitorId - The competitor ID
 * @param {string} fieldName - The database field name
 * @param {boolean} hasBorder - Whether to show bottom border
 * @returns {string} HTML string
 */
function createBattlecardEditableRow(label, value, competitorId, fieldName, hasBorder = true, sourceData = null) {
    const displayValue = (!value || value === 'Unknown' || value === 'null' || value === '????' || value === '')
        ? 'N/A'
        : value;
    const borderStyle = hasBorder ? 'border-bottom: 1px solid #e2e8f0;' : '';
    const safeValue = String(displayValue).replace(/'/g, "\\'").replace(/"/g, "&quot;");

    // v6.3.9: Add source link for each data field
    const sourceId = `source-${competitorId}-${fieldName}`;

    // v8.3.0: Prefer deep_link_url from API, fall back to building one
    const deepSourceUrl = (sourceData && sourceData.source_url)
        ? (sourceData.deep_link_url || buildDeepSourceLink(sourceData.source_url, sourceData.current_value || displayValue))
        : '';

    const valueHtml = (sourceData && sourceData.source_url)
        ? `<a href="${escapeHtml(deepSourceUrl)}" target="_blank" rel="noopener"
              style="color: #2563eb; font-weight: 700; text-decoration: underline; text-underline-offset: 3px;"
              title="Source: ${escapeHtml(sourceData.source_name || 'Verified')} - Click to view exact data on source page">${escapeHtml(String(displayValue))}</a>
           <span class="battlecard-edit-icon" style="cursor:pointer; font-size:12px; opacity:0.5; margin-left:4px;"
                 onclick="openDataFieldPopup(${competitorId}, '${fieldName}', '${label}', '${safeValue}')"
                 title="Click to edit">&#9998;</span>`
        : `<strong
              class="battlecard-editable-value"
              style="color: #1e293b; cursor: pointer; text-decoration: underline dotted; text-underline-offset: 3px;"
              onclick="openDataFieldPopup(${competitorId}, '${fieldName}', '${label}', '${safeValue}')"
              title="Click to edit"
          >${displayValue}</strong>`;

    const sourceClass = (sourceData && sourceData.source_url) ? 'has-source' : 'no-source';

    return `
        <div class="battlecard-editable-row" style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; ${borderStyle}">
            <span style="color: #64748b;">${label}</span>
            <div style="display: flex; align-items: center; gap: 6px;">
                ${valueHtml}
                <a href="#"
                   id="${sourceId}"
                   class="source-link ${sourceClass}"
                   onclick="openSourceLink(event, ${competitorId}, '${fieldName}')"
                   title="${(sourceData && sourceData.source_url) ? escapeHtml(sourceData.source_name || 'View source') : 'Loading source...'}">&#128279;</a>
            </div>
        </div>
    `;
}

/**
 * v8.2.1: Build a deep link with Text Fragment highlighting.
 * Appends #:~:text=VALUE to the URL so Chrome/Edge highlights
 * the exact data value on the target page.
 * @param {string} url - The base source URL
 * @param {string} value - The data value to highlight
 * @returns {string} URL with text fragment appended
 */
function buildDeepSourceLink(url, value) {
    if (!url || !value) return url || '';
    // Strip existing fragment
    const base = url.split('#')[0];
    // Clean value for text fragment: remove special chars, trim, take first 80 chars
    let searchText = String(value).trim();
    if (searchText === 'N/A' || searchText === 'Unknown' || searchText === '????' || !searchText) return base;
    // Remove currency symbols and common prefixes that may not match exactly
    searchText = searchText.replace(/^[\$~\u2248]/g, '').trim();
    if (searchText.length > 80) searchText = searchText.substring(0, 80);
    if (searchText.length < 2) return base;
    // Encode for URL fragment
    const encoded = encodeURIComponent(searchText);
    return `${base}#:~:text=${encoded}`;
}

/**
 * v6.3.9: Fetch and cache source information for a field
 */
async function fetchSourceForField(competitorId, fieldName) {
    try {
        const response = await fetch(`${API_BASE}/api/sources/field/${competitorId}/${fieldName}`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        return null;
    }
}

/**
 * v8.2.1: Open source URL in new tab with text fragment highlighting.
 * Uses the stored current_value to build a deep link that highlights
 * the exact data on the source page.
 */
async function openSourceLink(event, competitorId, fieldName) {
    event.preventDefault();
    event.stopPropagation();

    const source = await fetchSourceForField(competitorId, fieldName);

    if (source && source.source_url) {
        // v8.3.0: Prefer deep_link_url from API, fall back to building one
        const deepUrl = source.deep_link_url || buildDeepSourceLink(source.source_url, source.current_value || source.value);
        openSourceUrlWithDeepLink(source.source_url, deepUrl, source.current_value || source.value);
    } else {
        showToast('No source available yet. Run AI Source Discovery to find sources.', 'info');
    }
}

/**
 * v6.3.9: Update source link status after fetching
 */
function updateSourceLinkStatus(competitorId, fieldName, hasSource, sourceName, confidence) {
    const sourceId = `source-${competitorId}-${fieldName}`;
    const link = document.getElementById(sourceId);
    if (!link) return;

    if (hasSource) {
        link.classList.remove('no-source');
        link.classList.add('has-source');
        link.title = `Source: ${sourceName || 'Available'} (${confidence || 0}% confidence)`;
    } else {
        link.classList.remove('has-source');
        link.classList.add('no-source');
        link.title = 'No source available - AI discovery pending';
    }
}

/**
 * v6.3.9: Load source statuses for all visible battlecard fields
 */
async function loadBattlecardSourceStatuses(competitorId) {
    try {
        const response = await fetch(`${API_BASE}/api/sources/${competitorId}`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) return;

        const data = await response.json();
        const sources = data.sources || {};

        // Update all source links for this competitor
        for (const [fieldName, sourceInfo] of Object.entries(sources)) {
            updateSourceLinkStatus(
                competitorId,
                fieldName,
                !!sourceInfo.source_url,
                sourceInfo.source_name,
                sourceInfo.confidence_score
            );
        }
    } catch (e) {
        console.error('Error loading source statuses:', e);
    }
}

/**
 * Start verification of all competitors' data
 */
async function startVerifyAllData() {
    try {
        const resp = await fetchAPI('/api/verification/run-all', {
            method: 'POST'
        });
        if (!resp) {
            showToast('Failed to start verification', 'error');
            return;
        }
        if (resp.status === 'already_running') {
            showToast('Verification already in progress', 'warning');
        }
        showVerificationProgressModal();
        pollVerificationProgress();
    } catch (e) {
        showToast('Failed to start verification', 'error');
    }
}

/**
 * Show modal with verification progress bar and stat counters
 */
function showVerificationProgressModal() {
    const content = `
        <div style="max-width: 600px; width: 100%;">
            <h2 style="margin: 0 0 20px 0; color: #1e293b;">Data Verification in Progress</h2>
            <div style="margin-bottom: 16px;">
                <div style="background: #e2e8f0; border-radius: 8px; height: 24px; overflow: hidden;">
                    <div id="verifyProgressBar" style="background: linear-gradient(90deg, #2563eb, #7c3aed); height: 100%; width: 0%; transition: width 0.5s ease; border-radius: 8px;"></div>
                </div>
                <div id="verifyProgressText" style="text-align: center; margin-top: 8px; color: #64748b; font-size: 13px;">Starting verification...</div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                <div style="background: #f0fdf4; padding: 12px; border-radius: 8px; text-align: center;">
                    <div id="verifyCountVerified" style="font-size: 24px; font-weight: 700; color: #15803d;">0</div>
                    <div style="font-size: 11px; color: #64748b;">Verified</div>
                </div>
                <div style="background: #fef3c7; padding: 12px; border-radius: 8px; text-align: center;">
                    <div id="verifyCountCorrected" style="font-size: 24px; font-weight: 700; color: #b45309;">0</div>
                    <div style="font-size: 11px; color: #64748b;">Corrected</div>
                </div>
                <div style="background: #f1f5f9; padding: 12px; border-radius: 8px; text-align: center;">
                    <div id="verifyCountNA" style="font-size: 24px; font-weight: 700; color: #64748b;">0</div>
                    <div style="font-size: 11px; color: #64748b;">Unverifiable</div>
                </div>
            </div>
            <div id="verifyCurrentComp" style="color: #64748b; font-size: 13px; text-align: center;">Preparing...</div>
            <div id="verifyETA" style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 4px;"></div>
        </div>
    `;
    showModal(content);
}

let _verifyPollInterval = null;
let _verifyPolling = false;
let _verifyLastProgress = null;

/**
 * Poll verification progress endpoint every 3 seconds
 */
function pollVerificationProgress() {
    _verifyPolling = true;
    _verifyLastProgress = null;
    if (_verifyPollInterval) clearInterval(_verifyPollInterval);
    _verifyPollInterval = setInterval(async () => {
        try {
            const data = await fetchAPI('/api/verification/progress', { silent: true });
            if (!data) return;
            _verifyLastProgress = data;
            updateVerificationProgress(data);
            if (data.status === 'completed' || data.status === 'error') {
                clearInterval(_verifyPollInterval);
                _verifyPollInterval = null;
                _verifyPolling = false;
                if (data.status === 'completed') {
                    Object.keys(_sourceVerificationCache).forEach(k => delete _sourceVerificationCache[k]);
                    showToast(`Verification complete! ${data.fields_verified} verified, ${data.fields_corrected} corrected, ${data.fields_marked_na} unverifiable`, 'success');
                    setTimeout(() => { closeModal(); loadBattlecards(); }, 2000);
                } else {
                    showToast('Verification encountered an error', 'error');
                }
            }
        } catch (e) { /* silent */ }
    }, 3000);
}

/**
 * Resume verification progress modal when user returns to battlecards page.
 * Returns true if verification is currently in progress.
 */
function resumeVerificationIfRunning() {
    if (!_verifyPolling) return false;

    // Re-show the verification modal with last known progress
    showVerificationProgressModal();
    if (_verifyLastProgress) {
        // Small delay to ensure modal DOM is ready
        setTimeout(() => updateVerificationProgress(_verifyLastProgress), 100);
    }

    return true;
}

/**
 * Update verification progress modal with latest data
 */
function updateVerificationProgress(data) {
    const bar = document.getElementById('verifyProgressBar');
    const text = document.getElementById('verifyProgressText');
    const verified = document.getElementById('verifyCountVerified');
    const corrected = document.getElementById('verifyCountCorrected');
    const na = document.getElementById('verifyCountNA');
    const current = document.getElementById('verifyCurrentComp');
    const eta = document.getElementById('verifyETA');

    if (!bar) return;

    const pct = data.competitors_total > 0
        ? Math.round((data.competitors_processed / data.competitors_total) * 100)
        : 0;
    bar.style.width = pct + '%';
    if (text) text.textContent = `${data.competitors_processed} / ${data.competitors_total} competitors (${pct}%)`;
    if (verified) verified.textContent = data.fields_verified || 0;
    if (corrected) corrected.textContent = data.fields_corrected || 0;
    if (na) na.textContent = data.fields_marked_na || 0;
    if (current) current.textContent = data.current_competitor ? `Currently verifying: ${escapeHtml(data.current_competitor)}` : 'Processing...';
    if (eta && data.estimated_time_remaining) {
        const mins = Math.ceil(data.estimated_time_remaining / 60);
        eta.textContent = `Estimated time remaining: ~${mins} min`;
    }
}

/**
 * Verify data for a single competitor
 */
async function verifySingleCompetitor(competitorId) {
    showToast('Verifying competitor data...', 'info');
    try {
        const resp = await fetchAPI(`/api/verification/run/${competitorId}`, { method: 'POST' });
        if (resp) {
            delete _sourceVerificationCache[competitorId];
            showToast(`Verified! ${resp.fields_verified || 0} confirmed, ${resp.fields_corrected || 0} corrected`, 'success');
            viewBattlecard(competitorId);
        } else {
            showToast('Verification failed', 'error');
        }
    } catch (e) {
        showToast('Verification failed', 'error');
    }
}

/**
 * P2-2: Generate confidence indicator badge for battlecards
 * @param {number} score - Confidence score 0-100
 * @returns {string} - HTML string for confidence badge
 */
function getConfidenceBadge(score) {
    if (score === null || score === undefined) {
        return '<span class="confidence-badge confidence-unknown" title="Data confidence: Unknown">❓ Unverified</span>';
    }

    let confidenceClass, confidenceLabel, confidenceIcon;

    if (score >= 80) {
        confidenceClass = 'confidence-high';
        confidenceLabel = 'High Confidence';
        confidenceIcon = '✓';
    } else if (score >= 60) {
        confidenceClass = 'confidence-moderate';
        confidenceLabel = 'Moderate';
        confidenceIcon = '~';
    } else if (score >= 40) {
        confidenceClass = 'confidence-low';
        confidenceLabel = 'Low Confidence';
        confidenceIcon = '!';
    } else {
        confidenceClass = 'confidence-very-low';
        confidenceLabel = 'Unverified';
        confidenceIcon = '?';
    }

    return `<span class="confidence-badge ${confidenceClass}" title="Data confidence: ${score}%">${confidenceIcon} ${confidenceLabel} (${score}%)</span>`;
}

/**
 * P2-2: Generate inline confidence indicator dot
 */
function getConfidenceDot(score) {
    if (score === null || score === undefined) {
        return '<span class="confidence-dot confidence-unknown" title="Confidence: Unknown"></span>';
    }

    let confidenceClass;
    if (score >= 80) confidenceClass = 'confidence-high';
    else if (score >= 60) confidenceClass = 'confidence-moderate';
    else if (score >= 40) confidenceClass = 'confidence-low';
    else confidenceClass = 'confidence-very-low';

    return `<span class="confidence-dot ${confidenceClass}" title="Confidence: ${score}%"></span>`;
}

async function viewBattlecard(id) {
    const comp = competitors.find(c => c.id === id);
    if (!comp) return;

    // v8.0.8: Pre-load saved strategy from DB if not in memory cache
    if (!_battlecardStrategyCache[id]) {
        try {
            const saved = await fetchAPI(`/api/ai/battlecard-strategy/${id}`, { silent: true });
            if (saved && saved.content) {
                const html = renderStrategyMarkdown(saved.content)
                    + `<div style="margin-top:12px;padding-top:8px;border-top:1px solid #c7d2fe;font-size:10px;color:#818cf8;">Generated ${saved.generated_at ? new Date(saved.generated_at).toLocaleString() : ''}</div>`;
                _battlecardStrategyCache[id] = html;
            }
        } catch (e) { /* no saved strategy */ }
    }

    // Pre-load source verification data
    const sourceData = await _loadSourceVerificationData(comp.id);

    // Generate threat level specific styling
    const threatColors = {
        high: { bg: '#fee2e2', border: '#dc2626', text: '#b91c1c' },
        medium: { bg: '#fef3c7', border: '#f59e0b', text: '#b45309' },
        low: { bg: '#dcfce7', border: '#22c55e', text: '#15803d' }
    };
    const threat = threatColors[(comp.threat_level || 'medium').toLowerCase()] || threatColors.medium;

    // P2-2: Get confidence badge
    const confidenceBadge = getConfidenceBadge(comp.data_quality_score);
    const freshnessBadge = getDataFreshnessBadge(comp.last_updated);

    // Build dimension scores section if available
    const dimensionScores = [];
    const dimensionFields = [
        { key: 'dim_product_packaging_score', label: 'Product Packaging' },
        { key: 'dim_integration_depth_score', label: 'Integration' },
        { key: 'dim_support_service_score', label: 'Support' },
        { key: 'dim_retention_stickiness_score', label: 'Retention' },
        { key: 'dim_user_adoption_score', label: 'User Adoption' },
        { key: 'dim_implementation_ttv_score', label: 'Implementation' },
        { key: 'dim_reliability_enterprise_score', label: 'Reliability' },
        { key: 'dim_pricing_flexibility_score', label: 'Pricing' },
        { key: 'dim_reporting_analytics_score', label: 'Analytics' }
    ];
    dimensionFields.forEach(d => {
        if (comp[d.key]) {
            dimensionScores.push({ label: d.label, score: comp[d.key] });
        }
    });

    const dimensionHtml = dimensionScores.length > 0 ? `
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0;">
            ${dimensionScores.map(d => `
                <div style="background: ${d.score >= 4 ? '#dcfce7' : d.score >= 3 ? '#fef3c7' : '#fee2e2'}; padding: 12px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: 700; color: ${d.score >= 4 ? '#15803d' : d.score >= 3 ? '#b45309' : '#b91c1c'};">${d.score}/5</div>
                    <div style="font-size: 11px; color: #64748b; margin-top: 4px;">${d.label}</div>
                </div>
            `).join('')}
        </div>
    ` : '';

    const content = `
        <div class="battlecard-full enhanced" style="max-width: 920px; width: 100%;">
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
                <div style="display: flex; gap: 16px; align-items: flex-start;">
                    <div style="flex-shrink: 0;">${createLogoImg(comp.website, comp.name, 56)}</div>
                    <div>
                    <h2 style="margin: 0 0 8px 0; font-size: 28px; color: #1e293b; display: flex; align-items: center; gap: 12px;">
                        ${escapeHtml(comp.name)}
                        ${comp.is_public ? '<span style="font-size: 11px; background: #22c55e; color: white; padding: 4px 10px; border-radius: 4px;">NYSE: ' + (comp.ticker_symbol || 'PUBLIC') + '</span>' : ''}
                    </h2>
                    <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                        <span class="threat-badge ${(comp.threat_level || 'medium').toLowerCase()}" style="background: ${threat.bg}; color: ${threat.text}; border: 1px solid ${threat.border}; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 12px;">
                            ${comp.threat_level || 'Medium'} Threat
                        </span>
                        ${confidenceBadge}
                        ${freshnessBadge.badge}
                        ${comp.primary_market ? `<span style="background: #f1f5f9; padding: 4px 10px; border-radius: 20px; font-size: 12px; color: #475569;">${comp.primary_market}</span>` : ''}
                        ${comp.dim_overall_score ? `<span style="background: #eef2ff; padding: 4px 10px; border-radius: 20px; font-size: 12px; color: #4f46e5;">Overall Score: ${comp.dim_overall_score.toFixed(1)}/5</span>` : ''}
                    </div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-secondary" onclick="downloadBattlecardPDF(${id})" style="padding: 8px 16px; font-size: 13px;">
                        📄 PDF
                    </button>
                    ${comp.website ? `<a href="${comp.website}" target="_blank" class="btn btn-primary" style="padding: 8px 16px; font-size: 13px; text-decoration: none;">&#127760; Website</a>` : ''}
                    <button class="btn btn-secondary" onclick="verifySingleCompetitor(${id})" style="padding: 8px 16px; font-size: 13px;">
                        &#10003; Verify
                    </button>
                </div>
            </div>

            <!-- Stock Data Section (if public) -->
            <div id="stockSection">
                ${comp.is_public ? '<p class="loading">Loading stock data...</p>' : ''}
            </div>

            <!-- Quick Facts Grid -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; margin-bottom: 24px;">
                <!-- Company Info -->
                <div style="background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0;">
                    <h3 style="margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">📊 Company Overview</h3>
                    <div style="display: grid; gap: 12px;">
                        ${createBattlecardEditableRow('Founded', comp.year_founded, comp.id, 'year_founded', true, sourceData['year_founded'])}
                        ${createBattlecardEditableRow('Headquarters', comp.headquarters, comp.id, 'headquarters', true, sourceData['headquarters'])}
                        ${createBattlecardEditableRow('Employees', comp.employee_count, comp.id, 'employee_count', true, sourceData['employee_count'])}
                        ${createBattlecardEditableRow('Customers', comp.customer_count, comp.id, 'customer_count', false, sourceData['customer_count'])}
                    </div>
                </div>

                <!-- Financial Info -->
                <div style="background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0;">
                    <h3 style="margin: 0 0 16px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">💰 Financial & Pricing</h3>
                    <div style="display: grid; gap: 12px;">
                        ${createBattlecardEditableRow('Funding', comp.funding_total, comp.id, 'funding_total', true, sourceData['funding_total'])}
                        ${createBattlecardEditableRow('Revenue', comp.annual_revenue || comp.estimated_revenue, comp.id, 'annual_revenue', true, sourceData['annual_revenue'])}
                        ${createBattlecardEditableRow('Pricing Model', comp.pricing_model, comp.id, 'pricing_model', true, sourceData['pricing_model'])}
                        ${createBattlecardEditableRow('Base Price', comp.base_price, comp.id, 'base_price', false, sourceData['base_price'])}
                    </div>
                </div>
            </div>

            <!-- Dimension Scores (if available) -->
            ${dimensionHtml ? `
                <div style="margin-bottom: 24px;">
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">📈 Competitive Dimensions</h3>
                    ${dimensionHtml}
                </div>
            ` : ''}

            <!-- Products & Features -->
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; margin-bottom: 24px;">
                <div>
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">🛠️ Products</h3>
                    <p style="margin: 0; padding: 16px; background: #f8fafc; border-radius: 8px; line-height: 1.6; color: #334155;">
                        ${escapeHtml(comp.product_categories || 'No product information available')}
                    </p>
                </div>
                <div>
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">✨ Key Features</h3>
                    <p style="margin: 0; padding: 16px; background: #f8fafc; border-radius: 8px; line-height: 1.6; color: #334155;">
                        ${escapeHtml(comp.key_features || 'No feature information available')}
                    </p>
                </div>
            </div>

            <!-- Market & Compliance -->
            ${(comp.target_segments || comp.certifications || comp.integration_partners) ? `
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; margin-bottom: 24px;">
                <div>
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">🎯 Target Market</h3>
                    <p style="margin: 0; padding: 16px; background: #f8fafc; border-radius: 8px; line-height: 1.6; color: #334155;">
                        ${escapeHtml(comp.target_segments || 'N/A')}
                    </p>
                </div>
                <div>
                    <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">🔒 Certifications & Integrations</h3>
                    <div style="padding: 16px; background: #f8fafc; border-radius: 8px; line-height: 1.6; color: #334155;">
                        ${comp.certifications ? `<div style="margin-bottom:6px;"><strong style="font-size:11px;color:#64748b;">Certifications:</strong> ${escapeHtml(comp.certifications)}</div>` : ''}
                        ${comp.integration_partners ? `<div><strong style="font-size:11px;color:#64748b;">Integrations:</strong> ${escapeHtml(comp.integration_partners)}</div>` : ''}
                        ${!comp.certifications && !comp.integration_partners ? 'N/A' : ''}
                    </div>
                </div>
            </div>
            ` : ''}

            <!-- News Section -->
            <div style="margin-bottom: 24px;">
                <h3 style="margin: 0 0 12px 0; font-size: 14px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px;">📰 Latest News</h3>
                <div id="newsSection" class="news-section" style="max-height: 300px; overflow-y: auto; background: #f8fafc; border-radius: 8px; padding: 16px;">
                    <p class="loading">Loading news articles...</p>
                </div>
            </div>

            <!-- AI Win Strategy -->
            <div style="background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%); padding: 20px; border-radius: 12px; margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="margin: 0; font-size: 14px; text-transform: uppercase; color: #4f46e5; letter-spacing: 0.5px;">🏆 How to Win Against ${escapeHtml(comp.name)}</h3>
                    <div style="display: flex; gap: 8px;">
                        <button id="clearStrategyBtn_${id}" class="btn btn-secondary" onclick="event.stopPropagation(); clearBattlecardStrategy(${id})" style="padding: 8px 12px; font-size: 12px; display: ${_battlecardStrategyCache[id] ? 'inline-flex' : 'none'};">
                            🗑️ Clear
                        </button>
                        <button id="generateStrategyBtn_${id}" class="btn btn-primary" onclick="generateBattlecardStrategy(${id}, '${escapeHtml(comp.name)}')" style="padding: 8px 16px; font-size: 12px;">
                            ${_battlecardStrategyCache[id] ? '🔄 Regenerate' : '🤖 Generate AI Strategy'}
                        </button>
                    </div>
                </div>
                <div id="battlecardStrategyContent_${id}" style="color: #312e81; line-height: 1.7;">
                    ${_battlecardStrategyCache[id] || '<p style="margin: 0; color: #64748b; font-style: italic;">Click "Generate AI Strategy" to create a custom competitive strategy based on ' + escapeHtml(comp.name) + '\'s latest data, news, dimensions, and market position.</p>'}
                </div>
            </div>

            <!-- Annotations Panel -->
            <div class="annotations-panel" style="margin: 20px 0; padding: 20px; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <h4 style="margin: 0; font-size: 15px; color: #1e293b;">Team Notes & Annotations</h4>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <select id="annotationFilterType_${id}" onchange="filterAnnotations(${id})" style="padding: 4px 8px; font-size: 11px; border-radius: 4px; border: 1px solid #cbd5e1; background: white; color: #334155;">
                            <option value="">All Types</option>
                            <option value="note">Notes</option>
                            <option value="insight">Insights</option>
                            <option value="warning">Warnings</option>
                            <option value="opportunity">Opportunities</option>
                            <option value="action_item">Action Items</option>
                        </select>
                        <button class="btn btn-sm btn-secondary" onclick="toggleAnnotationForm(${id})" style="padding: 4px 12px; font-size: 12px;">+ Add Note</button>
                    </div>
                </div>
                <!-- Add annotation form (hidden) -->
                <div id="annotationForm_${id}" style="display: none; margin-bottom: 12px; padding: 12px; background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <input type="text" id="annotationTitle_${id}" placeholder="Title (optional)" style="width: 100%; padding: 6px 10px; margin-bottom: 8px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; box-sizing: border-box; color: #1e293b;">
                    <textarea id="annotationContent_${id}" placeholder="Write your note..." rows="3" style="width: 100%; padding: 6px 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; resize: vertical; box-sizing: border-box; color: #1e293b;"></textarea>
                    <div style="display: flex; gap: 8px; margin-top: 8px; align-items: center;">
                        <select id="annotationType_${id}" style="padding: 4px 8px; font-size: 12px; border-radius: 4px; border: 1px solid #cbd5e1;">
                            <option value="note">Note</option>
                            <option value="insight">Insight</option>
                            <option value="warning">Warning</option>
                            <option value="opportunity">Opportunity</option>
                            <option value="action_item">Action Item</option>
                        </select>
                        <select id="annotationPriority_${id}" style="padding: 4px 8px; font-size: 12px; border-radius: 4px; border: 1px solid #cbd5e1;">
                            <option value="normal">Normal</option>
                            <option value="low">Low</option>
                            <option value="high">High</option>
                            <option value="critical">Critical</option>
                        </select>
                        <span style="flex:1;"></span>
                        <button class="btn btn-sm btn-secondary" onclick="toggleAnnotationForm(${id})" style="padding: 4px 10px; font-size: 12px;">Cancel</button>
                        <button class="btn btn-sm btn-primary" onclick="submitAnnotation(${id})" style="padding: 4px 10px; font-size: 12px;">Save</button>
                    </div>
                </div>
                <div id="annotationsList_${id}" style="max-height: 300px; overflow-y: auto;">
                    <p style="color: #94a3b8; font-size: 13px; text-align: center; padding: 8px;">Loading annotations...</p>
                </div>
            </div>

            <!-- Action Buttons -->
            <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                <button class="btn btn-primary" onclick="downloadBattlecardPDF(${id})" style="padding: 12px 24px;">
                    📄 Download Full Battlecard
                </button>
                <button class="btn btn-secondary" onclick="showCompetitorComparison(${id})" style="padding: 12px 24px;">
                    📊 Compare with Certify
                </button>
                ${comp.website ? `<a href="${comp.website}" target="_blank" class="btn btn-secondary" style="padding: 12px 24px; text-decoration: none;">🌐 Visit Website</a>` : ''}
            </div>
        </div>
    `;

    showModal(content);

    // Fetch and display stock data (only for public companies)
    if (comp.is_public) {
        loadCompanyStockData(comp.name);
    }

    // Fetch and display news
    loadCompetitorNews(comp.name, id);

    // Load annotations
    loadAnnotations(id);
}

/**
 * v7.1.0: Generate AI-powered competitive strategy for a specific battlecard.
 * Uses the competitor's actual data, dimensions, news, and market position.
 */
async function generateBattlecardStrategy(competitorId, competitorName) {
    const btn = document.getElementById(`generateStrategyBtn_${competitorId}`);
    const contentDiv = document.getElementById(`battlecardStrategyContent_${competitorId}`);
    if (!btn || !contentDiv) return;

    const comp = competitors.find(c => c.id === competitorId);
    if (!comp) {
        showToast('Competitor data not found', 'error');
        return;
    }

    // Loading state
    btn.disabled = true;
    btn.innerHTML = '⏳ Generating...';
    contentDiv.innerHTML = `
        <div style="text-align: center; padding: 16px;">
            <div class="spinner" style="margin: 0 auto 10px; width: 22px; height: 22px;"></div>
            <p style="margin: 0; color: #64748b; font-size: 12px;">Searching live sources & generating strategy...</p>
        </div>
    `;

    // Build context from dimension scores (all 9 dimensions)
    const dims = [
        { key: 'dim_product_packaging_score', label: 'Product Packaging' },
        { key: 'dim_integration_depth_score', label: 'Integration Depth' },
        { key: 'dim_support_service_score', label: 'Support & Service' },
        { key: 'dim_retention_stickiness_score', label: 'Retention & Stickiness' },
        { key: 'dim_user_adoption_score', label: 'User Adoption' },
        { key: 'dim_implementation_ttv_score', label: 'Implementation' },
        { key: 'dim_reliability_enterprise_score', label: 'Enterprise Reliability' },
        { key: 'dim_pricing_flexibility_score', label: 'Pricing Flexibility' },
        { key: 'dim_reporting_analytics_score', label: 'Analytics' }
    ];
    const dimScores = dims.filter(d => comp[d.key]).map(d => `${d.label}: ${comp[d.key]}/5`);
    const contextStr = dimScores.length > 0 ? `Dimension Scores: ${dimScores.join(', ')}` : '';

    try {
        const response = await fetchAPI('/api/ai/generate-battlecard', {
            method: 'POST',
            body: JSON.stringify({
                competitor_name: competitorName,
                competitor_id: competitorId,
                additional_context: contextStr || undefined
            })
        });

        // Check for explicit error from AI provider
        if (response && response.success === false && response.error) {
            throw new Error(response.error);
        }

        if (response && (response.content || response.sections)) {
            const strategyText = response.content || '';
            let html = '';

            if (strategyText) {
                html = renderStrategyMarkdown(strategyText);
            } else if (response.sections && Object.keys(response.sections).length > 0) {
                for (const [section, sectionContent] of Object.entries(response.sections)) {
                    html += `<div style="margin-bottom: 14px;">`;
                    html += `<h4 style="color: #4f46e5; margin: 0 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;">${escapeHtml(section)}</h4>`;
                    html += `<div style="color: #334155; font-size: 13px; line-height: 1.6;">${renderStrategyMarkdown(sectionContent)}</div>`;
                    html += `</div>`;
                }
            }

            // Add provider attribution footer
            const providerName = response.provider || 'AI';
            const modelName = response.model || '';
            html += `<div style="margin-top:12px;padding-top:8px;border-top:1px solid #c7d2fe;font-size:10px;color:#818cf8;">Generated by ${escapeHtml(providerName)}${modelName ? ' (' + escapeHtml(modelName) + ')' : ''}</div>`;

            contentDiv.innerHTML = html;

            // Cache the generated strategy HTML so it persists across navigation
            _battlecardStrategyCache[competitorId] = html;

            // Show clear button
            const clearBtn = document.getElementById(`clearStrategyBtn_${competitorId}`);
            if (clearBtn) clearBtn.style.display = 'inline-flex';

            // Add conversational chat widget below the strategy content
            const chatDivId = `battlecardChat_${competitorId}`;
            let chatDiv = document.getElementById(chatDivId);
            if (!chatDiv) {
                chatDiv = document.createElement('div');
                chatDiv.id = chatDivId;
                contentDiv.appendChild(chatDiv);
            }
            createChatWidget(chatDivId, {
                pageContext: 'battlecard_' + competitorId,
                competitorId: competitorId,
                placeholder: 'Ask follow-up questions about this strategy...',
                endpoint: '/api/analytics/chat'
            });

            btn.innerHTML = '✅ Strategy Generated';
            btn.onclick = () => generateBattlecardStrategy(competitorId, competitorName);
            setTimeout(() => { btn.innerHTML = '🔄 Regenerate'; btn.disabled = false; }, 2000);
            showToast(`Strategy generated for ${competitorName}`, 'success');
        } else {
            throw new Error('No strategy content returned');
        }

    } catch (error) {
        console.error('Strategy generation error:', error);
        contentDiv.innerHTML = `<p style="color: #dc2626; margin: 0; font-size: 13px;">Failed to generate strategy. ${escapeHtml(error.message || 'Please try again.')}</p>`;
        btn.innerHTML = '🤖 Retry';
        btn.disabled = false;
        showToast('Strategy generation failed', 'error');
    }
}

/**
 * Clear the cached AI strategy for a battlecard
 */
function clearBattlecardStrategy(competitorId) {
    delete _battlecardStrategyCache[competitorId];
    const contentDiv = document.getElementById(`battlecardStrategyContent_${competitorId}`);
    const clearBtn = document.getElementById(`clearStrategyBtn_${competitorId}`);
    const genBtn = document.getElementById(`generateStrategyBtn_${competitorId}`);
    if (contentDiv) {
        const comp = competitors.find(c => c.id === competitorId);
        const name = comp ? escapeHtml(comp.name) : 'this competitor';
        contentDiv.innerHTML = `<p style="margin: 0; color: #64748b; font-style: italic;">Click "Generate AI Strategy" to create a custom competitive strategy based on ${name}'s latest data, news, dimensions, and market position.</p>`;
    }
    if (clearBtn) clearBtn.style.display = 'none';
    if (genBtn) genBtn.innerHTML = '🤖 Generate AI Strategy';
    showToast('Strategy cleared', 'info');
}
window.clearBattlecardStrategy = clearBattlecardStrategy;

/**
 * Render AI strategy markdown into clean, professional HTML.
 * Handles headers, bullets, numbered lists, bold, and URLs.
 */
function renderStrategyMarkdown(md) {
    if (!md) return '';
    const lines = md.split('\n');
    let html = '';
    let inList = false;

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            if (inList) { html += '</ul>'; inList = false; }
            continue;
        }

        // Section headers (## HEADER)
        const h2 = trimmed.match(/^##\s+(.+)/);
        if (h2) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h4 style="color: #4f46e5; margin: 16px 0 6px; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">${escapeHtml(h2[1])}</h4>`;
            continue;
        }

        // Skip # top-level headers and ---
        if (trimmed.startsWith('# ') || trimmed === '---') continue;

        // Bullet or numbered list
        const bullet = trimmed.match(/^[\-\*•]\s+(.+)/);
        const numbered = trimmed.match(/^\d+[\.\)]\s+(.+)/);
        if (bullet || numbered) {
            if (!inList) { html += '<ul style="margin: 0 0 8px; padding-left: 18px; list-style: disc;">'; inList = true; }
            const text = bullet ? bullet[1] : numbered[1];
            html += `<li style="margin-bottom: 6px; font-size: 13px; line-height: 1.55; color: #334155;">${formatInlineMarkdown(text)}</li>`;
            continue;
        }

        // Regular paragraph
        if (inList) { html += '</ul>'; inList = false; }
        if (trimmed.length > 5) {
            html += `<p style="margin: 0 0 8px; font-size: 13px; line-height: 1.55; color: #334155;">${formatInlineMarkdown(trimmed)}</p>`;
        }
    }
    if (inList) html += '</ul>';
    return html;
}

/**
 * Format inline markdown: bold, italic, and convert URLs to clickable links.
 */
function formatInlineMarkdown(text) {
    if (!text) return '';
    // Escape HTML first
    let safe = escapeHtml(text);
    // Bold **text**
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic *text*
    safe = safe.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Inline code `text`
    safe = safe.replace(/`(.+?)`/g, '<code style="background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:12px;">$1</code>');
    // Markdown links [text](url)
    safe = safe.replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:#4f46e5;text-decoration:underline;">$1</a>');
    // Bare URLs (not already in an <a> tag)
    safe = safe.replace(/(^|[^"'>])(https?:\/\/[^\s<)"]+)/g, '$1<a href="$2" target="_blank" rel="noopener" style="color:#4f46e5;text-decoration:underline;word-break:break-all;">$2</a>');
    // Quoted objection handling: "They..." → styled
    safe = safe.replace(/"([^"]{5,}?)"\s*→/g, '<em style="color:#64748b;">"$1"</em> →');
    return safe;
}

async function loadCompetitorNews(companyName, compId) {
    const newsSection = document.getElementById('newsSection');
    if (!newsSection) return;

    try {
        const response = await fetch(`${API_BASE}/api/news/${encodeURIComponent(companyName)}`);

        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        const data = await response.json();

        if (data.articles && data.articles.length > 0) {
            const sentimentColors = { positive: '#16a34a', negative: '#dc2626', neutral: '#64748b' };
            newsSection.innerHTML = '<h4 style="margin:0 0 8px;font-size:12px;color:#94a3b8;text-transform:uppercase;">Recent News (from Database)</h4>' +
                data.articles.map(article => {
                const safeTitle = escapeHtml(article.title || 'Untitled');
                const safeSource = escapeHtml(article.source || 'Unknown');
                const safeDate = escapeHtml(article.published_date || '');
                const safeSnippet = escapeHtml(article.snippet || '');
                const safeUrl = encodeURI(article.url || '#');
                const sentiment = article.sentiment || 'neutral';
                const sentColor = sentimentColors[sentiment] || '#64748b';
                const eventTag = article.event_type
                    ? `<span style="background:#eef2ff;color:#4f46e5;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;text-transform:uppercase;margin-left:6px;">${escapeHtml(article.event_type)}</span>`
                    : '';
                return `
                <div class="news-item" style="padding:10px 0;border-bottom:1px solid #e2e8f0;">
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                        <span style="width:8px;height:8px;border-radius:50%;background:${sentColor};display:inline-block;flex-shrink:0;" title="${escapeHtml(sentiment)} sentiment"></span>
                        <a href="${safeUrl}" target="_blank" rel="noopener" style="color:#1e293b;font-weight:600;font-size:13px;text-decoration:none;line-height:1.4;">${safeTitle}</a>
                        ${eventTag}
                    </div>
                    <div style="display:flex;gap:12px;font-size:11px;color:#64748b;">
                        <span>${safeSource}</span>
                        <span>${safeDate}</span>
                    </div>
                    ${safeSnippet ? `<p style="margin:4px 0 0;font-size:12px;color:#475569;line-height:1.4;">${safeSnippet}</p>` : ''}
                </div>`;
            }).join('');
            if (compId) {
                newsSection.innerHTML += `<div style="text-align:center;margin-top:12px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.1);">
                    <a href="#" onclick="navigateTo('newsfeed');setTimeout(()=>{const sel=document.getElementById('newsCompetitorFilter');if(sel){sel.value='${compId}';loadNewsFeed(1);}},200);return false;" style="color:#818cf8;font-size:12px;">
                        View All News for ${escapeHtml(companyName)} &rarr;
                    </a>
                </div>`;
            }
        } else {
            newsSection.innerHTML = '<p class="empty-state" style="color:#64748b;font-size:13px;">No news articles in database. Run AI Fetch News on the Live News tab to populate.</p>';
        }
    } catch (e) {
        console.error("Error loading news:", e);
        newsSection.innerHTML = `<div class="error-state">
            <p style="color:#64748b;font-size:13px;">Unable to load news.</p>
            <small style="color: #ef4444;">${escapeHtml(e.message)}</small>
        </div>`;
    }
}

async function loadCompanyStockData(companyName) {
    const stockSection = document.getElementById('stockSection');
    if (!stockSection) return;

    try {
        const response = await fetch(`${API_BASE}/api/stock/${encodeURIComponent(companyName)}`);
        const data = await response.json();

        if (data.is_public) {
            const changeClass = data.change >= 0 ? 'up' : 'down';
            const changeSign = data.change >= 0 ? '+' : '';

            // Formatting helpers
            const fmtNum = (n, suffix = '') => n ? (n / 1000000).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'M' + suffix : 'N/A';
            const fmtLgNum = (n) => {
                if (!n) return 'N/A';
                if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
                if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
                return n.toLocaleString();
            };
            const fmtCur = (n) => n ? '$' + n.toFixed(2) : 'N/A';
            const fmtPct = (n) => n ? (n * 100).toFixed(2) + '%' : 'N/A';
            const fmtRawPct = (n) => n ? n.toFixed(2) + '%' : 'N/A'; // For values already in % (0-100) or decimal (0-1)? 
            // Assumption: data from backend like profitMargin is decimal (0.15 = 15%) or float?
            // yfinance usually returns margins as 0.15 (15%). 
            // shortPercentOfFloat is usually 0.05 (5%)

            stockSection.innerHTML = `
                <div class="stock-section" style="background: white; padding: 20px; border-radius: 8px;">
                    <!-- Header -->
                    <div class="stock-header-row" style="display: flex; align-items: center; flex-wrap: nowrap; gap: 12px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 2px solid #e2e8f0; white-space: nowrap;">
                        <span style="background: #22c55e; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 0.85em;">PUBLIC</span>
                        <span style="font-size: 1.25em; font-weight: 700; color: #122753;">${data.ticker} <span style="font-size: 0.8em; color: #64748b; font-weight: 500;">(${data.exchange})</span></span>
                        <span style="font-size: 1.25em; font-weight: 700; color: #122753;">${fmtCur(data.price)}</span>
                        <span class="stock-change ${changeClass}" style="font-weight: 600;">
                            ${changeSign}${data.change?.toFixed(2)} (${changeSign}${data.change_percent?.toFixed(2)}%)
                        </span>
                    </div>

                    <!-- Financial Grid -->
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px;">
                        
                        <!-- Valuation -->
                        <div class="fin-group" style="background: #f8fafc; padding: 16px; border-radius: 6px;">
                            <h4 style="color: #122753; font-size: 0.9em; text-transform: uppercase; margin-bottom: 12px; border-bottom: 2px solid #122753; padding-bottom: 8px; text-decoration: underline; text-underline-offset: 4px;">Valuation & Multiples</h4>
                            <div class="fin-row"><span>Enterprise Value</span> <strong>${fmtLgNum(data.enterprise_value)}</strong></div>
                            <div class="fin-row"><span>P/E (Trailing)</span> <strong>${data.pe_trailing?.toFixed(2) || 'N/A'}</strong></div>
                            <div class="fin-row"><span>P/E (Forward)</span> <strong>${data.pe_forward?.toFixed(2) || 'N/A'}</strong></div>
                            <div class="fin-row"><span>EV/EBITDA</span> <strong>${data.ev_ebitda?.toFixed(2) || 'N/A'}</strong></div>
                            <div class="fin-row"><span>Price/Book</span> <strong>${data.price_to_book?.toFixed(2) || 'N/A'}</strong></div>
                            <div class="fin-row"><span>PEG Ratio</span> <strong>${data.peg_ratio?.toFixed(2) || 'N/A'}</strong></div>
                        </div>

                        <!-- Operating -->
                        <div class="fin-group" style="background: #f8fafc; padding: 16px; border-radius: 6px;">
                            <h4 style="color: #122753; font-size: 0.9em; text-transform: uppercase; margin-bottom: 12px; border-bottom: 2px solid #122753; padding-bottom: 8px; text-decoration: underline; text-underline-offset: 4px;">Operating Fundamentals</h4>
                            <div class="fin-row"><span>Revenue (TTM)</span> <strong>${fmtLgNum(data.revenue_ttm)}</strong></div>
                            <div class="fin-row"><span>EBITDA</span> <strong>${fmtLgNum(data.ebitda)}</strong></div>
                            <div class="fin-row"><span>EPS (Trailing)</span> <strong>${data.eps_trailing?.toFixed(2) || 'N/A'}</strong></div>
                            <div class="fin-row"><span>Free Cash Flow</span> <strong>${fmtLgNum(data.free_cash_flow)}</strong></div>
                            <div class="fin-row"><span>Profit Margin</span> <strong>${fmtPct(data.profit_margin)}</strong></div>
                        </div>

                         <!-- Risk -->
                         <div class="fin-group" style="background: #f8fafc; padding: 16px; border-radius: 6px;">
                            <h4 style="color: #122753; font-size: 0.9em; text-transform: uppercase; margin-bottom: 12px; border-bottom: 2px solid #122753; padding-bottom: 8px; text-decoration: underline; text-underline-offset: 4px;">Risk & Trading</h4>
                            <div class="fin-row"><span>Beta</span> <strong>${data.beta?.toFixed(2) || 'N/A'}</strong></div>
                            <div class="fin-row"><span>Short Interest</span> <strong>${fmtPct(data.short_interest)}</strong></div>
                            <div class="fin-row"><span>Avg Volume (90d)</span> <strong>${fmtLgNum(data.avg_volume_90d)}</strong></div>
                            <div class="fin-row"><span>Float</span> <strong>${fmtLgNum(data.float_shares)}</strong></div>
                            <div class="fin-row"><span>52W Range</span> <strong style="font-size: 0.9em;">$${data.fifty_two_week_low?.toFixed(2)} - $${data.fifty_two_week_high?.toFixed(2)}</strong></div>
                        </div>

                         <!-- Capital -->
                         <div class="fin-group" style="background: #f8fafc; padding: 16px; border-radius: 6px;">
                            <h4 style="color: #122753; font-size: 0.9em; text-transform: uppercase; margin-bottom: 12px; border-bottom: 2px solid #122753; padding-bottom: 8px; text-decoration: underline; text-underline-offset: 4px;">Capital Structure</h4>
                            <div class="fin-row"><span>Market Cap</span> <strong>${fmtLgNum(data.market_cap)}</strong></div>
                            <div class="fin-row"><span>Shares Out</span> <strong>${fmtLgNum(data.shares_outstanding)}</strong></div>
                            <div class="fin-row"><span>Inst. Ownership</span> <strong>${fmtPct(data.inst_ownership)}</strong></div>
                            <div class="fin-row"><span>Dividend Yield</span> <strong>${fmtPct(data.dividend_yield)}</strong></div>
                            <div class="fin-row"><span>Next Earnings</span> <strong>${data.next_earnings}</strong></div>
                        </div>
                    </div>
                    
                    <div style="font-size: 0.8em; color: #94a3b8; text-align: right; margin-top: 20px; padding-top: 12px; border-top: 1px solid #e2e8f0;">
                        Data provided by Yahoo Finance • Delayed 15 mins
                    </div>
                </div>

                <style>
                    .fin-row { display: flex; justify-content: space-between; font-size: 0.9em; padding: 6px 0; border-bottom: 1px dashed #e2e8f0; }
                    .fin-row:last-child { border-bottom: none; }
                    .fin-row span { color: #64748b; }
                    .fin-row strong { color: #1e293b; font-weight: 600; }
                </style>
            `;
        } else {
            // Check if we have rich private data (Headcount, Funding, etc.)
            if (data.headcount || data.total_funding) {
                stockSection.innerHTML = `
                <div class="stock-section private-mode">
                    <!-- Header -->
                    <div class="stock-header-row" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0;">
                         <div style="display: flex; align-items: center; gap: 10px;">
                            <span class="badge" style="background: #64748b; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 600;">PRIVATE</span>
                            <span style="font-size: 1.25em; font-weight: 700; color: var(--navy-dark);">${data.company}</span>
                        </div>
                        <div style="text-align: right;">
                             <span class="badge" style="background: #e0f2fe; color: #0369a1; padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 0.9em;">${data.stage || 'Private Company'}</span>
                        </div>
                    </div>

                    <!-- Private Intelligence Grid -->
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                        
                        <!-- Valuation & Capital -->
                        <div class="fin-group">
                            <h4 style="color: var(--text-secondary); font-size: 0.85em; text-transform: uppercase; margin-bottom: 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">Capital & Valuation</h4>
                            <div class="fin-row"><span>Total Funding</span> <strong>${fmtLgNum(data.total_funding)}</strong></div>
                            <div class="fin-row"><span>Latest Round</span> <strong>${data.latest_deal_type || 'N/A'}</strong></div>
                            <div class="fin-row"><span>Deal Size</span> <strong>${fmtLgNum(data.latest_deal_amount)}</strong></div>
                            <div class="fin-row"><span>Deal Date</span> <strong>${data.latest_deal_date || 'N/A'}</strong></div>
                            <div class="fin-row"><span>Est. Revenue</span> <strong>${fmtLgNum(data.est_revenue)}</strong></div>
                        </div>


                        <!-- Growth & People -->
                        <div class="fin-group">
                            <h4 style="color: var(--text-secondary); font-size: 0.85em; text-transform: uppercase; margin-bottom: 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">Growth Signals</h4>
                            <div class="fin-row"><span>Headcount</span> <strong>${data.headcount?.toLocaleString() || 'N/A'}</strong></div>
                            <div class="fin-row"><span>6mo Growth</span> <strong style="color: ${data.growth_rate_6mo >= 0 ? '#16a34a' : '#dc2626'}">${fmtRawPct(data.growth_rate_6mo)}</strong></div>
                            <div class="fin-row"><span>Active Jobs</span> <strong>${data.active_hiring || 0} Openings</strong></div>
                            <div class="fin-row"><span>Hiring Focus</span> <strong>${data.hiring_departments?.[0] || 'N/A'}</strong></div>
                             <div class="fin-row"><span>Founded</span> <strong>${data.founded || 'N/A'}</strong></div>
                        </div>


                        <!-- Alternative Intelligence -->
                        <div class="fin-group">
                            <h4 style="color: var(--text-secondary); font-size: 0.85em; text-transform: uppercase; margin-bottom: 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">Health & Quality</h4>
                            <div class="fin-row" title="USAspending.gov Prime Contracts"><span>Gov Contracts</span> <strong>${fmtLgNum(data.gov_contracts?.total_amount)}</strong></div>
                            <div class="fin-row" title="Avg Engineering Salary (H-1B)"><span>Eng Salary</span> <strong>${data.h1b_data?.avg_salary ? '$' + Math.round(data.h1b_data.avg_salary / 1000) + 'k' : 'N/A'}</strong></div>
                            <div class="fin-row" title="Patent Portfolio Size"><span>Patents</span> <strong>${data.innovation?.patents || 0} (${data.innovation?.pending || 0} pending)</strong></div>
                            <div class="fin-row" title="Glassdoor CEO Approval"><span>CEO Approval</span> <strong style="color: ${data.employee_sentiment?.ceo_approval >= 80 ? '#16a34a' : '#64748b'}">${data.employee_sentiment?.ceo_approval || 0}%</strong></div>
                            <div class="fin-row" title="Mobile App Quality"><span>App Rating</span> <strong>${data.app_quality?.avg_rating || 'N/A'} <small>(${data.app_quality?.downloads || '0'})</small></strong></div>
                        </div>


                        <!-- Google Digital Footprint -->
                        <div class="fin-group">
                            <h4 style="color: var(--text-secondary); font-size: 0.85em; text-transform: uppercase; margin-bottom: 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">Digital Footprint</h4>
                            <div class="fin-row" title="Google Ads Transparency"><span>Active Ads</span> <strong>${data.google_ecosystem?.ads_active || 0} Creatives</strong></div>
                            <div class="fin-row" title="Google Trends 12mo Benchmark"><span>Brand Interest</span> <strong>${data.google_ecosystem?.brand_index || 0}/100 <small>(${data.google_ecosystem?.trend || 'Flat'})</small></strong></div>
                            <div class="fin-row" title="Google Maps Review Velocity"><span>Reviews/Mo</span> <strong>${data.google_ecosystem?.review_velocity || 0}</strong></div>
                            <div class="fin-row" title="Marketing Tech Stack Signal"><span>Tech Spend</span> <strong>${data.tech_stack?.signal || 'Unknown'}</strong></div>
                            <div class="fin-row" title="Tools Detected"><span>Key Tools</span> <strong style="font-size: 0.8em; text-align: right; max-width: 120px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${data.tech_stack?.tools?.slice(0, 2).join(', ') || 'N/A'}</strong></div>
                        </div>

                        <!-- Deep Dive Intelligence (New) -->
                        <div class="fin-group">
                            <h4 style="color: var(--text-secondary); font-size: 0.85em; text-transform: uppercase; margin-bottom: 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px;">Deep Dive</h4>
                            <div class="fin-row" title="G2 / Capterra Score"><span>B2B Reviews</span> <strong>${data.sentiment?.g2_score || 'N/A'}/5 <small>(${data.sentiment?.g2_badges?.length || 0} Badges)</small></strong></div>
                            <div class="fin-row" title="Trustpilot Consumer Score"><span>Trustpilot</span> <strong>${data.sentiment?.trustpilot || 'N/A'}/5</strong></div>
                            <div class="fin-row" title="Moz Domain Authority"><span>Domain Auth</span> <strong>${data.seo?.da || 0}/100</strong></div>
                            <div class="fin-row" title="Page Load Speed"><span>Site Speed</span> <strong style="color: ${data.seo?.speed >= 80 ? '#16a34a' : (data.seo?.speed < 50 ? '#dc2626' : '#d97706')}">${data.seo?.speed || 0}/100</strong></div>
                            <div class="fin-row" title="Founder Exit History / Tier 1 VC"><span>Pedigree</span> <strong>${data.risk_mgmt?.founder_exit ? 'Exited Founder' : (data.risk_mgmt?.tier1_vc ? 'Tier 1 VC' : 'Standard')}</strong></div>
                             <div class="fin-row" title="SOC2 / WARN Notices"><span>Risk Flags</span> <strong>${data.risk_mgmt?.warn > 0 ? '⚠️ LAYOFFS' : (data.risk_mgmt?.soc2 ? '✅ SOC2' : 'None')}</strong></div>
                        </div>
                    </div>
                    
                    <div style="font-size: 0.8em; color: #94a3b8; text-align: right; margin-top: 15px;">
                        Data sources: ${data.data_sources?.join(', ') || 'SEC Form D, LinkedIn'}
                    </div>
                </div>
                <style>
                    /* Reuse fin-row styles from above */
                </style>
                `;
            } else {
                // Fallback for minimal data
                stockSection.innerHTML = `
                    <div class="private-badge" style="background: #e2e8f0; color: #64748b; display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: 600; margin-bottom: 10px;">
                        PRIVATE COMPANY
                    </div>
                    <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 16px;">
                        Data sources: ${data.data_sources?.join(', ') || 'Company website, LinkedIn, News'}
                    </p>
                `;
            }
        }
    } catch (error) {
        console.warn("Stock data load error", error);
        stockSection.innerHTML = '<div class="private-badge">Private Company (Data Unavailable)</div>';
    }
}

async function downloadBattlecard(id) {
    showToast('Generating battlecard PDF...', 'info');
    // In production, this would call the backend to generate the PDF
    window.open(`${API_BASE}/api/reports/battlecard/${id}`, '_blank');
}

// Battlecard PDF export - uses client-side jsPDF if available, else server-side
async function downloadBattlecardPDF(id) {
    const comp = competitors.find(c => c.id === id);
    if (!comp) {
        showToast('Competitor not found', 'error');
        return;
    }

    showToast('Generating battlecard PDF...', 'info');

    // Try client-side PDF first
    if (window.pdfExporter && window.jspdf) {
        try {
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

            // Header
            doc.setFontSize(20);
            doc.setTextColor(18, 39, 83);
            doc.text(comp.name + ' - Battlecard', 14, 22);

            doc.setFontSize(10);
            doc.setTextColor(100, 100, 100);
            doc.text('Generated: ' + new Date().toLocaleDateString() + ' | Certify Intel', 14, 30);
            doc.text('Threat Level: ' + (comp.threat_level || 'Medium'), 14, 36);

            // Company overview table
            const overviewHeaders = ['Field', 'Value'];
            const overviewRows = [
                ['Website', comp.website || 'N/A'],
                ['Headquarters', comp.headquarters || 'N/A'],
                ['Founded', String(comp.year_founded || 'N/A')],
                ['Employees', String(comp.employee_count || 'N/A')],
                ['Customers', String(comp.customer_count || 'N/A')],
                ['Funding', comp.funding_total || 'N/A'],
                ['Revenue', comp.annual_revenue || comp.estimated_revenue || 'N/A'],
                ['Pricing Model', comp.pricing_model || 'N/A'],
                ['Base Price', comp.base_price || 'N/A'],
                ['G2 Rating', comp.g2_rating ? comp.g2_rating + '/5' : 'N/A'],
            ];

            doc.autoTable({
                head: [overviewHeaders],
                body: overviewRows,
                startY: 42,
                theme: 'striped',
                headStyles: { fillColor: [58, 149, 237] },
                styles: { fontSize: 9 },
            });

            // Key features
            if (comp.key_features) {
                const finalY = doc.lastAutoTable.finalY + 10;
                doc.setFontSize(12);
                doc.setTextColor(18, 39, 83);
                doc.text('Key Features', 14, finalY);
                doc.setFontSize(9);
                doc.setTextColor(60, 60, 60);
                const features = doc.splitTextToSize(comp.key_features, 180);
                doc.text(features, 14, finalY + 6);
            }

            // Strengths/weaknesses
            if (comp.strengths || comp.weaknesses) {
                doc.addPage();
                let y = 20;
                if (comp.strengths) {
                    doc.setFontSize(12);
                    doc.setTextColor(21, 128, 61);
                    doc.text('Strengths', 14, y);
                    doc.setFontSize(9);
                    doc.setTextColor(60, 60, 60);
                    const sText = doc.splitTextToSize(comp.strengths, 180);
                    doc.text(sText, 14, y + 6);
                    y += 6 + sText.length * 4 + 10;
                }
                if (comp.weaknesses) {
                    doc.setFontSize(12);
                    doc.setTextColor(185, 28, 28);
                    doc.text('Weaknesses', 14, y);
                    doc.setFontSize(9);
                    doc.setTextColor(60, 60, 60);
                    const wText = doc.splitTextToSize(comp.weaknesses, 180);
                    doc.text(wText, 14, y + 6);
                }
            }

            const dateStr = new Date().toISOString().split('T')[0];
            const safeName = comp.name.replace(/[^a-zA-Z0-9]/g, '_');
            doc.save('battlecard_' + safeName + '_' + dateStr + '.pdf');
            showToast('Battlecard PDF exported', 'success');
            return;
        } catch (err) {
            console.warn('[Battlecard] Client-side PDF failed, falling back to server:', err);
        }
    }

    // Fallback: server-side PDF
    try {
        window.open(`${API_BASE}/api/reports/battlecard/${id}`, '_blank');
        showToast('PDF download started', 'success');
    } catch (error) {
        console.error('Error downloading battlecard:', error);
        showToast('Error generating PDF', 'error');
    }
}

// Show comparison modal between competitor and Certify Health (v6.1.2)
function showCompetitorComparison(competitorId) {
    const comp = competitors.find(c => c.id === competitorId);
    if (!comp) {
        showToast('Competitor not found', 'error');
        return;
    }

    // Look up Certify Health from the competitors table (id=1 is "Our Company")
    const certifyComp = competitors.find(c => c.name && c.name.toLowerCase().includes('certify'));

    // Build Certify data from the actual database record, with sensible defaults
    const certifyData = {
        name: certifyComp ? certifyComp.name : 'Certify Health',
        employee_count: certifyComp?.employee_count || 'N/A',
        customer_count: certifyComp?.customer_count || 'N/A',
        year_founded: certifyComp?.year_founded || certifyComp?.founding_year || 'N/A',
        headquarters: certifyComp?.headquarters || 'N/A',
        pricing_model: certifyComp?.pricing_model || 'N/A',
        hipaa_compliant: certifyComp?.hipaa_compliant !== undefined ? certifyComp.hipaa_compliant : true,
        implementation_days: certifyComp?.implementation_time || 'N/A',
        support: certifyComp?.support_model || certifyComp?.support_hours || 'N/A'
    };

    // Helper to build a comparison row with source dot for competitor
    function compRow(label, certVal, compVal, idx, fieldName) {
        const bg = idx % 2 === 0 ? 'background: #f8fafc;' : '';
        const border = 'border-bottom: 1px solid #e2e8f0;';
        const dot = fieldName ? renderSourceDot(comp.id, fieldName, compVal) : '';
        return `<tr style="${bg}">
            <td style="padding: 12px 16px; ${border} font-weight: 500;">${label}</td>
            <td style="padding: 12px 16px; ${border} text-align: center; font-weight: 600;">${certVal}</td>
            <td style="padding: 12px 16px; ${border} text-align: center;"><span style="display:inline-flex;align-items:center;gap:4px;">${dot} ${compVal}</span></td>
        </tr>`;
    }

    const rows = [
        compRow('Employees', certifyData.employee_count, comp.employee_count || 'Unknown', 0, 'employee_count'),
        compRow('Customers', certifyData.customer_count, comp.customer_count || 'Unknown', 1, 'customer_count'),
        compRow('Founded', certifyData.year_founded, comp.year_founded || comp.founding_year || 'Unknown', 2, 'year_founded'),
        compRow('Headquarters', certifyData.headquarters, comp.headquarters || 'Unknown', 3, 'headquarters'),
        compRow('Pricing Model', certifyData.pricing_model, comp.pricing_model || 'Unknown', 4, 'pricing_model'),
        compRow('HIPAA Compliant', certifyData.hipaa_compliant ? '✓ Yes' : 'Unknown', comp.hipaa_compliant ? '✓ Yes' : 'Unknown', 5, 'hipaa_compliant'),
        compRow('Implementation', certifyData.implementation_days, comp.implementation_time || 'Unknown', 6, 'implementation_time'),
        compRow('Support', certifyData.support, comp.support_model || comp.support_hours || 'Unknown', 7, 'support_model'),
    ];

    const content = `
        <div style="max-width: 800px;">
            <h2 style="margin: 0 0 24px 0; text-align: center; color: #1e293b;">
                📊 Competitive Comparison
            </h2>
            <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: var(--shadow-sm);">
                <thead>
                    <tr style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);">
                        <th style="padding: 16px; text-align: left; color: white; font-weight: 600;">Attribute</th>
                        <th style="padding: 16px; text-align: center; color: #ffd700; font-weight: 700;">✨ ${escapeHtml(certifyData.name)}</th>
                        <th style="padding: 16px; text-align: center; color: white; font-weight: 600;">${escapeHtml(comp.name)}</th>
                    </tr>
                </thead>
                <tbody>${rows.join('')}</tbody>
            </table>
            <p style="text-align: center; color: #94a3b8; font-size: 11px; margin-top: 12px;">Data sourced from competitor database. Update via Competitor Details or Settings.</p>
            <div style="margin-top: 16px; text-align: center;">
                <button class="btn btn-secondary" onclick="closeModal()" style="padding: 10px 24px;">Close</button>
            </div>
        </div>
    `;

    showModal(content);
}

async function generateAllBattlecards() {
    showToast('Generating all battlecards...', 'info');
    // Call backend endpoint
}

// ============== Reports ==============

async function generateWeeklyBriefing() {
    showToast('Generating executive briefing...', 'info');
    window.open(`${API_BASE}/api/reports/weekly-briefing`, '_blank');
}

async function generateComparisonReport() {
    showToast('Generating comparison report...', 'info');
    window.open(`${API_BASE}/api/reports/comparison`, '_blank');
}

// ============== Sales & Marketing Module ==============

/**
 * Initialize Sales & Marketing module: populate all competitor dropdowns.
 */
function initSalesMarketingModule() {
    const selects = [
        'dimensionCompetitorSelect', 'battlecardCompetitorSelect',
        'compareCompetitor1', 'compareCompetitor2',
        'talkingPointsCompetitor', 'dealIntelCompetitorSelect',
        'winThemesCompetitorSelect', 'objectionCompetitorSelect',
        'quickLookupCompetitor', 'playbookCompetitor',
        'pricingCompetitor1', 'pricingCompetitor2', 'pricingCompetitor3'
    ];
    selects.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const current = el.value;
        el.innerHTML = '<option value="">-- Select Competitor --</option>';
        (competitors || []).forEach(c => {
            if (c.name && !c.name.toLowerCase().includes('certify')) {
                el.innerHTML += `<option value="${c.id}">${escapeHtml(c.name)}</option>`;
            }
        });
        if (current) el.value = current;
    });

    // Populate dimension filter dropdowns
    const dimSelect = document.getElementById('talkingPointsDimension');
    if (dimSelect && dimSelect.options.length <= 1) {
        const dims = ['Product Packaging','Integration Depth','Support & Service','Retention & Stickiness','User Adoption','Implementation & TTV','Enterprise Reliability','Pricing Flexibility','Reporting & Analytics'];
        dims.forEach(d => { dimSelect.innerHTML += `<option value="${d}">${d}</option>`; });
    }
}
window.initSalesMarketingModule = initSalesMarketingModule;

/**
 * Switch between Sales & Marketing tabs.
 */
function showSalesMarketingTab(tabName) {
    // Hide all tab content panels
    document.querySelectorAll('.sm-tab-content').forEach(el => { el.style.display = 'none'; el.classList.remove('active'); });
    // Deactivate all tab buttons
    document.querySelectorAll('.sm-tab-btn').forEach(btn => btn.classList.remove('active'));

    // Show the selected tab
    const tabEl = document.getElementById(`sm-${tabName}Tab`);
    if (tabEl) { tabEl.style.display = 'block'; tabEl.classList.add('active'); }

    // Activate the clicked button
    const clickedBtn = event && event.target ? event.target.closest('.sm-tab-btn') : null;
    if (clickedBtn) clickedBtn.classList.add('active');
}
window.showSalesMarketingTab = showSalesMarketingTab;

/**
 * Show Deal Room sub-tabs.
 */
function showDealRoomTab(tabName) {
    document.querySelectorAll('.deal-room-content').forEach(el => { el.style.display = 'none'; el.classList.remove('active'); });
    document.querySelectorAll('.deal-tab-btn').forEach(btn => btn.classList.remove('active'));
    const tabEl = document.getElementById(`dealRoom-${tabName}Tab`);
    if (tabEl) { tabEl.style.display = 'block'; tabEl.classList.add('active'); }
    const clickedBtn = event && event.target ? event.target.closest('.deal-tab-btn') : null;
    if (clickedBtn) clickedBtn.classList.add('active');
}
window.showDealRoomTab = showDealRoomTab;

/**
 * Load competitor dimension scores from the API.
 */
async function loadCompetitorDimensions() {
    const select = document.getElementById('dimensionCompetitorSelect');
    const competitorId = select ? select.value : '';
    if (!competitorId) return;

    try {
        const data = await fetchAPI(`/api/sales-marketing/competitors/${competitorId}/dimensions`);
        const summary = document.getElementById('dimensionProfileSummary');
        if (summary) summary.style.display = 'flex';

        // Populate dimension score cards
        if (data && data.dimensions) {
            const overallEl = document.getElementById('smOverallScore');
            if (overallEl) overallEl.textContent = data.overall_score ? data.overall_score.toFixed(1) : '--';

            const strengthEl = document.getElementById('smStrengthCount');
            const weakEl = document.getElementById('smWeaknessCount');
            let strengths = 0, weaknesses = 0;
            data.dimensions.forEach(d => { if (d.score >= 4) strengths++; if (d.score <= 2) weaknesses++; });
            if (strengthEl) strengthEl.textContent = strengths;
            if (weakEl) weakEl.textContent = weaknesses;

            // Render dimension cards
            const container = document.getElementById('dimensionGrid');
            if (container) {
                container.innerHTML = data.dimensions.map(d => `
                    <div class="sm-dimension-card">
                        <h4>${escapeHtml(d.name || d.dimension_name || '')}</h4>
                        <div class="sm-score-display">${d.score ? d.score.toFixed(1) : '--'} / 5.0</div>
                        <input type="range" min="0" max="5" step="0.1" value="${d.score || 0}"
                            data-dimension-id="${d.id || d.dimension_id}" class="sm-score-slider"
                            oninput="this.previousElementSibling.textContent = parseFloat(this.value).toFixed(1) + ' / 5.0'">
                        <textarea class="sm-notes" placeholder="Notes...">${escapeHtml(d.notes || '')}</textarea>
                    </div>
                `).join('');
            }
        }
    } catch (err) {
        console.error('Failed to load dimensions:', err);
        showToast('Failed to load dimension scores', 'error');
    }
}
window.loadCompetitorDimensions = loadCompetitorDimensions;

/**
 * AI suggest dimension scores.
 */
async function aiSuggestDimensions() {
    const select = document.getElementById('dimensionCompetitorSelect');
    const competitorId = select ? select.value : '';
    if (!competitorId) { showToast('Select a competitor first', 'warning'); return; }

    showToast('AI analyzing competitor dimensions...', 'info');
    try {
        const data = await fetchAPI(`/api/sales-marketing/competitors/${competitorId}/dimensions/ai-suggest`, { method: 'POST' });
        if (data && data.suggestions) {
            showToast(`AI suggested scores for ${data.suggestions.length} dimensions`, 'success');
            loadCompetitorDimensions(); // Reload to show suggestions

            // Add conversational chat widget for dimension follow-ups
            const dimSection = select.closest('.card') || select.parentElement;
            let dimChatDiv = document.getElementById('dimensionChatWidget');
            if (!dimChatDiv) {
                dimChatDiv = document.createElement('div');
                dimChatDiv.id = 'dimensionChatWidget';
                dimSection.appendChild(dimChatDiv);
            }
            createChatWidget('dimensionChatWidget', {
                pageContext: 'dimensions_' + competitorId,
                competitorId: parseInt(competitorId),
                placeholder: 'Ask why these scores were suggested...',
                endpoint: '/api/analytics/chat'
            });
        }
    } catch (err) {
        console.error('AI suggest failed:', err);
        showToast('AI suggestion failed', 'error');
    }
}
window.aiSuggestDimensions = aiSuggestDimensions;

/**
 * Save all dimension scores.
 */
async function saveAllDimensions() {
    const select = document.getElementById('dimensionCompetitorSelect');
    const competitorId = select ? select.value : '';
    if (!competitorId) { showToast('Select a competitor first', 'warning'); return; }

    const sliders = document.querySelectorAll('.sm-score-slider');
    const updates = [];
    sliders.forEach(slider => {
        const dimId = slider.dataset.dimensionId;
        const notes = slider.closest('.sm-dimension-card')?.querySelector('.sm-notes')?.value || '';
        updates.push({ dimension_id: parseInt(dimId), score: parseFloat(slider.value), notes });
    });

    try {
        await fetchAPI(`/api/sales-marketing/competitors/${competitorId}/dimensions/bulk-update`, {
            method: 'POST', body: JSON.stringify({ updates })
        });
        showToast('Dimension scores saved', 'success');
    } catch (err) {
        console.error('Save dimensions failed:', err);
        showToast('Failed to save dimensions', 'error');
    }
}
window.saveAllDimensions = saveAllDimensions;

/**
 * Generate dynamic battlecard for selected competitor.
 */
async function generateDynamicBattlecard() {
    const select = document.getElementById('battlecardCompetitorSelect');
    const competitorId = select ? select.value : '';
    const typeSelect = document.getElementById('battlecardType');
    const bcType = typeSelect ? typeSelect.value : 'full';
    if (!competitorId) { showToast('Select a competitor first', 'warning'); return; }

    const container = document.getElementById('dynamicBattlecardContent');
    if (container) container.innerHTML = '<div style="text-align:center;padding:30px;"><div class="spinner" style="margin:0 auto 12px;width:24px;height:24px;"></div><p style="color:#64748b;">Generating battlecard...</p></div>';

    try {
        const data = await fetchAPI('/api/sales-marketing/battlecards/generate', {
            method: 'POST', body: JSON.stringify({ competitor_id: parseInt(competitorId), type: bcType })
        });
        if (data && data.content && container) {
            container.innerHTML = `<div class="sm-battlecard-rendered">${renderStrategyMarkdown(data.content)}</div>`;

            // Add conversational chat widget below the dynamic battlecard
            let dynChatDiv = document.getElementById('dynamicBattlecardChatWidget');
            if (!dynChatDiv) {
                dynChatDiv = document.createElement('div');
                dynChatDiv.id = 'dynamicBattlecardChatWidget';
                container.appendChild(dynChatDiv);
            }
            createChatWidget('dynamicBattlecardChatWidget', {
                pageContext: 'dynamic_battlecard_' + competitorId,
                competitorId: parseInt(competitorId),
                placeholder: 'Ask follow-up questions about this battlecard...',
                endpoint: '/api/analytics/chat'
            });
        } else if (container) {
            container.innerHTML = '<p class="sm-placeholder">Battlecard generated. Check the Battlecards page for the full view.</p>';
        }
        showToast('Battlecard generated', 'success');
    } catch (err) {
        console.error('Battlecard generation failed:', err);
        if (container) container.innerHTML = '<p style="color:#dc2626;">Failed to generate battlecard.</p>';
        showToast('Battlecard generation failed', 'error');
    }
}
window.generateDynamicBattlecard = generateDynamicBattlecard;

/**
 * Load talking points for a competitor filtered by dimension and type.
 */
async function loadTalkingPoints() {
    const compId = document.getElementById('talkingPointsCompetitor')?.value;
    if (!compId) return;
    const dimension = document.getElementById('talkingPointsDimension')?.value || '';
    const tpType = document.getElementById('talkingPointsType')?.value || '';

    const container = document.getElementById('talkingPointsList');
    if (!container) return;

    try {
        let url = `/api/sales-marketing/competitors/${compId}/talking-points`;
        const params = [];
        if (dimension) params.push(`dimension=${encodeURIComponent(dimension)}`);
        if (tpType) params.push(`type=${encodeURIComponent(tpType)}`);
        if (params.length) url += '?' + params.join('&');

        const data = await fetchAPI(url);
        const points = data.talking_points || data || [];

        if (!Array.isArray(points) || points.length === 0) {
            container.innerHTML = '<p class="sm-placeholder">No talking points found. Add some or run AI analysis first.</p>';
            return;
        }

        container.innerHTML = points.map(tp => `
            <div class="sm-talking-point-card" style="background:#f8fafc;border-radius:8px;padding:14px;margin-bottom:10px;border-left:4px solid ${tp.type === 'strength' ? '#16a34a' : tp.type === 'weakness' ? '#dc2626' : '#3b82f6'};">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-weight:600;font-size:13px;color:#1e293b;">${escapeHtml(tp.dimension || 'General')}</span>
                    <span style="font-size:11px;padding:2px 8px;border-radius:4px;background:${tp.type === 'strength' ? '#dcfce7' : tp.type === 'weakness' ? '#fef2f2' : '#eff6ff'};color:${tp.type === 'strength' ? '#15803d' : tp.type === 'weakness' ? '#b91c1c' : '#1d4ed8'};">${escapeHtml(tp.type || 'point')}</span>
                </div>
                <p style="margin:0;font-size:13px;line-height:1.5;color:#334155;">${escapeHtml(tp.content || tp.text || '')}</p>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load talking points:', err);
        container.innerHTML = '<p style="color:#dc2626;">Failed to load talking points.</p>';
    }
}
window.loadTalkingPoints = loadTalkingPoints;

/**
 * Show Add Talking Point modal.
 */
function showAddTalkingPointModal() {
    const compId = document.getElementById('talkingPointsCompetitor')?.value;
    if (!compId) { showToast('Select a competitor first', 'warning'); return; }
    const comp = competitors.find(c => c.id == compId);

    const content = `
        <div style="max-width:500px;">
            <h3 style="margin:0 0 16px;">➕ Add Talking Point for ${escapeHtml(comp?.name || 'Competitor')}</h3>
            <select id="newTpDimension" class="form-select" style="width:100%;margin-bottom:10px;">
                <option value="">-- Dimension --</option>
                <option value="Product Packaging">Product Packaging</option>
                <option value="Integration Depth">Integration Depth</option>
                <option value="Support & Service">Support & Service</option>
                <option value="User Adoption">User Adoption</option>
                <option value="Pricing Flexibility">Pricing Flexibility</option>
                <option value="Enterprise Reliability">Enterprise Reliability</option>
            </select>
            <select id="newTpType" class="form-select" style="width:100%;margin-bottom:10px;">
                <option value="strength">Strength</option>
                <option value="weakness">Weakness</option>
                <option value="objection">Objection</option>
                <option value="counter">Counter-Point</option>
            </select>
            <textarea id="newTpContent" class="form-control" rows="4" placeholder="Enter the talking point..." style="width:100%;margin-bottom:12px;"></textarea>
            <div style="display:flex;gap:10px;justify-content:flex-end;">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-primary" onclick="submitTalkingPoint(${compId})">Save</button>
            </div>
        </div>
    `;
    showModal(content);
}
window.showAddTalkingPointModal = showAddTalkingPointModal;

async function submitTalkingPoint(compId) {
    const dimension = document.getElementById('newTpDimension')?.value;
    const tpType = document.getElementById('newTpType')?.value;
    const content = document.getElementById('newTpContent')?.value;
    if (!content) { showToast('Enter talking point text', 'warning'); return; }

    try {
        await fetchAPI('/api/sales-marketing/talking-points', {
            method: 'POST', body: JSON.stringify({ competitor_id: compId, dimension, type: tpType, content })
        });
        closeModal();
        showToast('Talking point added', 'success');
        loadTalkingPoints();
    } catch (err) {
        showToast('Failed to add talking point', 'error');
    }
}
window.submitTalkingPoint = submitTalkingPoint;

/**
 * Load Deal Intelligence for a competitor.
 */
async function loadDealIntelligence() {
    const compId = document.getElementById('dealIntelCompetitorSelect')?.value;
    if (!compId) return;
    const comp = competitors.find(c => c.id == compId);
    const container = document.getElementById('dealIntelContent');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;padding:20px;"><div class="spinner" style="margin:0 auto 10px;width:22px;height:22px;"></div><p style="color:#64748b;font-size:12px;">Loading deal intelligence...</p></div>';

    try {
        const data = await fetchAPI(`/api/sales-marketing/compare/${compId}/vs-certify`);
        let html = `<h3 style="margin:0 0 14px;font-size:15px;">Deal Intel: ${escapeHtml(comp?.name || '')}</h3>`;

        if (data.advantages && data.advantages.length) {
            html += '<h4 style="color:#16a34a;font-size:13px;margin:12px 0 6px;">✅ Our Advantages</h4><ul style="margin:0;padding-left:18px;">';
            data.advantages.forEach(a => { html += `<li style="font-size:13px;margin-bottom:4px;">${escapeHtml(typeof a === 'string' ? a : a.text || a.description || JSON.stringify(a))}</li>`; });
            html += '</ul>';
        }
        if (data.disadvantages && data.disadvantages.length) {
            html += '<h4 style="color:#dc2626;font-size:13px;margin:12px 0 6px;">⚠️ Their Advantages</h4><ul style="margin:0;padding-left:18px;">';
            data.disadvantages.forEach(d => { html += `<li style="font-size:13px;margin-bottom:4px;">${escapeHtml(typeof d === 'string' ? d : d.text || d.description || JSON.stringify(d))}</li>`; });
            html += '</ul>';
        }
        if (data.recommendation) {
            html += `<h4 style="color:#3b82f6;font-size:13px;margin:12px 0 6px;">💡 Recommendation</h4><p style="font-size:13px;color:#334155;">${escapeHtml(data.recommendation)}</p>`;
        }

        container.innerHTML = html || '<p class="sm-placeholder">No deal intelligence data available for this competitor.</p>';
    } catch (err) {
        console.error('Deal intelligence load failed:', err);
        container.innerHTML = '<p class="sm-placeholder">Could not load deal intelligence. Select a competitor with dimension scores.</p>';
    }
}
window.loadDealIntelligence = loadDealIntelligence;

/**
 * Generate Win Themes for a competitor.
 */
async function generateWinThemes() {
    const compId = document.getElementById('winThemesCompetitorSelect')?.value;
    if (!compId) { showToast('Select a competitor first', 'warning'); return; }
    const container = document.getElementById('winThemesContent');
    if (!container) return;

    container.innerHTML = '<div style="text-align:center;padding:20px;"><div class="spinner" style="margin:0 auto 10px;width:22px;height:22px;"></div><p style="color:#64748b;font-size:12px;">Generating win themes...</p></div>';

    try {
        const comp = competitors.find(c => c.id == compId);
        const data = await fetchAPI(`/api/sales-marketing/compare/${compId}/vs-certify`);
        let html = `<h3 style="margin:0 0 14px;font-size:15px;">🏆 Win Themes vs ${escapeHtml(comp?.name || '')}</h3>`;

        if (data.advantages) {
            html += data.advantages.map((a, i) => `
                <div style="background:#f0fdf4;border-radius:8px;padding:12px;margin-bottom:8px;border-left:4px solid #16a34a;">
                    <strong style="font-size:13px;">Theme ${i+1}:</strong>
                    <span style="font-size:13px;color:#334155;"> ${escapeHtml(typeof a === 'string' ? a : a.text || a.description || '')}</span>
                </div>`).join('');
        }
        container.innerHTML = html || '<p class="sm-placeholder">No win themes available. Score dimensions first.</p>';
    } catch (err) {
        container.innerHTML = '<p class="sm-placeholder">Could not generate win themes. Score dimensions first.</p>';
    }
}
window.generateWinThemes = generateWinThemes;

/**
 * Load Objections for a competitor.
 */
async function loadObjections() {
    const compId = document.getElementById('objectionCompetitorSelect')?.value;
    if (!compId) return;
    const container = document.getElementById('objectionsList');
    if (!container) return;

    try {
        const comp = competitors.find(c => c.id == compId);
        const data = await fetchAPI(`/api/sales-marketing/competitors/${compId}/talking-points?type=objection`);
        const points = data.talking_points || data || [];

        if (!Array.isArray(points) || points.length === 0) {
            container.innerHTML = '<p class="sm-placeholder">No objections recorded. Add objections via the Talking Points tab.</p>';
            return;
        }

        container.innerHTML = `<h3 style="margin:0 0 14px;font-size:15px;">💬 Common Objections for ${escapeHtml(comp?.name || '')}</h3>` +
            points.map(tp => `
            <div style="background:#fff7ed;border-radius:8px;padding:12px;margin-bottom:8px;border-left:4px solid #f97316;">
                <p style="margin:0;font-size:13px;color:#334155;"><strong>"${escapeHtml(tp.content || tp.text || '')}"</strong></p>
                ${tp.counter ? `<p style="margin:6px 0 0;font-size:12px;color:#16a34a;">→ ${escapeHtml(tp.counter)}</p>` : ''}
            </div>`).join('');
    } catch (err) {
        if (container) container.innerHTML = '<p class="sm-placeholder">Could not load objections.</p>';
    }
}
window.loadObjections = loadObjections;

/**
 * Compare two competitors' dimensions (radar chart).
 */
function compareVsCertify() {
    const compId = document.getElementById('compareCompetitor1')?.value;
    if (!compId) { showToast('Select a competitor first', 'warning'); return; }
    const comp = competitors.find(c => c.id == compId);
    if (comp) showCompetitorComparison(comp.id);
}
window.compareVsCertify = compareVsCertify;

/**
 * Quick Lookup — AI briefing on a competitor.
 */
async function performQuickLookup() {
    const compId = document.getElementById('quickLookupCompetitor')?.value;
    if (!compId) { showToast('Select a competitor first', 'warning'); return; }
    const container = document.getElementById('quickLookupResult');
    if (!container) return;

    const comp = competitors.find(c => c.id == compId);
    container.innerHTML = '<div style="text-align:center;padding:20px;"><div class="spinner" style="margin:0 auto 10px;width:22px;height:22px;"></div><p style="color:#64748b;font-size:12px;">AI generating quick briefing...</p></div>';

    try {
        const data = await fetchAPI('/api/ai/generate-battlecard', {
            method: 'POST', body: JSON.stringify({ competitor_name: comp?.name, competitor_id: parseInt(compId) })
        });
        if (data && data.content) {
            container.innerHTML = renderStrategyMarkdown(data.content);

            // Add conversational chat widget below the quick lookup result
            let qlChatDiv = document.getElementById('quickLookupChatWidget');
            if (!qlChatDiv) {
                qlChatDiv = document.createElement('div');
                qlChatDiv.id = 'quickLookupChatWidget';
                container.appendChild(qlChatDiv);
            }
            createChatWidget('quickLookupChatWidget', {
                pageContext: 'quick_lookup_' + compId,
                competitorId: parseInt(compId),
                placeholder: 'Ask follow-up questions about this competitor...',
                endpoint: '/api/analytics/chat'
            });
        } else {
            container.innerHTML = '<p class="sm-placeholder">No briefing generated.</p>';
        }
    } catch (err) {
        container.innerHTML = '<p style="color:#dc2626;">Quick lookup failed. Try again.</p>';
    }
}
window.performQuickLookup = performQuickLookup;

function quickLookupCategory(category) {
    showToast(`Filtering by ${category}...`, 'info');
    performQuickLookup();
}
window.quickLookupCategory = quickLookupCategory;

/**
 * Pricing Calculator - calculates competitive pricing comparison
 */
function calculatePricing() {
    const users = parseInt(document.getElementById('pricingUsers')?.value) || 100;
    const contractLength = parseInt(document.getElementById('pricingContractLength')?.value) || 3;
    const implementation = document.getElementById('pricingImplementation')?.value || 'standard';
    const support = document.getElementById('pricingSupport')?.value || 'premium';

    const comp1Id = document.getElementById('pricingCompetitor1')?.value;
    const comp2Id = document.getElementById('pricingCompetitor2')?.value;
    const comp3Id = document.getElementById('pricingCompetitor3')?.value;

    const resultContainer = document.getElementById('pricingComparisonResult');
    if (!resultContainer) return;

    // Base pricing calculation (simplified model)
    const basePerUser = 50;
    const implementationCost = {
        'basic': 5000,
        'standard': 15000,
        'enterprise': 35000
    };
    const supportMultiplier = {
        'standard': 1.0,
        'premium': 1.2,
        'dedicated': 1.5
    };

    const annualCost = (users * basePerUser * 12 * supportMultiplier[support]) + (implementationCost[implementation] / contractLength);
    const totalCost = annualCost * contractLength;

    let html = '<div class="pricing-results">';
    html += '<div class="pricing-summary-card">';
    html += '<h4>Certify Health Estimate</h4>';
    html += `<div class="pricing-amount">$${annualCost.toLocaleString('en-US', {maximumFractionDigits: 0})} <span style="font-size:14px;color:#64748b;">/year</span></div>`;
    html += `<p style="color:#64748b;font-size:13px;margin:5px 0 0 0;">Total ${contractLength}-year cost: $${totalCost.toLocaleString('en-US', {maximumFractionDigits: 0})}</p>`;
    html += '</div>';

    // Add competitor comparisons if selected
    const selectedCompetitors = [comp1Id, comp2Id, comp3Id].filter(id => id && id !== '');
    if (selectedCompetitors.length > 0) {
        html += '<div class="pricing-comparison-grid" style="margin-top:20px;">';
        selectedCompetitors.forEach(compId => {
            const comp = competitors.find(c => c.id == compId);
            if (comp) {
                html += '<div class="pricing-competitor-card">';
                html += `<h5>${escapeHtml(comp.name || 'Unknown')}</h5>`;
                const compPricing = comp.pricing_model || 'N/A';
                html += `<p style="color:#64748b;font-size:12px;margin:5px 0;">Model: ${escapeHtml(compPricing)}</p>`;
                if (comp.price_range) {
                    html += `<div class="pricing-amount" style="font-size:18px;">${escapeHtml(comp.price_range)}</div>`;
                } else {
                    html += `<p style="color:#94a3b8;font-size:12px;font-style:italic;margin:5px 0;">Pricing data not available</p>`;
                }
                html += '</div>';
            }
        });
        html += '</div>';
    } else {
        html += '<p class="sm-placeholder" style="margin-top:20px;">Select competitors above to compare pricing</p>';
    }

    html += '</div>';
    resultContainer.innerHTML = html;
}
window.calculatePricing = calculatePricing;

/**
 * Generate Sales Playbook for a competitor.
 */
async function generatePlaybook() {
    const compId = document.getElementById('playbookCompetitor')?.value;
    if (!compId) { showToast('Select a competitor first', 'warning'); return; }
    const container = document.getElementById('playbookResult');
    if (!container) return;

    const comp = competitors.find(c => c.id == compId);
    container.innerHTML = '<div style="text-align:center;padding:20px;"><div class="spinner" style="margin:0 auto 10px;width:22px;height:22px;"></div><p style="color:#64748b;font-size:12px;">Generating sales playbook...</p></div>';

    try {
        const data = await fetchAPI('/api/ai/generate-battlecard', {
            method: 'POST', body: JSON.stringify({ competitor_name: comp?.name, competitor_id: parseInt(compId), additional_context: 'Generate a concise sales playbook with key talking points, objection responses, and win strategies.' })
        });
        if (data && data.content) {
            container.innerHTML = renderStrategyMarkdown(data.content);

            // Add conversational chat widget below the playbook result
            let pbChatDiv = document.getElementById('playbookChatWidget');
            if (!pbChatDiv) {
                pbChatDiv = document.createElement('div');
                pbChatDiv.id = 'playbookChatWidget';
                container.appendChild(pbChatDiv);
            }
            createChatWidget('playbookChatWidget', {
                pageContext: 'playbook_' + compId,
                competitorId: parseInt(compId),
                placeholder: 'Ask follow-up questions about this playbook...',
                endpoint: '/api/analytics/chat'
            });
        } else {
            container.innerHTML = '<p class="sm-placeholder">Could not generate playbook.</p>';
        }
    } catch (err) {
        container.innerHTML = '<p style="color:#dc2626;">Playbook generation failed.</p>';
    }
}
window.generatePlaybook = generatePlaybook;

function updatePlaybookContext() { /* no-op — context auto-updates */ }
window.updatePlaybookContext = updatePlaybookContext;

function exportPositioningMatrix() {
    const canvas = document.getElementById('positioningMatrixChart');
    if (!canvas) {
        showToast('Chart not found', 'error');
        return;
    }

    try {
        // Convert canvas to data URL
        const dataURL = canvas.toDataURL('image/png');

        // Create download link
        const link = document.createElement('a');
        link.download = `positioning-matrix-${new Date().toISOString().split('T')[0]}.png`;
        link.href = dataURL;
        link.click();

        showToast('Chart exported successfully', 'success');
    } catch (error) {
        console.error('Export failed:', error);
        showToast('Export failed. Please try again.', 'error');
    }
}
window.exportPositioningMatrix = exportPositioningMatrix;

function searchObjections() {
    // Filter objections by search text and category — reloads from existing list
    loadObjections();
}
window.searchObjections = searchObjections;

// ============== Settings ==============

// NOTE: showAddRuleModal is defined later in the file with the improved FEAT-001 modal

// ============== Actions ==============

async function triggerScrape(id) {
    showToast('Starting data refresh...', 'info');
    const result = await fetchAPI(`/api/scrape/${id}`, { method: 'POST' });
    if (result) {
        showToast('Refresh queued successfully', 'success');
    }
}

// Note: triggerScrapeAll is defined earlier in this file with progress tracking

async function triggerDiscovery() {
    showToast('Starting autonomous discovery agent...', 'info');
    try {
        const response = await fetch(`${API_BASE}/api/discovery/run`, { method: 'POST' });
        const data = await response.json();

        if (data.status === 'success') {
            const count = data.candidates ? data.candidates.length : 0;
            showToast(`Discovery complete! Found ${count} potential competitors.`, 'success');

            // Show results in a modal
            const resultsHtml = data.candidates.map(c => `
                <div class="discovery-result" style="border: 1px solid #eee; padding: 15px; margin-bottom: 10px; border-radius: 8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0;"><a href="${escapeHtml(c.url)}" target="_blank">${escapeHtml(c.name)}</a></h4>
                        <span class="badge ${c.relevance_score > 80 ? 'high' : 'medium'}">${c.relevance_score}% Match</span>
                    </div>
                    <p style="margin: 5px 0; font-size: 0.9em; color: #666;">${escapeHtml(c.reasoning || '')}</p>
                    <button class="btn btn-sm btn-outline" onclick="addDiscoveredCompetitor('${escapeHtml(c.name)}', '${escapeHtml(c.url)}')">+ Track This</button>
                </div>
            `).join('');

            showModal(`
                <h2>🔭 Discovered Candidates</h2>
                <p>The autonomous agent found the following potential competitors:</p>
                <div class="discovery-list" style="max-height: 400px; overflow-y: auto; margin-top: 15px;">
                    ${resultsHtml || '<p>No new high-confidence matches found.</p>'}
                </div>
            `);
        } else {
            showToast('Discovery agent encountered an error.', 'error');
        }
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

function addDiscoveredCompetitor(name, website) {
    // Pre-fill the add modal
    closeModal();
    showAddCompetitorModal();
    setTimeout(() => {
        document.querySelector('input[name="name"]').value = name;
        document.querySelector('input[name="website"]').value = website;
    }, 100);
}

// ============== Utilities ==============

function showModal(content) {
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

function closeModal() {
    document.getElementById('modal').classList.remove('active');
}

// ==============================================================================
// UX-007: Enhanced Toast Notifications with Icons and Progress
// ==============================================================================

const TOAST_ICONS = {
    success: '✓',
    error: '✕',
    warning: '⚠',
    info: 'ℹ'
};

function showToast(message, type = 'info', options = {}) {
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
        <span class="toast-icon">${TOAST_ICONS[type] || 'ℹ'}</span>
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
const showNotification = showToast;
window.showNotification = showToast;

// ==============================================================================
// UX-007: Loading Overlay & Progress States
// ==============================================================================

let loadingOverlay = null;

function showLoading(text = 'Loading...') {
    if (!loadingOverlay) {
        loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'loadingOverlay';
        loadingOverlay.className = 'loading-overlay';
        loadingOverlay.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner large"></div>
                <div class="loading-text">${text}</div>
            </div>
        `;
        document.body.appendChild(loadingOverlay);
    } else {
        loadingOverlay.querySelector('.loading-text').textContent = text;
    }

    requestAnimationFrame(() => loadingOverlay.classList.add('active'));
}

function hideLoading() {
    if (loadingOverlay) {
        loadingOverlay.classList.remove('active');
    }
}

function updateLoadingText(text) {
    if (loadingOverlay) {
        loadingOverlay.querySelector('.loading-text').textContent = text;
    }
}

// Create skeleton loading card
function createSkeletonCard() {
    return `
        <div class="card-skeleton">
            <div class="card-skeleton-header">
                <div class="skeleton skeleton-avatar"></div>
                <div style="flex: 1;">
                    <div class="skeleton skeleton-text medium"></div>
                    <div class="skeleton skeleton-text short"></div>
                </div>
            </div>
            <div class="card-skeleton-body">
                <div class="skeleton skeleton-text long"></div>
                <div class="skeleton skeleton-text medium"></div>
                <div class="skeleton skeleton-text short"></div>
            </div>
        </div>
    `;
}

// Set button loading state
function setButtonLoading(button, loading = true) {
    if (typeof button === 'string') {
        button = document.getElementById(button) || document.querySelector(button);
    }
    if (!button) return;

    if (loading) {
        button.classList.add('loading');
        button.disabled = true;
        button.dataset.originalText = button.textContent;
    } else {
        button.classList.remove('loading');
        button.disabled = false;
        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
        }
    }
}

// ==============================================================================
// UX-003: PWA Install Prompt
// ==============================================================================

let deferredInstallPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent automatic prompt
    e.preventDefault();
    deferredInstallPrompt = e;

    // Show our custom install banner
    showPWAInstallBanner();
});

function showPWAInstallBanner() {
    // Don't show if already installed or dismissed
    if (localStorage.getItem('pwa-install-dismissed')) return;
    if (window.matchMedia('(display-mode: standalone)').matches) return;

    let banner = document.getElementById('pwaInstallBanner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'pwaInstallBanner';
        banner.className = 'pwa-install-banner';
        banner.innerHTML = `
            <div class="pwa-install-banner-content">
                <span class="pwa-install-banner-icon">📱</span>
                <div class="pwa-install-banner-text">
                    <h4>Install Certify Intel</h4>
                    <p>Get quick access from your home screen</p>
                </div>
            </div>
            <div class="pwa-install-banner-actions">
                <button class="pwa-dismiss-btn" onclick="dismissPWABanner()">Not Now</button>
                <button class="pwa-install-btn" onclick="installPWA()">Install</button>
            </div>
        `;
        document.body.appendChild(banner);
    }

    setTimeout(() => banner.classList.add('visible'), 100);
}

function dismissPWABanner() {
    const banner = document.getElementById('pwaInstallBanner');
    if (banner) {
        banner.classList.remove('visible');
        setTimeout(() => banner.remove(), 300);
    }
    localStorage.setItem('pwa-install-dismissed', 'true');
}

async function installPWA() {
    if (!deferredInstallPrompt) {
        showToast('App cannot be installed at this time', 'warning');
        return;
    }

    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;

    if (outcome === 'accepted') {
        showToast('App installed successfully!', 'success', { title: 'Welcome!' });
    }

    deferredInstallPrompt = null;
    dismissPWABanner();
}

// Register service worker (with forced cache purge on version mismatch)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
        try {
            const EXPECTED_CACHE = 'v10.0.0';
            const lastCacheVersion = localStorage.getItem('sw_cache_version');

            // Force purge if cache version changed
            if (lastCacheVersion && lastCacheVersion !== EXPECTED_CACHE) {
                console.log('[PWA] Cache version mismatch, purging old caches...');
                const registrations = await navigator.serviceWorker.getRegistrations();
                for (const reg of registrations) {
                    await reg.unregister();
                }
                const cacheNames = await caches.keys();
                for (const name of cacheNames) {
                    await caches.delete(name);
                }
                localStorage.setItem('sw_cache_version', EXPECTED_CACHE);
                console.log('[PWA] Caches purged, reloading...');
                window.location.reload();
                return;
            }
            localStorage.setItem('sw_cache_version', EXPECTED_CACHE);

            const registration = await navigator.serviceWorker.register('/service-worker.js');

            // Check for updates
            registration.addEventListener('updatefound', () => {
                const newWorker = registration.installing;
                newWorker.addEventListener('statechange', () => {
                    if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                        // Auto-activate the new service worker
                        newWorker.postMessage({ type: 'SKIP_WAITING' });
                        showToast('App updated. Refreshing...', 'info', {
                            title: 'Update Applied',
                            duration: 2000
                        });
                        setTimeout(() => window.location.reload(), 1500);
                    }
                });
            });
        } catch (error) {
            console.error('[PWA] Service Worker registration failed:', error);
        }
    });
}

// ==============================================================================
// REL-003: Data Confidence Visualization
// ==============================================================================

/**
 * Get source tooltip HTML
 */
function getSourceTooltip(sources) {
    if (!sources || sources.length === 0) return '';

    const sourceList = sources.map(s => {
        const icon = getSourceIcon(s.source_type);
        return `${icon} ${s.source_type} (${new Date(s.retrieved_at).toLocaleDateString()})`;
    }).join('\\n');

    return `title="${sourceList}"`;
}

/**
 * Get icon for source type
 */
function getSourceIcon(sourceType) {
    const icons = {
        'sec_filing': '📊',
        'api': '🔌',
        'news_article': '📰',
        'website_scrape': '🌐',
        'manual_entry': '✍️',
        'client_provided': '📋'
    };
    return icons[sourceType] || '📄';
}

/**
 * Calculate trust score based on multiple factors
 */
function calculateTrustScore(field, competitor) {
    let score = 50; // Base score

    // Factor 1: Has data source
    if (competitor.data_sources?.[field]) {
        score += 15;
    }

    // Factor 2: Data freshness
    const lastUpdated = competitor.last_updated || competitor.updated_at;
    if (lastUpdated) {
        const daysSinceUpdate = Math.floor((Date.now() - new Date(lastUpdated)) / (1000 * 60 * 60 * 24));
        if (daysSinceUpdate < 7) score += 20;
        else if (daysSinceUpdate < 30) score += 10;
        else if (daysSinceUpdate > 90) score -= 15;
    }

    // Factor 3: Source confidence
    const source = competitor.data_sources?.[field];
    if (source?.confidence) {
        score += (source.confidence - 50) / 2;
    }

    return Math.max(0, Math.min(100, Math.round(score)));
}

// ==============================================================================
// REL-004: Real-Time Input Validation
// ==============================================================================
// Note: validationRules is defined at line ~359 - using that instance

/**
 * Validate a single input field
 */
function validateInput(input, rules = []) {
    const value = input.value;
    const errors = [];

    rules.forEach(rule => {
        if (typeof rule === 'string' && validationRules[rule]) {
            const r = validationRules[rule];
            if (r.pattern && !r.pattern.test(value)) {
                errors.push(r.message);
            } else if (r.validate && !r.validate(value)) {
                errors.push(r.message);
            }
        } else if (typeof rule === 'object' && rule.validate) {
            if (!rule.validate(value)) {
                errors.push(rule.message);
            }
        }
    });

    // Update UI
    const errorEl = input.parentElement.querySelector('.validation-error');
    if (errors.length > 0) {
        input.classList.add('invalid');
        input.classList.remove('valid');
        if (errorEl) {
            errorEl.textContent = errors[0];
            errorEl.style.display = 'block';
        }
        return false;
    } else {
        input.classList.remove('invalid');
        input.classList.add('valid');
        if (errorEl) {
            errorEl.style.display = 'none';
        }
        return true;
    }
}

/**
 * Setup real-time validation for a form
 */
function setupFormValidation(formId, fieldRules) {
    const form = document.getElementById(formId);
    if (!form) return;

    Object.entries(fieldRules).forEach(([fieldName, rules]) => {
        const input = form.querySelector(`[name="${fieldName}"]`) ||
                      form.querySelector(`#${fieldName}`);
        if (!input) return;

        // Add validation error element if not present
        if (!input.parentElement.querySelector('.validation-error')) {
            const errorEl = document.createElement('span');
            errorEl.className = 'validation-error';
            errorEl.setAttribute('role', 'alert');
            errorEl.setAttribute('aria-live', 'polite');
            input.parentElement.appendChild(errorEl);
        }

        // Debounced validation on input
        const debouncedValidate = debounce(() => validateInput(input, rules), 300);
        input.addEventListener('input', debouncedValidate);
        input.addEventListener('blur', () => validateInput(input, rules));
    });
}

// ==============================================================================
// REL-005: Error Recovery & Retry
// ==============================================================================

const retryConfig = {
    maxRetries: 3,
    baseDelay: 1000,
    maxDelay: 10000
};

/**
 * Fetch with automatic retry and exponential backoff
 */
async function fetchWithRetry(url, options = {}, retries = retryConfig.maxRetries) {
    try {
        const response = await fetch(url, options);

        if (response.ok) {
            return response;
        }

        // Don't retry 4xx errors (client errors)
        if (response.status >= 400 && response.status < 500) {
            throw new Error(`Client error: ${response.status}`);
        }

        // Retry on 5xx errors (server errors)
        if (retries > 0 && response.status >= 500) {
            const delay = Math.min(
                retryConfig.baseDelay * Math.pow(2, retryConfig.maxRetries - retries),
                retryConfig.maxDelay
            );
            await new Promise(r => setTimeout(r, delay));
            return fetchWithRetry(url, options, retries - 1);
        }

        throw new Error(`HTTP error: ${response.status}`);
    } catch (error) {
        if (retries > 0 && error.name === 'TypeError') {
            // Network error, retry
            const delay = Math.min(
                retryConfig.baseDelay * Math.pow(2, retryConfig.maxRetries - retries),
                retryConfig.maxDelay
            );
            await new Promise(r => setTimeout(r, delay));
            return fetchWithRetry(url, options, retries - 1);
        }
        throw error;
    }
}

/**
 * Offline operation queue
 */
const offlineQueue = [];

/**
 * Queue operation for when online
 */
function queueOfflineOperation(operation) {
    offlineQueue.push({
        ...operation,
        timestamp: Date.now()
    });

    // Save to localStorage
    try {
        localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
    } catch (e) {
        console.error('Failed to save offline queue:', e);
    }

    showToast('Operation queued - will sync when online', 'info');
}

/**
 * Process offline queue when back online
 */
async function processOfflineQueue() {
    if (offlineQueue.length === 0) return;

    showToast(`Syncing ${offlineQueue.length} queued operations...`, 'info');

    const results = {
        success: 0,
        failed: 0
    };

    while (offlineQueue.length > 0) {
        const operation = offlineQueue.shift();

        try {
            await fetch(operation.url, operation.options);
            results.success++;
        } catch (error) {
            console.error('Failed to sync operation:', error);
            results.failed++;
        }
    }

    // Clear localStorage
    localStorage.removeItem('offlineQueue');

    if (results.failed > 0) {
        showToast(`Synced ${results.success}, ${results.failed} failed`, 'warning');
    } else {
        showToast(`Synced ${results.success} operations successfully`, 'success');
    }
}

// Listen for online event
window.addEventListener('online', () => {
    showToast('Back online', 'success');
    processOfflineQueue();
});

window.addEventListener('offline', () => {
    showToast('You are offline - changes will be synced when reconnected', 'warning');
});

// ==============================================================================
// REL-006: Data Staleness Indicators
// ==============================================================================

const STALENESS_THRESHOLDS = {
    fresh: 7,      // Days - data is fresh
    stale: 30,     // Days - data is getting stale
    old: 90        // Days - data is old
};

/**
 * Get staleness indicator for a date
 */
function getStalenessIndicator(dateString) {
    if (!dateString) {
        return {
            level: 'unknown',
            text: 'Never updated',
            icon: '❓',
            color: '#94A3B8'
        };
    }

    const date = new Date(dateString);
    const daysSince = Math.floor((Date.now() - date) / (1000 * 60 * 60 * 24));

    if (daysSince <= STALENESS_THRESHOLDS.fresh) {
        return {
            level: 'fresh',
            text: daysSince === 0 ? 'Updated today' : `Updated ${daysSince} day${daysSince !== 1 ? 's' : ''} ago`,
            icon: '✓',
            color: '#10B981'
        };
    } else if (daysSince <= STALENESS_THRESHOLDS.stale) {
        return {
            level: 'recent',
            text: `Updated ${daysSince} days ago`,
            icon: '○',
            color: '#F59E0B'
        };
    } else if (daysSince <= STALENESS_THRESHOLDS.old) {
        return {
            level: 'stale',
            text: `Last updated ${daysSince} days ago`,
            icon: '!',
            color: '#EF4444'
        };
    } else {
        return {
            level: 'old',
            text: `Over ${Math.floor(daysSince / 30)} months old`,
            icon: '⚠',
            color: '#DC2626'
        };
    }
}

/**
 * Get staleness badge HTML
 */
function getStalenessBadge(dateString) {
    const staleness = getStalenessIndicator(dateString);

    return `
        <span class="staleness-badge ${staleness.level}" title="${staleness.text}" style="color: ${staleness.color}">
            <span class="staleness-icon">${staleness.icon}</span>
            <span class="staleness-text">${staleness.text}</span>
        </span>
    `;
}

/**
 * Add freshness warnings to competitor data
 */
function addFreshnessWarnings(competitor) {
    const warnings = [];
    const lastUpdated = competitor.last_scraped || competitor.updated_at;

    if (lastUpdated) {
        const staleness = getStalenessIndicator(lastUpdated);
        if (staleness.level === 'stale' || staleness.level === 'old') {
            warnings.push({
                field: 'general',
                message: `Data may be outdated - ${staleness.text.toLowerCase()}`,
                level: staleness.level
            });
        }
    } else {
        warnings.push({
            field: 'general',
            message: 'No update timestamp available',
            level: 'unknown'
        });
    }

    return warnings;
}

// Export reliability functions
window.getConfidenceBadge = getConfidenceBadge;
window.validateInput = validateInput;
window.setupFormValidation = setupFormValidation;
window.fetchWithRetry = fetchWithRetry;
window.getStalenessIndicator = getStalenessIndicator;
window.getStalenessBadge = getStalenessBadge;

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
    });
}

/**
 * P2-1: Calculate data freshness and return badge HTML
 * @param {string} lastUpdated - ISO date string of last update
 * @returns {object} - { badge: HTML string, class: CSS class, label: text label, days: number }
 */
function getDataFreshnessBadge(lastUpdated) {
    if (!lastUpdated) {
        return {
            badge: '<span class="freshness-badge freshness-unknown" title="Last updated: Unknown">Unknown</span>',
            class: 'freshness-unknown',
            label: 'Unknown',
            days: null
        };
    }

    const lastDate = new Date(lastUpdated);
    const now = new Date();
    const diffTime = Math.abs(now - lastDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    let freshnessClass, freshnessLabel, freshnessIcon;

    if (diffDays <= 7) {
        freshnessClass = 'freshness-fresh';
        freshnessLabel = 'Fresh';
        freshnessIcon = '🟢';
    } else if (diffDays <= 30) {
        freshnessClass = 'freshness-recent';
        freshnessLabel = 'Recent';
        freshnessIcon = '🟡';
    } else if (diffDays <= 90) {
        freshnessClass = 'freshness-aging';
        freshnessLabel = 'Aging';
        freshnessIcon = '🟠';
    } else {
        freshnessClass = 'freshness-stale';
        freshnessLabel = 'Stale';
        freshnessIcon = '🔴';
    }

    const formattedDate = formatDate(lastUpdated);
    const daysText = diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;

    return {
        badge: `<span class="freshness-badge ${freshnessClass}" title="Last updated: ${formattedDate} (${daysText})">${freshnessIcon} ${freshnessLabel}</span>`,
        class: freshnessClass,
        label: freshnessLabel,
        days: diffDays,
        formattedDate: formattedDate
    };
}

/**
 * Get freshness indicator for inline display (smaller version)
 */
function getFreshnessIndicator(lastUpdated) {
    const freshness = getDataFreshnessBadge(lastUpdated);
    if (freshness.days === null) {
        return '<span class="freshness-dot freshness-unknown" title="Unknown update date"></span>';
    }
    return `<span class="freshness-dot ${freshness.class}" title="Last updated: ${freshness.formattedDate}"></span>`;
}


// ==============================================================================
// UX-004: Enhanced Global Search with Server-Side API
// ==============================================================================

const SEARCH_ICONS = {
    competitor: '🏢',
    product: '📦',
    news: '📰',
    knowledge: '📚'
};

async function handleSearch(event) {
    const query = event.target.value.trim();
    const dropdown = document.getElementById('searchDropdown');

    if (!dropdown) return;

    // Hide dropdown if query is empty or too short
    if (!query || query.length < 2) {
        dropdown.style.display = 'none';
        return;
    }

    // Show loading state
    dropdown.innerHTML = `
        <div style="padding: 16px; text-align: center; color: #94a3b8;">
            <div class="loading-spinner"></div>
            Searching...
        </div>
    `;
    dropdown.style.display = 'block';

    try {
        // Use server-side search API
        const result = await fetchAPI(`/api/search?q=${encodeURIComponent(query)}&limit=12`);

        if (!result || !result.results || result.results.length === 0) {
            // Fallback to client-side competitor search
            const filtered = competitors.filter(c =>
                c.name.toLowerCase().includes(query.toLowerCase()) ||
                (c.product_categories || '').toLowerCase().includes(query.toLowerCase())
            ).slice(0, 8);

            if (filtered.length === 0) {
                dropdown.innerHTML = `<div style="padding: 16px; color: #94a3b8; text-align: center;">No results found for "${escapeHtml(query)}"</div>`;
                return;
            }

            // Render client-side results
            dropdown.innerHTML = filtered.map(c => renderSearchResult({
                type: 'competitor',
                id: c.id,
                title: c.name,
                subtitle: c.product_categories || 'Competitor',
                snippet: c.threat_level ? `${c.threat_level} threat` : null
            })).join('');
            return;
        }

        // Group results by type
        const grouped = {};
        result.results.forEach(r => {
            if (!grouped[r.type]) grouped[r.type] = [];
            grouped[r.type].push(r);
        });

        // Render grouped results
        let html = '';
        for (const [type, items] of Object.entries(grouped)) {
            html += `<div class="search-group-header" style="padding: 8px 14px; background: #0f172a; color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">${SEARCH_ICONS[type] || '📄'} ${type}s (${items.length})</div>`;
            html += items.map(r => renderSearchResult(r)).join('');
        }

        dropdown.innerHTML = html || `<div style="padding: 16px; color: #94a3b8; text-align: center;">No results found</div>`;

    } catch (error) {
        console.error('Search error:', error);
        // Fallback to client-side search on API error
        const filtered = competitors.filter(c =>
            c.name.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 8);

        dropdown.innerHTML = filtered.length > 0
            ? filtered.map(c => renderSearchResult({
                type: 'competitor',
                id: c.id,
                title: c.name,
                subtitle: c.product_categories || 'Competitor'
            })).join('')
            : `<div style="padding: 16px; color: #94a3b8; text-align: center;">Search unavailable</div>`;
    }
}

function renderSearchResult(result) {
    const icon = SEARCH_ICONS[result.type] || '📄';
    const clickHandler = result.type === 'competitor'
        ? `navigateToCompetitor(${result.id})`
        : result.type === 'product'
        ? `navigateToCompetitor(${result.id})`
        : `navigateToSearchResult('${result.type}', ${result.id})`;

    return `
        <div class="search-result-item" onclick="${clickHandler}" style="
            padding: 12px 14px;
            cursor: pointer;
            display: flex;
            gap: 12px;
            align-items: flex-start;
            border-bottom: 1px solid #1e293b;
            transition: background 0.2s;
        " onmouseover="this.style.background='#1e293b'" onmouseout="this.style.background='transparent'">
            <span style="font-size: 1.4em; opacity: 0.8;">${icon}</span>
            <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 600; color: #f1f5f9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${result.title}</div>
                ${result.subtitle ? `<div style="font-size: 0.8em; color: #64748b; margin-top: 2px;">${result.subtitle}</div>` : ''}
                ${result.snippet ? `<div style="font-size: 0.75em; color: #94a3b8; margin-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${result.snippet}</div>` : ''}
            </div>
        </div>
    `;
}

function navigateToSearchResult(type, id) {
    const dropdown = document.getElementById('searchDropdown');
    const searchInput = document.getElementById('globalSearch');
    if (dropdown) dropdown.style.display = 'none';
    if (searchInput) searchInput.value = '';

    // Navigate based on type
    switch(type) {
        case 'knowledge':
            showPage('dataquality');
            break;
        case 'news':
            showPage('newsfeed');
            break;
        default:
            showPage('competitors');
    }
}

// Navigate to competitor detail
function navigateToCompetitor(competitorId) {
    const dropdown = document.getElementById('searchDropdown');
    const searchInput = document.getElementById('globalSearch');
    if (dropdown) dropdown.style.display = 'none';
    if (searchInput) searchInput.value = '';

    // Show competitors page and open detail modal
    showPage('competitors');
    setTimeout(() => showCompetitorDetail(competitorId), 300);
}

// Close search dropdown when clicking outside
document.addEventListener('click', function (e) {
    const dropdown = document.getElementById('searchDropdown');
    const searchInput = document.getElementById('globalSearch');
    if (dropdown && searchInput && !searchInput.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
    }
});

// Close modal on outside click
document.getElementById('modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'modal') closeModal();
});

// ==============================================================================
// UX-001: Enhanced Keyboard Shortcuts
// Ctrl+K: Command palette, Ctrl+/: Help, Esc: Close modals
// Vim-style: j/k for navigation in lists
// ==============================================================================

let commandPaletteOpen = false;
let keyboardHelpOpen = false;

const KEYBOARD_SHORTCUTS = [
    { key: 'Ctrl+K', action: 'Open command palette', fn: () => toggleCommandPalette() },
    { key: 'Ctrl+/', action: 'Show keyboard shortcuts', fn: () => toggleKeyboardHelp() },
    { key: 'Ctrl+F', action: 'Focus search', fn: () => focusGlobalSearch() },
    { key: 'Escape', action: 'Close modal/palette', fn: () => closeAllOverlays() },
    { key: 'g h', action: 'Go to Dashboard', fn: () => showPage('dashboard') },
    { key: 'g c', action: 'Go to Competitors', fn: () => showPage('competitors') },
    { key: 'g s', action: 'Go to Sales & Marketing', fn: () => showPage('sales-marketing') },
    { key: 'g n', action: 'Go to News Feed', fn: () => showPage('news') },
    { key: 'g a', action: 'Go to Analytics', fn: () => showPage('analytics') },
    { key: 'g r', action: 'Go to Reports', fn: () => showPage('reports') },
    { key: 'g l', action: 'Go to Change Log', fn: () => showPage('changes') },
    { key: 'g t', action: 'Go to Settings', fn: () => showPage('settings') },
    { key: 'r', action: 'Refresh current page', fn: () => refreshCurrentPage() },
    { key: 'n', action: 'New competitor', fn: () => openAddCompetitorModal() }
];

let goPending = false; // For "g" key combo

document.addEventListener('keydown', (e) => {
    // Don't trigger shortcuts when typing in inputs
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
        if (e.key === 'Escape') {
            e.target.blur();
            closeAllOverlays();
        }
        return;
    }

    const key = e.key.toLowerCase();
    const ctrl = e.ctrlKey || e.metaKey;

    // Ctrl+K: Command palette
    if (ctrl && key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
        return;
    }

    // Ctrl+/: Help
    if (ctrl && key === '/') {
        e.preventDefault();
        toggleKeyboardHelp();
        return;
    }

    // Ctrl+F: Global search
    if (ctrl && key === 'f') {
        // Only prevent if we have global search
        const searchInput = document.getElementById('globalSearchInput') || document.querySelector('.search-input');
        if (searchInput) {
            e.preventDefault();
            focusGlobalSearch();
        }
        return;
    }

    // Escape: Close everything
    if (key === 'escape') {
        closeAllOverlays();
        return;
    }

    // G key combinations (vim-style navigation)
    if (key === 'g' && !goPending) {
        goPending = true;
        setTimeout(() => { goPending = false; }, 1000);
        return;
    }

    if (goPending) {
        goPending = false;
        switch(key) {
            case 'h': showPage('dashboard'); break;
            case 'c': showPage('competitors'); break;
            case 's': showPage('sales-marketing'); break;
            case 'n': showPage('news'); break;
            case 'a': showPage('analytics'); break;
            case 'r': showPage('reports'); break;
            case 'l': showPage('changes'); break;
            case 't': showPage('settings'); break;
        }
        return;
    }

    // Single key shortcuts (only when not in "g" mode)
    if (key === 'r' && !ctrl) {
        refreshCurrentPage();
    } else if (key === 'n' && !ctrl) {
        openAddCompetitorModal();
    } else if (key === 'j') {
        // Vim-style: move down in list
        navigateList(1);
    } else if (key === 'k') {
        // Vim-style: move up in list
        navigateList(-1);
    }
});

function closeAllOverlays() {
    closeModal();
    closeCommandPalette();
    closeKeyboardHelp();
    commandPaletteOpen = false;
    keyboardHelpOpen = false;
}

function toggleCommandPalette() {
    if (commandPaletteOpen) {
        closeCommandPalette();
    } else {
        openCommandPalette();
    }
}

function openCommandPalette() {
    // Create command palette if it doesn't exist
    let palette = document.getElementById('commandPalette');
    if (!palette) {
        palette = document.createElement('div');
        palette.id = 'commandPalette';
        palette.className = 'command-palette';
        palette.innerHTML = `
            <div class="command-palette-backdrop" onclick="closeCommandPalette()"></div>
            <div class="command-palette-content">
                <input type="text" id="commandPaletteInput" placeholder="Type a command..." autocomplete="off">
                <div id="commandPaletteResults" class="command-palette-results"></div>
            </div>
        `;
        document.body.appendChild(palette);

        // Setup command input handler
        const input = document.getElementById('commandPaletteInput');
        input.addEventListener('input', filterCommands);
        input.addEventListener('keydown', handleCommandKeydown);
    }

    palette.classList.add('open');
    commandPaletteOpen = true;
    document.getElementById('commandPaletteInput').value = '';
    document.getElementById('commandPaletteInput').focus();
    filterCommands();
}

function closeCommandPalette() {
    const palette = document.getElementById('commandPalette');
    if (palette) {
        palette.classList.remove('open');
    }
    commandPaletteOpen = false;
}

const COMMANDS = [
    { name: 'Go to Dashboard', shortcut: 'g h', action: () => showPage('dashboard') },
    { name: 'Go to Competitors', shortcut: 'g c', action: () => showPage('competitors') },
    { name: 'Go to Sales & Marketing', shortcut: 'g s', action: () => showPage('sales-marketing') },
    { name: 'Go to News Feed', shortcut: 'g n', action: () => showPage('news') },
    { name: 'Go to Analytics', shortcut: 'g a', action: () => showPage('analytics') },
    { name: 'Go to Reports', shortcut: 'g r', action: () => showPage('reports') },
    { name: 'Go to Change Log', shortcut: 'g l', action: () => showPage('changes') },
    { name: 'Go to Settings', shortcut: 'g t', action: () => showPage('settings') },
    { name: 'Add New Competitor', shortcut: 'n', action: () => openAddCompetitorModal() },
    { name: 'Refresh Data', shortcut: 'r', action: () => refreshCurrentPage() },
    { name: 'Run Discovery Agent', shortcut: '', action: () => { showPage('dashboard'); setTimeout(() => showDiscoveryModal(), 100); } },
    { name: 'Generate Report', shortcut: '', action: () => showPage('reports') },
    { name: 'Export Data', shortcut: '', action: () => exportCompetitors('xlsx') },
    { name: 'Show Keyboard Shortcuts', shortcut: 'Ctrl+/', action: () => toggleKeyboardHelp() },
    { name: 'Logout', shortcut: '', action: () => logout() }
];

let selectedCommandIndex = 0;

function filterCommands() {
    const input = document.getElementById('commandPaletteInput');
    const results = document.getElementById('commandPaletteResults');
    const query = input.value.toLowerCase();

    const filtered = COMMANDS.filter(cmd =>
        cmd.name.toLowerCase().includes(query) ||
        (cmd.shortcut && cmd.shortcut.toLowerCase().includes(query))
    );

    selectedCommandIndex = 0;
    results.innerHTML = filtered.map((cmd, idx) => `
        <div class="command-item ${idx === 0 ? 'selected' : ''}" data-index="${idx}" onclick="executeCommand(${idx})">
            <span class="command-name">${cmd.name}</span>
            ${cmd.shortcut ? `<span class="command-shortcut">${cmd.shortcut}</span>` : ''}
        </div>
    `).join('') || '<div class="command-empty">No commands found</div>';

    // Store filtered commands for execution
    results.filteredCommands = filtered;
}

function handleCommandKeydown(e) {
    const results = document.getElementById('commandPaletteResults');
    const items = results.querySelectorAll('.command-item');

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedCommandIndex = Math.min(selectedCommandIndex + 1, items.length - 1);
        updateCommandSelection(items);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedCommandIndex = Math.max(selectedCommandIndex - 1, 0);
        updateCommandSelection(items);
    } else if (e.key === 'Enter') {
        e.preventDefault();
        executeCommand(selectedCommandIndex);
    }
}

function updateCommandSelection(items) {
    items.forEach((item, idx) => {
        item.classList.toggle('selected', idx === selectedCommandIndex);
    });
}

function executeCommand(index) {
    const results = document.getElementById('commandPaletteResults');
    const filtered = results.filteredCommands || COMMANDS;
    if (filtered[index]) {
        closeCommandPalette();
        filtered[index].action();
    }
}

function toggleKeyboardHelp() {
    if (keyboardHelpOpen) {
        closeKeyboardHelp();
    } else {
        openKeyboardHelp();
    }
}

function openKeyboardHelp() {
    let help = document.getElementById('keyboardHelp');
    if (!help) {
        help = document.createElement('div');
        help.id = 'keyboardHelp';
        help.className = 'keyboard-help';
        help.innerHTML = `
            <div class="keyboard-help-backdrop" onclick="closeKeyboardHelp()"></div>
            <div class="keyboard-help-content">
                <div class="keyboard-help-header">
                    <h2>Keyboard Shortcuts</h2>
                    <button onclick="closeKeyboardHelp()" class="close-btn">&times;</button>
                </div>
                <div class="keyboard-help-body">
                    <div class="shortcut-group">
                        <h3>General</h3>
                        <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>K</kbd> <span>Command palette</span></div>
                        <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>/</kbd> <span>Show this help</span></div>
                        <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>F</kbd> <span>Focus search</span></div>
                        <div class="shortcut-item"><kbd>Esc</kbd> <span>Close modal/palette</span></div>
                        <div class="shortcut-item"><kbd>R</kbd> <span>Refresh page</span></div>
                        <div class="shortcut-item"><kbd>N</kbd> <span>New competitor</span></div>
                    </div>
                    <div class="shortcut-group">
                        <h3>Navigation (Press G then...)</h3>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>H</kbd> <span>Dashboard (Home)</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>C</kbd> <span>Competitors</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>S</kbd> <span>Sales & Marketing</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>N</kbd> <span>News Feed</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>A</kbd> <span>Analytics</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>R</kbd> <span>Reports</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>L</kbd> <span>Change Log</span></div>
                        <div class="shortcut-item"><kbd>G</kbd> <kbd>T</kbd> <span>Settings</span></div>
                    </div>
                    <div class="shortcut-group">
                        <h3>List Navigation</h3>
                        <div class="shortcut-item"><kbd>J</kbd> <span>Move down</span></div>
                        <div class="shortcut-item"><kbd>K</kbd> <span>Move up</span></div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(help);
    }

    help.classList.add('open');
    keyboardHelpOpen = true;
}

function closeKeyboardHelp() {
    const help = document.getElementById('keyboardHelp');
    if (help) {
        help.classList.remove('open');
    }
    keyboardHelpOpen = false;
}

function focusGlobalSearch() {
    const searchInput = document.getElementById('globalSearchInput') ||
                       document.querySelector('.search-input') ||
                       document.querySelector('input[type="search"]');
    if (searchInput) {
        searchInput.focus();
        searchInput.select();
    }
}

function refreshCurrentPage() {
    const activePage = document.querySelector('.page.active');
    if (activePage) {
        const pageId = activePage.id.replace('-page', '');
        showPage(pageId);
        showToast('Page refreshed', 'success');
    }
}

function openAddCompetitorModal() {
    // Legacy function - redirect to the working implementation
    showAddCompetitorModal();
}

function navigateList(direction) {
    // Find active list on current page
    const lists = document.querySelectorAll('.competitor-card, .news-item, .change-item, tr[data-id]');
    if (lists.length === 0) return;

    const selected = document.querySelector('.competitor-card.selected, .news-item.selected, .change-item.selected, tr.selected');
    let currentIndex = selected ? Array.from(lists).indexOf(selected) : -1;
    let newIndex = currentIndex + direction;

    // Clamp to valid range
    newIndex = Math.max(0, Math.min(newIndex, lists.length - 1));

    // Update selection
    lists.forEach(item => item.classList.remove('selected'));
    lists[newIndex]?.classList.add('selected');
    lists[newIndex]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ============== Discovery Functions ==============

let discoveredCompetitors = [];

// Global discovery state — survives page navigation (same pattern as _newsFetchPolling)
let _discoveryTaskId = null;
let _discoveryPolling = false;
let _discoveryResult = null;       // Full result object (candidates + metadata)
let _discoverySummary = null;      // AI summary text
let _discoveryError = null;        // Error message if failed

async function loadDiscovered() {
    // Load previously discovered competitors from session or API
    const resultsDiv = document.getElementById('discoveryResults');
    const resultsList = document.getElementById('discoveryResultsList');
    const emptyState = document.getElementById('discoveryEmptyState');

    if (!resultsDiv) return;

    // Initialize defaults and load profiles when discovery page is shown
    if (typeof initializeDiscoveryDefaults === 'function') {
        initializeDiscoveryDefaults();
    }
    if (typeof loadDiscoveryProfiles === 'function') {
        loadDiscoveryProfiles();
    }

    // Resume any in-progress or cached discovery state
    const resumeState = resumeDiscoveryIfRunning();
    if (resumeState === 'polling' || resumeState === 'results') {
        // State is already displayed from globals — collapse criteria & hide empty state
        collapseCriteriaPanel();
        if (emptyState) emptyState.style.display = 'none';
        return;
    }

    // Try to load from API (silent mode to avoid error toasts for empty results)
    let result = null;
    try {
        result = await fetchAPI('/api/discovery/results', { silent: true });
    } catch (e) {
    }

    if (result && result.candidates && result.candidates.length > 0) {
        discoveredCompetitors = result.candidates;
        window.discoveredCandidates = result.candidates;
        window.discoveryMetadata = {
            stages_run: result.stages_run,
            processing_time_ms: result.processing_time_ms,
            last_run: result.last_run
        };

        // Use the unified renderDiscoveryResults for cached results too (Issue #1)
        const resultsHeader = document.getElementById('discoveryResultsHeader');
        const resultCount = document.getElementById('discoveryResultCount');
        const actionsDiv = document.getElementById('discoveryActions');

        if (resultsHeader && resultCount) {
            resultsHeader.style.display = 'block';
            resultCount.textContent = result.candidates.length + ' competitors found';
        }
        renderDiscoveryResults(result.candidates);
        resultsDiv.style.display = 'block';
        if (actionsDiv) actionsDiv.style.display = 'flex';
        if (emptyState) emptyState.style.display = 'none';

        // Collapse criteria panel when results exist (Issue #4)
        collapseCriteriaPanel();
    } else {
        // Show empty state, expand criteria
        resultsDiv.style.display = 'none';
        if (emptyState) {
            emptyState.style.display = 'block';
            // Enhanced empty state guidance (Issue #11)
            const desc = document.getElementById('discoveryEmptyDescription');
            if (desc) {
                const criteria = _summarizeCriteria();
                desc.innerHTML = criteria
                    ? `Current criteria: <strong>${escapeHtml(criteria)}</strong>. Click <strong>Start AI Discovery</strong> to find competitors matching these criteria, or customize the criteria above.`
                    : 'Configure your criteria above and click <strong>Start AI Discovery</strong> to find competitors matching your search parameters.';
            }
        }
        expandCriteriaPanel();
    }
}

const DEFAULT_DISCOVERY_CRITERIA = `• Target Market: Patient engagement, patient intake, healthcare check-in solutions
• Company Size: 50-5000 employees (growth-stage or established)
• Geography: US-based or significant US presence
• Product Focus: Digital check-in, eligibility verification, patient payments, scheduling
• Technology: Cloud-based SaaS, mobile-first, EHR integrations
• Funding: Series A+ or profitable private company
• Customer Base: Medical practices, health systems, ambulatory care
• Competitive Signals: Similar keywords, overlapping customer segments
• Exclude: Pure EHR vendors, hospital-only solutions, international-only`;

function resetCriteria() {
    const textarea = document.getElementById('discoveryCriteria');
    if (textarea) {
        textarea.value = DEFAULT_DISCOVERY_CRITERIA;
        showToast('Criteria reset to defaults', 'success');
    }
}

// NOTE: runDiscovery() is defined later in the file (line ~10993) with better error handling
// This duplicate was removed to prevent conflicts

// renderDiscoveredGrid() removed in v8.1.0 — unified into renderDiscoveryResults() (Issue #1)

function getScoreColor(score) {
    if (score >= 70) return '#22c55e';  // Green for high match
    if (score >= 50) return '#f59e0b';  // Orange for medium match
    return '#ef4444';  // Red for low match
}

/**
 * Get normalized match score from a candidate object.
 * Handles multiple field names from different pipeline stages.
 */
function getMatchScore(candidate) {
    const score = candidate.match_score ?? candidate.qualification_score ?? candidate.relevance_score ?? candidate.score ?? null;
    return score;
}

// ============== Criteria Panel Collapse/Expand (Issue #4) ==============

function _summarizeCriteria() {
    const segments = Array.from(document.querySelectorAll('input[name="segment"]:checked')).map(cb => cb.parentElement.textContent.trim());
    const capabilities = Array.from(document.querySelectorAll('input[name="capability"]:checked')).map(cb => cb.parentElement.textContent.trim());
    const geo = Array.from(document.querySelectorAll('input[name="geography"]:checked')).map(cb => cb.parentElement.textContent.trim());
    const parts = [...segments.slice(0, 2), ...capabilities.slice(0, 2), ...geo.slice(0, 1)];
    return parts.join(', ');
}

function collapseCriteriaPanel() {
    const expanded = document.getElementById('criteriaExpandedContent');
    const summary = document.getElementById('criteriaSummaryBar');
    const summaryText = document.getElementById('criteriaSummaryText');
    if (!expanded || !summary) return;

    expanded.style.display = 'none';
    summary.style.display = 'block';

    // Build summary text from current criteria
    const criteria = _summarizeCriteria();
    const maxResults = document.getElementById('discoveryMaxCandidates')?.value || '10';
    if (summaryText) {
        summaryText.textContent = criteria ? `${criteria} - ${maxResults} results` : `${maxResults} results`;
    }
}

function expandCriteriaPanel() {
    const expanded = document.getElementById('criteriaExpandedContent');
    const summary = document.getElementById('criteriaSummaryBar');
    if (!expanded || !summary) return;

    expanded.style.display = 'block';
    summary.style.display = 'none';
}

function toggleCriteriaPanel(forceExpand) {
    const expanded = document.getElementById('criteriaExpandedContent');
    if (!expanded) return;
    if (forceExpand || expanded.style.display === 'none') {
        expandCriteriaPanel();
    } else {
        collapseCriteriaPanel();
    }
}

window.toggleCriteriaPanel = toggleCriteriaPanel;
window.collapseCriteriaPanel = collapseCriteriaPanel;
window.expandCriteriaPanel = expandCriteriaPanel;

// Trigger discovery from competitors page

// ============== Insight Streams (Redesigned v6.3.1) ==============

async function showCompetitorInsights(id) {
    const comp = competitors.find(c => c.id === id);
    if (!comp) return;

    // Build content using AVAILABLE data sources only
    const content = `
        <div class="insights-header" style="background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); padding: 24px; border-radius: 12px; margin-bottom: 24px; text-align: center;">
            <h2 style="color: white; margin-bottom: 8px;">${escapeHtml(comp.name)} Intelligence</h2>
            <div style="color: rgba(255,255,255,0.7);">Competitive insights from verified data sources</div>
        </div>

        <div class="insights-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px;">

            <!-- Company Overview (from database) -->
            <div class="analytics-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #1e293b;">📊 Company Overview</h3>
                    <span class="badge" style="background: rgba(34, 197, 94, 0.1); color: #16a34a;">Database</span>
                </div>
                <div style="display: grid; gap: 12px;">
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">Founded</span>
                        <strong style="color: #1e293b;">${comp.year_founded || 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">Headquarters</span>
                        <strong style="color: #1e293b;">${comp.headquarters || 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">Employees</span>
                        <strong style="color: #1e293b;">${comp.employee_count || 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">Funding</span>
                        <strong style="color: #1e293b;">${comp.funding_total || 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                        <span style="color: #64748b;">Threat Level</span>
                        <strong style="color: ${comp.threat_level === 'High' ? '#dc2626' : comp.threat_level === 'Medium' ? '#f59e0b' : '#22c55e'};">${comp.threat_level}</strong>
                    </div>
                </div>
            </div>

            <!-- Ratings & Reviews (from database) -->
            <div class="analytics-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #1e293b;">⭐ Ratings & Reviews</h3>
                    <span class="badge" style="background: rgba(34, 197, 94, 0.1); color: #16a34a;">Database</span>
                </div>
                <div style="display: grid; gap: 12px;">
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">G2 Rating</span>
                        <strong style="color: #1e293b;">${comp.g2_rating ? comp.g2_rating + '/5' : 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">Glassdoor Rating</span>
                        <strong style="color: #1e293b;">${comp.glassdoor_rating ? comp.glassdoor_rating + '/5' : 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                        <span style="color: #64748b;">KLAS Rating</span>
                        <strong style="color: #1e293b;">${comp.klas_rating ? comp.klas_rating + '/100' : 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                        <span style="color: #64748b;">Overall Score</span>
                        <strong style="color: #1e293b;">${comp.dim_overall_score ? comp.dim_overall_score.toFixed(1) + '/5' : 'N/A'}</strong>
                    </div>
                </div>
            </div>

            <!-- Products (from products table) -->
            <div class="analytics-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #1e293b;">📦 Products</h3>
                    <span class="badge" style="background: rgba(59, 130, 246, 0.1); color: #2563eb;">Products DB</span>
                </div>
                <div id="insightsProducts-${id}" style="max-height: 200px; overflow-y: auto;">
                    <div style="color: #64748b; text-align: center; padding: 20px;">Loading products...</div>
                </div>
            </div>

            <!-- Recent News (from news cache) -->
            <div class="analytics-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #1e293b;">📰 Recent News</h3>
                    <span class="badge" style="background: rgba(249, 115, 22, 0.1); color: #ea580c;">Google News</span>
                </div>
                <div id="insightsNews-${id}" style="max-height: 200px; overflow-y: auto;">
                    <div style="color: #64748b; text-align: center; padding: 20px;">Loading news...</div>
                </div>
            </div>

            <!-- SEC Filings (if public company) -->
            ${comp.is_public ? `
            <div class="analytics-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #1e293b;">📑 SEC Filings</h3>
                    <span class="badge" style="background: rgba(139, 92, 246, 0.1); color: #7c3aed;">SEC EDGAR</span>
                </div>
                <div id="insightsSEC-${id}" style="max-height: 200px; overflow-y: auto;">
                    <div style="color: #64748b; text-align: center; padding: 20px;">Loading SEC filings...</div>
                </div>
            </div>
            ` : ''}

            <!-- Patents (USPTO) -->
            <div class="analytics-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #1e293b;">💡 Patents</h3>
                    <span class="badge" style="background: rgba(59, 130, 246, 0.1); color: #2563eb;">USPTO</span>
                </div>
                <div id="insightsPatents-${id}" style="text-align: center; padding: 20px;">
                    <div style="font-size: 36px; font-weight: 700; color: #1e293b;">${comp.patent_count || 0}</div>
                    <div style="color: #64748b;">Patents Filed</div>
                </div>
            </div>

        </div>
    `;

    showModal(content);

    // Load data from AVAILABLE sources only
    loadInsightsProducts(id);
    loadInsightsNews(id);
    if (comp.is_public) loadInsightsSEC(id);
}

// --- New Data Loaders (using available sources) ---

async function loadInsightsProducts(id) {
    const container = document.getElementById(`insightsProducts-${id}`);
    if (!container) return;

    try {
        const products = await fetchAPI(`/api/products/competitor/${id}`);
        if (products && products.length > 0) {
            container.innerHTML = products.slice(0, 6).map(p => `
                <div style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                    <div style="font-weight: 600; color: #1e293b;">${p.name}</div>
                    <div style="font-size: 12px; color: #64748b;">${p.category || 'Uncategorized'}</div>
                </div>
            `).join('') + (products.length > 6 ? `<div style="padding: 8px; color: #64748b; text-align: center;">+${products.length - 6} more products</div>` : '');
        } else {
            container.innerHTML = '<div style="color: #64748b; text-align: center;">No products found</div>';
        }
    } catch (e) {
        container.innerHTML = '<div style="color: #dc2626; text-align: center;">Failed to load products</div>';
    }
}

async function loadInsightsNews(id) {
    const container = document.getElementById(`insightsNews-${id}`);
    if (!container) return;

    try {
        const news = await fetchAPI(`/api/competitors/${id}/news?limit=5`);
        if (news && news.length > 0) {
            container.innerHTML = news.map(n => `
                <div style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                    <a href="${n.url}" target="_blank" style="font-weight: 500; color: #2563eb; text-decoration: none; display: block; margin-bottom: 4px;">${n.title?.substring(0, 60)}...</a>
                    <div style="font-size: 11px; color: #64748b;">${n.source} • ${n.published_date ? new Date(n.published_date).toLocaleDateString() : 'Recent'}</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div style="color: #64748b; text-align: center;">No recent news</div>';
        }
    } catch (e) {
        container.innerHTML = '<div style="color: #dc2626; text-align: center;">Failed to load news</div>';
    }
}

async function loadInsightsSEC(id) {
    const container = document.getElementById(`insightsSEC-${id}`);
    if (!container) return;

    try {
        const filings = await fetchAPI(`/api/competitors/${id}/sec-filings?limit=5`);
        if (filings && filings.length > 0) {
            container.innerHTML = filings.map(f => `
                <div style="padding: 8px 0; border-bottom: 1px solid #e2e8f0;">
                    <a href="${f.url}" target="_blank" style="font-weight: 500; color: #7c3aed; text-decoration: none;">${f.form_type}: ${f.description?.substring(0, 40)}...</a>
                    <div style="font-size: 11px; color: #64748b;">${new Date(f.filing_date).toLocaleDateString()}</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div style="color: #64748b; text-align: center;">No SEC filings found</div>';
        }
    } catch (e) {
        container.innerHTML = '<div style="color: #64748b; text-align: center;">SEC data unavailable</div>';
    }
}

// --- Data Loaders ---

async function loadFundingData(id) {
    try {
        const data = await fetchAPI(`/api/competitors/${id}/funding`);
        if (data && data.rounds) {
            Visualizations.renderFundingTimeline(`fundingChart-${id}`, data.rounds);
            document.getElementById(`fundingStats-${id}`).innerHTML = `
                <strong>Total Funding:</strong> $${(data.total_funding_usd / 1000000).toFixed(1)}M<br>
                <strong>Latest Round:</strong> ${data.latest_round_type} (${data.latest_round_date})
            `;
        } else {
            document.getElementById(`fundingStats-${id}`).textContent = "No funding data available.";
        }
    } catch (e) { console.warn("Funding load failed", e); }
}

async function loadEmployeeData(id) {
    try {
        const data = await fetchAPI(`/api/competitors/${id}/employee-reviews`);
        if (data) {
            Visualizations.renderSentimentGauge(`sentimentChart-${id}`, data.overall_rating || 0);
            document.getElementById(`sentimentStats-${id}`).innerHTML = `
                Based on <strong>${data.total_reviews}</strong> reviews<br>
                CEO Approval: <strong>${data.ceo_approval}%</strong>
            `;
        }
    } catch (e) { console.warn("Review load failed", e); }
}

async function loadHiringData(id) {
    try {
        const data = await fetchAPI(`/api/competitors/${id}/jobs`);
        if (data && data.history) {
            Visualizations.renderHiringTrend(`hiringChart-${id}`, data.history);
        }
    } catch (e) { console.warn("Hiring load failed", e); }
}

async function loadPatentData(id) {
    try {
        const data = await fetchAPI(`/api/competitors/${id}/patents`);
        if (data && data.categories) {
            Visualizations.renderInnovationRadar(`patentChart-${id}`, data.categories);
        }
    } catch (e) { console.warn("Patent load failed", e); }
}

async function loadMobileData(id) {
    try {
        const data = await fetchAPI(`/api/competitors/${id}/mobile-apps`);
        const container = document.getElementById(`appStoreStats-${id}`);
        if (data && data.apps && data.apps.length > 0) {
            container.innerHTML = data.apps.map(app => `
                <div style="background: #f8fafc; padding: 12px; border-radius: 6px; border: 1px solid #e2e8f0;">
                    <div style="font-weight: 600; color: var(--navy-dark);">${app.platform}</div>
                    <div style="font-size: 1.5em; font-weight: 700;">${app.rating} ⭐</div>
                    <div style="font-size: 0.9em; color: var(--text-secondary);">${app.review_count} reviews</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = "No mobile apps found.";
        }
    } catch (e) { console.warn("Mobile load failed", e); }
}

// ============== Market Map ==============

let marketMapChart = null;
let marketQuadrantChart = null;

function loadMarketMap() {
    renderMarketMapChart();
    renderCategoryBreakdown();
    renderMarketMapTable();
}

function updateMarketMap() {
    renderMarketMapChart();
}

function renderMarketMapChart() {
    const canvas = document.getElementById('marketMapChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (marketMapChart) {
        marketMapChart.destroy();
    }

    // Prepare data for bubble chart
    const threatMap = { 'High': 3, 'Medium': 2, 'Low': 1 };
    const colorMap = { 'High': '#dc3545', 'Medium': '#f59e0b', 'Low': '#22c55e' };

    const bubbleData = competitors.map(comp => {
        // Parse employee count for size
        let empCount = 100;
        if (comp.employee_count) {
            const num = parseInt(comp.employee_count.replace(/[^0-9]/g, ''));
            empCount = isNaN(num) ? 100 : Math.min(num, 5000);
        }

        // Parse customer count for X axis
        let custCount = 500;
        if (comp.customer_count) {
            const num = parseInt(comp.customer_count.replace(/[^0-9]/g, ''));
            custCount = isNaN(num) ? 500 : num;
        }

        return {
            x: custCount,
            y: threatMap[comp.threat_level] || 2,
            r: Math.max(8, Math.min(40, Math.sqrt(empCount) * 1.5)),
            name: comp.name,
            threat: comp.threat_level,
            isPublic: comp.is_public,
            color: colorMap[comp.threat_level] || '#64748b',
            ticker: comp.ticker_symbol || ''
        };
    });

    // Group by threat level
    const highThreat = bubbleData.filter(d => d.threat === 'High');
    const mediumThreat = bubbleData.filter(d => d.threat === 'Medium');
    const lowThreat = bubbleData.filter(d => d.threat === 'Low');

    marketMapChart = new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [
                {
                    label: 'High Threat',
                    data: highThreat,
                    backgroundColor: 'rgba(220, 53, 69, 0.7)',
                    borderColor: '#dc3545',
                    borderWidth: 2
                },
                {
                    label: 'Medium Threat',
                    data: mediumThreat,
                    backgroundColor: 'rgba(245, 158, 11, 0.7)',
                    borderColor: '#f59e0b',
                    borderWidth: 2
                },
                {
                    label: 'Low Threat',
                    data: lowThreat,
                    backgroundColor: 'rgba(34, 197, 94, 0.7)',
                    borderColor: '#22c55e',
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#e2e8f0', padding: 15, font: { size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const d = ctx.raw;
                            const pub = d.isPublic ? ` (${d.ticker})` : ' (Private)';
                            return `${d.name}${pub}: ${d.x.toLocaleString()} customers`;
                        },
                        afterLabel: ctx => {
                            const d = ctx.raw;
                            const fullComp = competitors.find(c => c.name === d.name);
                            return fullComp?.website ? `Source: ${fullComp.website}` : '';
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Customer Count', font: { weight: 'bold' }, color: '#e2e8f0' },
                    type: 'logarithmic',
                    min: 50,
                    max: 50000,
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(148,163,184,0.15)' }
                },
                y: {
                    title: { display: true, text: 'Threat Level', font: { weight: 'bold' }, color: '#e2e8f0' },
                    min: 0.5,
                    max: 3.5,
                    ticks: {
                        stepSize: 1,
                        callback: val => ['', 'Low', 'Medium', 'High'][val] || '',
                        color: '#94a3b8'
                    },
                    grid: { color: 'rgba(148,163,184,0.15)' }
                }
            },
            onClick: (evt, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    const datasetIdx = elements[0].datasetIndex;
                    const comp = marketMapChart.data.datasets[datasetIdx].data[idx];
                    const fullComp = competitors.find(c => c.name === comp.name);
                    if (fullComp) viewBattlecard(fullComp.id);
                }
            }
        }
    });
}

function renderCategoryBreakdown() {
    const container = document.getElementById('categoryList');
    if (!container) return;

    // Group competitors by product category
    const categories = {};
    competitors.forEach(comp => {
        const cats = (comp.product_categories || 'Unknown').split(';').map(c => c.trim());
        cats.forEach(cat => {
            if (!categories[cat]) categories[cat] = [];
            categories[cat].push(comp);
        });
    });

    // Sort by count
    const sorted = Object.entries(categories).sort((a, b) => b[1].length - a[1].length);

    container.innerHTML = sorted.map(([cat, comps]) => {
        const color = comps.length > 20 ? '#dc3545' : comps.length > 10 ? '#f59e0b' : '#22c55e';
        return `
            <div style="margin-bottom: 12px; padding: 10px; background: #f8fafc; border-radius: 6px; border-left: 4px solid ${color};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="color: #122753;">${cat}</strong>
                    <span style="background: ${color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">${comps.length}</span>
                </div>
                <div style="font-size: 0.85em; color: #64748b;">
                    ${comps.slice(0, 5).map(c => c.name).join(', ')}${comps.length > 5 ? ` +${comps.length - 5} more` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function renderMarketMapTable() {
    const tbody = document.getElementById('marketMapTable');
    if (!tbody) return;

    // Sort by threat level then name
    const sorted = [...competitors].sort((a, b) => {
        const order = { 'High': 1, 'Medium': 2, 'Low': 3 };
        if (order[a.threat_level] !== order[b.threat_level]) {
            return order[a.threat_level] - order[b.threat_level];
        }
        return a.name.localeCompare(b.name);
    });

    tbody.innerHTML = sorted.map(comp => {
        const threatColors = { 'High': '#dc3545', 'Medium': '#f59e0b', 'Low': '#22c55e' };
        const statusBadge = comp.is_public ?
            `<span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.8em;">PUBLIC ${comp.ticker_symbol || ''}</span>` :
            `<span style="background: #64748b; color: white; padding: 2px 8px; border-radius: 3px; font-size: 0.8em;">PRIVATE</span>`;

        // Helper to wrap data values with source links
        const src = comp.website || '';
        const link = (val) => {
            if (!val || val === 'N/A') return 'N/A';
            return src ? `<a href="${src}" target="_blank" rel="noopener" title="Source: ${src}" style="color:inherit;text-decoration:underline dotted;">${val}</a>` : val;
        };

        return `
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 12px;">
                    <div style="font-weight: 600; color: #122753;">${comp.website ? `<a href="${escapeHtml(comp.website)}" target="_blank" rel="noopener" style="color:#122753;text-decoration:none;">${escapeHtml(comp.name)}</a>` : escapeHtml(comp.name)}</div>
                    <div style="font-size: 0.8em; color: #64748b;">${comp.website || ''}</div>
                </td>
                <td style="padding: 12px; text-align: center;">${statusBadge}</td>
                <td style="padding: 12px; text-align: center;">
                    <span style="background: ${threatColors[comp.threat_level] || '#64748b'}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600;">${comp.threat_level}</span>
                </td>
                <td style="padding: 12px; text-align: center;">${link(comp.employee_count)}</td>
                <td style="padding: 12px; text-align: center;">${link(comp.customer_count)}</td>
                <td style="padding: 12px; text-align: center;">${comp.g2_rating ? link(`${comp.g2_rating} ⭐`) : 'N/A'}</td>
                <td style="padding: 12px; text-align: center;">${link(comp.base_price)}</td>
                <td style="padding: 12px; text-align: center;">
                    <button onclick="viewBattlecard(${comp.id})" style="background: #3A95ED; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em;">
                        View
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function exportMarketMap() {
    // Export as CSV
    const headers = ['Company', 'Status', 'Ticker', 'Threat Level', 'Employees', 'Customers', 'G2 Rating', 'Pricing', 'Website'];
    const rows = competitors.map(c => [
        c.name,
        c.is_public ? 'Public' : 'Private',
        c.ticker_symbol || '',
        c.threat_level,
        c.employee_count || '',
        c.customer_count || '',
        c.g2_rating || '',
        c.base_price || '',
        c.website || ''
    ]);

    const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = 'market_map_export.csv';
    a.click();
    URL.revokeObjectURL(url);

    showToast('Market Map exported to CSV', 'success');
}

/**
 * Render Market Position Quadrant bubble chart on Analytics page.
 * Fetches from GET /api/analytics/market-quadrant.
 * x=market_strength, y=growth_momentum, r=company_size, color=threat_level
 */
async function renderMarketQuadrantChart() {
    const container = document.getElementById('marketQuadrantChartContainer');
    const canvas = document.getElementById('marketQuadrantChart');
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (marketQuadrantChart) marketQuadrantChart.destroy();

    // Loading state
    const loader = document.createElement('div');
    loader.id = 'marketQuadrantLoader';
    loader.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:var(--bg-secondary);border-radius:8px;z-index:2;';
    loader.innerHTML = '<div class="spinner" style="margin:0 auto;"></div>';
    container.appendChild(loader);

    try {
        const data = await fetchAPI('/api/analytics/market-quadrant', { silent: true });

        const loaderEl = document.getElementById('marketQuadrantLoader');
        if (loaderEl) loaderEl.remove();

        if (!data || !data.competitors || data.competitors.length === 0) {
            container.innerHTML = '<canvas id="marketQuadrantChart"></canvas><div style="text-align:center;padding:40px;color:var(--text-secondary);">No market position data available yet.</div>';
            return;
        }

        const threatColors = {
            'High': { bg: 'rgba(239, 68, 68, 0.6)', border: '#ef4444' },
            'Medium': { bg: 'rgba(245, 158, 11, 0.6)', border: '#f59e0b' },
            'Low': { bg: 'rgba(34, 197, 94, 0.6)', border: '#22c55e' }
        };

        const bubbles = data.competitors.map(c => {
            const colors = threatColors[c.threat_level] || { bg: 'rgba(148, 163, 184, 0.6)', border: '#94a3b8' };
            return {
                x: (c.market_strength || 0) / 10,
                y: (c.growth_momentum || 0) / 10,
                r: Math.max(6, Math.min(30, (c.company_size || 5))),
                name: c.name,
                threat: c.threat_level || 'Unknown',
                bgColor: colors.bg,
                borderColor: colors.border
            };
        });

        // Quadrant divider lines plugin
        const quadrantPlugin = {
            id: 'quadrantDividers',
            beforeDraw(chart) {
                const { ctx: drawCtx, chartArea: { left, right, top, bottom }, scales: { x: xScale, y: yScale } } = chart;
                const midX = xScale.getPixelForValue(5);
                const midY = yScale.getPixelForValue(5);

                drawCtx.save();
                drawCtx.strokeStyle = 'rgba(148, 163, 184, 0.3)';
                drawCtx.lineWidth = 1;
                drawCtx.setLineDash([6, 4]);

                // Vertical divider
                drawCtx.beginPath();
                drawCtx.moveTo(midX, top);
                drawCtx.lineTo(midX, bottom);
                drawCtx.stroke();

                // Horizontal divider
                drawCtx.beginPath();
                drawCtx.moveTo(left, midY);
                drawCtx.lineTo(right, midY);
                drawCtx.stroke();

                drawCtx.setLineDash([]);

                // Quadrant labels
                drawCtx.font = '11px system-ui, sans-serif';
                drawCtx.fillStyle = 'rgba(148, 163, 184, 0.5)';
                drawCtx.textAlign = 'center';

                const padX = 50;
                const padY = 16;
                drawCtx.fillText('Question Marks', (left + midX) / 2, top + padY);
                drawCtx.fillText('Stars', (midX + right) / 2, top + padY);
                drawCtx.fillText('Dogs', (left + midX) / 2, bottom - padY + 6);
                drawCtx.fillText('Cash Cows', (midX + right) / 2, bottom - padY + 6);

                drawCtx.restore();
            }
        };

        marketQuadrantChart = new Chart(ctx, {
            type: 'bubble',
            data: {
                datasets: [{
                    label: 'Competitors',
                    data: bubbles,
                    backgroundColor: bubbles.map(b => b.bgColor),
                    borderColor: bubbles.map(b => b.borderColor),
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#e2e8f0',
                        bodyColor: '#e2e8f0',
                        borderColor: 'rgba(148, 163, 184, 0.2)',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        callbacks: {
                            title: (items) => {
                                const idx = items[0]?.dataIndex;
                                return bubbles[idx]?.name || '';
                            },
                            label: (item) => {
                                const b = bubbles[item.dataIndex];
                                return [
                                    `Market Strength: ${b.x.toFixed(1)}`,
                                    `Growth Momentum: ${b.y.toFixed(1)}`,
                                    `Threat: ${b.threat}`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        min: 0,
                        max: 10,
                        grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        ticks: { color: '#94a3b8', font: { size: 11 } },
                        title: {
                            display: true,
                            text: 'Market Strength',
                            color: '#94a3b8',
                            font: { size: 12, weight: '600' }
                        }
                    },
                    y: {
                        min: 0,
                        max: 10,
                        grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        ticks: { color: '#94a3b8', font: { size: 11 } },
                        title: {
                            display: true,
                            text: 'Growth Momentum',
                            color: '#94a3b8',
                            font: { size: 12, weight: '600' }
                        }
                    }
                }
            },
            plugins: [quadrantPlugin]
        });
    } catch (e) {
        const loaderEl = document.getElementById('marketQuadrantLoader');
        if (loaderEl) loaderEl.remove();

        console.error('[Analytics] Market quadrant chart failed:', e);
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = 'text-align:center;padding:40px;color:var(--text-secondary);';
        errorDiv.textContent = 'Unable to load market position data.';
        container.appendChild(errorDiv);
    }
}

// ============== Data Quality ==============

// P2-3: Load and display data conflicts
async function loadDataConflicts() {
    const container = document.getElementById('dataConflicts');
    const countBadge = document.getElementById('conflictCount');
    if (!container) return;

    container.innerHTML = '<div class="loading">Loading conflicts...</div>';

    try {
        const data = await fetchAPI('/api/reconciliation/conflicts');

        if (!data || !data.conflicts || data.conflicts.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="text-align: center; padding: 40px; color: var(--text-muted);">
                    <div style="font-size: 48px; margin-bottom: 16px;">✅</div>
                    <h4 style="color: var(--text-primary); margin-bottom: 8px;">No Data Conflicts</h4>
                    <p>All KB extractions match live data or have been resolved.</p>
                </div>
            `;
            if (countBadge) {
                countBadge.textContent = '0 conflicts';
                countBadge.style.background = '#dcfce7';
                countBadge.style.color = '#16a34a';
            }
            return;
        }

        // Update count badge
        if (countBadge) {
            countBadge.textContent = `${data.total_conflicts} conflict${data.total_conflicts !== 1 ? 's' : ''}`;
            countBadge.style.background = '#fee2e2';
            countBadge.style.color = '#dc2626';
        }

        // Render conflict cards
        container.innerHTML = data.conflicts.map(conflict => `
            <div class="conflict-card" data-extraction-id="${conflict.extraction_id}" style="
                border: 1px solid var(--border-color);
                border-left: 4px solid #f59e0b;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 12px;
                background: var(--bg-secondary);
            ">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div>
                        <h4 style="margin: 0 0 4px 0; color: var(--text-primary);">${conflict.competitor_name}</h4>
                        <span style="font-size: 12px; color: var(--text-muted);">Field: <strong>${formatFieldName(conflict.field_name)}</strong></span>
                    </div>
                    <span class="conflict-status-badge" style="background: #fef3c7; color: #b45309; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                        Pending Review
                    </span>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
                    <!-- KB Value -->
                    <div style="background: #f0f9ff; padding: 12px; border-radius: 6px; border: 1px solid #bae6fd;">
                        <div style="font-size: 11px; color: #0369a1; margin-bottom: 6px; font-weight: 600;">📄 KB EXTRACTED VALUE</div>
                        <div style="font-weight: 600; color: #0c4a6e; word-break: break-word;">${conflict.kb_value || 'N/A'}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                            ${conflict.kb_confidence ? `Confidence: ${conflict.kb_confidence}%` : ''}
                            ${conflict.kb_date ? `• Date: ${formatDate(conflict.kb_date)}` : ''}
                        </div>
                    </div>

                    <!-- Live Value -->
                    <div style="background: #fef2f2; padding: 12px; border-radius: 6px; border: 1px solid #fecaca;">
                        <div style="font-size: 11px; color: #dc2626; margin-bottom: 6px; font-weight: 600;">🔴 CURRENT LIVE VALUE</div>
                        <div style="font-weight: 600; color: #7f1d1d; word-break: break-word;">${conflict.live_value || 'N/A'}</div>
                        <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
                            ${conflict.live_confidence ? `Confidence: ${conflict.live_confidence}%` : ''}
                            ${conflict.live_date ? `• Date: ${formatDate(conflict.live_date)}` : ''}
                        </div>
                    </div>
                </div>

                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-primary btn-sm" onclick="resolveConflict(${conflict.extraction_id}, 'accept_kb')" style="padding: 6px 12px; font-size: 12px;">
                        ✅ Accept KB Value
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="resolveConflict(${conflict.extraction_id}, 'accept_live')" style="padding: 6px 12px; font-size: 12px;">
                        🔄 Keep Live Value
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="resolveConflict(${conflict.extraction_id}, 'reject')" style="padding: 6px 12px; font-size: 12px; color: #dc2626; border-color: #dc2626;">
                        ❌ Reject
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="viewConflictDetails(${conflict.extraction_id}, ${conflict.competitor_id})" style="padding: 6px 12px; font-size: 12px;">
                        🔍 Details
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load conflicts:', error);
        container.innerHTML = `
            <div class="error-state" style="text-align: center; padding: 40px; color: var(--danger);">
                <p>Failed to load conflicts. <a href="#" onclick="loadDataConflicts(); return false;">Retry</a></p>
            </div>
        `;
    }
}

// P2-3: Resolve a data conflict
async function resolveConflict(extractionId, resolution) {
    const resolutionLabels = {
        'accept_kb': 'accept the KB value',
        'accept_live': 'keep the live value',
        'reject': 'reject this extraction'
    };

    if (!confirm(`Are you sure you want to ${resolutionLabels[resolution]}?`)) {
        return;
    }

    try {
        const result = await fetchAPI(`/api/reconciliation/resolve/${extractionId}?resolution=${resolution}`, {
            method: 'PUT'
        });

        if (result) {
            showToast(`Conflict resolved: ${resolutionLabels[resolution]}`, 'success');
            // Refresh the conflicts list
            await loadDataConflicts();
        }
    } catch (error) {
        console.error('Failed to resolve conflict:', error);
        showToast('Failed to resolve conflict', 'error');
    }
}

// P2-3: View conflict details in modal
async function viewConflictDetails(extractionId, competitorId) {
    try {
        // Get competitor details
        const competitor = competitors.find(c => c.id === competitorId);
        if (!competitor) {
            showToast('Competitor not found', 'error');
            return;
        }

        // Show competitor battlecard/details
        viewBattlecard(competitorId);
    } catch (error) {
        console.error('Failed to load conflict details:', error);
        showToast('Failed to load details', 'error');
    }
}

// P2-3: Format field name for display
function formatFieldName(fieldName) {
    if (!fieldName) return 'Unknown';
    return fieldName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

async function loadDataQuality() {
    // Show skeleton loading for charts
    const qualityChart = document.getElementById('qualityTierChart');
    const coverageChart = document.getElementById('fieldCoverageChart');
    if (qualityChart?.parentElement) showSkeleton(qualityChart.parentElement.id || 'qualityChart', 'chart');
    if (coverageChart?.parentElement) showSkeleton(coverageChart.parentElement.id || 'coverageChart', 'chart');

    try {
        // Load all data quality metrics in parallel
        const [completeness, scores, stale] = await Promise.all([
            fetchAPI('/api/data-quality/completeness'),
            fetchAPI('/api/data-quality/scores'),
            fetchAPI('/api/data-quality/stale?days=30')
        ]);

        // Store data for filtering
        window.qualityData = { completeness, scores, stale };

        // Update summary cards
        if (completeness) {
            document.getElementById('overallCompleteness').textContent = completeness.overall_completeness + '%';
        }
        if (scores) {
            document.getElementById('avgQualityScore').textContent = scores.average_score + '/100';
        }
        if (stale) {
            document.getElementById('staleCount').textContent = stale.stale_count;
            document.getElementById('freshCount').textContent = stale.fresh_count;
        }

        // Render charts
        if (scores && scores.scores) {
            renderQualityTierChart(scores.scores);
        }
        if (completeness && completeness.fields) {
            renderFieldCoverageChart(completeness.fields);
            renderFieldCompleteness(completeness.fields);
        }

        // Render quality scores
        if (scores && scores.scores) {
            renderQualityScores(scores.scores);
        }

        // Render stale records
        if (stale && stale.stale_records) {
            renderStaleRecords(stale.stale_records);
        }
    } catch (error) {
        console.error('Failed to load data quality metrics:', error);
        showToast('Failed to load data quality metrics. Please try again.', 'error');
    }
}

// Quality Tier Distribution Chart
let qualityTierChart = null;
function renderQualityTierChart(scores) {
    const ctx = document.getElementById('qualityTierChart')?.getContext('2d');
    if (!ctx) return;

    if (qualityTierChart) qualityTierChart.destroy();

    const tiers = { Excellent: 0, Good: 0, Fair: 0, Poor: 0 };
    scores.forEach(s => { tiers[s.tier] = (tiers[s.tier] || 0) + 1; });

    qualityTierChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Excellent (90+)', 'Good (70-89)', 'Fair (50-69)', 'Poor (<50)'],
            datasets: [{
                data: [tiers.Excellent, tiers.Good, tiers.Fair, tiers.Poor],
                backgroundColor: ['#22c55e', '#3b82f6', '#f59e0b', '#dc3545'],
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

// Field Coverage Overview Chart
let fieldCoverageChart = null;
function renderFieldCoverageChart(fields) {
    const ctx = document.getElementById('fieldCoverageChart')?.getContext('2d');
    if (!ctx) return;

    if (fieldCoverageChart) fieldCoverageChart.destroy();

    const labels = fields.slice(0, 10).map(f => f.field.replace(/_/g, ' ').substring(0, 15));
    const data = fields.slice(0, 10).map(f => f.completeness_percent);
    const colors = data.map(d => d >= 80 ? '#22c55e' : d >= 60 ? '#f59e0b' : '#dc3545');

    fieldCoverageChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{ label: 'Completeness %', data: data, backgroundColor: colors }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, max: 100 } }
        }
    });
}

// Filter fields by completeness level
function filterFields() {
    const filter = document.getElementById('fieldFilter')?.value || 'all';
    const fields = window.qualityData?.completeness?.fields || [];

    const filtered = fields.filter(f => {
        if (filter === 'all') return true;
        if (filter === 'low') return f.completeness_percent < 60;
        if (filter === 'medium') return f.completeness_percent >= 60 && f.completeness_percent < 80;
        if (filter === 'high') return f.completeness_percent >= 80;
        return true;
    });

    renderFieldCompleteness(filtered);
}

// Filter scores by tier
function filterScores() {
    const filter = document.getElementById('scoreFilter')?.value || 'all';
    const scores = window.qualityData?.scores?.scores || [];

    const filtered = filter === 'all' ? scores : scores.filter(s => s.tier === filter);
    renderQualityScores(filtered);
}

// Verify all records
async function verifyAllRecords() {
    if (!confirm('Mark all competitor records as verified? This will update the last_verified_at timestamp for all records.')) return;

    showToast('Verifying all records...', 'info');
    const competitors = window.qualityData?.scores?.scores || [];
    let success = 0;

    for (const comp of competitors) {
        const result = await fetchAPI(`/api/data-quality/verify/${comp.id}`, { method: 'POST' });
        if (result?.success) success++;
    }

    showToast(`Verified ${success} records successfully!`, 'success');
    loadDataQuality();
}

// Export quality report
function exportQualityReport() {
    const data = window.qualityData;
    if (!data) return showToast('No data to export', 'error');

    const report = {
        generated_at: new Date().toISOString(),
        overall_completeness: data.completeness?.overall_completeness,
        average_score: data.scores?.average_score,
        stale_count: data.stale?.stale_count,
        fresh_count: data.stale?.fresh_count,
        fields: data.completeness?.fields,
        scores: data.scores?.scores
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `data_quality_report_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);

    showToast('Quality report exported!', 'success');
}

// Refresh stale data
async function refreshStaleData() {
    showToast('Refreshing stale data...', 'info');
    const stale = await fetchAPI('/api/data-quality/stale?days=30');
    if (stale) {
        window.qualityData.stale = stale;
        document.getElementById('staleCount').textContent = stale.stale_count;
        document.getElementById('freshCount').textContent = stale.fresh_count;
        renderStaleRecords(stale.stale_records);
        showToast('Stale data refreshed', 'success');
    }
}

// Show quality details modal
function showQualityDetails(type) {
    const data = window.qualityData;
    if (!data) return;

    let content = '';
    switch (type) {
        case 'completeness':
            content = `<h3>Data Completeness Details</h3><p>Overall: ${data.completeness?.overall_completeness}%</p><p>Total fields tracked: ${data.completeness?.total_fields}</p><p>Total competitors: ${data.completeness?.total_competitors}</p>`;
            break;
        case 'scores':
            content = `<h3>Quality Score Details</h3><p>Average Score: ${data.scores?.average_score}/100</p><p>Total scored: ${data.scores?.total_competitors}</p>`;
            break;
        case 'stale':
            content = `<h3>Stale Records</h3><p>${data.stale?.stale_count} competitors have data older than 30 days.</p>`;
            break;
        case 'fresh':
            content = `<h3>Fresh Records</h3><p>${data.stale?.fresh_count} competitors have been verified within the last 30 days.</p>`;
            break;
        case 'verified':
            const overview = window.qualityOverview;
            if (overview) {
                const verified = overview.total_data_points - overview.needs_attention?.unverified_count || 0;
                content = `<h3>Verification Status</h3>
                    <p>Verification Rate: <strong>${overview.verification_rate || 0}%</strong></p>
                    <p>Verified Data Points: <strong>${verified}</strong></p>
                    <p>Unverified Data Points: <strong>${overview.needs_attention?.unverified_count || 0}</strong></p>
                    <p>Total Data Points: <strong>${overview.total_data_points || 0}</strong></p>
                    <hr style="margin: 12px 0; border-color: var(--border-color);">
                    <p style="font-size: 13px; color: var(--text-secondary);">
                        Verified data has been confirmed through triangulation, manual review, or authoritative sources like SEC filings.
                    </p>`;
            } else {
                content = `<h3>Verification Status</h3><p>Loading verification data...</p>`;
            }
            break;
    }
    showModal(content);
}

function renderFieldCompleteness(fields) {
    const container = document.getElementById('fieldCompleteness');
    if (!container) return;

    container.innerHTML = fields.map(field => {
        const pct = field.completeness_percent;
        const barColor = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#dc3545';
        const fieldName = field.field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

        return `
            <div style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                    <span style="font-weight: 500;">${fieldName}</span>
                    <span style="font-weight: 600; color: ${barColor};">${pct}%</span>
                </div>
                <div style="height: 8px; background: var(--border-color); border-radius: 4px; overflow: hidden;">
                    <div style="height: 100%; width: ${pct}%; background: ${barColor}; border-radius: 4px; transition: width 0.3s;"></div>
                </div>
                <div style="font-size: 0.8em; color: var(--text-secondary); margin-top: 4px;">
                    ${field.filled} of ${field.total} competitors
                </div>
            </div>
        `;
    }).join('');
}

function renderQualityScores(scores) {
    const container = document.getElementById('qualityScores');
    if (!container) return;

    container.innerHTML = `
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: var(--bg-tertiary);">
                    <th style="padding: 12px; text-align: left;">Rank</th>
                    <th style="padding: 12px; text-align: left;">Competitor</th>
                    <th style="padding: 12px; text-align: center;">Score</th>
                    <th style="padding: 12px; text-align: center;">Tier</th>
                    <th style="padding: 12px; text-align: center;">Verified</th>
                    <th style="padding: 12px; text-align: center;">Actions</th>
                </tr>
            </thead>
            <tbody>
                ${scores.map((s, i) => {
        const tierColor = s.tier === 'Excellent' ? '#22c55e' :
            s.tier === 'Good' ? '#3b82f6' :
                s.tier === 'Fair' ? '#f59e0b' : '#dc3545';
        return `
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 10px;">#${i + 1}</td>
                            <td style="padding: 10px; font-weight: 500;">${s.name}</td>
                            <td style="padding: 10px; text-align: center;">
                                <span style="font-weight: 600; color: ${tierColor};">${s.score}/100</span>
                            </td>
                            <td style="padding: 10px; text-align: center;">
                                <span style="background: ${tierColor}20; color: ${tierColor}; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 500;">
                                    ${s.tier}
                                </span>
                            </td>
                            <td style="padding: 10px; text-align: center;">
                                <span id="qs-verif-${s.id}" style="font-size:11px;color:#94a3b8;">--</span>
                            </td>
                            <td style="padding: 10px; text-align: center;">
                                <button onclick="verifyCompetitor(${s.id})" style="background: var(--navy-dark); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em;">
                                    ✅ Verify
                                </button>
                            </td>
                        </tr>
                    `;
    }).join('')}
            </tbody>
        </table>
    `;

    // v7.2: Async-load verification percentages for each row
    _loadQualityScoreVerification(scores);
}

/**
 * v7.2: Load verification summary for each competitor in quality scores table
 */
async function _loadQualityScoreVerification(scores) {
    for (const s of scores) {
        const el = document.getElementById(`qs-verif-${s.id}`);
        if (!el) continue;
        const summary = await getVerificationSummary(s.id);
        const pct = Math.round(summary.percent || 0);
        const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444';
        el.innerHTML = `<span style="font-weight:600;color:${color};">${pct}%</span>`;
    }
}

function renderStaleRecords(staleRecords) {
    const container = document.getElementById('staleRecords');
    if (!container) return;

    if (staleRecords.length === 0) {
        container.innerHTML = '<p style="color: #22c55e; font-weight: 500;">✅ All records are fresh! No stale data found.</p>';
        return;
    }

    container.innerHTML = `
        <div style="display: grid; gap: 10px;">
            ${staleRecords.slice(0, 20).map(record => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #fef2f220; border: 1px solid #fecaca; border-radius: 8px;">
                    <div>
                        <span style="font-weight: 500;">${record.name}</span>
                        <span style="color: var(--text-secondary); font-size: 0.9em; margin-left: 8px;">
                            Last verified: ${record.last_verified ? new Date(record.last_verified).toLocaleDateString() : 'Never'}
                        </span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="color: #dc3545; font-weight: 600;">${record.days_old} days old</span>
                        <button onclick="verifyCompetitor(${record.id})" style="background: #22c55e; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em;">
                            🔄 Mark Verified
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
        ${staleRecords.length > 20 ? `<p style="color: var(--text-secondary); margin-top: 10px;">... and ${staleRecords.length - 20} more stale records</p>` : ''}
    `;
}

async function verifyCompetitor(id) {
    const result = await fetchAPI(`/api/data-quality/verify/${id}`, { method: 'POST' });
    if (result && result.success) {
        showToast(`${result.name} marked as verified! Score: ${result.quality_score}/100`, 'success');
        loadDataQuality();  // Refresh the page
    }
}

// ============== PHASE 7: DATA QUALITY DASHBOARD ==============

// Store for quality overview data
window.qualityOverview = null;

// Confidence Distribution Chart
let confidenceDistributionChart = null;

/**
 * Load enhanced data quality overview (Phase 7)
 */
async function loadDataQualityOverview() {
    try {
        const overview = await fetchAPI('/api/data-quality/overview');
        if (!overview) return;

        window.qualityOverview = overview;

        // Update confidence distribution cards
        updateConfidenceCards(overview.confidence_distribution);

        // Update verification rate
        document.getElementById('verificationRate').textContent = overview.verification_rate + '%';
        const verifiedCount = overview.total_data_points - overview.needs_attention.unverified_count;
        document.getElementById('verifiedCount').textContent = verifiedCount + ' verified';

        // Render confidence distribution chart
        renderConfidenceDistributionChart(overview.confidence_distribution);

        // Render source type breakdown
        renderSourceTypeBreakdown(overview.source_type_breakdown);

        // Render field confidence analysis
        renderFieldConfidenceAnalysis(overview.field_coverage);

        // Render competitor quality ranking
        renderCompetitorQualityRanking(overview.competitor_scores);

    } catch (error) {
        console.error('Error loading data quality overview:', error);
    }
}

/**
 * Update confidence distribution stat cards
 */
function updateConfidenceCards(distribution) {
    if (!distribution) return;

    // High confidence
    const highEl = document.getElementById('highConfidenceCount');
    const highPctEl = document.getElementById('highConfidencePercent');
    if (highEl) highEl.textContent = distribution.high?.count || 0;
    if (highPctEl) highPctEl.textContent = (distribution.high?.percentage || 0) + '% of data';

    // Moderate confidence
    const modEl = document.getElementById('moderateConfidenceCount');
    const modPctEl = document.getElementById('moderateConfidencePercent');
    if (modEl) modEl.textContent = distribution.moderate?.count || 0;
    if (modPctEl) modPctEl.textContent = (distribution.moderate?.percentage || 0) + '% of data';

    // Low confidence
    const lowEl = document.getElementById('lowConfidenceCount');
    const lowPctEl = document.getElementById('lowConfidencePercent');
    if (lowEl) lowEl.textContent = distribution.low?.count || 0;
    if (lowPctEl) lowPctEl.textContent = (distribution.low?.percentage || 0) + '% of data';
}

/**
 * Render confidence distribution doughnut chart
 */
function renderConfidenceDistributionChart(distribution) {
    const ctx = document.getElementById('confidenceDistributionChart')?.getContext('2d');
    if (!ctx || !distribution) return;

    if (confidenceDistributionChart) {
        confidenceDistributionChart.destroy();
    }

    confidenceDistributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['High (70-100)', 'Moderate (40-69)', 'Low (0-39)', 'Unscored'],
            datasets: [{
                data: [
                    distribution.high?.count || 0,
                    distribution.moderate?.count || 0,
                    distribution.low?.count || 0,
                    distribution.unscored?.count || 0
                ],
                backgroundColor: ['#10b981', '#f59e0b', '#ef4444', '#64748b'],
                borderWidth: 2,
                borderColor: '#1e293b'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#e2e8f0', padding: 15 }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((context.raw / total) * 100).toFixed(1) : 0;
                            return `${context.label}: ${context.raw} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render source type breakdown grid
 */
function renderSourceTypeBreakdown(sourceTypes) {
    const container = document.getElementById('sourceTypeBreakdown');
    if (!container || !sourceTypes) return;

    const sourceIcons = {
        'sec_filing': '📊',
        'api_verified': '🔌',
        'website_scrape': '🌐',
        'manual': '✏️',
        'manual_verified': '✅',
        'news_article': '📰',
        'klas_report': '📋',
        'unknown': '❓'
    };

    const sourceLabels = {
        'sec_filing': 'SEC Filing',
        'api_verified': 'API Verified',
        'website_scrape': 'Website Scrape',
        'manual': 'Manual Entry',
        'manual_verified': 'Manual Verified',
        'news_article': 'News Article',
        'klas_report': 'KLAS Report',
        'unknown': 'Unknown'
    };

    const html = Object.entries(sourceTypes).map(([type, data]) => {
        const icon = sourceIcons[type] || '📄';
        const label = sourceLabels[type] || type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const avgConf = data.avg_confidence || 0;
        const confLevel = avgConf >= 70 ? 'high' : avgConf >= 40 ? 'moderate' : 'low';

        return `
            <div class="source-type-card">
                <div class="source-type-header">
                    <div class="source-type-icon ${type}">${icon}</div>
                    <span class="source-type-name">${label}</span>
                </div>
                <div class="source-type-stats">
                    <span class="source-type-count">${data.count} data points</span>
                    <div class="source-type-confidence">
                        <div class="source-type-confidence-bar">
                            <div class="source-type-confidence-fill ${confLevel}" style="width: ${avgConf}%;"></div>
                        </div>
                        <span class="source-type-confidence-score" style="color: ${confLevel === 'high' ? '#10b981' : confLevel === 'moderate' ? '#f59e0b' : '#ef4444'};">
                            ${avgConf}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html || '<p style="color: var(--text-secondary);">No source data available.</p>';
}

/**
 * Render field confidence analysis grid
 */
function renderFieldConfidenceAnalysis(fieldCoverage) {
    const container = document.getElementById('fieldConfidenceAnalysis');
    if (!container || !fieldCoverage) return;

    const fieldLabels = {
        'customer_count': 'Customer Count',
        'base_price': 'Base Price',
        'pricing_model': 'Pricing Model',
        'employee_count': 'Employee Count',
        'year_founded': 'Year Founded',
        'key_features': 'Key Features'
    };

    const html = Object.entries(fieldCoverage).map(([field, data]) => {
        const label = fieldLabels[field] || field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        const coveragePct = data.percentage || 0;
        const avgConf = data.avg_confidence || 0;
        const confLevel = avgConf >= 70 ? 'high' : avgConf >= 40 ? 'moderate' : 'low';

        return `
            <div class="field-confidence-card">
                <div class="field-confidence-header">
                    <span class="field-confidence-name">${label}</span>
                    <span class="field-confidence-coverage">${data.populated}/${data.total}</span>
                </div>
                <div class="field-confidence-bars">
                    <div class="field-confidence-bar-row">
                        <span class="field-confidence-bar-label">Coverage</span>
                        <div class="field-confidence-bar-container">
                            <div class="field-confidence-bar-fill coverage" style="width: ${coveragePct}%;"></div>
                        </div>
                        <span class="field-confidence-bar-value" style="color: ${coveragePct >= 80 ? '#10b981' : coveragePct >= 50 ? '#f59e0b' : '#ef4444'};">
                            ${coveragePct}%
                        </span>
                    </div>
                    <div class="field-confidence-bar-row">
                        <span class="field-confidence-bar-label">Confidence</span>
                        <div class="field-confidence-bar-container">
                            <div class="field-confidence-bar-fill confidence-${confLevel}" style="width: ${avgConf}%;"></div>
                        </div>
                        <span class="field-confidence-bar-value" style="color: ${confLevel === 'high' ? '#10b981' : confLevel === 'moderate' ? '#f59e0b' : '#ef4444'};">
                            ${avgConf}
                        </span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html || '<p style="color: var(--text-secondary);">No field data available.</p>';
}

/**
 * Render competitor quality ranking list
 */
function renderCompetitorQualityRanking(competitorScores) {
    const container = document.getElementById('competitorQualityRanking');
    if (!container) return;

    if (!competitorScores || competitorScores.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary);">No competitor data available.</p>';
        return;
    }

    // Store for filtering
    window.competitorQualityScores = competitorScores;

    renderFilteredQualityRanking(competitorScores);
}

/**
 * Render filtered quality ranking
 */
function renderFilteredQualityRanking(scores) {
    const container = document.getElementById('competitorQualityRanking');
    if (!container) return;

    const html = scores.map((comp, index) => {
        const rank = index + 1;
        const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : rank === 3 ? 'rank-3' : 'default';
        const tierClass = comp.quality_tier || 'Poor';
        const scoreClass = tierClass.toLowerCase();

        return `
            <div class="competitor-quality-row">
                <div class="competitor-quality-rank ${rankClass}">${rank}</div>
                <div class="competitor-quality-info">
                    <div class="competitor-quality-name">${escapeHtml(comp.name)}</div>
                    <div class="competitor-quality-details">
                        <span>${comp.total_fields} fields tracked</span>
                        <span>${comp.verified_count} verified</span>
                        <span>${comp.high_confidence_count} high conf.</span>
                    </div>
                </div>
                <div class="competitor-quality-score">
                    <span class="competitor-quality-score-value ${scoreClass}">${comp.avg_confidence}</span>
                    <span class="competitor-quality-tier ${tierClass}">${tierClass}</span>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = html;
}

/**
 * Filter quality ranking by tier
 */
function filterQualityRanking() {
    const filter = document.getElementById('qualityRankingFilter')?.value || 'all';
    const scores = window.competitorQualityScores || [];

    const filtered = filter === 'all' ? scores : scores.filter(s => s.quality_tier === filter);
    renderFilteredQualityRanking(filtered);
}

/**
 * Filter data by confidence level
 */
async function filterByConfidence(level) {
    // Navigate to a filtered view or show modal
    let threshold = 0;
    if (level === 'low') threshold = 40;
    else if (level === 'moderate') threshold = 70;
    else if (level === 'high') threshold = 100;

    const data = await fetchAPI(`/api/data-quality/low-confidence?threshold=${threshold}`);
    if (data) {
        const content = `
            <h3>${level.charAt(0).toUpperCase() + level.slice(1)} Confidence Data Points</h3>
            <p>Total: ${data.total_low_confidence} data points across ${data.competitors_affected} competitors</p>
            <div style="max-height: 400px; overflow-y: auto; margin-top: 16px;">
                ${data.data?.map(comp => `
                    <div style="margin-bottom: 12px; padding: 10px; background: rgba(30, 41, 59, 0.6); border-radius: 8px;">
                        <strong>${comp.competitor_name}</strong>
                        <div style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                            ${comp.fields.slice(0, 5).map(f => `
                                <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                                    <span>${f.field.replace(/_/g, ' ')}</span>
                                    <span style="color: ${f.confidence_score >= 70 ? '#10b981' : f.confidence_score >= 40 ? '#f59e0b' : '#ef4444'};">
                                        ${f.confidence_score}/100
                                    </span>
                                </div>
                            `).join('')}
                            ${comp.fields.length > 5 ? `<div style="color: var(--text-muted);">...and ${comp.fields.length - 5} more</div>` : ''}
                        </div>
                    </div>
                `).join('') || '<p>No data found.</p>'}
            </div>
        `;
        showModal(content);
    }
}

/**
 * Recalculate all confidence scores
 */
async function recalculateAllConfidence() {
    if (!confirm('Recalculate confidence scores for all data sources? This may take a moment.')) return;

    showToast('Recalculating confidence scores...', 'info');

    try {
        const result = await fetchAPI('/api/data-quality/recalculate-confidence', { method: 'POST' });
        if (result?.success) {
            showToast(`Recalculated ${result.updated_count} data sources`, 'success');
            loadDataQuality();
            loadDataQualityOverview();
        }
    } catch (error) {
        showToast('Error recalculating scores: ' + error.message, 'error');
    }
}

// Override the original loadDataQuality to also load the new overview
const originalLoadDataQuality = loadDataQuality;
loadDataQuality = async function() {
    await originalLoadDataQuality();
    await loadDataQualityOverview();
};

// ============== KNOWLEDGE BASE IMPORT UI ==============

/**
 * Switch between Validation tabs (Data Validation / KB Import)
 */
function showValidationTab(tabName) {
    document.querySelectorAll('.validation-tab-content').forEach(el => {
        el.style.display = 'none';
        el.classList.remove('active');
    });
    document.querySelectorAll('.validation-tab-btn').forEach(btn => btn.classList.remove('active'));

    const tabEl = document.getElementById(`dq-${tabName}Tab`);
    if (tabEl) {
        tabEl.style.display = 'block';
        tabEl.classList.add('active');
    }

    const clickedBtn = event && event.target ? event.target.closest('.validation-tab-btn') : null;
    if (clickedBtn) clickedBtn.classList.add('active');

    // Toggle header actions visibility
    const headerActions = document.getElementById('dqHeaderActions');
    if (headerActions) {
        headerActions.style.display = tabName === 'dataquality' ? 'flex' : 'none';
    }
}
window.showValidationTab = showValidationTab;

/**
 * Scan the knowledge base directory for importable files
 */
async function scanKnowledgeBase() {
    const btn = document.getElementById('kbScanBtn');
    const progress = document.getElementById('kbScanProgress');
    const results = document.getElementById('kbScanResults');
    const previewPanel = document.getElementById('kbPreviewPanel');
    const importPanel = document.getElementById('kbImportPanel');

    if (btn) btn.disabled = true;
    if (progress) progress.style.display = 'block';
    if (results) results.style.display = 'none';

    try {
        const files = await fetchAPI('/api/knowledge-base/scan');

        if (progress) progress.style.display = 'none';
        if (btn) btn.disabled = false;

        if (!files || files.length === 0) {
            if (results) {
                results.style.display = 'block';
                const fileList = document.getElementById('kbFileList');
                if (fileList) {
                    fileList.innerHTML = '<div class="empty-state" style="text-align:center;padding:30px;color:var(--text-secondary);"><p>No files found in the knowledge base directory.</p></div>';
                }
            }
            return;
        }

        if (results) {
            results.style.display = 'block';
            const fileList = document.getElementById('kbFileList');
            if (fileList) {
                const fileTypeIcons = {
                    'pdf': '📄', 'csv': '📊', 'json': '📋',
                    'xlsx': '📗', 'xls': '📗', 'txt': '📝',
                    'md': '📝', 'docx': '📘'
                };

                fileList.innerHTML = `
                    <p style="color:var(--text-secondary);margin-bottom:10px;">${files.length} file${files.length !== 1 ? 's' : ''} found</p>
                    <div class="kb-file-list">
                        ${files.map(f => {
                            const ext = (f.file_type || f.filename.split('.').pop() || '').toLowerCase();
                            const icon = fileTypeIcons[ext] || '📄';
                            const sizeStr = f.size_bytes >= 1048576
                                ? (f.size_bytes / 1048576).toFixed(1) + ' MB'
                                : f.size_bytes >= 1024
                                    ? (f.size_bytes / 1024).toFixed(1) + ' KB'
                                    : f.size_bytes + ' B';
                            return `<div class="kb-file-item">
                                <span class="kb-file-icon">${icon}</span>
                                <div class="kb-file-info">
                                    <div class="kb-file-name">${escapeHtml(f.filename)}</div>
                                    <div class="kb-file-meta">${escapeHtml(f.path || '')}</div>
                                </div>
                                <span class="kb-file-size">${sizeStr}</span>
                            </div>`;
                        }).join('')}
                    </div>
                `;
            }
        }

        if (previewPanel) previewPanel.style.display = 'block';
        if (importPanel) importPanel.style.display = 'block';
        await previewKnowledgeBase();

    } catch (error) {
        if (progress) progress.style.display = 'none';
        if (btn) btn.disabled = false;
        showToast('Failed to scan knowledge base.', 'error');
    }
}
window.scanKnowledgeBase = scanKnowledgeBase;

/**
 * Preview the parsed KB data before importing
 */
async function previewKnowledgeBase() {
    const statsEl = document.getElementById('kbPreviewStats');
    const tableEl = document.getElementById('kbPreviewTable');
    const warningsEl = document.getElementById('kbPreviewWarnings');
    const errorsEl = document.getElementById('kbPreviewErrors');

    if (tableEl) tableEl.innerHTML = '<div class="loading">Parsing files...</div>';

    try {
        const preview = await fetchAPI('/api/knowledge-base/preview');
        if (!preview) {
            if (tableEl) tableEl.innerHTML = '<p style="color:var(--text-secondary);">No preview data available.</p>';
            return;
        }

        if (statsEl) {
            statsEl.innerHTML = `
                <div class="stat-card"><div class="stat-value">${preview.total_files || 0}</div><div class="stat-label">Files Parsed</div></div>
                <div class="stat-card"><div class="stat-value">${preview.competitors_found || 0}</div><div class="stat-label">Competitors Found</div></div>
                <div class="stat-card"><div class="stat-value">${preview.unique_competitors || 0}</div><div class="stat-label">Unique Competitors</div></div>
            `;
        }

        if (warningsEl) {
            if (preview.warnings && preview.warnings.length > 0) {
                warningsEl.style.display = 'block';
                warningsEl.innerHTML = `<div class="kb-warning-box"><strong>Warnings:</strong><ul style="margin:6px 0 0 16px;">${preview.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul></div>`;
            } else {
                warningsEl.style.display = 'none';
            }
        }

        if (errorsEl) {
            if (preview.errors && preview.errors.length > 0) {
                errorsEl.style.display = 'block';
                errorsEl.innerHTML = `<div class="kb-error-box"><strong>Errors:</strong><ul style="margin:6px 0 0 16px;">${preview.errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul></div>`;
            } else {
                errorsEl.style.display = 'none';
            }
        }

        if (tableEl) {
            if (!preview.competitors || preview.competitors.length === 0) {
                tableEl.innerHTML = '<p style="color:var(--text-secondary);">No competitors found in scanned files.</p>';
                return;
            }

            tableEl.innerHTML = `
                <table class="kb-preview-table">
                    <thead>
                        <tr>
                            <th>Competitor</th>
                            <th>Status</th>
                            <th>Fields</th>
                            <th>Source File</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${preview.competitors.map(c => `
                            <tr>
                                <td style="font-weight:500;">${escapeHtml(c.name)}</td>
                                <td>${c.is_existing
                                    ? '<span class="kb-badge kb-badge-existing">Existing</span>'
                                    : '<span class="kb-badge kb-badge-new">New</span>'
                                }</td>
                                <td>${c.fields_populated || 0}</td>
                                <td style="font-size:12px;color:var(--text-secondary);">${escapeHtml(c.source_file || '-')}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    } catch (error) {
        if (tableEl) tableEl.innerHTML = '<p style="color:#f87171;">Failed to load preview.</p>';
    }
}
window.previewKnowledgeBase = previewKnowledgeBase;

/**
 * Run the knowledge base import
 */
async function importKnowledgeBase() {
    const dryRun = document.getElementById('kbDryRun')?.checked ?? true;
    const overwrite = document.getElementById('kbOverwrite')?.checked ?? false;
    const btn = document.getElementById('kbImportBtn');
    const progress = document.getElementById('kbImportProgress');
    const resultsEl = document.getElementById('kbImportResults');

    if (btn) btn.disabled = true;
    if (progress) progress.style.display = 'block';
    if (resultsEl) resultsEl.style.display = 'none';

    try {
        const result = await fetchAPI('/api/knowledge-base/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: dryRun, overwrite_existing: overwrite })
        });

        if (progress) progress.style.display = 'none';
        if (btn) btn.disabled = false;

        if (!result) {
            showToast('Import failed - no response from server.', 'error');
            return;
        }

        if (resultsEl) {
            resultsEl.style.display = 'block';
            const modeLabel = dryRun ? '(Dry Run - no changes saved)' : '';

            resultsEl.innerHTML = `
                <div style="margin-bottom:12px;">
                    <span style="font-weight:600;color:${result.success ? '#22c55e' : '#f87171'};">
                        ${result.success ? 'Import Successful' : 'Import Completed with Errors'}
                    </span>
                    <span style="color:var(--text-secondary);font-size:13px;margin-left:8px;">${modeLabel}</span>
                </div>
                <div class="kb-import-summary">
                    <div class="kb-import-stat" style="border-left:3px solid #22c55e;">
                        <div class="kb-import-stat-value">${result.competitors_imported || 0}</div>
                        <div class="kb-import-stat-label">Imported</div>
                    </div>
                    <div class="kb-import-stat" style="border-left:3px solid #3b82f6;">
                        <div class="kb-import-stat-value">${result.competitors_updated || 0}</div>
                        <div class="kb-import-stat-label">Updated</div>
                    </div>
                    <div class="kb-import-stat" style="border-left:3px solid #94a3b8;">
                        <div class="kb-import-stat-value">${result.competitors_skipped || 0}</div>
                        <div class="kb-import-stat-label">Skipped</div>
                    </div>
                </div>
                ${result.imported && result.imported.length > 0 ? `
                    <div style="max-height:300px;overflow-y:auto;">
                        <table class="kb-preview-table">
                            <thead><tr><th>Competitor</th><th>Status</th><th>Fields Updated</th><th>Source</th></tr></thead>
                            <tbody>
                                ${result.imported.map(item => `
                                    <tr>
                                        <td style="font-weight:500;">${escapeHtml(item.name)}</td>
                                        <td>${item.is_new
                                            ? '<span class="kb-badge kb-badge-new">New</span>'
                                            : '<span class="kb-badge kb-badge-existing">Updated</span>'
                                        }</td>
                                        <td>${item.fields_updated || 0}</td>
                                        <td style="font-size:12px;color:var(--text-secondary);">${escapeHtml(item.source_file || '-')}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                ` : ''}
                ${result.errors && result.errors.length > 0 ? `
                    <div class="kb-error-box" style="margin-top:12px;">
                        <strong>Errors:</strong>
                        <ul style="margin:6px 0 0 16px;">${result.errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul>
                    </div>
                ` : ''}
            `;
        }

        if (result.success && !dryRun) {
            showToast(`Imported ${result.competitors_imported || 0} competitors, updated ${result.competitors_updated || 0}.`, 'success');
        } else if (dryRun) {
            showToast('Dry run complete - no changes saved.', 'info');
        }

    } catch (error) {
        if (progress) progress.style.display = 'none';
        if (btn) btn.disabled = false;
        showToast('Import failed.', 'error');
    }
}
window.importKnowledgeBase = importKnowledgeBase;

/**
 * Load the KB verification queue
 */
async function loadKbVerificationQueue() {
    const container = document.getElementById('kbVerificationQueue');
    if (!container) return;

    container.innerHTML = '<div class="loading">Loading verification queue...</div>';

    try {
        const items = await fetchAPI('/api/knowledge-base/verification-queue');

        if (!items || items.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="text-align:center;padding:40px;color:var(--text-secondary);">
                    <div style="font-size:36px;margin-bottom:12px;">✅</div>
                    <p>No items pending verification.</p>
                </div>
            `;
            const bulkBtn = document.getElementById('kbBulkApproveBtn');
            if (bulkBtn) bulkBtn.style.display = 'none';
            return;
        }

        const bulkBtn = document.getElementById('kbBulkApproveBtn');
        if (bulkBtn) bulkBtn.style.display = 'inline-flex';

        container.innerHTML = `
            <div class="kb-select-all-bar">
                <label>
                    <input type="checkbox" id="kbSelectAll" onchange="toggleKbSelectAll(this.checked)">
                    <span>Select All (${items.length})</span>
                </label>
            </div>
            <div id="kbVerificationList">
                ${items.map(item => `
                    <div class="kb-verification-item" data-kb-id="${item.id}">
                        <div class="kb-verification-checkbox">
                            <input type="checkbox" class="kb-item-check" value="${item.id}" onchange="updateKbBulkState()">
                        </div>
                        <div class="kb-verification-info">
                            <div class="kb-verification-field">${escapeHtml(item.competitor_name || 'Unknown')} - ${escapeHtml(item.field_name || item.field || 'Field')}</div>
                            <div class="kb-verification-value">Value: ${escapeHtml(String(item.value || item.extracted_value || '-'))}</div>
                            ${item.source_file ? `<div style="font-size:11px;color:var(--text-secondary);margin-top:2px;">Source: ${escapeHtml(item.source_file)}</div>` : ''}
                        </div>
                        <div class="kb-verification-actions">
                            <button class="btn btn-primary" onclick="approveKbItem(${item.id}, this)" style="background:#22c55e;border-color:#22c55e;">Approve</button>
                            <button class="btn btn-secondary" onclick="rejectKbItem(${item.id}, this)" style="background:#ef4444;border-color:#ef4444;color:white;">Reject</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (error) {
        container.innerHTML = '<p style="color:#f87171;">Failed to load verification queue.</p>';
    }
}
window.loadKbVerificationQueue = loadKbVerificationQueue;

function toggleKbSelectAll(checked) {
    document.querySelectorAll('.kb-item-check').forEach(cb => { cb.checked = checked; });
    updateKbBulkState();
}
window.toggleKbSelectAll = toggleKbSelectAll;

function updateKbBulkState() {
    const checks = document.querySelectorAll('.kb-item-check:checked');
    const bulkBtn = document.getElementById('kbBulkApproveBtn');
    if (bulkBtn) {
        bulkBtn.textContent = checks.length > 0 ? `Bulk Approve (${checks.length})` : 'Bulk Approve Selected';
    }
}
window.updateKbBulkState = updateKbBulkState;

async function approveKbItem(id, btnEl) {
    if (btnEl) btnEl.disabled = true;
    const result = await fetchAPI(`/api/knowledge-base/verification/approve/${id}`, { method: 'POST' });
    if (result) {
        const row = btnEl?.closest('.kb-verification-item');
        if (row) { row.style.opacity = '0.5'; row.style.pointerEvents = 'none'; }
        showToast('Item approved.', 'success');
    } else {
        if (btnEl) btnEl.disabled = false;
    }
}
window.approveKbItem = approveKbItem;

async function rejectKbItem(id, btnEl) {
    if (btnEl) btnEl.disabled = true;
    const result = await fetchAPI(`/api/knowledge-base/verification/reject/${id}`, { method: 'POST' });
    if (result) {
        const row = btnEl?.closest('.kb-verification-item');
        if (row) { row.style.opacity = '0.5'; row.style.pointerEvents = 'none'; }
        showToast('Item rejected.', 'info');
    } else {
        if (btnEl) btnEl.disabled = false;
    }
}
window.rejectKbItem = rejectKbItem;

async function bulkApproveKbItems() {
    const checks = document.querySelectorAll('.kb-item-check:checked');
    if (checks.length === 0) { showToast('No items selected.', 'info'); return; }

    const ids = Array.from(checks).map(cb => parseInt(cb.value, 10));
    if (!confirm(`Approve ${ids.length} selected item${ids.length !== 1 ? 's' : ''}?`)) return;

    const bulkBtn = document.getElementById('kbBulkApproveBtn');
    if (bulkBtn) bulkBtn.disabled = true;

    try {
        const result = await fetchAPI('/api/knowledge-base/verification/bulk-approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        if (result) {
            showToast(`Approved ${ids.length} item${ids.length !== 1 ? 's' : ''}.`, 'success');
            await loadKbVerificationQueue();
        }
    } catch (error) {
        showToast('Bulk approve failed.', 'error');
    } finally {
        if (bulkBtn) bulkBtn.disabled = false;
    }
}
window.bulkApproveKbItems = bulkApproveKbItems;

// ============== Universal Data Sourcing (Task 6) ==============

// Cache for source data to avoid repeated API calls
const sourceCache = {};

// Cache for manual edits (tracks which fields have been manually edited and approved)
const manualEditCache = {};

/**
 * Create a sourced value HTML element - CLEAN VERSION
 * No side graphics, N/A for missing values, clickable label opens edit popup
 * @param {string|number} value - The data value to display
 * @param {number} competitorId - The competitor ID
 * @param {string} fieldName - The field name (e.g., 'customer_count')
 * @param {string} fallbackType - Fallback source type if not in cache
 * @returns {string} HTML string for the sourced value
 */
// === Source Verification Dot System ===
const _sourceVerificationCache = {};

async function _loadSourceVerificationData(competitorId) {
    if (_sourceVerificationCache[competitorId]) return _sourceVerificationCache[competitorId];
    try {
        const resp = await fetchAPI(`/api/sources/batch?competitor_ids=${competitorId}`);
        const data = (resp && resp.sources) ? resp.sources[String(competitorId)] || {} : {};
        _sourceVerificationCache[competitorId] = data;
        return data;
    } catch (e) {
        _sourceVerificationCache[competitorId] = {};
        return {};
    }
}

function renderSourceDot(competitorId, fieldName, value) {
    const dotId = `sd-${competitorId}-${fieldName}-${Date.now()}`;
    setTimeout(() => _hydrateSourceDot(competitorId, fieldName, dotId), 50);
    return `<span class="source-dot-wrapper" id="${dotId}"><span class="source-dot dot-loading"></span><div class="source-dot-tooltip"><div class="sdt-label">Loading...</div></div></span>`;
}

async function _hydrateSourceDot(competitorId, fieldName, dotId) {
    const el = document.getElementById(dotId);
    if (!el) return;
    const sources = await _loadSourceVerificationData(competitorId);
    const src = sources[fieldName];
    const dot = el.querySelector('.source-dot');
    const tooltip = el.querySelector('.source-dot-tooltip');
    if (!dot || !tooltip) return;

    // v8.3.0: Use quality-level dot class when url_quality is available
    const qualityClass = _getQualityDotClass(src);

    // v8.3.0: Quality-specific tooltip labels
    const qualityLabel = src && src.url_quality === 'exact_page' ? 'Verified - Exact text match'
        : src && src.url_quality === 'page_level' ? 'Page level - correct page, text not matched'
        : src && src.url_quality === 'homepage_only' ? 'Homepage only'
        : null;

    if (src && src.is_verified && src.source_url) {
        dot.className = 'source-dot ' + qualityClass;
        // Prefer deep_link_url from API when available, fall back to building one
        const deepUrl = src.deep_link_url || buildDeepSourceLink(src.source_url, src.current_value);
        const linkUrl = escapeHtml(deepUrl);
        const clickHandler = !_supportsTextFragments && src.current_value
            ? ` onclick="event.preventDefault(); openSourceUrlWithDeepLink('${escapeHtml(src.source_url)}', '${linkUrl}', '${escapeHtml(String(src.current_value).substring(0, 60))}')"` : '';
        const labelText = qualityLabel || src.source_name || 'Verified Source';
        tooltip.innerHTML = `<div class="sdt-label">${escapeHtml(labelText)}</div><a class="sdt-url" href="${linkUrl}" target="_blank" rel="noopener"${clickHandler}>View Source</a><div class="sdt-meta">${src.confidence_score ? src.confidence_score + '% confidence' : ''}${src.extracted_at ? ' &bull; ' + new Date(src.extracted_at).toLocaleDateString() : ''}</div>`;
    } else if (src && (src.source_url || src.source_name)) {
        dot.className = 'source-dot ' + qualityClass;
        const deepUrl2 = src.deep_link_url || (src.source_url ? buildDeepSourceLink(src.source_url, src.current_value) : '');
        const labelText2 = qualityLabel || src.source_name || 'Unverified Source';
        tooltip.innerHTML = `<div class="sdt-label">${escapeHtml(labelText2)}</div>${deepUrl2 ? '<a class="sdt-url" href="' + escapeHtml(deepUrl2) + '" target="_blank" rel="noopener">View Source</a>' : ''}<div class="sdt-meta">Unverified${src.confidence_score ? ' &bull; ' + src.confidence_score + '% confidence' : ''}</div>`;
    } else {
        dot.className = 'source-dot dot-unlinked';
        tooltip.innerHTML = '<div class="sdt-label">Unverified</div><div class="sdt-meta">No source linked</div>';
    }
}

/**
 * v8.3.0: Map source url_quality field to the appropriate dot CSS class.
 * Falls back to the legacy verified/unverified/none classes when url_quality is absent.
 */
function _getQualityDotClass(src) {
    if (!src) return 'dot-unlinked';
    // Use new quality-based class if url_quality is present
    if (src.url_quality) {
        const q = src.url_quality;
        if (q === 'exact_page') return 'dot-exact';
        if (q === 'page_level') return 'dot-page';
        if (q === 'homepage_only') return 'dot-homepage';
        if (q === 'broken' || q === 'none') return 'dot-unlinked';
    }
    // Legacy fallback
    if (src.is_verified && src.source_url) return 'dot-verified';
    if (src.source_url || src.source_name) return 'dot-unverified';
    return 'dot-unlinked';
}

async function getVerificationSummary(competitorId) {
    try {
        return await fetchAPI(`/api/competitors/${competitorId}/verification-summary`);
    } catch (e) {
        return { total_fields: 0, verified_count: 0, verification_percentage: 0 };
    }
}

function renderVerificationBar(percent) {
    const p = Math.min(100, Math.max(0, Math.round(percent || 0)));
    const level = p >= 70 ? 'high' : p >= 40 ? 'medium' : 'low';
    return `<div class="verification-bar-wrapper"><div class="verification-bar"><div class="verification-bar-fill vb-${level}" style="width:${p}%"></div></div><span>${p}% verified</span></div>`;
}

function renderDataQualityBadge(percent) {
    const p = Math.min(100, Math.max(0, Math.round(percent || 0)));
    const level = p >= 70 ? 'high' : p >= 40 ? 'medium' : 'low';
    return `<span class="data-quality-badge quality-${level}">Based on ${p}% verified data</span>`;
}

function createSourcedValue(value, competitorId, fieldName, fallbackType = 'unknown') {
    // Always show N/A for missing values
    const displayValue = (!value || value === 'Unknown' || value === 'null' || value === '????' || value === '')
        ? 'N/A'
        : value;

    const cacheKey = `${competitorId}-${fieldName}`;
    const cached = typeof sourceCache !== 'undefined' ? sourceCache[cacheKey] : null;
    const manualEdit = manualEditCache[cacheKey];

    // Check if this field was manually edited and approved
    const isManuallyApproved = manualEdit?.status === 'approved';
    const valueClass = isManuallyApproved ? 'manual-approved-value' : '';

    return `<span class="data-value ${valueClass}" data-competitor="${competitorId}" data-field="${fieldName}">${displayValue}</span>`;
}

/**
 * Create a data field with clickable label that opens edit popup
 * @param {string} label - The field label (e.g., "Pricing")
 * @param {string|number} value - The data value
 * @param {number} competitorId - The competitor ID
 * @param {string} fieldName - The database field name
 * @returns {string} HTML string
 */
function createEditableDataField(label, value, competitorId, fieldName) {
    const displayValue = (!value || value === 'Unknown' || value === 'null' || value === '????' || value === '')
        ? 'N/A'
        : value;

    const cacheKey = `${competitorId}-${fieldName}`;
    const manualEdit = manualEditCache[cacheKey];
    const isManuallyApproved = manualEdit?.status === 'approved';
    const valueClass = isManuallyApproved ? 'manual-approved-value' : '';

    // Escape special characters for onclick
    const safeValue = String(displayValue).replace(/'/g, "\\'").replace(/"/g, "&quot;");

    return `
        <div class="editable-data-field">
            <span class="data-label clickable-label" onclick="openDataFieldPopup(${competitorId}, '${fieldName}', '${label}', '${safeValue}')">${label}:</span>
            <span class="data-value ${valueClass}" data-competitor="${competitorId}" data-field="${fieldName}">${displayValue}</span>
        </div>
    `;
}

/**
 * Open the data field edit popup
 */
async function openDataFieldPopup(competitorId, fieldName, label, currentValue) {
    // Get source info from cache or API
    const cacheKey = `${competitorId}-${fieldName}`;
    let sourceData = sourceCache[cacheKey] || {};

    // Try to load from API if not cached
    if (!sourceData.source_url) {
        try {
            const response = await fetchAPI(`/api/sources/${competitorId}`);
            if (response?.sources?.[fieldName]) {
                sourceData = response.sources[fieldName];
                sourceCache[cacheKey] = sourceData;
            }
        } catch (e) {
        }
    }

    const sourceUrl = sourceData.source_url || '';
    const sourceName = sourceData.source_name || 'Unknown';
    const sourceType = sourceData.source_type || 'unknown';

    // Check for pending edits
    const pendingEdit = manualEditCache[cacheKey];
    const hasPending = pendingEdit?.status === 'pending';

    const modal = document.getElementById('dataFieldModal');
    if (!modal) {
        createDataFieldModal();
    }

    document.getElementById('dfm-title').textContent = `Edit: ${label}`;
    document.getElementById('dfm-field-label').textContent = label;
    document.getElementById('dfm-competitor-id').value = competitorId;
    document.getElementById('dfm-field-name').value = fieldName;
    document.getElementById('dfm-current-value').textContent = currentValue === 'N/A' ? 'No data' : currentValue;
    document.getElementById('dfm-current-source').textContent = sourceUrl ? sourceName : 'No source recorded';
    document.getElementById('dfm-current-source-url').textContent = sourceUrl || 'N/A';
    document.getElementById('dfm-current-source-url').href = sourceUrl || '#';
    document.getElementById('dfm-new-value').value = currentValue === 'N/A' ? '' : currentValue;
    document.getElementById('dfm-new-source-url').value = sourceUrl || '';
    document.getElementById('dfm-value-type').value = isNaN(currentValue) ? 'text' : 'number';

    // Show pending status if exists
    const pendingBanner = document.getElementById('dfm-pending-banner');
    if (hasPending) {
        pendingBanner.style.display = 'block';
        pendingBanner.innerHTML = `<strong>⏳ Pending Change:</strong> "${pendingEdit.new_value}" awaiting admin approval`;
    } else {
        pendingBanner.style.display = 'none';
    }

    document.getElementById('dataFieldModal').style.display = 'flex';
}

/**
 * Create the data field edit modal (added to DOM once)
 */
function createDataFieldModal() {
    const modalHtml = `
        <div class="modal-overlay" id="dataFieldModal" style="display:none; z-index: 3000;" onclick="if(event.target===this)closeDataFieldModal()">
            <div class="modal data-field-modal">
                <div class="modal-header">
                    <h3 id="dfm-title">Edit Data Field</h3>
                    <button class="modal-close" onclick="closeDataFieldModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="dfm-pending-banner" class="pending-edit-banner" style="display:none;"></div>

                    <div class="dfm-section">
                        <h4>Current Value</h4>
                        <div class="dfm-current-info">
                            <div class="dfm-row">
                                <span class="dfm-label" id="dfm-field-label">Field</span>
                                <span class="dfm-value" id="dfm-current-value">—</span>
                            </div>
                            <div class="dfm-row">
                                <span class="dfm-label">Source</span>
                                <span class="dfm-value" id="dfm-current-source">Unknown</span>
                            </div>
                            <div class="dfm-row">
                                <span class="dfm-label">Source URL</span>
                                <a class="dfm-link" id="dfm-current-source-url" href="#" target="_blank">N/A</a>
                            </div>
                        </div>
                    </div>

                    <div class="dfm-section">
                        <h4>Update Value</h4>
                        <input type="hidden" id="dfm-competitor-id">
                        <input type="hidden" id="dfm-field-name">

                        <div class="dfm-form-row">
                            <label for="dfm-value-type">Value Type</label>
                            <select id="dfm-value-type" class="dfm-input">
                                <option value="text">Text</option>
                                <option value="number">Number</option>
                            </select>
                        </div>

                        <div class="dfm-form-row">
                            <label for="dfm-new-value">New Value</label>
                            <input type="text" id="dfm-new-value" class="dfm-input" placeholder="Enter new value...">
                        </div>

                        <div class="dfm-form-row">
                            <label for="dfm-new-source-url">Source URL</label>
                            <input type="url" id="dfm-new-source-url" class="dfm-input" placeholder="https://...">
                        </div>

                        <div class="dfm-form-row">
                            <label for="dfm-notes">Notes (optional)</label>
                            <textarea id="dfm-notes" class="dfm-input" rows="2" placeholder="Reason for change..."></textarea>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="closeDataFieldModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="saveDataFieldChange()">Save (Pending Approval)</button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

/**
 * Close the data field modal
 */
function closeDataFieldModal() {
    const modal = document.getElementById('dataFieldModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Save data field change (creates pending changelog entry)
 */
async function saveDataFieldChange() {
    const competitorId = document.getElementById('dfm-competitor-id').value;
    const fieldName = document.getElementById('dfm-field-name').value;
    const newValue = document.getElementById('dfm-new-value').value;
    const sourceUrl = document.getElementById('dfm-new-source-url').value;
    const valueType = document.getElementById('dfm-value-type').value;
    const notes = document.getElementById('dfm-notes').value;
    const currentValue = document.getElementById('dfm-current-value').textContent;

    if (!newValue.trim()) {
        showToast('Please enter a value', 'warning');
        return;
    }

    // Validate number type
    if (valueType === 'number' && isNaN(parseFloat(newValue))) {
        showToast('Please enter a valid number', 'warning');
        return;
    }

    try {
        const response = await fetchAPI('/api/data-changes/submit', {
            method: 'POST',
            body: JSON.stringify({
                competitor_id: parseInt(competitorId),
                field_name: fieldName,
                old_value: currentValue === 'No data' ? null : currentValue,
                new_value: valueType === 'number' ? parseFloat(newValue) : newValue,
                source_url: sourceUrl || null,
                notes: notes || null,
                value_type: valueType
            })
        });

        if (response?.success) {
            // Cache the pending change
            const cacheKey = `${competitorId}-${fieldName}`;
            manualEditCache[cacheKey] = {
                status: 'pending',
                new_value: newValue,
                source_url: sourceUrl
            };

            showToast('Change submitted for approval', 'success');
            closeDataFieldModal();
        } else {
            showToast(response?.message || 'Failed to submit change', 'error');
        }
    } catch (error) {
        showToast('Error submitting change: ' + error.message, 'error');
    }
}

/**
 * Get confidence level from numeric score
 */
function getConfidenceLevelFromScore(score) {
    if (score === null || score === undefined) return 'unknown';
    if (score >= 70) return 'high';
    if (score >= 40) return 'moderate';
    return 'low';
}

/**
 * Create confidence indicator HTML
 */
function createConfidenceIndicator(score, level, sourceType) {
    // If no score, derive a default based on source type
    if (score === null || score === undefined) {
        const defaultScores = {
            'sec_filing': 90,
            'api_verified': 80,
            'api': 75,
            'manual_verified': 70,
            'klas_report': 75,
            'website_scrape': 40,
            'manual': 50,
            'news_article': 45,
            'unknown': 30
        };
        score = defaultScores[sourceType] || 35;
        level = getConfidenceLevelFromScore(score);
    }

    const icons = {
        'high': '✓',
        'moderate': '~',
        'low': '!',
        'unknown': '?'
    };

    const tooltipText = `Confidence: ${score}/100 (${level})`;

    return `
        <span class="confidence-indicator-wrapper">
            <span class="confidence-indicator confidence-${level}" title="${tooltipText}">
                ${icons[level] || '?'}
            </span>
            <span class="confidence-tooltip">${tooltipText}</span>
        </span>
    `;
}

/**
 * Load and cache source data for a competitor
 * @param {number} competitorId - The competitor ID
 */
async function loadCompetitorSources(competitorId) {
    if (sourceCache[`loaded-${competitorId}`]) return;

    const sources = await fetchAPI(`/api/sources/${competitorId}`);
    if (sources && sources.sources) {
        Object.entries(sources.sources).forEach(([field, sourceData]) => {
            sourceCache[`${competitorId}-${field}`] = sourceData;
        });
        sourceCache[`loaded-${competitorId}`] = true;
    }
}

/**
 * Initialize source icons for visible competitor cards
 */
async function initSourceIcons() {
    const cards = document.querySelectorAll('.competitor-card');
    for (const card of cards) {
        const competitorId = card.dataset?.competitorId;
        if (competitorId) {
            await loadCompetitorSources(parseInt(competitorId));
        }
    }
}

/**
 * v7.2: Async-load verification bars for competitor cards
 */
async function _loadCompetitorVerificationBars(comps) {
    for (const comp of comps) {
        const container = document.getElementById(`verif-bar-${comp.id}`);
        if (!container) continue;
        const summary = await getVerificationSummary(comp.id);
        const pct = summary.percent || 0;
        container.innerHTML = renderVerificationBar(pct);
    }
}

/**
 * Get source info for a specific field via click
 */
async function showSourceInfo(competitorId, fieldName) {
    const source = await fetchAPI(`/api/sources/${competitorId}/${fieldName}`);
    if (!source) return;

    let content = '';
    switch (source.source_type) {
        case 'external':
            content = `
                <h3>Data Source</h3>
                <p><strong>Source:</strong> ${source.source_name || 'External'}</p>
                ${source.source_url ? `<p><a href="${source.source_url}" target="_blank">Open Source →</a></p>` : ''}
                <p><strong>Verified:</strong> ${source.verified_at ? new Date(source.verified_at).toLocaleString() : 'Not verified'}</p>
            `;
            break;
        case 'manual':
            content = `
                <h3>Manual Entry</h3>
                <p><strong>Entered by:</strong> ${source.entered_by || 'Unknown'}</p>
                <p><strong>Verified:</strong> ${source.verified_at ? new Date(source.verified_at).toLocaleString() : 'N/A'}</p>
            `;
            break;
        case 'calculated':
            content = `
                <h3>Calculated Value</h3>
                <p><strong>Formula:</strong></p>
                <pre style="background: #f0f4f8; padding: 10px; border-radius: 4px;">${source.formula || 'Unknown formula'}</pre>
            `;
            break;
        default:
            content = `
                <h3>Source Information</h3>
                <p>No source information recorded for this data point.</p>
                <p>Field: ${fieldName}</p>
            `;
    }

    showModal(content);
}

// ============== Analytics & Reports ==============

async function loadAnalytics() {
    // 1. Load data if needed
    if (!competitors || competitors.length === 0) {
        competitors = await fetchAPI('/api/competitors') || [];
    }

    // AR-002: Initialize LIVE Competitive Heatmap (Flagship Feature)
    if (typeof initAnalyticsPage === 'function') {
        await initAnalyticsPage();
    }

    // 2. Initial Matrix Render
    updatePositioningMatrix();

    // 3. Populate SWOT Dropdown
    const swotSelect = document.getElementById('swot-competitor-select');
    if (swotSelect) {
        swotSelect.innerHTML = '<option value="">Select a competitor...</option>';
        competitors.sort((a, b) => a.name.localeCompare(b.name)).forEach(c => {
            const option = document.createElement('option');
            option.value = c.id;
            option.textContent = c.name;
            swotSelect.appendChild(option);
        });
    }

    // 4. Render Trends (Mock for now, or based on history)
    renderMarketTrends();

    // Market Position Quadrant chart
    try {
        if (document.getElementById('marketQuadrantChart')) {
            renderMarketQuadrantChart();
        }
    } catch (e) { console.error('[Analytics] Market quadrant chart failed:', e); }

    // v7.2: Add data quality badge to analytics chart headers
    _addAnalyticsDataQualityBadges();

    // Win/Loss deal tracker
    try { await loadWinLossDeals(); } catch (e) { console.error('[Analytics] Win/loss load failed:', e); }
}

/**
 * v7.2: Fetch overall data quality and inject badges near analytics chart titles
 */
async function _addAnalyticsDataQualityBadges() {
    try {
        const qualityData = await fetchAPI('/api/data-quality/overview');
        const pct = qualityData?.overall_score || qualityData?.verified_percentage || 0;
        const badgeHtml = renderDataQualityBadge(pct);

        // Inject badge into the positioning matrix card header
        const matrixHeader = document.querySelector('#analyticsPage .card-header h3');
        if (matrixHeader && !matrixHeader.querySelector('.data-quality-badge')) {
            matrixHeader.insertAdjacentHTML('beforeend', badgeHtml);
        }
    } catch (e) {
    }
}

function updatePositioningMatrix() {
    const xAxis = document.getElementById('matrix-x-axis').value; // price, employees
    const yAxis = document.getElementById('matrix-y-axis').value; // satisfaction, market_presence

    const chartData = competitors.map(c => {
        let xVal = 0;
        let yVal = 0;
        let rVal = 5; // Default radius

        // X-Axis
        if (xAxis === 'price') {
            // Extract number from "$100/mo" or "Contact Sales"
            const price = c.base_price ? parseFloat(c.base_price.replace(/[^0-9.]/g, '')) : 0;
            xVal = isNaN(price) ? 0 : price;
        } else if (xAxis === 'employees') {
            const emp = c.employee_count ? parseInt(c.employee_count.replace(/[^0-9]/g, '')) : 0;
            xVal = isNaN(emp) ? 0 : emp;
        }

        // Y-Axis
        if (yAxis === 'satisfaction') {
            const rating = c.g2_rating ? parseFloat(c.g2_rating) : 0;
            yVal = isNaN(rating) ? 0 : rating;
        } else if (yAxis === 'market_presence') {
            // Proxy: News mentions + social following
            const news = c.news_mentions ? parseInt(c.news_mentions) : 0;
            yVal = news; // Simple proxy
        }

        // Radius (Market Share / Customer Count)
        const customers = c.customer_count ? parseInt(c.customer_count.replace(/[^0-9]/g, '')) : 100;
        rVal = Math.max(5, Math.min(30, Math.sqrt(customers) / 2));

        return {
            x: xVal,
            y: yVal,
            r: rVal,
            label: c.name,
            color: c.threat_level === 'High' ? 'rgba(220, 53, 69, 0.6)' :
                c.threat_level === 'Medium' ? 'rgba(255, 193, 7, 0.6)' :
                    'rgba(40, 167, 69, 0.6)',
            borderColor: c.threat_level === 'High' ? '#dc3545' :
                c.threat_level === 'Medium' ? '#ffc107' :
                    '#28a745'
        };
    });

    Visualizations.renderPositioningMatrix(
        'positioningMatrixChart',
        chartData,
        xAxis === 'price' ? 'Base Price ($)' : 'Employee Count',
        yAxis === 'satisfaction' ? 'G2 Rating (0-5)' : 'Market Presence (Mentions)'
    );
}

async function renderMarketTrends() {
    const canvas = document.getElementById('marketTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Destroy existing
    const existing = Chart.getChart('marketTrendChart');
    if (existing) existing.destroy();

    try {
        const response = await fetch(`${API_BASE}/api/analytics/trends`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });

        // Default data if fetch fails or is empty
        let chartData = {
            labels: [],
            datasets: []
        };

        if (response.ok) {
            chartData = await response.json();
            // Assign yAxisID to the New Competitors dataset (index 1 usually, based on backend)
            // Backend sends datasets. We need to ensure yAxisID is set correctly for the second dataset
            if (chartData.datasets && chartData.datasets.length > 1) {
                chartData.datasets[1].yAxisID = 'y1';
            }
        }

        new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true, // Average price shouldn't obscure variations, but starting at 0 is safer
                        title: { display: true, text: 'Price ($)' }
                    },
                    y1: {
                        position: 'right',
                        beginAtZero: true,
                        title: { display: true, text: 'New Competitors' },
                        grid: { drawOnChartArea: false } // Only draw grid for left axis
                    }
                }
            }
        });
    } catch (e) {
        console.error("Failed to load trends:", e);
    }
}

async function generateSWOT() {
    const select = document.getElementById('swot-competitor-select');
    const compId = select.value;
    if (!compId) return;

    const loading = document.getElementById('swot-loading');
    const content = document.getElementById('swot-content');
    const grid = content.querySelector('.swot-grid');

    loading.style.display = 'block';
    content.style.opacity = '0.5';

    try {
        const result = await fetchAPI('/api/agents/battlecard', {
            method: 'POST',
            body: JSON.stringify({ competitor_id: parseInt(compId), type: 'swot' })
        });

        if (result && result.swot) {
            const swot = result.swot;
            const renderList = (items) => {
                if (!items || items.length === 0) return '<li>No data available</li>';
                return items.map(i => `<li>${escapeHtml(String(i))}</li>`).join('');
            };

            grid.innerHTML = `
                <div class="swot-box strengths">
                    <h4>Strengths</h4>
                    <ul>${renderList(swot.strengths)}</ul>
                </div>
                <div class="swot-box weaknesses">
                    <h4>Weaknesses</h4>
                    <ul>${renderList(swot.weaknesses)}</ul>
                </div>
                <div class="swot-box opportunities">
                    <h4>Opportunities</h4>
                    <ul>${renderList(swot.opportunities)}</ul>
                </div>
                <div class="swot-box threats">
                    <h4>Threats</h4>
                    <ul>${renderList(swot.threats)}</ul>
                </div>
            `;

            // Add conversational chat widget below the SWOT grid
            let swotChatDiv = document.getElementById('swotChatWidget');
            if (!swotChatDiv) {
                swotChatDiv = document.createElement('div');
                swotChatDiv.id = 'swotChatWidget';
                content.appendChild(swotChatDiv);
            }
            createChatWidget('swotChatWidget', {
                pageContext: 'analytics_swot_' + compId,
                competitorId: parseInt(compId),
                placeholder: 'Ask follow-up questions about this SWOT analysis...',
                endpoint: '/api/analytics/chat'
            });
        } else {
            grid.innerHTML = '<p class="placeholder-text" style="padding:20px;text-align:center;">Select a competitor and click to generate a SWOT analysis using AI.</p>';
        }

    } catch (e) {
        grid.innerHTML = '<p class="placeholder-text" style="padding:20px;text-align:center;">SWOT generation failed. Please check your AI configuration and try again.</p>';
        showToast("Error generating SWOT: " + e.message, 'error');
    } finally {
        loading.style.display = 'none';
        content.style.opacity = '1';
    }
}

function downloadExecutiveReport() {
    // Use Excel export for comprehensive data download
    window.open(`${API_BASE}/api/export/excel`, '_blank');
    showToast("Generating Excel report... Download will start shortly.", "info");
}

// ==============================================================================
// AI BACKGROUND TASK NOTIFICATION SYSTEM (v7.2.0)
// ==============================================================================

/**
 * Manages background AI task notifications.
 * Polls the backend for pending tasks and shows toast + badge when tasks complete.
 */
const AINotificationManager = {
    _pollInterval: null,
    _knownTasks: {},  // {task_id: last_known_status}

    /** Start polling for background AI task updates every 5 seconds */
    startPolling() {
        if (this._pollInterval) return;
        this._pollInterval = setInterval(() => this.poll(), 5000);
        this.poll();  // Immediate first poll
    },

    /** Stop polling */
    stopPolling() {
        if (this._pollInterval) {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
        }
    },

    /** Poll the backend for pending AI tasks */
    async poll() {
        try {
            const tasks = await fetchAPI('/api/ai/tasks/pending', { silent: true });
            if (!tasks || !Array.isArray(tasks)) return;

            // Check for newly completed tasks (were running, now completed)
            for (const task of tasks) {
                const prev = this._knownTasks[task.task_id];
                if (prev === 'running' && task.status === 'completed') {
                    this._showCompletionToast(task);
                }
                this._knownTasks[task.task_id] = task.status;
            }

            this._updateBadge(tasks);
            this._renderPanel(tasks);
        } catch (e) {
            // Silent fail - don't spam console for polling failures
        }
    },

    /** Show a toast when an AI task completes */
    _showCompletionToast(task) {
        const label = this._getTaskLabel(task.task_type);
        const pageContext = task.page_context || 'dashboard';
        showToast(`AI ${label} is ready! Click to view.`, 'success', {
            duration: 8000,
            className: 'toast-ai-ready',
            onClick: () => {
                showPage(pageContext);
                this.markRead(task.task_id);
            }
        });
    },

    /** Get human-readable label for a task type */
    _getTaskLabel(taskType) {
        if (!taskType) return 'Task';
        if (taskType.startsWith('battlecard_')) return 'Battlecard';
        if (taskType.startsWith('swot_')) return 'SWOT Analysis';
        const labels = {
            'executive_summary': 'Executive Summary',
            'news_summary': 'News Summary',
            'discovery_pipeline': 'Discovery',
            'ai_news_fetch': 'News Fetch',
        };
        return labels[taskType] || 'Task';
    },

    /** Get icon for task type */
    _getTaskIcon(taskType) {
        if (!taskType) return '&#9889;';
        if (taskType.startsWith('battlecard_')) return '&#9876;';
        if (taskType.startsWith('swot_')) return '&#128200;';
        const icons = {
            'executive_summary': '&#128202;',
            'news_summary': '&#128240;',
            'discovery_pipeline': '&#128269;',
            'ai_news_fetch': '&#128225;',
        };
        return icons[taskType] || '&#9889;';
    },

    /** Update the badge count */
    _updateBadge(tasks) {
        const countEl = document.getElementById('aiNotifCount');
        if (!countEl) return;
        const unread = tasks.filter(t => t.status === 'completed' && !t.read_at).length;
        const running = tasks.filter(t => t.status === 'running').length;
        const total = unread + running;
        if (total > 0) {
            countEl.textContent = total;
            countEl.classList.add('visible');
        } else {
            countEl.classList.remove('visible');
        }
    },

    /** Render the notification panel dropdown */
    _renderPanel(tasks) {
        const listEl = document.getElementById('aiNotifList');
        if (!listEl) return;

        if (!tasks.length) {
            listEl.innerHTML = '<div class="ai-notif-empty">No background AI tasks</div>';
            return;
        }

        listEl.innerHTML = tasks.map(t => {
            const label = this._getTaskLabel(t.task_type);
            const icon = this._getTaskIcon(t.task_type);
            const isUnread = t.status === 'completed' && !t.read_at;
            const timeAgo = this._timeAgo(t.started_at);
            return `<div class="ai-notif-item ${isUnread ? 'unread' : ''}"
                onclick="AINotificationManager.handleNotifClick('${t.task_id}', '${t.page_context || 'dashboard'}')">
                <span class="ai-notif-icon">${icon}</span>
                <div class="ai-notif-body">
                    <div class="ai-notif-title">${label}</div>
                    <div class="ai-notif-time">${timeAgo}</div>
                </div>
                <span class="ai-notif-status ${t.status}">${t.status}</span>
            </div>`;
        }).join('');
    },

    /** Handle clicking a notification item */
    handleNotifClick(taskId, pageContext) {
        this.markRead(taskId);
        showPage(pageContext);
        // Close the panel
        const panel = document.getElementById('aiNotifPanel');
        if (panel) panel.classList.remove('active');
    },

    /** Mark a single task as read */
    async markRead(taskId) {
        try {
            await fetchAPI(`/api/ai/tasks/${taskId}/read`, {
                method: 'PUT',
                silent: true
            });
            delete this._knownTasks[taskId];
            this.poll();
        } catch (e) {
            console.error('Failed to mark AI task read:', e);
        }
    },

    /** Mark all notifications as read */
    async markAllRead() {
        try {
            const tasks = await fetchAPI('/api/ai/tasks/pending', { silent: true });
            if (!tasks || !Array.isArray(tasks)) return;
            for (const t of tasks) {
                if (t.status === 'completed' && !t.read_at) {
                    await fetchAPI(`/api/ai/tasks/${t.task_id}/read`, {
                        method: 'PUT',
                        silent: true
                    });
                }
            }
            this._knownTasks = {};
            this.poll();
        } catch (e) {
            console.error('Failed to mark all AI tasks read:', e);
        }
    },

    /** Simple time-ago formatter */
    _timeAgo(isoStr) {
        if (!isoStr) return '';
        const diff = Date.now() - new Date(isoStr + 'Z').getTime();
        const seconds = Math.floor(diff / 1000);
        if (seconds < 60) return 'just now';
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        return `${Math.floor(hours / 24)}d ago`;
    }
};

/** Toggle the AI notification panel dropdown */
function toggleAINotificationPanel() {
    const panel = document.getElementById('aiNotifPanel');
    if (panel) panel.classList.toggle('active');
}

/** Mark all AI notifications as read (called from panel header button) */
function markAllAINotificationsRead() {
    AINotificationManager.markAllRead();
}

// Close AI notification panel when clicking outside
document.addEventListener('click', (e) => {
    const bell = document.getElementById('aiNotifBell');
    const panel = document.getElementById('aiNotifPanel');
    if (bell && panel && !bell.contains(e.target) && !panel.contains(e.target)) {
        panel.classList.remove('active');
    }
});

// Start AI notification polling on page load
AINotificationManager.startPolling();

/**
 * Run an AI call with automatic page-leave detection (v7.2.0).
 *
 * If the user navigates away from startPage before the call completes,
 * the result is saved as a background notification instead of rendered.
 *
 * @param {Function} apiCall - async function that performs the API call
 * @param {string} pageContext - page name (e.g. 'dashboard', 'battlecards')
 * @param {Function} onComplete - callback to render result if still on same page
 * @returns {*} the API result, or null if user navigated away
 */
async function runAIWithPageDetection(apiCall, pageContext, onComplete) {
    // Determine current page from the active nav item
    const startNav = document.querySelector('.nav-item.active');
    const startPage = startNav ? startNav.getAttribute('data-page') : null;

    try {
        const result = await apiCall();
        // Check if user is still on the same page
        const currentNav = document.querySelector('.nav-item.active');
        const currentPageNow = currentNav ? currentNav.getAttribute('data-page') : null;

        if (currentPageNow === startPage) {
            // User still on same page - render normally
            if (onComplete) onComplete(result);
        } else {
            // User navigated away - store as local notification
            AINotificationManager._knownTasks['local-' + Date.now()] = 'completed';
            AINotificationManager.poll();
            showToast('AI result ready! Check the AI Tasks bell.', 'info');
        }
        return result;
    } catch (e) {
        showToast('AI generation failed: ' + (e.message || 'Unknown error'), 'error');
        return null;
    }
}

// Export to window for global access
window.AINotificationManager = AINotificationManager;
window.toggleAINotificationPanel = toggleAINotificationPanel;
window.markAllAINotificationsRead = markAllAINotificationsRead;
window.runAIWithPageDetection = runAIWithPageDetection;


// ============== Notifications ==============

async function loadNotifications() {
    try {
        const notifications = await fetchAPI('/api/notifications?limit=5', { silent: true });
        const list = document.getElementById('notificationList');
        const badge = document.getElementById('notificationBadge');

        if (!notifications || notifications.length === 0) {
            list.innerHTML = '<div class="notification-empty">No new alerts</div>';
            badge.style.display = 'none';
            return;
        }

        // Update badge
        badge.innerText = notifications.length;
        badge.style.display = 'flex';

        // Render items
        list.innerHTML = notifications.map(n => `
            <div class="notification-item ${n.type || 'info'}">
                <div class="notif-header">
                    <span class="notif-comp">${escapeHtml(n.title || 'Alert')}</span>
                    <span class="notif-time">${n.timestamp ? new Date(n.timestamp).toLocaleDateString() : ''}</span>
                </div>
                <div class="notif-body">
                    ${escapeHtml(n.message || '')}
                </div>
            </div>
        `).join('');

    } catch (e) {
        console.error("Error loading notifications:", e);
    }
}

function toggleNotifications() {
    const dropdown = document.getElementById('notificationDropdown');
    dropdown.classList.toggle('active');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const container = document.querySelector('.notification-container');
    const dropdown = document.getElementById('notificationDropdown');
    if (container && !container.contains(e.target) && dropdown.classList.contains('active')) {
        dropdown.classList.remove('active');
    }
});

// Init Notifications
window._notificationIntervalId = setInterval(loadNotifications, 60000); // Poll every minute
loadNotifications(); // Initial load

// ============== Threat Criteria Settings ==============

async function showThreatCriteriaModal() {
    showModal(`
        <div style="text-align: center; padding: 20px;">
            <div class="ai-spinner" style="font-size: 24px;">⏳</div>
            <p>Loading current criteria...</p>
        </div>
    `);

    try {
        const criteria = await fetchAPI('/api/settings/threat-criteria');

        const content = `
            <h2>⚠️ Configure Threat Level Criteria</h2>
            <p style="color: #64748b; margin-bottom: 20px;">
                Define the rules the AI uses to classify competitors. 
                Updating these will trigger a re-analysis of all competitors.
            </p>
            
            <form id="threatCriteriaForm" onsubmit="saveThreatCriteria(event)">
                <div class="form-group">
                    <label style="color: #dc2626; font-weight: 600;">High Threat Criteria</label>
                    <textarea name="high_threat_criteria" rows="3" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px;">${criteria.high || ''}</textarea>
                    <small style="color: #64748b;">Direct competitors causing immediate revenue loss.</small>
                </div>
                
                <div class="form-group" style="margin-top: 16px;">
                    <label style="color: #d97706; font-weight: 600;">Medium Threat Criteria</label>
                    <textarea name="medium_threat_criteria" rows="3" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px;">${criteria.medium || ''}</textarea>
                    <small style="color: #64748b;">Emerging competitors or partial overlap.</small>
                </div>
                
                <div class="form-group" style="margin-top: 16px;">
                    <label style="color: #059669; font-weight: 600;">Low Threat Criteria</label>
                    <textarea name="low_threat_criteria" rows="3" style="width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px;">${criteria.low || ''}</textarea>
                    <small style="color: #64748b;">Indirect or different market focus.</small>
                </div>
                
                <div style="margin-top: 24px; display: flex; justify-content: flex-end; gap: 12px;">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary" style="background: linear-gradient(135deg, #122753 0%, #1E3A75 100%);">
                        💾 Save & Re-Classify
                    </button>
                </div>
            </form>
        `;

        showModal(content);

    } catch (e) {
        showModal(`<div style="color: red;">Error loading settings: ${e.message}</div>`);
    }
}

async function saveThreatCriteria(event) {
    event.preventDefault();
    const form = event.target;
    // Show saving state
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.innerHTML = '⏳ Saving...';
    submitBtn.disabled = true;

    const data = {
        high_threat_criteria: form.high_threat_criteria.value,
        medium_threat_criteria: form.medium_threat_criteria.value,
        low_threat_criteria: form.low_threat_criteria.value
    };

    try {
        const result = await fetchAPI('/api/settings/threat-criteria', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        showToast(result.message || 'Criteria saved successfully', 'success');
        closeModal();

        // Optional: show a banner that re-classification is in progress
        showToast("AI is re-analyzing competitors in the background...", "info");

    } catch (e) {
        showToast('Error saving criteria: ' + e.message, 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}
// ============== User Management ==============

let _currentTeamId = null;
let _userTeams = [];

const TEAM_ROLE_COLORS = {
    owner: { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', label: 'Owner' },
    admin: { bg: 'rgba(59, 130, 246, 0.15)', color: '#3b82f6', label: 'Admin' },
    member: { bg: 'rgba(100, 116, 139, 0.15)', color: '#94a3b8', label: 'Member' },
    viewer: { bg: 'rgba(100, 116, 139, 0.15)', color: '#94a3b8', label: 'Viewer' },
    analyst: { bg: 'rgba(139, 92, 246, 0.15)', color: '#8b5cf6', label: 'Analyst' }
};

async function loadTeam() {
    const list = document.getElementById('teamList');
    if (!list) return;

    list.innerHTML = '<div class="loading">Loading team...</div>';

    try {
        // Load teams the user belongs to
        const teams = await fetchAPI('/api/teams', { silent: true }).catch(() => []);
        _userTeams = teams || [];

        // Render team selector if multiple teams
        const selectorEl = document.getElementById('teamSelector');
        if (selectorEl) {
            if (_userTeams.length > 1) {
                selectorEl.style.display = 'block';
                let opts = _userTeams.map(t =>
                    `<option value="${t.id}" ${t.id === _currentTeamId ? 'selected' : ''}>${escapeHtml(t.name)} (${t.member_count || 0} members)</option>`
                ).join('');
                selectorEl.innerHTML = `<select class="form-control form-control-sm team-selector-dropdown" onchange="switchTeam(this.value)">${opts}</select>`;
                if (!_currentTeamId && _userTeams.length > 0) _currentTeamId = _userTeams[0].id;
            } else if (_userTeams.length === 1) {
                selectorEl.style.display = 'block';
                _currentTeamId = _userTeams[0].id;
                selectorEl.innerHTML = `<span class="team-name-badge">${escapeHtml(_userTeams[0].name)}</span>`;
            } else {
                selectorEl.style.display = 'none';
            }
        }

        // If user has a team, load team members from team endpoint
        if (_currentTeamId) {
            const members = await fetchAPI(`/api/teams/${_currentTeamId}/members`, { silent: true }).catch(() => []);
            if (members && members.length > 0) {
                renderTeamMembers(list, members);
                return;
            }
        }

        // Fallback: load users from /api/users
        const users = await fetchAPI('/api/users');
        if (!users || users.length === 0) {
            list.innerHTML = '<p style="color: var(--text-secondary);">No team members found. Invite someone to get started.</p>';
            return;
        }

        renderTeamMembersFromUsers(list, users);
    } catch (e) {
        list.innerHTML = '<p style="color: var(--danger-color);">Unable to load team members.</p>';
    }
}

function renderTeamMembers(container, members) {
    container.innerHTML = `
        <table class="team-members-table">
            <thead>
                <tr>
                    <th>Member</th>
                    <th>Role</th>
                    <th>Joined</th>
                    <th style="text-align:right">Actions</th>
                </tr>
            </thead>
            <tbody>
                ${members.map(m => {
                    const roleConf = TEAM_ROLE_COLORS[m.role] || TEAM_ROLE_COLORS.member;
                    const joined = m.joined_at ? new Date(m.joined_at).toLocaleDateString() : 'N/A';
                    const isOwner = m.role === 'owner';
                    return `<tr>
                        <td>
                            <div class="team-member-info">
                                <div class="team-member-avatar">${escapeHtml((m.full_name || m.email || '?').charAt(0).toUpperCase())}</div>
                                <div>
                                    <div class="team-member-name">${escapeHtml(m.full_name || 'No Name')}</div>
                                    <div class="team-member-email">${escapeHtml(m.email || m.user_email || '')}</div>
                                </div>
                            </div>
                        </td>
                        <td><span class="team-role-badge" style="background:${roleConf.bg};color:${roleConf.color};">${escapeHtml(roleConf.label)}</span></td>
                        <td style="color: var(--text-secondary); font-size: 13px;">${joined}</td>
                        <td style="text-align:right">
                            ${!isOwner ? `<button class="btn btn-sm btn-icon" onclick="removeTeamMember(${_currentTeamId}, ${m.user_id})" title="Remove Member" style="color: var(--danger-color);">&#128465;</button>` : ''}
                        </td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

function renderTeamMembersFromUsers(container, users) {
    container.innerHTML = `
        <table class="team-members-table">
            <thead>
                <tr>
                    <th>Member</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th style="text-align:right">Actions</th>
                </tr>
            </thead>
            <tbody>
                ${users.map(u => {
                    const roleConf = TEAM_ROLE_COLORS[u.role] || TEAM_ROLE_COLORS.member;
                    return `<tr>
                        <td>
                            <div class="team-member-info">
                                <div class="team-member-avatar">${escapeHtml((u.full_name || u.email || '?').charAt(0).toUpperCase())}</div>
                                <div>
                                    <div class="team-member-name">${escapeHtml(u.full_name || 'No Name')}</div>
                                    <div class="team-member-email">${escapeHtml(u.email || '')}</div>
                                </div>
                            </div>
                        </td>
                        <td><span class="team-role-badge" style="background:${roleConf.bg};color:${roleConf.color};">${escapeHtml(roleConf.label)}</span></td>
                        <td>${u.is_active ? '<span style="color: var(--success-color);">Active</span>' : '<span style="color: var(--text-light);">Inactive</span>'}</td>
                        <td style="text-align:right">
                            <button class="btn btn-sm btn-icon" onclick="deleteUser(${u.id})" title="Remove User" style="color: var(--danger-color);">&#128465;</button>
                        </td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

function switchTeam(teamId) {
    _currentTeamId = parseInt(teamId);
    loadTeam();
    loadTeamActivity();
}

async function removeTeamMember(teamId, userId) {
    if (!confirm('Remove this member from the team?')) return;
    try {
        await fetchAPI(`/api/teams/${teamId}/members/${userId}`, { method: 'DELETE' });
        showToast('Member removed', 'success');
        loadTeam();
    } catch (e) {
        showToast('Failed to remove member', 'error');
    }
}

function showCreateTeamModal() {
    showModal(`
        <h3>Create New Team</h3>
        <form id="createTeamForm" onsubmit="handleCreateTeam(event)">
            <div class="form-group">
                <label>Team Name</label>
                <input type="text" name="name" class="form-control" required placeholder="e.g. Competitive Intel Team">
            </div>
            <div class="form-group">
                <label>Description (Optional)</label>
                <textarea name="description" class="form-control" rows="2" placeholder="Brief team description"></textarea>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Create Team</button>
            </div>
        </form>
    `);
}

async function handleCreateTeam(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Creating...';

    try {
        const result = await fetchAPI('/api/teams', {
            method: 'POST',
            body: JSON.stringify({
                name: form.name.value.trim(),
                description: form.description.value.trim() || null
            })
        });
        if (result?.id) {
            _currentTeamId = result.id;
            closeModal();
            showToast('Team created', 'success');
            loadTeam();
            loadTeamActivity();
        }
    } catch (err) {
        showToast('Failed to create team', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create Team';
    }
}

function showInviteUserModal() {
    showModal(`
        <h3>Invite Team Member</h3>
        <form id="inviteUserForm" onsubmit="handleInviteUser(event)">
            <div class="form-group">
                <label>Email Address</label>
                <input type="email" name="email" class="form-control" required placeholder="colleague@company.com">
            </div>
            <div class="form-group">
                <label>Full Name (Optional)</label>
                <input type="text" name="full_name" class="form-control" placeholder="John Doe">
            </div>
            <div class="form-group">
                <label>Role</label>
                <select name="role" class="form-control">
                    <option value="viewer">Viewer (Read-only)</option>
                    <option value="analyst">Analyst (Can edit)</option>
                    <option value="admin">Admin (Full access)</option>
                </select>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Send Invite</button>
            </div>
        </form>
    `);
}

async function handleInviteUser(e) {
    e.preventDefault();
    const form = e.target;
    const btn = form.querySelector('button[type="submit"]');
    const originalText = btn.innerText;

    btn.innerText = 'Sending...';
    btn.disabled = true;

    const data = {
        email: form.email.value,
        full_name: form.full_name.value,
        role: form.role.value
    };

    try {
        const result = await fetchAPI('/api/users/invite', {
            method: 'POST',
            body: JSON.stringify(data)
        });

        if (result) {
            closeModal();
            if (result.email_sent) {
                showToast('User invited! Email sent with login credentials.', 'success');
            } else {
                // Show credentials since email wasn't sent
                showModal(`
                    <h3>✅ User Created Successfully</h3>
                    <p>Email could not be sent (SMTP not configured). Please share these credentials manually:</p>
                    <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p><strong>Email:</strong> ${data.email}</p>
                        <p><strong>Temporary Password:</strong> <code style="background: #e5e7eb; padding: 2px 8px; border-radius: 4px;">Welcome123!</code></p>
                        <p><strong>Role:</strong> ${data.role}</p>
                    </div>
                    <p style="color: #666; font-size: 12px;">The user should change their password after first login.</p>
                    <button class="btn btn-primary" onclick="closeModal()" style="margin-top: 10px;">Got it</button>
                `);
            }
            loadTeam();
        }
    } catch (err) {
        showToast('Error inviting user: ' + err.message, 'error');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to remove this user?')) return;

    try {
        await fetchAPI(`/api/users/${userId}`, { method: 'DELETE' });
        showToast('User removed', 'success');
        loadTeam();
    } catch (e) {
        showToast('Error removing user: ' + e.message, 'error');
    }
}

// ==============================================================================
// Team Collaboration & Annotations
// ==============================================================================

const ANNOTATION_TYPE_CONFIG = {
    note: { label: 'Note', color: '#3b82f6', bg: '#eff6ff' },
    insight: { label: 'Insight', color: '#8b5cf6', bg: '#f5f3ff' },
    warning: { label: 'Warning', color: '#f59e0b', bg: '#fffbeb' },
    opportunity: { label: 'Opportunity', color: '#10b981', bg: '#ecfdf5' },
    action_item: { label: 'Action Item', color: '#ef4444', bg: '#fef2f2' }
};

const PRIORITY_CONFIG = {
    low: { label: 'Low', color: '#64748b' },
    normal: { label: 'Normal', color: '#3b82f6' },
    high: { label: 'High', color: '#f59e0b' },
    critical: { label: 'Critical', color: '#ef4444' }
};

/**
 * Load annotations for a competitor (used in battlecard modal)
 */
async function loadAnnotations(competitorId, typeFilter) {
    const container = document.getElementById(`annotationsList_${competitorId}`);
    if (!container) return;

    try {
        let url = `/api/teams/annotations/competitor/${competitorId}`;
        if (typeFilter) url += `?annotation_type=${typeFilter}`;

        const annotations = await fetchAPI(url, { silent: true });

        if (!annotations || annotations.length === 0) {
            container.innerHTML = '<p style="color: #94a3b8; font-size: 13px; text-align: center; padding: 12px;">No annotations yet. Be the first to add a note.</p>';
            return;
        }

        container.innerHTML = annotations.map(a => {
            const typeConf = ANNOTATION_TYPE_CONFIG[a.annotation_type] || ANNOTATION_TYPE_CONFIG.note;
            const prioConf = PRIORITY_CONFIG[a.priority] || PRIORITY_CONFIG.normal;
            const date = a.created_at ? new Date(a.created_at).toLocaleDateString() : '';
            const pinIcon = a.is_pinned ? '<span title="Pinned" style="color: #f59e0b; margin-right: 4px;">&#128204;</span>' : '';

            return `<div class="annotation-item" style="padding: 10px; margin-bottom: 8px; background: white; border-radius: 8px; border: 1px solid #e2e8f0; border-left: 3px solid ${typeConf.color};">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
                    <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
                        ${pinIcon}
                        <span style="padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; background: ${typeConf.bg}; color: ${typeConf.color};">${escapeHtml(typeConf.label)}</span>
                        ${a.priority !== 'normal' ? `<span style="font-size: 10px; color: ${prioConf.color}; font-weight: 600;">${escapeHtml(prioConf.label)}</span>` : ''}
                        ${a.title ? `<span style="font-weight: 600; font-size: 13px; color: #1e293b;">${escapeHtml(a.title)}</span>` : ''}
                    </div>
                    <div style="display: flex; gap: 4px;">
                        <button onclick="toggleAnnotationPin(${a.id}, ${competitorId})" title="Toggle Pin" style="border: none; background: none; cursor: pointer; font-size: 12px; padding: 2px 4px; color: #94a3b8;">${a.is_pinned ? '&#128204;' : '&#128392;'}</button>
                        <button onclick="deleteAnnotation(${a.id}, ${competitorId})" title="Delete" style="border: none; background: none; cursor: pointer; font-size: 12px; padding: 2px 4px; color: #94a3b8;">&#128465;</button>
                    </div>
                </div>
                <p style="margin: 4px 0 6px; font-size: 13px; color: #334155; line-height: 1.5;">${escapeHtml(a.content)}</p>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 11px; color: #94a3b8;">${escapeHtml(a.user_name || a.user_email || 'Unknown')} &middot; ${date}</span>
                    <button onclick="toggleReplies(${a.id}, ${competitorId})" style="border: none; background: none; cursor: pointer; font-size: 11px; color: #3b82f6;">${a.replies_count > 0 ? a.replies_count + ' replies' : 'Reply'}</button>
                </div>
                <div id="replies_${a.id}" style="display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid #e2e8f0;"></div>
            </div>`;
        }).join('');

    } catch (error) {
        console.error('Load annotations error:', error);
        container.innerHTML = '<p style="color: #94a3b8; font-size: 13px; text-align: center; padding: 12px;">Unable to load annotations.</p>';
    }
}

function filterAnnotations(competitorId) {
    const filter = document.getElementById(`annotationFilterType_${competitorId}`)?.value || '';
    loadAnnotations(competitorId, filter || undefined);
}

function toggleAnnotationForm(competitorId) {
    const form = document.getElementById(`annotationForm_${competitorId}`);
    if (form) form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function submitAnnotation(competitorId) {
    const title = (document.getElementById(`annotationTitle_${competitorId}`)?.value || '').trim();
    const content = (document.getElementById(`annotationContent_${competitorId}`)?.value || '').trim();
    const type = document.getElementById(`annotationType_${competitorId}`)?.value || 'note';
    const priority = document.getElementById(`annotationPriority_${competitorId}`)?.value || 'normal';

    if (!content) { showToast('Please enter annotation content', 'warning'); return; }

    try {
        const result = await fetchAPI('/api/teams/annotations', {
            method: 'POST',
            body: JSON.stringify({
                competitor_id: competitorId,
                title: title || null,
                content,
                annotation_type: type,
                priority,
                is_public: true
            })
        });

        if (result?.id) {
            showToast('Annotation saved', 'success');
            toggleAnnotationForm(competitorId);
            loadAnnotations(competitorId);
        } else {
            showToast('Failed to save annotation', 'error');
        }
    } catch (error) {
        console.error('Submit annotation error:', error);
        showToast('Failed to save annotation', 'error');
    }
}

async function toggleAnnotationPin(annotationId, competitorId) {
    try {
        await fetchAPI(`/api/teams/annotations/${annotationId}/pin`, { method: 'POST' });
        loadAnnotations(competitorId);
    } catch (error) {
        showToast('Failed to toggle pin', 'error');
    }
}

async function deleteAnnotation(annotationId, competitorId) {
    if (!confirm('Delete this annotation?')) return;
    try {
        await fetchAPI(`/api/teams/annotations/${annotationId}`, { method: 'DELETE' });
        showToast('Annotation deleted', 'success');
        loadAnnotations(competitorId);
    } catch (error) {
        showToast('Failed to delete annotation', 'error');
    }
}

async function toggleReplies(annotationId, competitorId) {
    const container = document.getElementById(`replies_${annotationId}`);
    if (!container) return;

    if (container.style.display !== 'none') {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    container.innerHTML = '<p style="color: #94a3b8; font-size: 12px;">Loading replies...</p>';

    try {
        const replies = await fetchAPI(`/api/teams/annotations/${annotationId}/replies`, { silent: true });

        let html = (replies || []).map(r => {
            const date = r.created_at ? new Date(r.created_at).toLocaleDateString() : '';
            return `<div style="padding: 6px 0; border-bottom: 1px solid #f1f5f9;">
                <p style="margin: 0 0 2px; font-size: 12px; color: #334155;">${escapeHtml(r.content)}</p>
                <span style="font-size: 10px; color: #94a3b8;">${escapeHtml(r.user_name || r.user_email || 'Unknown')} &middot; ${date}</span>
            </div>`;
        }).join('');

        html += `<div style="margin-top: 8px; display: flex; gap: 6px;">
            <input type="text" id="replyInput_${annotationId}" placeholder="Write a reply..." style="flex: 1; padding: 4px 8px; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 4px; color: #1e293b;">
            <button onclick="submitReply(${annotationId}, ${competitorId})" class="btn btn-sm btn-primary" style="padding: 4px 10px; font-size: 11px;">Reply</button>
        </div>`;

        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<p style="color: #94a3b8; font-size: 12px;">Unable to load replies.</p>';
    }
}

async function submitReply(annotationId, competitorId) {
    const input = document.getElementById(`replyInput_${annotationId}`);
    const content = (input?.value || '').trim();
    if (!content) return;

    try {
        await fetchAPI(`/api/teams/annotations/${annotationId}/replies`, {
            method: 'POST',
            body: JSON.stringify({ content })
        });
        input.value = '';
        toggleReplies(annotationId, competitorId);
        toggleReplies(annotationId, competitorId); // re-open to refresh
        loadAnnotations(competitorId); // refresh reply count
    } catch (error) {
        showToast('Failed to post reply', 'error');
    }
}

/**
 * Load team activity feed (for Settings > Team Management)
 */
async function loadTeamActivity(limit) {
    const container = document.getElementById('teamActivityFeed');
    if (!container) return;

    const fetchLimit = limit || 10;

    try {
        const teamId = _currentTeamId || (_userTeams.length > 0 ? _userTeams[0].id : null);
        if (!teamId) {
            // Fallback: try to fetch teams
            const teams = await fetchAPI('/api/teams', { silent: true }).catch(() => []);
            if (!teams || teams.length === 0) {
                container.innerHTML = '<p style="color: var(--text-light); font-size: 13px; padding: 8px;">No team activity yet. Create a team to get started.</p>';
                return;
            }
        }

        const resolvedId = _currentTeamId || (_userTeams.length > 0 ? _userTeams[0].id : null);
        if (!resolvedId) {
            container.innerHTML = '<p style="color: var(--text-light); font-size: 13px; padding: 8px;">No team activity yet.</p>';
            return;
        }

        const activities = await fetchAPI(`/api/teams/${resolvedId}/activity?limit=${fetchLimit}`, { silent: true });

        if (!activities || activities.length === 0) {
            container.innerHTML = '<p style="color: var(--text-light); font-size: 13px; padding: 8px;">No recent activity.</p>';
            return;
        }

        const ACTIVITY_BADGES = {
            annotation: { label: 'Annotation', color: '#8b5cf6' },
            reply: { label: 'Reply', color: '#3b82f6' },
            member_added: { label: 'Member Added', color: '#10b981' },
            member_removed: { label: 'Member Removed', color: '#f59e0b' },
            team_created: { label: 'Team Created', color: '#10b981' }
        };

        container.innerHTML = activities.map(a => {
            const date = a.created_at ? new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
            const details = a.activity_details || {};
            let desc = a.activity_type;
            if (a.activity_type === 'annotation') {
                desc = `added a ${details.type || 'note'}${details.title ? ': ' + details.title : ''}`;
            } else if (a.activity_type === 'reply') {
                desc = 'replied to an annotation';
            } else if (a.activity_type === 'member_added') {
                desc = 'added a new member';
            } else if (a.activity_type === 'member_removed') {
                desc = 'removed a member';
            }
            const badge = ACTIVITY_BADGES[a.activity_type] || { label: a.activity_type, color: '#64748b' };
            const compName = a.competitor_name ? ` on <strong>${escapeHtml(a.competitor_name)}</strong>` : '';
            return `<div class="team-activity-item">
                <div class="team-activity-left">
                    <span class="team-activity-badge" style="color:${badge.color};border-color:${badge.color};">${escapeHtml(badge.label)}</span>
                    <span style="color: var(--text-primary); font-weight: 500;">${escapeHtml(a.user_email)}</span>
                    <span style="color: var(--text-secondary);"> ${desc}${compName}</span>
                </div>
                <span class="team-activity-time">${date}</span>
            </div>`;
        }).join('');

        // Show/hide "View More" button
        const moreBtn = document.getElementById('teamActivityMore');
        if (moreBtn) {
            moreBtn.style.display = activities.length >= fetchLimit ? 'block' : 'none';
        }
    } catch (error) {
        container.innerHTML = '<p style="color: var(--text-light); font-size: 13px;">Unable to load activity.</p>';
    }
}

// ==============================================================================
// Competitor Detail — Annotations Tab
// ==============================================================================

function switchCompDetailTab(tab) {
    const overviewEl = document.getElementById('competitorDetailContent');
    const annotationsEl = document.getElementById('competitorDetailAnnotations');
    if (!overviewEl || !annotationsEl) return;

    // Toggle tab buttons
    document.querySelectorAll('.comp-detail-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    if (tab === 'overview') {
        overviewEl.style.display = '';
        annotationsEl.style.display = 'none';
    } else {
        overviewEl.style.display = 'none';
        annotationsEl.style.display = '';
    }
}

/**
 * Load annotations into the competitor detail modal annotations tab
 */
async function loadCompDetailAnnotations(competitorId) {
    const container = document.getElementById('competitorDetailAnnotations');
    if (!container) return;

    container.innerHTML = `
        <div class="comp-detail-annotations-wrapper">
            <!-- Filter bar -->
            <div class="comp-ann-filter-bar">
                <div class="comp-ann-filter-btns">
                    <button class="comp-ann-filter-btn active" onclick="filterCompDetailAnnotations(${competitorId}, '')" data-filter="">All</button>
                    <button class="comp-ann-filter-btn" onclick="filterCompDetailAnnotations(${competitorId}, 'note')" data-filter="note">Notes</button>
                    <button class="comp-ann-filter-btn" onclick="filterCompDetailAnnotations(${competitorId}, 'insight')" data-filter="insight">Insights</button>
                    <button class="comp-ann-filter-btn" onclick="filterCompDetailAnnotations(${competitorId}, 'warning')" data-filter="warning">Warnings</button>
                    <button class="comp-ann-filter-btn" onclick="filterCompDetailAnnotations(${competitorId}, 'opportunity')" data-filter="opportunity">Opportunities</button>
                    <button class="comp-ann-filter-btn" onclick="filterCompDetailAnnotations(${competitorId}, 'action_item')" data-filter="action_item">Action Items</button>
                </div>
                <button class="btn btn-sm btn-primary" onclick="toggleCompDetailAnnotationForm(${competitorId})">+ Add</button>
            </div>
            <!-- Add annotation form (hidden) -->
            <div id="compDetailAnnotationForm_${competitorId}" class="comp-ann-form" style="display: none;">
                <div class="comp-ann-form-row">
                    <input type="text" id="compDetailAnnTitle_${competitorId}" placeholder="Title (optional)" class="form-control form-control-sm">
                </div>
                <div class="comp-ann-form-row">
                    <textarea id="compDetailAnnContent_${competitorId}" placeholder="Write your annotation..." rows="3" class="form-control form-control-sm" style="resize: vertical;"></textarea>
                </div>
                <div class="comp-ann-form-actions">
                    <select id="compDetailAnnType_${competitorId}" class="form-control form-control-sm" style="width: auto;">
                        <option value="note">Note</option>
                        <option value="insight">Insight</option>
                        <option value="warning">Warning</option>
                        <option value="opportunity">Opportunity</option>
                        <option value="action_item">Action Item</option>
                    </select>
                    <select id="compDetailAnnPriority_${competitorId}" class="form-control form-control-sm" style="width: auto;">
                        <option value="normal">Normal</option>
                        <option value="low">Low</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                    </select>
                    <span style="flex: 1;"></span>
                    <button class="btn btn-sm btn-secondary" onclick="toggleCompDetailAnnotationForm(${competitorId})">Cancel</button>
                    <button class="btn btn-sm btn-primary" onclick="submitCompDetailAnnotation(${competitorId})">Save</button>
                </div>
            </div>
            <!-- Annotations list -->
            <div id="compDetailAnnotationsList_${competitorId}" class="comp-ann-list">
                <div class="loading" style="padding: 20px; text-align: center;">Loading annotations...</div>
            </div>
        </div>
    `;

    fetchCompDetailAnnotations(competitorId);
}

async function fetchCompDetailAnnotations(competitorId, typeFilter) {
    const listEl = document.getElementById(`compDetailAnnotationsList_${competitorId}`);
    if (!listEl) return;

    try {
        let url = `/api/teams/annotations/competitor/${competitorId}`;
        if (typeFilter) url += `?annotation_type=${typeFilter}`;

        const annotations = await fetchAPI(url, { silent: true });

        // Update badge count
        const badge = document.getElementById('compDetailAnnotationCount');
        if (badge && annotations) {
            badge.textContent = annotations.length;
            badge.style.display = annotations.length > 0 ? 'inline-flex' : 'none';
        }

        if (!annotations || annotations.length === 0) {
            listEl.innerHTML = '<div class="comp-ann-empty">No annotations yet. Be the first to add a note or insight.</div>';
            return;
        }

        // Sort: pinned first, then by date descending
        const sorted = [...annotations].sort((a, b) => {
            if (a.is_pinned && !b.is_pinned) return -1;
            if (!a.is_pinned && b.is_pinned) return 1;
            return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        });

        listEl.innerHTML = sorted.map(a => {
            const typeConf = ANNOTATION_TYPE_CONFIG[a.annotation_type] || ANNOTATION_TYPE_CONFIG.note;
            const prioConf = PRIORITY_CONFIG[a.priority] || PRIORITY_CONFIG.normal;
            const date = a.created_at ? new Date(a.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
            const isHighPrio = a.priority === 'high' || a.priority === 'critical';

            return `<div class="comp-ann-item ${a.is_pinned ? 'pinned' : ''} ${isHighPrio ? 'high-priority' : ''}">
                <div class="comp-ann-item-header">
                    <div class="comp-ann-item-tags">
                        ${a.is_pinned ? '<span class="comp-ann-pin-indicator" title="Pinned">&#128204;</span>' : ''}
                        <span class="comp-ann-type-badge" style="background:${typeConf.bg || 'rgba(59,130,246,0.1)'};color:${typeConf.color};">${escapeHtml(typeConf.label)}</span>
                        ${a.priority !== 'normal' ? `<span class="comp-ann-priority-badge" style="color:${prioConf.color};">${escapeHtml(prioConf.label)}</span>` : ''}
                        ${a.title ? `<span class="comp-ann-title">${escapeHtml(a.title)}</span>` : ''}
                    </div>
                    <div class="comp-ann-item-actions">
                        <button onclick="toggleCompDetailPin(${a.id}, ${competitorId})" title="${a.is_pinned ? 'Unpin' : 'Pin'}" class="comp-ann-action-btn">${a.is_pinned ? '&#128204;' : '&#128392;'}</button>
                        <button onclick="deleteCompDetailAnnotation(${a.id}, ${competitorId})" title="Delete" class="comp-ann-action-btn" style="color: var(--danger-color);">&#128465;</button>
                    </div>
                </div>
                <p class="comp-ann-content">${escapeHtml(a.content)}</p>
                <div class="comp-ann-footer">
                    <span class="comp-ann-author">${escapeHtml(a.user_name || a.user_email || 'Unknown')} &middot; ${date}</span>
                    <button onclick="toggleCompDetailReplies(${a.id}, ${competitorId})" class="comp-ann-reply-btn">${a.replies_count > 0 ? a.replies_count + ' replies' : 'Reply'}</button>
                </div>
                <div id="compDetailReplies_${a.id}" class="comp-ann-replies" style="display: none;"></div>
            </div>`;
        }).join('');

    } catch (error) {
        listEl.innerHTML = '<div class="comp-ann-empty">Unable to load annotations.</div>';
    }
}

function filterCompDetailAnnotations(competitorId, type) {
    // Update active filter button
    document.querySelectorAll('.comp-ann-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === type);
    });
    fetchCompDetailAnnotations(competitorId, type || undefined);
}

function toggleCompDetailAnnotationForm(competitorId) {
    const form = document.getElementById(`compDetailAnnotationForm_${competitorId}`);
    if (form) form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function submitCompDetailAnnotation(competitorId) {
    const title = (document.getElementById(`compDetailAnnTitle_${competitorId}`)?.value || '').trim();
    const content = (document.getElementById(`compDetailAnnContent_${competitorId}`)?.value || '').trim();
    const type = document.getElementById(`compDetailAnnType_${competitorId}`)?.value || 'note';
    const priority = document.getElementById(`compDetailAnnPriority_${competitorId}`)?.value || 'normal';

    if (!content) { showToast('Please enter annotation content', 'warning'); return; }

    try {
        const result = await fetchAPI('/api/teams/annotations', {
            method: 'POST',
            body: JSON.stringify({
                competitor_id: competitorId,
                title: title || null,
                content,
                annotation_type: type,
                priority,
                is_public: true
            })
        });

        if (result?.id) {
            showToast('Annotation saved', 'success');
            toggleCompDetailAnnotationForm(competitorId);
            // Clear form
            const titleInput = document.getElementById(`compDetailAnnTitle_${competitorId}`);
            const contentInput = document.getElementById(`compDetailAnnContent_${competitorId}`);
            if (titleInput) titleInput.value = '';
            if (contentInput) contentInput.value = '';
            fetchCompDetailAnnotations(competitorId);
        }
    } catch (error) {
        showToast('Failed to save annotation', 'error');
    }
}

async function toggleCompDetailPin(annotationId, competitorId) {
    try {
        await fetchAPI(`/api/teams/annotations/${annotationId}/pin`, { method: 'POST' });
        fetchCompDetailAnnotations(competitorId);
    } catch (error) {
        showToast('Failed to toggle pin', 'error');
    }
}

async function deleteCompDetailAnnotation(annotationId, competitorId) {
    if (!confirm('Delete this annotation?')) return;
    try {
        await fetchAPI(`/api/teams/annotations/${annotationId}`, { method: 'DELETE' });
        showToast('Annotation deleted', 'success');
        fetchCompDetailAnnotations(competitorId);
    } catch (error) {
        showToast('Failed to delete annotation', 'error');
    }
}

async function toggleCompDetailReplies(annotationId, competitorId) {
    const container = document.getElementById(`compDetailReplies_${annotationId}`);
    if (!container) return;

    if (container.style.display !== 'none') {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    container.innerHTML = '<p style="color: var(--text-light); font-size: 12px; padding: 4px;">Loading replies...</p>';

    try {
        const replies = await fetchAPI(`/api/teams/annotations/${annotationId}/replies`, { silent: true });

        let html = (replies || []).map(r => {
            const date = r.created_at ? new Date(r.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
            return `<div class="comp-ann-reply-item">
                <p class="comp-ann-reply-content">${escapeHtml(r.content)}</p>
                <span class="comp-ann-reply-meta">${escapeHtml(r.user_name || r.user_email || 'Unknown')} &middot; ${date}</span>
            </div>`;
        }).join('');

        html += `<div class="comp-ann-reply-input-row">
            <input type="text" id="compDetailReplyInput_${annotationId}" placeholder="Write a reply..." class="form-control form-control-sm" style="flex: 1;">
            <button onclick="submitCompDetailReply(${annotationId}, ${competitorId})" class="btn btn-sm btn-primary">Reply</button>
        </div>`;

        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<p style="color: var(--text-light); font-size: 12px;">Unable to load replies.</p>';
    }
}

async function submitCompDetailReply(annotationId, competitorId) {
    const input = document.getElementById(`compDetailReplyInput_${annotationId}`);
    const content = (input?.value || '').trim();
    if (!content) return;

    try {
        await fetchAPI(`/api/teams/annotations/${annotationId}/replies`, {
            method: 'POST',
            body: JSON.stringify({ content })
        });
        input.value = '';
        // Re-open to refresh
        const container = document.getElementById(`compDetailReplies_${annotationId}`);
        if (container) container.style.display = 'none';
        toggleCompDetailReplies(annotationId, competitorId);
        fetchCompDetailAnnotations(competitorId);
    } catch (error) {
        showToast('Failed to post reply', 'error');
    }
}

// Export annotation and team functions to window
window.loadAnnotations = loadAnnotations;
window.filterAnnotations = filterAnnotations;
window.toggleAnnotationForm = toggleAnnotationForm;
window.submitAnnotation = submitAnnotation;
window.toggleAnnotationPin = toggleAnnotationPin;
window.deleteAnnotation = deleteAnnotation;
window.toggleReplies = toggleReplies;
window.submitReply = submitReply;
window.loadTeamActivity = loadTeamActivity;
window.switchTeam = switchTeam;
window.removeTeamMember = removeTeamMember;
window.showCreateTeamModal = showCreateTeamModal;
window.handleCreateTeam = handleCreateTeam;
window.switchCompDetailTab = switchCompDetailTab;
window.loadCompDetailAnnotations = loadCompDetailAnnotations;
window.filterCompDetailAnnotations = filterCompDetailAnnotations;
window.toggleCompDetailAnnotationForm = toggleCompDetailAnnotationForm;
window.submitCompDetailAnnotation = submitCompDetailAnnotation;
window.toggleCompDetailPin = toggleCompDetailPin;
window.deleteCompDetailAnnotation = deleteCompDetailAnnotation;
window.toggleCompDetailReplies = toggleCompDetailReplies;
window.submitCompDetailReply = submitCompDetailReply;
window.fetchCompDetailAnnotations = fetchCompDetailAnnotations;

async function loadSettings() {
    loadTeam();
    if (typeof loadAlertRules === 'function') loadAlertRules();
    if (typeof checkIntegrations === 'function') checkIntegrations();
    loadAIProviderStatus(); // v5.0.2
    loadSystemReadiness(); // v8.3.1
    loadWebhooks();
    loadTeamActivity();
    loadDataProviderStatus(); // v8.3.0
    loadAuditLogs(); // v9 audit log viewer
}

// ==============================================================================
// Settings - Password Change
// ==============================================================================

/**
 * Handle password change form submission.
 */
async function changePassword() {
    const currentPwd = document.getElementById('currentPassword');
    const newPwd = document.getElementById('newPassword');
    const confirmPwd = document.getElementById('confirmPassword');
    const msgEl = document.getElementById('passwordChangeMsg');

    if (!currentPwd || !newPwd || !confirmPwd) return;

    const current = currentPwd.value;
    const newPass = newPwd.value;
    const confirm = confirmPwd.value;

    if (!current || !newPass || !confirm) {
        if (msgEl) {
            msgEl.textContent = 'Please fill in all fields.';
            msgEl.style.color = 'var(--danger-color, #f87171)';
        }
        return;
    }

    if (newPass.length < 8) {
        if (msgEl) {
            msgEl.textContent = 'New password must be at least 8 characters.';
            msgEl.style.color = 'var(--danger-color, #f87171)';
        }
        return;
    }

    if (newPass !== confirm) {
        if (msgEl) {
            msgEl.textContent = 'New passwords do not match.';
            msgEl.style.color = 'var(--danger-color, #f87171)';
        }
        return;
    }

    try {
        const result = await fetchAPI('/api/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({
                current_password: current,
                new_password: newPass
            })
        });

        if (result && (result.status === 'success' || result.message)) {
            if (msgEl) {
                msgEl.textContent = 'Password updated successfully.';
                msgEl.style.color = 'var(--success-color, #10b981)';
            }
            currentPwd.value = '';
            newPwd.value = '';
            confirmPwd.value = '';
            showToast('Password changed successfully', 'success');
        } else {
            if (msgEl) {
                msgEl.textContent = 'Failed to update password. Check your current password.';
                msgEl.style.color = 'var(--danger-color, #f87171)';
            }
        }
    } catch (error) {
        console.error('Password change failed:', error);
        if (msgEl) {
            msgEl.textContent = 'Failed to update password. Please try again.';
            msgEl.style.color = 'var(--danger-color, #f87171)';
        }
    }
}

window.changePassword = changePassword;

// ==============================================================================
// Settings - Audit Log Viewer
// ==============================================================================

let _auditLogData = [];
let _auditLogPage = 1;

/**
 * Load audit logs from the API and populate the settings audit log table.
 */
async function loadAuditLogs() {
    const tbody = document.getElementById('auditLogBody');
    if (!tbody) return;

    try {
        const data = await fetchAPI(`/api/activity-logs?page=${_auditLogPage}&per_page=50`, { silent: true });

        if (!data) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:24px;">No audit logs available.</td></tr>';
            return;
        }

        const logs = data.logs || data.items || (Array.isArray(data) ? data : []);
        _auditLogData = logs;

        renderAuditLogTable(logs);

    } catch (error) {
        console.error('Failed to load audit logs:', error);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--danger-color, #f87171);padding:24px;">Failed to load audit logs.</td></tr>';
    }
}

/**
 * Filter the currently loaded audit logs by search text and action type.
 */
function filterAuditLogs() {
    const searchEl = document.getElementById('auditLogSearch');
    const filterEl = document.getElementById('auditLogActionFilter');

    const search = (searchEl?.value || '').toLowerCase().trim();
    const actionFilter = (filterEl?.value || '').toLowerCase();

    let filtered = _auditLogData;

    if (search) {
        filtered = filtered.filter(log => {
            const user = (log.user_email || log.username || '').toLowerCase();
            const action = (log.action_type || log.action || '').toLowerCase();
            const details = (log.details || log.description || '').toLowerCase();
            return user.includes(search) || action.includes(search) || details.includes(search);
        });
    }

    if (actionFilter) {
        filtered = filtered.filter(log => {
            const action = (log.action_type || log.action || '').toLowerCase();
            return action.includes(actionFilter);
        });
    }

    renderAuditLogTable(filtered);
}

/**
 * Render audit log entries into the table.
 * @param {Array} logs - The log entries to render
 */
function renderAuditLogTable(logs) {
    const tbody = document.getElementById('auditLogBody');
    if (!tbody) return;

    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:24px;">No matching audit logs found.</td></tr>';
        return;
    }

    tbody.innerHTML = logs.map(log => {
        const timestamp = log.created_at || log.timestamp || '';
        const dateStr = timestamp ? new Date(timestamp).toLocaleString() : 'N/A';
        const user = escapeHtml(log.user_email || log.username || 'System');
        const action = escapeHtml(log.action_type || log.action || 'unknown');
        const details = escapeHtml(log.details || log.description || '');

        const actionClass = action.toLowerCase().includes('delete') ? 'danger' :
            action.toLowerCase().includes('create') ? 'success' :
            action.toLowerCase().includes('login') ? 'info' : 'secondary';

        return `<tr>
            <td style="white-space:nowrap;color:var(--text-secondary);font-size:12px;">${escapeHtml(dateStr)}</td>
            <td style="color:var(--text-primary);">${user}</td>
            <td><span class="activity-badge ${actionClass}">${action}</span></td>
            <td style="color:var(--text-secondary);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${details}">${details}</td>
        </tr>`;
    }).join('');
}

window.loadAuditLogs = loadAuditLogs;
window.filterAuditLogs = filterAuditLogs;

// ==============================================================================
// Webhooks Admin UI
// ==============================================================================

let _webhookEventTypes = [];

async function loadWebhooks() {
    const container = document.getElementById('webhooksTableContainer');
    if (!container) return;

    try {
        // Fetch event types and webhooks in parallel
        const [eventsRes, webhooks] = await Promise.all([
            fetchAPI('/api/webhooks/events', { silent: true }).catch(() => ({ event_types: [] })),
            fetchAPI('/api/webhooks', { silent: true }).catch(() => [])
        ]);

        _webhookEventTypes = eventsRes?.event_types || [];

        if (!webhooks || webhooks.length === 0) {
            container.innerHTML = '<p class="empty-state-text" style="color:var(--text-muted);padding:12px 0;">No webhooks configured yet. Click "+ Add Webhook" to get started.</p>';
            return;
        }

        let tableHtml = '<table class="webhooks-table"><thead><tr>';
        tableHtml += '<th>Name</th><th>URL</th><th>Events</th><th>Actions</th>';
        tableHtml += '</tr></thead><tbody>';

        webhooks.forEach(hook => {
            const events = (hook.event_types || '').split(',').filter(Boolean);
            const eventBadges = events.map(e => `<span class="webhook-event-badge">${escapeHtml(e.trim())}</span>`).join('');
            const truncatedUrl = (hook.url || '').length > 45 ? hook.url.substring(0, 45) + '...' : (hook.url || '');

            tableHtml += '<tr>';
            tableHtml += `<td>${escapeHtml(hook.name || 'Unnamed')}</td>`;
            tableHtml += `<td class="webhook-url-cell" title="${escapeHtml(hook.url || '')}">${escapeHtml(truncatedUrl)}</td>`;
            tableHtml += `<td class="webhook-events-cell">${eventBadges}</td>`;
            tableHtml += '<td class="webhook-actions-cell">';
            tableHtml += `<button class="btn btn-secondary btn-xs" onclick="testWebhook(${hook.id})">Test</button>`;
            tableHtml += `<button class="btn btn-danger btn-xs" onclick="deleteWebhook(${hook.id})">Delete</button>`;
            tableHtml += '</td>';
            tableHtml += '</tr>';
        });

        tableHtml += '</tbody></table>';
        container.innerHTML = tableHtml;
    } catch (error) {
        console.error('Failed to load webhooks:', error);
        container.innerHTML = '<p style="color:var(--danger-color);padding:12px 0;">Failed to load webhooks.</p>';
    }
}

function showAddWebhookForm() {
    const form = document.getElementById('addWebhookForm');
    if (!form) return;

    // Populate event type checkboxes
    const eventsGrid = document.getElementById('webhookEventTypes');
    if (eventsGrid && _webhookEventTypes.length > 0) {
        eventsGrid.innerHTML = _webhookEventTypes.map(evt => {
            const id = 'wh-evt-' + evt.replace(/\./g, '-');
            return `<label class="webhook-event-check"><input type="checkbox" id="${id}" value="${escapeHtml(evt)}"> <span>${escapeHtml(evt)}</span></label>`;
        }).join('');
    } else if (eventsGrid) {
        // Fallback if events haven't loaded yet
        eventsGrid.innerHTML = '<p style="color:var(--text-muted);">Loading event types...</p>';
        fetchAPI('/api/webhooks/events', { silent: true }).then(res => {
            _webhookEventTypes = res?.event_types || [];
            if (_webhookEventTypes.length > 0) {
                eventsGrid.innerHTML = _webhookEventTypes.map(evt => {
                    const id = 'wh-evt-' + evt.replace(/\./g, '-');
                    return `<label class="webhook-event-check"><input type="checkbox" id="${id}" value="${escapeHtml(evt)}"> <span>${escapeHtml(evt)}</span></label>`;
                }).join('');
            }
        }).catch(() => {});
    }

    // Clear form fields
    const nameInput = document.getElementById('webhookName');
    const urlInput = document.getElementById('webhookUrl');
    if (nameInput) nameInput.value = '';
    if (urlInput) urlInput.value = '';

    form.style.display = 'block';
}

function hideAddWebhookForm() {
    const form = document.getElementById('addWebhookForm');
    if (form) form.style.display = 'none';
}

async function saveWebhook() {
    const name = (document.getElementById('webhookName')?.value || '').trim();
    const url = (document.getElementById('webhookUrl')?.value || '').trim();

    if (!name) { showToast('Please enter a webhook name', 'warning'); return; }
    if (!url || !url.startsWith('http')) { showToast('Please enter a valid URL', 'warning'); return; }

    // Collect checked event types
    const checked = document.querySelectorAll('#webhookEventTypes input[type="checkbox"]:checked');
    const eventTypes = Array.from(checked).map(cb => cb.value);
    if (eventTypes.length === 0) { showToast('Please select at least one event type', 'warning'); return; }

    try {
        const result = await fetchAPI('/api/webhooks', {
            method: 'POST',
            body: JSON.stringify({ name, url, event_types: eventTypes.join(',') })
        });

        if (result?.status === 'success' || result?.id) {
            showToast('Webhook created successfully', 'success');
            hideAddWebhookForm();
            loadWebhooks();
        } else {
            showToast('Failed to create webhook', 'error');
        }
    } catch (error) {
        console.error('Create webhook error:', error);
        showToast('Failed to create webhook', 'error');
    }
}

async function testWebhook(webhookId) {
    showToast('Sending test event...', 'info');
    try {
        const result = await fetchAPI(`/api/webhooks/${webhookId}/test`, {
            method: 'POST'
        });

        if (result?.success !== false) {
            showToast('Test event sent successfully', 'success');
        } else {
            showToast('Test event failed', 'error');
        }
    } catch (error) {
        console.error('Test webhook error:', error);
        showToast('Test event failed', 'error');
    }
}

async function deleteWebhook(webhookId) {
    if (!confirm('Delete this webhook? This action cannot be undone.')) return;

    try {
        const result = await fetchAPI(`/api/webhooks/${webhookId}`, {
            method: 'DELETE'
        });

        if (result?.status === 'success') {
            showToast('Webhook deleted', 'success');
            loadWebhooks();
        } else {
            showToast('Failed to delete webhook', 'error');
        }
    } catch (error) {
        console.error('Delete webhook error:', error);
        showToast('Failed to delete webhook', 'error');
    }
}

// Export webhook functions to window
window.showAddWebhookForm = showAddWebhookForm;
window.hideAddWebhookForm = hideAddWebhookForm;
window.saveWebhook = saveWebhook;
window.testWebhook = testWebhook;
window.deleteWebhook = deleteWebhook;

// ============== AI Provider Status (v5.0.2) ==============

async function loadAIProviderStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/ai/status`);
        if (!response.ok) {
            console.warn('AI status endpoint not available');
            return;
        }

        const data = await response.json();

        // Update OpenAI status
        const openaiStatusBadge = document.getElementById('openaiStatusBadge');
        const openaiModel = document.getElementById('openaiModel');
        if (openaiStatusBadge && data.providers?.openai) {
            openaiStatusBadge.textContent = data.providers.openai.available ? 'Active' : 'Not Configured';
            openaiStatusBadge.style.background = data.providers.openai.available ? '#10B981' : '#6B7280';
            openaiStatusBadge.style.color = 'white';
            openaiStatusBadge.style.padding = '2px 8px';
            openaiStatusBadge.style.borderRadius = '4px';
            openaiStatusBadge.style.fontSize = '0.75em';
        }
        if (openaiModel && data.providers?.openai?.model) {
            openaiModel.textContent = data.providers.openai.model;
        }

        // Update Gemini status
        const geminiStatusBadge = document.getElementById('geminiStatusBadge');
        const geminiModel = document.getElementById('geminiModel');
        if (geminiStatusBadge && data.providers?.gemini) {
            geminiStatusBadge.textContent = data.providers.gemini.available ? 'Active' : 'Not Configured';
            geminiStatusBadge.style.background = data.providers.gemini.available ? '#4285F4' : '#6B7280';
            geminiStatusBadge.style.color = 'white';
            geminiStatusBadge.style.padding = '2px 8px';
            geminiStatusBadge.style.borderRadius = '4px';
            geminiStatusBadge.style.fontSize = '0.75em';
        }
        if (geminiModel && data.providers?.gemini?.model) {
            geminiModel.textContent = data.providers.gemini.model;
        }

        // Update Anthropic (Claude) status
        const anthropicStatusBadge = document.getElementById('anthropicStatusBadge');
        const anthropicModel = document.getElementById('anthropicModel');
        if (anthropicStatusBadge && data.providers?.anthropic) {
            anthropicStatusBadge.textContent = data.providers.anthropic.available ? 'Active' : 'Not Configured';
            anthropicStatusBadge.style.background = data.providers.anthropic.available ? '#D97706' : '#6B7280';
            anthropicStatusBadge.style.color = 'white';
            anthropicStatusBadge.style.padding = '2px 8px';
            anthropicStatusBadge.style.borderRadius = '4px';
            anthropicStatusBadge.style.fontSize = '0.75em';
        }
        if (anthropicModel && data.providers?.anthropic?.model) {
            anthropicModel.textContent = data.providers.anthropic.model;
        }

        // Update DeepSeek status
        const deepseekStatusBadge = document.getElementById('deepseekStatusBadge');
        const deepseekModel = document.getElementById('deepseekModel');
        if (deepseekStatusBadge && data.providers?.deepseek) {
            deepseekStatusBadge.textContent = data.providers.deepseek.available ? 'Active' : 'Not Configured';
            deepseekStatusBadge.style.background = data.providers.deepseek.available ? '#0EA5E9' : '#6B7280';
            deepseekStatusBadge.style.color = 'white';
            deepseekStatusBadge.style.padding = '2px 8px';
            deepseekStatusBadge.style.borderRadius = '4px';
            deepseekStatusBadge.style.fontSize = '0.75em';
        }
        if (deepseekModel && data.providers?.deepseek?.model) {
            deepseekModel.textContent = data.providers.deepseek.model;
        }

        // Update task routing display
        const routingExtraction = document.getElementById('routingExtraction');
        const routingSummary = document.getElementById('routingSummary');
        const routingBulk = document.getElementById('routingBulk');
        const routingQuality = document.getElementById('routingQuality');

        if (data.routing) {
            if (routingExtraction) routingExtraction.textContent = data.routing.data_extraction || '-';
            if (routingSummary) routingSummary.textContent = data.routing.executive_summary || '-';
            if (routingBulk) routingBulk.textContent = data.routing.bulk_tasks || '-';
            if (routingQuality) routingQuality.textContent = data.routing.quality_tasks || '-';

            // Color code active providers
            [routingExtraction, routingSummary, routingBulk, routingQuality].forEach(el => {
                if (el) {
                    const provider = el.textContent.toLowerCase();
                    if (provider === 'gemini') {
                        el.style.color = '#4285F4';
                    } else if (provider === 'openai') {
                        el.style.color = '#10B981';
                    } else if (provider === 'anthropic') {
                        el.style.color = '#D97706';
                    } else if (provider === 'deepseek') {
                        el.style.color = '#0EA5E9';
                    } else {
                        el.style.color = 'var(--text-secondary)';
                    }
                }
            });
        }


    } catch (error) {
        console.warn('Failed to load AI provider status:', error);
    }
}

async function loadSystemReadiness() {
    const container = document.getElementById('systemReadinessContent');
    if (!container) return;

    try {
        const data = await fetchAPI('/readiness', { silent: true });
        if (!data || !data.checks) {
            container.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85em;">Unable to check system readiness.</p>';
            return;
        }

        let html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;">';

        for (const [name, status] of Object.entries(data.checks)) {
            const dotColor = status ? '#22c55e' : '#ef4444';
            const statusText = status ? 'Connected' : 'Offline';
            const displayName = escapeHtml(name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()));

            html += `
                <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:rgba(255,255,255,0.03);border-radius:8px;">
                    <span style="width:8px;height:8px;border-radius:50%;background:${dotColor};flex-shrink:0;"></span>
                    <div>
                        <div style="font-size:13px;font-weight:500;">${displayName}</div>
                        <div style="font-size:11px;color:var(--text-secondary);">${statusText}</div>
                    </div>
                </div>`;
        }

        html += '</div>';
        html += `<div style="margin-top:8px;font-size:12px;color:var(--text-tertiary);">System: ${escapeHtml(data.status || 'unknown')} &bull; v${escapeHtml(data.version || '?')}</div>`;

        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85em;">System readiness unavailable.</p>';
    }
}

// ============== Enterprise Data Providers (v8.3.0) ==============

async function loadDataProviderStatus() {
    const grid = document.getElementById('dataProvidersGrid');
    if (!grid) return;

    try {
        const data = await fetchAPI('/api/admin/data-providers/status', { silent: true });
        if (!data || !data.providers || data.providers.length === 0) {
            grid.innerHTML = '<p style="color:var(--text-secondary);padding:8px 0;">No data providers available.</p>';
            return;
        }

        let html = '';
        data.providers.forEach(provider => {
            const isConfigured = provider.configured || false;
            const statusClass = isConfigured ? 'configured' : 'unconfigured';
            const statusLabel = isConfigured ? 'Configured' : 'Not Configured';
            const providerName = escapeHtml(provider.name || 'Unknown');
            const providerDesc = escapeHtml(provider.description || '');
            const envKey = escapeHtml(provider.env_key || '');
            const providerSlug = escapeHtml(provider.slug || provider.name || '');

            html += `<div class="data-provider-card">
                <div class="data-provider-card-header">
                    <span class="provider-name">${providerName}</span>
                    <span class="provider-status-dot ${statusClass}" title="${statusLabel}"></span>
                </div>
                <div class="provider-desc">${providerDesc}</div>
                ${envKey ? `<div class="provider-env-hint">Set ${envKey} in .env</div>` : ''}
                <div class="provider-actions">
                    <button class="btn-test-provider" onclick="testDataProvider('${providerSlug}')" ${isConfigured ? '' : 'disabled'} title="${isConfigured ? 'Test connection' : 'Configure API key first'}">Test Connection</button>
                </div>
            </div>`;
        });

        grid.innerHTML = html;
    } catch (error) {
        console.error('Failed to load data provider status:', error);
        grid.innerHTML = '<p style="color:var(--text-secondary);padding:8px 0;">Data provider status unavailable.</p>';
    }
}

async function testDataProvider(providerSlug) {
    showToast('Testing connection...', 'info');
    try {
        const result = await fetchAPI(`/api/admin/data-providers/test/${encodeURIComponent(providerSlug)}`, {
            method: 'POST'
        });

        if (result && result.success) {
            showToast(`${escapeHtml(providerSlug)}: Connection successful`, 'success');
        } else {
            showToast(`${escapeHtml(providerSlug)}: ${escapeHtml(result?.error || 'Connection failed')}`, 'error');
        }
    } catch (error) {
        console.error('Test provider error:', error);
        showToast(`${escapeHtml(providerSlug)}: Connection test failed`, 'error');
    }
}

window.testDataProvider = testDataProvider;

// ============== Source Quality Dashboard (v8.3.0) ==============

async function loadSourceQualityStats() {
    const container = document.getElementById('sourceQualityStats');
    if (!container) return;

    try {
        const data = await fetchAPI('/api/sources/quality-summary', { silent: true });
        if (!data) {
            container.innerHTML = '<p style="color:var(--text-secondary);grid-column:1/-1;padding:8px 0;">Source quality data unavailable.</p>';
            return;
        }

        const total = data.total || 0;
        const exact = data.exact_page || 0;
        const page = data.page_level || 0;
        const homepage = data.homepage_only || 0;
        const broken = data.broken || 0;

        // Show helpful empty state when pipeline hasn't run
        if (total === 0 || (exact === 0 && page === 0 && homepage === 0 && broken === 0)) {
            container.innerHTML = `
                <div style="grid-column:1/-1;text-align:center;padding:20px 16px;">
                    <p style="color:var(--text-secondary);margin:0 0 12px 0;font-size:14px;">
                        No sources have been content-matched yet.
                    </p>
                    <p style="color:var(--text-tertiary);margin:0 0 16px 0;font-size:13px;">
                        Click <strong>Refine All URLs</strong> above to start the deep link pipeline,
                        or <strong>Re-run Content Matching</strong> to reprocess existing sources.
                    </p>
                </div>`;
            return;
        }

        const coveragePct = total > 0 ? Math.round(((exact + page) / total) * 100) : 0;

        container.innerHTML = `
            <div class="source-quality-stat">
                <div class="sq-count sq-count-total">${total}</div>
                <div class="sq-label">Total Sources</div>
            </div>
            <div class="source-quality-stat">
                <div class="sq-count sq-count-exact">${exact}</div>
                <div class="sq-label">Exact Page</div>
            </div>
            <div class="source-quality-stat">
                <div class="sq-count sq-count-page">${page}</div>
                <div class="sq-label">Page-Level</div>
            </div>
            <div class="source-quality-stat">
                <div class="sq-count sq-count-homepage">${homepage}</div>
                <div class="sq-label">Homepage Only</div>
            </div>
            <div class="source-quality-stat">
                <div class="sq-count sq-count-broken">${broken}</div>
                <div class="sq-label">Broken</div>
            </div>
            <div class="source-quality-coverage" style="grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.08);">
                <span style="color:var(--text-secondary);font-size:13px;">Content-matched coverage: <strong style="color:var(--text-primary);">${coveragePct}%</strong> (${exact + page} of ${total})</span>
                <button class="btn btn-secondary btn-sm" onclick="rerunContentMatching()" style="font-size:12px;padding:4px 12px;">Re-run Content Matching</button>
            </div>`;
    } catch (error) {
        console.error('Failed to load source quality stats:', error);
        container.innerHTML = '<p style="color:var(--text-secondary);grid-column:1/-1;padding:8px 0;">Source quality data unavailable.</p>';
    }
}

let _refineUrlsTaskId = null;

async function refineAllSourceUrls() {
    const btn = document.getElementById('refineAllUrlsBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Starting...';
    }

    try {
        const result = await fetchAPI('/api/sources/refine-urls/all', { method: 'POST' });
        if (result && result.task_id) {
            _refineUrlsTaskId = result.task_id;
            showToast('URL refinement started', 'success');
            const progressContainer = document.getElementById('refineProgressContainer');
            if (progressContainer) progressContainer.style.display = 'block';
            pollRefineUrlsProgress(result.task_id);
        } else {
            showToast('Failed to start URL refinement', 'error');
            if (btn) { btn.disabled = false; btn.textContent = 'Refine All URLs'; }
        }
    } catch (error) {
        console.error('Refine URLs error:', error);
        showToast('Failed to start URL refinement', 'error');
        if (btn) { btn.disabled = false; btn.textContent = 'Refine All URLs'; }
    }
}

async function pollRefineUrlsProgress(taskId) {
    const progressFill = document.getElementById('refineProgressFill');
    const progressLabel = document.getElementById('refineProgressLabel');
    const progressPercent = document.getElementById('refineProgressPercent');
    const progressContainer = document.getElementById('refineProgressContainer');
    const btn = document.getElementById('refineAllUrlsBtn');

    while (true) {
        await new Promise(r => setTimeout(r, 2000));

        // Guard DOM checks for SPA navigation
        if (!document.getElementById('refineProgressContainer')) break;

        try {
            const status = await fetchAPI(`/api/ai/tasks/${taskId}`, { silent: true });
            if (!status) break;

            const pct = status.progress || 0;
            if (progressFill) progressFill.style.width = pct + '%';
            if (progressPercent) progressPercent.textContent = pct + '%';
            if (progressLabel) progressLabel.textContent = status.status_message || 'Refining URLs...';

            if (status.status === 'completed' || status.status === 'failed') {
                if (status.status === 'completed') {
                    showToast('URL refinement complete', 'success');
                    loadSourceQualityStats();
                } else {
                    showToast('URL refinement failed', 'error');
                }

                if (progressContainer) progressContainer.style.display = 'none';
                if (btn) { btn.disabled = false; btn.textContent = 'Refine All URLs'; }
                _refineUrlsTaskId = null;
                break;
            }
        } catch (e) {
            break;
        }
    }
}

async function rerunContentMatching() {
    showToast('Re-running content matching on all sources...', 'info');

    try {
        const result = await fetchAPI('/api/sources/refine-urls/all?force_refresh=true', { method: 'POST' });
        if (result && result.task_id) {
            _refineUrlsTaskId = result.task_id;
            showToast('Content matching reprocessing started', 'success');
            const progressContainer = document.getElementById('refineProgressContainer');
            if (progressContainer) progressContainer.style.display = 'block';
            pollRefineUrlsProgress(result.task_id);
        } else {
            showToast('Failed to start content matching', 'error');
        }
    } catch (error) {
        console.error('Rerun content matching error:', error);
        showToast('Failed to start content matching', 'error');
    }
}

window.refineAllSourceUrls = refineAllSourceUrls;
window.rerunContentMatching = rerunContentMatching;

// ============== Deep Link Enhancement (v8.3.0) ==============

/**
 * Check if the browser supports Text Fragments (Chrome 80+, Edge 80+).
 */
const _supportsTextFragments = (() => {
    // Chrome 80+, Edge 80+ have fragmentDirective
    if ('fragmentDirective' in document) return true;
    // Firefox 131+ supports Text Fragments (but not fragmentDirective API)
    const ffMatch = navigator.userAgent.match(/Firefox\/(\d+)/);
    if (ffMatch && parseInt(ffMatch[1], 10) >= 131) return true;
    return false;
})();

/**
 * Open a source URL, preferring deep_link_url when available.
 * If Text Fragments are not supported, show a toast with the search text.
 */
function openSourceUrlWithDeepLink(sourceUrl, deepLinkUrl, searchValue) {
    if (deepLinkUrl && _supportsTextFragments) {
        window.open(deepLinkUrl, '_blank');
    } else if (deepLinkUrl && !_supportsTextFragments) {
        // Open the non-fragment URL and show a hint
        const baseUrl = deepLinkUrl.split('#')[0];
        window.open(baseUrl, '_blank');
        if (searchValue) {
            showToast(`Look for: "${searchValue}" on this page (use Ctrl+F to search)`, 'info', { duration: 6000 });
        }
    } else if (sourceUrl) {
        window.open(sourceUrl, '_blank');
    } else {
        showToast('No source URL available', 'info');
    }
}

window.openSourceUrlWithDeepLink = openSourceUrlWithDeepLink;

// ============== Mobile Responsiveness ==============

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.mobile-overlay');

    if (sidebar) sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('open');
}

function navigateTo(pageName) {
    // Wrapper for showPage that also handles mobile UI
    if (typeof showPage === 'function') {
        showPage(pageName);
    }

    // Update bottom nav active state
    document.querySelectorAll('.bottom-nav-item').forEach(item => {
        if (item.getAttribute('onclick') && item.getAttribute('onclick').includes('${pageName}')) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Close sidebar on mobile
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && sidebar.classList.contains('open')) {
        toggleSidebar();
    }

    // Scroll to top
    window.scrollTo(0, 0);
}

// ============== Data Corrections ==============

// ============== Data Corrections ==============

function openCorrectionModal(competitorId, field, currentValue) {
    // Clean up value for display
    const safeValue = (currentValue === 'null' || currentValue === 'undefined') ? '' : currentValue;
    const cleanFieldName = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

    // Find competitor name
    const comp = competitors.find(c => c.id === competitorId);
    const compName = comp ? comp.name : 'Unknown';

    const content = `
        <h2>Correct Data: ${cleanFieldName}</h2>
        <div style="margin-bottom: 16px; padding: 12px; background: #f8fafc; border-radius: 6px; color: #64748b; font-size: 0.9em;">
            <strong>Competitor:</strong> ${compName}<br>
            <strong>Current Value:</strong> ${safeValue || '<em style="color:#94a3b8">Empty</em>'}
        </div>
        
        <form id="correctionForm" onsubmit="submitCorrection(event, ${competitorId}, '${field}')">
            <div class="form-group">
                <label>New Correct Value</label>
                <input type="text" name="new_value" value="${safeValue}" required placeholder="Enter the correct value...">
            </div>
            <div class="form-group">
                <label>Reason for Change</label>
                <select name="reason">
                    <option value="Incorrect Data">Incorrect Data</option>
                    <option value="Outdated">Outdated Information</option>
                    <option value="Typo/Format">Typo or Formatting Issue</option>
                    <option value="Manual Override">Manual Override (Force)</option>
                </select>
            </div>
            <div style="margin-top: 24px; display: flex; justify-content: flex-end; gap: 12px;">
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button type="submit" class="btn btn-primary">Save Correction</button>
            </div>
        </form>
    `;

    showModal(content);
}

async function submitCorrection(event, competitorId, fieldName) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    const payload = {
        field: fieldName,
        new_value: formData.get('new_value'),
        reason: formData.get('reason')
    };

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerText;
    submitBtn.disabled = true;
    submitBtn.innerText = 'Saving...';

    try {
        const result = await fetchAPI(`/api/competitors/${competitorId}/correct`, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (result) {
            showToast('Correction saved and data point locked.', 'success');
            closeModal();
            // Reload data to reflect changes
            await loadCompetitors();

            // Also refresh changes list if visible
            if (document.getElementById('recentChanges')) {
                const changesData = await fetchAPI('/api/changes?days=7');
                changes = changesData?.changes || [];
                renderRecentChanges();
            }
        }
    } catch (e) {
        showToast('Error saving correction: ' + e.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = originalText;
    }
}


// ============== Discovery Pipeline (Phase 4) ==============

let discoveryContext = null;

function toggleConfigPanel() {
    const panel = document.getElementById('discoveryConfigPanel');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        loadDiscoveryContext();
        // Scroll to panel
        panel.scrollIntoView({ behavior: 'smooth' });
    } else {
        panel.style.display = 'none';
    }
}

async function loadDiscoveryContext() {
    try {
        const context = await fetchAPI('/api/discovery/context');
        discoveryContext = context;
        document.getElementById('jsonContextPreview').textContent = JSON.stringify(context, null, 2);
    } catch (e) {
        document.getElementById('jsonContextPreview').textContent = "Error loading context: " + e.message;
    }
}

// sendConfigChat() removed in v7.2.0 - orphaned dead code (configChatInput/configChatMessages don't exist in HTML)

async function scheduleRun() {
    const timeInput = document.getElementById('scheduleRunTime');
    const isoTime = timeInput.value;

    if (!isoTime) {
        showToast("Please select a date and time.", "error");
        return;
    }

    try {
        // DateTime input gives local time 'YYYY-MM-DDTHH:MM' 
        // We need to send it as ISO string. 
        // Let's create a Date object to handle timezone correctly if needed, or send as is if backend expects ISO.
        const dateObj = new Date(isoTime);
        const isoString = dateObj.toISOString();

        const result = await fetchAPI('/api/discovery/schedule', {
            method: 'POST',
            body: JSON.stringify({ run_at: isoString })
        });

        showToast(result.message, "success");
        toggleConfigPanel(); // Close panel on success

    } catch (e) {
        showToast("Error scheduling run: " + e.message, "error");
    }
}

// NOTE: runDiscovery() is defined later in file (line ~11098) with full implementation
// Removed duplicate function definition here to prevent conflicts

// ============== Discovery Custom Instructions ==============

// Dead code removed: openScoutInstructionsModal, closeScoutInstructionsModal,
// loadDefaultScoutPrompt, setGlobalDefaultPrompt, saveScoutPrompt
// Qualification is now consolidated into the structured criteria panel with custom instructions textarea.
// Keeping anchor comment so surrounding code isn't disturbed.
// v7.2: Dead code removed - Scout Instructions modal, DEFAULT_SCOUT_PROMPT,
// openScoutInstructionsModal, closeScoutInstructionsModal, loadDefaultScoutPrompt,
// setGlobalDefaultPrompt, saveScoutPrompt, initializeScoutPrompt.
// Custom instructions are now inline in the qualificationCriteriaPanel.

async function loadDiscoveredCandidates() {
    const grid = document.getElementById('discoveredGrid');
    if (!grid) return;

    grid.innerHTML = '<div class="loading">Loading discovered candidates...</div>';

    try {
        // Fetch competitors with status='Discovered'
        // Using existing endpoint with added filter param support (client-side filter fallback if backend ignores it)
        const allComps = await fetchAPI('/api/competitors');
        const discovered = allComps.filter(c => c.status === 'Discovered');

        if (discovered.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1/-1; text-align: center; padding: 40px; background: #f8fafc; border-radius: 8px;">
                    <div style="font-size: 40px; margin-bottom: 10px;">🔭</div>
                    <h3>No Candidates Found Yet</h3>
                    <p style="color: #64748b; margin-bottom: 20px;">Use the 'Run Discovery' button to scan for new competitors.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = discovered.map(c => renderCandidateCard(c)).join('');

    } catch (e) {
        grid.innerHTML = `<div class="error">Error loading candidates: ${e.message}</div>`;
    }
}

function renderCandidateCard(c) {
    // Parse notes for AI reasoning if available
    let reasoning = "No AI analysis available.";
    let score = c.relevance_score || 0;

    // Notes often contain the JSON from the agent, let's try to extract or display nicely
    // If notes is just a string, show it.
    if (c.notes) {
        reasoning = c.notes;
    }

    const scoreClass = score >= 80 ? 'high-score' : (score >= 50 ? 'med-score' : 'low-score');
    const scoreColor = score >= 80 ? '#22c55e' : (score >= 50 ? '#eab308' : '#cbd5e1');

    return `
        <div class="competitor-card discovery-card" style="border-left: 4px solid ${scoreColor}; position: relative;">
            <div class="card-header">
                <h3>${escapeHtml(c.name)}</h3>
                <span class="score-badge" style="background: ${scoreColor}; color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 0.85em; font-weight: bold;">
                    ${score}% Match
                </span>
            </div>
            <div class="card-body">
                <a href="${escapeHtml(c.website || '')}" target="_blank" class="website-link" style="font-size: 0.9em; display: inline-block; margin-bottom: 10px;">
                    🔗 ${escapeHtml(c.website || '')}
                </a>
                <div class="ai-reasoning" style="background: #f1f5f9; padding: 10px; border-radius: 6px; font-size: 0.9em; color: #334155; margin-bottom: 15px; max-height: 100px; overflow-y: auto;">
                    <strong>🤖 AI Analysis:</strong><br>
                    ${escapeHtml(reasoning || '')}
                </div>
            </div>
            <div class="card-footer" style="display: flex; gap: 8px; margin-top: auto;">
                <button class="btn btn-primary btn-sm" style="flex: 1;" onclick="approveCandidate(${c.id})">✅ Approve</button>
                <button class="btn btn-secondary btn-sm" style="flex: 1; border-color: #ef4444; color: #ef4444;" onclick="rejectCandidate(${c.id})">❌ Reject</button>
            </div>
        </div>
    `;
}

async function approveCandidate(id) {
    if (!confirm("Approve this competitor? It will be added to the main dashboard and a full scrape will be triggered.")) return;

    try {
        // 1. Update Status to Active
        await fetchAPI(`/api/competitors/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'Active' })
        });

        // 2. Trigger Scrape
        fetchAPI(`/api/scrape/${id}`, {
            method: 'POST'
        }); // Don't await, let it run in bg

        showToast("Competitor approved! Moving to dashboard...", "success");
        loadDiscoveredCandidates(); // Refresh list

    } catch (e) {
        showToast("Error approving candidate: " + e.message, "error");
    }
}

async function rejectCandidate(id) {
    if (!confirm("Reject this candidate? It will be hidden.")) return;

    try {
        await fetchAPI(`/api/competitors/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ status: 'Ignored' })
        });

        showToast("Candidate rejected.", "info");
        loadDiscoveredCandidates();

    } catch (e) {
        showToast("Error rejecting candidate: " + e.message, "error");
    }
}

// Hook into showPage to load data when tab is opened
// FIX v6.3.7: Call the original showPage first, then add discovery-specific logic
const originalShowPage = typeof showPage === 'function' ? showPage : null;
window.showPage = function (pageId) {
    // FIX v6.3.7: Call the original showPage which handles nav highlighting
    if (originalShowPage) {
        originalShowPage(pageId);
    } else {
        // Fallback: Handle nav and page switching manually
        // Step 1: Remove 'active' from ALL nav items
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        // Step 2: Add 'active' to matching nav item
        const activeNav = document.querySelector(`.nav-item[data-page="${pageId}"]`);
        if (activeNav) {
            activeNav.classList.add('active');
        }
        // Step 3: Hide all pages, show target page
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const targetPage = document.getElementById(pageId + 'Page');
        if (targetPage) {
            targetPage.classList.add('active');
        }
    }

    // Discovery-specific: load candidates when tab is opened
    if (pageId === 'discovered') {
        loadDiscoveryCandidates();
    }
};

// Also attach to the button in sidebar
document.addEventListener('DOMContentLoaded', () => {
    const discoveredLink = document.querySelector('a[data-page="discovered"]');
    if (discoveredLink) {
        discoveredLink.addEventListener('click', (e) => {
            e.preventDefault();
            showPage('discovered');
        });
    }
});

// ============== Prompt Selector Component (v7.2.0) ==============

/**
 * Reusable prompt selector dropdown for all pages.
 * Loads prompts from /api/admin/system-prompts?category=X
 * and renders a dropdown + preview/edit modal.
 *
 * Usage:
 *   initPromptSelector('battlecards', 'battlecardPromptSelect', onSelectCallback)
 */

// Cache loaded prompts by category
const _promptCache = {};

async function loadPromptsByCategory(category) {
    if (_promptCache[category]) return _promptCache[category];
    try {
        const prompts = await fetchAPI(`/api/admin/system-prompts?category=${category}`, { silent: true });
        _promptCache[category] = prompts || [];
        return _promptCache[category];
    } catch (e) {
        console.error(`Failed to load prompts for category: ${category}`, e);
        return [];
    }
}

function invalidatePromptCache(category) {
    if (category) {
        delete _promptCache[category];
    } else {
        Object.keys(_promptCache).forEach(k => delete _promptCache[k]);
    }
}

/**
 * Initialize a prompt selector dropdown on a page.
 * @param {string} category - Prompt category (dashboard, battlecards, news, discovery, competitor, knowledge_base)
 * @param {string} selectId - ID of the <select> element
 * @param {function} onSelect - Callback(promptObj) when user picks a prompt
 */
async function initPromptSelector(category, selectId, onSelect) {
    const selectEl = document.getElementById(selectId);
    if (!selectEl) return;

    const prompts = await loadPromptsByCategory(category);

    // Clear and rebuild options
    selectEl.innerHTML = '';
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = `-- Select a prompt (${prompts.length} available) --`;
    selectEl.appendChild(defaultOpt);

    prompts.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.key;
        opt.textContent = p.description || p.key;
        if (p.is_custom) opt.textContent += ' (custom)';
        opt.dataset.promptId = p.id;
        selectEl.appendChild(opt);
    });

    // Auto-select first prompt
    if (prompts.length > 0) {
        selectEl.value = prompts[0].key;
        if (onSelect) onSelect(prompts[0]);
    }

    selectEl.addEventListener('change', () => {
        const selected = prompts.find(p => p.key === selectEl.value);
        if (selected && onSelect) onSelect(selected);
    });

    return prompts;
}

/**
 * Get the currently selected prompt from a selector.
 */
function getSelectedPrompt(selectId, category) {
    const selectEl = document.getElementById(selectId);
    if (!selectEl || !selectEl.value) return null;
    const prompts = _promptCache[category] || [];
    return prompts.find(p => p.key === selectEl.value) || null;
}

/**
 * Open a modal to view/edit the currently selected prompt.
 */
function openPromptViewModal(selectId, category) {
    const prompt = getSelectedPrompt(selectId, category);
    if (!prompt) {
        showToast('Select a prompt first', 'warning');
        return;
    }

    // Create or reuse modal
    let modal = document.getElementById('promptViewModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'promptViewModal';
        modal.className = 'company-list-modal';
        document.body.appendChild(modal);
    }

    modal.style.display = 'block';
    modal.innerHTML = `
        <div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;">
            <div style="background:white;border-radius:12px;max-width:900px;width:95%;max-height:85vh;overflow:hidden;display:flex;flex-direction:column;">
                <div style="background:#1B2B65;color:white;padding:20px;display:flex;justify-content:space-between;align-items:center;">
                    <h3 style="margin:0;color:white!important;">${prompt.description || prompt.key}</h3>
                    <button onclick="closePromptViewModal()" style="background:none;border:none;color:white;font-size:24px;cursor:pointer;">&times;</button>
                </div>
                <div style="padding:20px;overflow-y:auto;flex:1;">
                    <p style="font-size:12px;color:#64748b;margin-bottom:8px;">
                        Category: <strong>${prompt.category || 'N/A'}</strong> &bull; Key: <code>${prompt.key}</code>
                        ${prompt.is_custom ? ' &bull; <span style="color:#2563eb;">Custom Override</span>' : ''}
                    </p>
                    <textarea id="promptViewTextarea"
                        style="width:100%;height:400px;padding:12px;border:1px solid #e2e8f0;border-radius:8px;font-family:monospace;font-size:13px;resize:vertical;line-height:1.5;"
                    >${prompt.content}</textarea>
                </div>
                <div style="padding:15px 20px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center;">
                    <button class="btn btn-secondary btn-sm" onclick="resetPromptToDefault('${prompt.key}', '${category}', '${selectId}')">Reset to Default</button>
                    <div style="display:flex;gap:10px;">
                        <button class="btn btn-secondary" onclick="closePromptViewModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="savePromptFromModal('${prompt.key}', '${category}', '${selectId}')">Save Changes</button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function closePromptViewModal() {
    const modal = document.getElementById('promptViewModal');
    if (modal) modal.style.display = 'none';
}

function closePromptEditorModal() {
    const modal = document.getElementById('promptEditorModal');
    if (modal) modal.style.display = 'none';
}
window.closePromptEditorModal = closePromptEditorModal;

async function refreshSavedPrompts() {
    const select = document.getElementById('savedPromptsSelect');
    if (!select) return;

    try {
        const prompts = await fetchAPI('/api/admin/system-prompts?category=dashboard');
        select.innerHTML = '<option value="">-- Select a saved prompt --</option>';
        if (prompts && prompts.length > 0) {
            prompts.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.key;
                opt.textContent = p.description || p.key;
                select.appendChild(opt);
            });
            showToast('Prompts refreshed', 'success');
        } else {
            showToast('No saved prompts found', 'info');
        }
    } catch (e) {
        showToast('Error loading prompts', 'error');
    }
}
window.refreshSavedPrompts = refreshSavedPrompts;

async function loadSelectedPrompt() {
    const select = document.getElementById('savedPromptsSelect');
    const textarea = document.getElementById('summaryPromptInput');
    if (!select || !textarea) return;

    const key = select.value;
    if (!key) {
        showToast('Please select a prompt first', 'warning');
        return;
    }

    try {
        const prompt = await fetchAPI(`/api/admin/system-prompts/${key}`);
        if (prompt && prompt.content) {
            textarea.value = prompt.content;
            showToast('Prompt loaded', 'success');
        }
    } catch (e) {
        showToast('Error loading prompt', 'error');
    }
}
window.loadSelectedPrompt = loadSelectedPrompt;

async function deleteSelectedPrompt() {
    const select = document.getElementById('savedPromptsSelect');
    if (!select || !select.value) {
        showToast('Please select a prompt first', 'warning');
        return;
    }

    if (!confirm('Delete this saved prompt?')) return;

    try {
        await fetchAPI(`/api/admin/system-prompts/${select.value}`, { method: 'DELETE' });
        showToast('Prompt deleted', 'success');
        await refreshSavedPrompts();
    } catch (e) {
        showToast('Error deleting prompt', 'error');
    }
}
window.deleteSelectedPrompt = deleteSelectedPrompt;

async function loadDefaultPrompt() {
    const textarea = document.getElementById('summaryPromptInput');
    if (!textarea) return;

    // Load whichever prompt is selected in the dropdown (not hardcoded key)
    const selectEl = document.getElementById('dashboardPromptSelect');
    const promptKey = (selectEl && selectEl.value) ? selectEl.value : 'dashboard_summary';

    try {
        const prompt = await fetchAPI(`/api/admin/system-prompts/${encodeURIComponent(promptKey)}`);
        if (prompt && prompt.content) {
            textarea.value = prompt.content;
        }
    } catch (e) {
        textarea.value = 'Generate a concise executive summary of competitive intelligence updates.';
        showToast('Loaded fallback default prompt', 'info');
    }
}
window.loadDefaultPrompt = loadDefaultPrompt;

async function saveSystemPrompt(key) {
    const textarea = document.getElementById('summaryPromptInput');
    if (!textarea) return;

    // Save to whichever prompt is selected in the dropdown
    const selectEl = document.getElementById('dashboardPromptSelect');
    const effectiveKey = (selectEl && selectEl.value) ? selectEl.value : key;

    try {
        await fetchAPI('/api/admin/system-prompts', {
            method: 'POST',
            body: JSON.stringify({
                key: effectiveKey,
                content: textarea.value,
                category: 'dashboard'
            })
        });
        // Invalidate prompt cache so next load gets the updated content
        invalidatePromptCache('dashboard');
        showToast('Prompt saved successfully', 'success');
        closePromptEditorModal();
    } catch (e) {
        showToast('Error saving prompt: ' + e.message, 'error');
    }
}
window.saveSystemPrompt = saveSystemPrompt;

async function saveAsNewPrompt() {
    const nameInput = document.getElementById('newPromptName');
    const textarea = document.getElementById('summaryPromptInput');
    if (!nameInput || !textarea) return;

    const name = nameInput.value.trim();
    if (!name) {
        showToast('Please enter a name for the prompt', 'warning');
        return;
    }

    const key = name.toLowerCase().replace(/[^a-z0-9]/g, '_');

    try {
        await fetchAPI('/api/admin/system-prompts', {
            method: 'POST',
            body: JSON.stringify({
                key: key,
                content: textarea.value,
                category: 'dashboard',
                description: name
            })
        });
        showToast('New prompt saved successfully', 'success');
        nameInput.value = '';
        await refreshSavedPrompts();
    } catch (e) {
        showToast('Error saving prompt: ' + e.message, 'error');
    }
}
window.saveAsNewPrompt = saveAsNewPrompt;

async function savePromptFromModal(key, category, selectId) {
    const textarea = document.getElementById('promptViewTextarea');
    if (!textarea) return;

    try {
        await fetchAPI('/api/admin/system-prompts', {
            method: 'POST',
            body: JSON.stringify({
                key: key,
                content: textarea.value,
                category: category,
            })
        });
        showToast('Prompt saved successfully', 'success');
        invalidatePromptCache(category);
        closePromptViewModal();
        // Reload dropdown
        await initPromptSelector(category, selectId, null);
    } catch (e) {
        showToast('Error saving prompt: ' + e.message, 'error');
    }
}

async function resetPromptToDefault(key, category, selectId) {
    if (!confirm('Reset this prompt to the system default? Your custom version will be removed.')) return;
    // Delete user-specific override — the global default will be used
    try {
        await fetchAPI(`/api/admin/system-prompts/${key}`, { method: 'DELETE' });
    } catch (e) {
        // May not have a delete endpoint yet, which is fine
    }
    invalidatePromptCache(category);
    closePromptViewModal();
    await initPromptSelector(category, selectId, null);
    showToast('Prompt reset to default', 'info');
}


// ============== AI Admin & Knowledge Base ==============

// Default prompts embedded for instant loading
const DEFAULT_PROMPTS = {
    'dashboard_summary': `You are Certify Health's competitive intelligence analyst. Generate a comprehensive, executive-level strategic summary using ONLY the LIVE data provided below.

**CRITICAL - PROVE YOU ARE USING LIVE DATA:**
- Start your summary with: "📊 **Live Intelligence Report** - Generated [TODAY'S DATE AND TIME]"
- State the EXACT total number of competitors being tracked (e.g., "Currently monitoring **X competitors**")
- Name at least 3-5 SPECIFIC competitor names from the data with their EXACT threat levels
- Quote SPECIFIC numbers: funding amounts, employee counts, pricing figures directly from the data
- Reference any recent changes or updates with their timestamps if available
- If a competitor has specific data points (headquarters, founding year, etc.), cite them exactly

**YOUR SUMMARY MUST INCLUDE:**

1. **📈 Executive Overview**
   - State exact competitor count and breakdown by threat level
   - Name the top 3 high-threat competitors BY NAME

2. **🎯 Threat Analysis**
   - List HIGH threat competitors by name with why they're threats
   - List MEDIUM threat competitors by name
   - Provide specific threat justifications using their data

3. **💰 Pricing Intelligence**
   - Name competitors with known pricing and their EXACT pricing models
   - Compare specific price points where available

4. **📊 Market Trends**
   - Reference specific data points that indicate trends
   - Name competitors showing growth signals

5. **✅ Strategic Recommendations**
   - 3-5 specific, actionable recommendations
   - Reference specific competitors in each recommendation

6. **👁️ Watch List**
   - Name the top 5 competitors requiring immediate attention
   - State WHY each is on the watch list with specific data

**IMPORTANT:** Every claim must reference actual data provided. Do NOT make up or assume any information. If data is missing, say "Data not available" rather than guessing.`,
    'chat_persona': 'You are a competitive intelligence analyst for Certify Health. Always reference specific data points and competitor names when answering questions. Cite exact numbers and dates when available.'
};

// Prompt cache for instant loading - initialize from localStorage first, then defaults
const PROMPT_STORAGE_KEY = 'certify_intel_prompts';

// Load cached prompts from localStorage immediately (synchronous, instant)
function loadPromptsFromStorage() {
    try {
        const stored = localStorage.getItem(PROMPT_STORAGE_KEY);
        if (stored) {
            return JSON.parse(stored);
        }
    } catch (e) {
    }
    return {};
}

// Save prompts to localStorage for instant access
function savePromptsToStorage(prompts) {
    try {
        localStorage.setItem(PROMPT_STORAGE_KEY, JSON.stringify(prompts));
    } catch (e) {
    }
}

// Initialize cache: localStorage first, then defaults as fallback
const storedPrompts = loadPromptsFromStorage();
const promptCache = {
    ...DEFAULT_PROMPTS,  // Defaults as base
    ...storedPrompts     // Override with any stored values
};

// ============== Knowledge Base Import (v5.0.8) ==============

/**
 * Initialize Knowledge Base Import status on Settings page load
 */
async function initKnowledgeBaseStatus() {
    try {
        // Scan folder to get file count
        const scanRes = await fetchAPI('/api/knowledge-base/scan');
        if (scanRes && Array.isArray(scanRes)) {
            document.getElementById('kbFilesCount').textContent = scanRes.length;
        }

        // Get verification queue count
        const queueRes = await fetchAPI('/api/knowledge-base/verification-queue');
        if (queueRes && Array.isArray(queueRes)) {
            document.getElementById('kbPendingCount').textContent = queueRes.length;
        }

        // Get competitor count
        const competitorsRes = await fetchAPI('/api/knowledge-base/competitor-names');
        if (competitorsRes && competitorsRes.count) {
            document.getElementById('kbCompetitorsCount').textContent = competitorsRes.count;
        }
    } catch (error) {
        console.error('Error initializing KB status:', error);
    }
}

/**
 * Preview what would be imported from the knowledge base
 */
async function previewKBImport() {
    const resultsDiv = document.getElementById('kbImportResults');
    const contentDiv = document.getElementById('kbImportResultsContent');

    resultsDiv.style.display = 'block';
    contentDiv.innerHTML = '<div class="loading">Scanning knowledge base files...</div>';

    try {
        const result = await fetchAPI('/api/knowledge-base/preview');

        if (result) {
            let html = `
                <div style="background: var(--glass-bg); padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center;">
                        <div>
                            <strong>${result.total_files}</strong><br>
                            <span style="font-size: 0.85em; color: var(--text-secondary);">Files Scanned</span>
                        </div>
                        <div>
                            <strong>${result.files_parsed}</strong><br>
                            <span style="font-size: 0.85em; color: var(--text-secondary);">Files Parsed</span>
                        </div>
                        <div>
                            <strong>${result.competitors_found}</strong><br>
                            <span style="font-size: 0.85em; color: var(--text-secondary);">Records Found</span>
                        </div>
                        <div>
                            <strong style="color: #4CAF50;">${result.unique_competitors}</strong><br>
                            <span style="font-size: 0.85em; color: var(--text-secondary);">Unique Competitors</span>
                        </div>
                    </div>
                </div>
            `;

            if (result.competitors && result.competitors.length > 0) {
                html += '<h5>Competitors to Import:</h5>';
                html += '<div style="max-height: 300px; overflow-y: auto; background: var(--card-bg); border-radius: 8px; padding: 10px;">';
                html += '<table style="width: 100%; font-size: 0.85em;">';
                html += '<thead><tr><th>Name</th><th>Website</th><th>Fields</th></tr></thead><tbody>';

                for (const comp of result.competitors.slice(0, 50)) {
                    html += `<tr>
                        <td><strong>${escapeHtml(comp.canonical_name)}</strong></td>
                        <td>${escapeHtml(comp.website || '-')}</td>
                        <td>${parseInt(comp.fields_populated) || 0} fields</td>
                    </tr>`;
                }

                if (result.competitors.length > 50) {
                    html += `<tr><td colspan="3" style="text-align: center; color: var(--text-secondary);">... and ${result.competitors.length - 50} more</td></tr>`;
                }

                html += '</tbody></table></div>';
            }

            if (result.errors && result.errors.length > 0) {
                html += `<div style="margin-top: 10px; color: #F44336;"><strong>Errors (${result.errors.length}):</strong> ${escapeHtml(result.errors[0])}</div>`;
            }

            contentDiv.innerHTML = html;
        }
    } catch (error) {
        contentDiv.innerHTML = `<div style="color: #F44336;">Error: ${escapeHtml(error.message || 'An error occurred')}</div>`;
    }
}

/**
 * Run the actual import from knowledge base
 */
async function runKBImport() {
    if (!confirm('This will import all competitor data from the Certify Health knowledge base. Continue?')) {
        return;
    }

    const resultsDiv = document.getElementById('kbImportResults');
    const contentDiv = document.getElementById('kbImportResultsContent');

    resultsDiv.style.display = 'block';
    contentDiv.innerHTML = '<div class="loading">Importing competitors...</div>';

    try {
        const result = await fetchAPI('/api/knowledge-base/import', {
            method: 'POST',
            body: JSON.stringify({ dry_run: false, overwrite_existing: false })
        });

        if (result && result.success) {
            let html = `
                <div style="background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <h4 style="margin: 0 0 10px 0;">✓ Import Complete!</h4>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; text-align: center;">
                        <div>
                            <strong style="font-size: 1.5em;">${result.competitors_imported}</strong><br>
                            New Competitors
                        </div>
                        <div>
                            <strong style="font-size: 1.5em;">${result.competitors_updated}</strong><br>
                            Updated
                        </div>
                        <div>
                            <strong style="font-size: 1.5em;">${result.competitors_skipped}</strong><br>
                            Skipped
                        </div>
                    </div>
                </div>
            `;

            if (result.imported && result.imported.length > 0) {
                html += '<h5>Imported Competitors:</h5>';
                html += '<div style="max-height: 200px; overflow-y: auto;">';

                for (const comp of result.imported.slice(0, 20)) {
                    const badge = comp.is_new
                        ? '<span class="source-badge-client">NEW</span>'
                        : '<span class="source-badge-client verified">UPDATED</span>';
                    html += `<div style="padding: 5px 0; border-bottom: 1px solid var(--border-color);">
                        ${badge} ${escapeHtml(comp.name)}
                    </div>`;
                }

                if (result.imported.length > 20) {
                    html += `<div style="padding: 10px; text-align: center; color: var(--text-secondary);">... and ${result.imported.length - 20} more</div>`;
                }

                html += '</div>';
            }

            contentDiv.innerHTML = html;

            // Refresh competitor list
            await loadCompetitors();

            // Update KB status
            await initKnowledgeBaseStatus();

            showNotification('Knowledge base import complete!', 'success');
        } else {
            contentDiv.innerHTML = `<div style="color: #F44336;">Import failed: ${escapeHtml(result?.errors?.join(', ') || 'Unknown error')}</div>`;
        }
    } catch (error) {
        contentDiv.innerHTML = `<div style="color: #F44336;">Error: ${escapeHtml(error.message || 'An error occurred')}</div>`;
    }
}

/**
 * Render source badge for data from Certify Health
 */
function renderSourceBadge(source) {
    if (!source) return '';

    if (source.source_type === 'client_provided') {
        // Check if this is preinstalled data
        const isPreinstalled = source.source_name && source.source_name.includes('Preinstalled');
        const verifiedClass = source.is_verified ? 'verified' : 'unverified';

        if (isPreinstalled) {
            // Preinstalled data - special purple badge
            const tooltip = 'Preinstalled from Certify Health knowledge base';
            return `<span class="source-badge-preinstalled" title="${tooltip}">Certify Health</span>`;
        }

        // Manual import - green badge
        const tooltip = source.is_verified
            ? `Verified by ${source.verified_by || 'admin'}`
            : 'Pending verification';
        return `<span class="source-badge-client ${verifiedClass}" title="${tooltip}">Certify Health</span>`;
    }

    // Default source icons for other types
    const icons = {
        'sec_filing': '📊',
        'api': '🔗',
        'website_scrape': '🌐',
        'manual': '✏️',
        'news': '📰'
    };

    return `<span class="source-icon ${escapeHtml(source.source_type || '')}" title="${escapeHtml(source.source_name || source.source_type || '')}">${icons[source.source_type] || '📄'}</span>`;
}

// ============== Verification Queue (v5.0.8) ==============

let verificationQueueData = [];

/**
 * Load and display the verification queue
 */
async function loadVerificationQueue() {
    const queueDiv = document.getElementById('verificationQueue');
    const pendingCount = document.getElementById('verifyPendingCount');

    queueDiv.innerHTML = '<div class="loading">Loading verification queue...</div>';

    try {
        const result = await fetchAPI('/api/knowledge-base/verification-queue');
        verificationQueueData = result || [];

        if (pendingCount) {
            pendingCount.textContent = verificationQueueData.length;
        }

        if (!verificationQueueData.length) {
            queueDiv.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <div style="font-size: 3em; margin-bottom: 10px;">✓</div>
                    <h3>All Clear!</h3>
                    <p>No data pending verification.</p>
                    <button class="btn btn-secondary" onclick="navigateTo('settings')">← Back to Settings</button>
                </div>
            `;
            return;
        }

        // Group by competitor
        const byCompetitor = {};
        for (const item of verificationQueueData) {
            if (!byCompetitor[item.competitor_name]) {
                byCompetitor[item.competitor_name] = [];
            }
            byCompetitor[item.competitor_name].push(item);
        }

        let html = '';
        for (const [compName, items] of Object.entries(byCompetitor)) {
            html += `
                <div class="verification-competitor" style="background: var(--card-bg); border-radius: 8px; margin-bottom: 15px; overflow: hidden;">
                    <div style="background: var(--glass-bg); padding: 12px 15px; border-bottom: 1px solid var(--border-color);">
                        <strong>${compName}</strong>
                        <span style="color: var(--text-secondary); font-size: 0.85em; margin-left: 10px;">${items.length} fields</span>
                    </div>
                    <div style="padding: 15px;">
            `;

            for (const item of items) {
                html += `
                    <div class="verification-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border-color);" data-source-id="${item.source_id}">
                        <div>
                            <div style="font-weight: 500;">${item.field_name.replace(/_/g, ' ')}</div>
                            <div style="color: var(--primary-color); font-size: 0.95em;">${item.value}</div>
                            <div style="font-size: 0.8em; color: var(--text-secondary);">
                                <span class="source-badge-client unverified">Certify Health</span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 5px;">
                            <button class="btn btn-sm btn-primary" onclick="approveVerification(${item.source_id})" title="Approve">✓</button>
                            <button class="btn btn-sm btn-secondary" onclick="editVerification(${item.source_id}, '${item.value.replace(/'/g, "\\'")}')" title="Edit">✏️</button>
                            <button class="btn btn-sm btn-danger" onclick="rejectVerification(${item.source_id})" title="Reject">✗</button>
                        </div>
                    </div>
                `;
            }

            html += '</div></div>';
        }

        queueDiv.innerHTML = html;

    } catch (error) {
        queueDiv.innerHTML = `<div style="color: #F44336; padding: 20px;">Error loading queue: ${escapeHtml(error.message || 'An error occurred')}</div>`;
    }
}

/**
 * Approve a single verification item
 */
async function approveVerification(sourceId) {
    try {
        await fetchAPI(`/api/knowledge-base/verification/approve/${sourceId}`, { method: 'POST' });

        // Remove from UI
        const itemDiv = document.querySelector(`[data-source-id="${sourceId}"]`);
        if (itemDiv) {
            itemDiv.style.background = '#4CAF5020';
            itemDiv.innerHTML = '<div style="padding: 10px; color: #4CAF50;">✓ Approved</div>';
            setTimeout(() => itemDiv.remove(), 1000);
        }

        // Update count
        const pendingCount = document.getElementById('verifyPendingCount');
        if (pendingCount) {
            pendingCount.textContent = Math.max(0, parseInt(pendingCount.textContent) - 1);
        }

        showNotification('Data point approved', 'success');

    } catch (error) {
        showNotification('Failed to approve: ' + error.message, 'error');
    }
}

/**
 * Edit a verification item value
 */
async function editVerification(sourceId, currentValue) {
    const newValue = prompt('Edit value:', currentValue);

    if (newValue !== null && newValue !== currentValue) {
        try {
            await fetchAPI(`/api/knowledge-base/verification/approve/${sourceId}?corrected_value=${encodeURIComponent(newValue)}`, {
                method: 'POST'
            });

            // Remove from UI
            const itemDiv = document.querySelector(`[data-source-id="${sourceId}"]`);
            if (itemDiv) {
                itemDiv.style.background = '#4CAF5020';
                itemDiv.innerHTML = `<div style="padding: 10px; color: #4CAF50;">✓ Updated to "${newValue}"</div>`;
                setTimeout(() => itemDiv.remove(), 1500);
            }

            showNotification('Data point updated and approved', 'success');

        } catch (error) {
            showNotification('Failed to update: ' + error.message, 'error');
        }
    }
}

/**
 * Reject a verification item
 */
async function rejectVerification(sourceId) {
    if (!confirm('Reject this data point? It will be removed from the competitor record.')) {
        return;
    }

    try {
        await fetchAPI(`/api/knowledge-base/verification/reject/${sourceId}`, { method: 'POST' });

        // Remove from UI
        const itemDiv = document.querySelector(`[data-source-id="${sourceId}"]`);
        if (itemDiv) {
            itemDiv.style.background = '#F4433620';
            itemDiv.innerHTML = '<div style="padding: 10px; color: #F44336;">✗ Rejected</div>';
            setTimeout(() => itemDiv.remove(), 1000);
        }

        // Update count
        const pendingCount = document.getElementById('verifyPendingCount');
        if (pendingCount) {
            pendingCount.textContent = Math.max(0, parseInt(pendingCount.textContent) - 1);
        }

        showNotification('Data point rejected', 'info');

    } catch (error) {
        showNotification('Failed to reject: ' + error.message, 'error');
    }
}

/**
 * Bulk approve all visible verification items
 */
async function bulkApproveVerification() {
    if (!verificationQueueData.length) {
        showNotification('No items to approve', 'info');
        return;
    }

    if (!confirm(`Approve all ${verificationQueueData.length} data points?`)) {
        return;
    }

    try {
        const sourceIds = verificationQueueData.map(item => item.source_id);

        await fetchAPI('/api/knowledge-base/verification/bulk-approve', {
            method: 'POST',
            body: JSON.stringify(sourceIds)
        });

        showNotification(`Approved ${sourceIds.length} data points`, 'success');

        // Reload queue
        await loadVerificationQueue();

    } catch (error) {
        showNotification('Bulk approve failed: ' + error.message, 'error');
    }
}

function openPromptEditor() {
    // Open the full-featured prompt editor modal (has all dashboard prompts + save/edit)
    const fullModal = document.getElementById('promptEditorModal');
    if (fullModal) {
        fullModal.style.display = 'block';
        // Auto-populate saved prompts dropdown
        refreshSavedPrompts();
        // Load selected prompt into textarea
        loadDefaultPrompt();
        // Sync dropdown changes to textarea
        const selectEl = document.getElementById('dashboardPromptSelect');
        if (selectEl && !selectEl._promptSyncWired) {
            selectEl._promptSyncWired = true;
            selectEl.addEventListener('change', () => loadDefaultPrompt());
        }
        return;
    }
    // Fallback to legacy modal
    const modal = document.getElementById('promptModal');
    if (modal) modal.classList.add('active');
    loadPromptContent();
}

function closePromptModal() {
    const modal = document.getElementById('promptModal');
    if (modal) modal.classList.remove('active');
    document.getElementById('promptSaveStatus').style.display = 'none';
}

async function loadPromptContent() {
    const key = document.getElementById('promptKeySelector').value;
    const editor = document.getElementById('promptContentEditor');

    // Show loading state initially
    editor.value = promptCache[key] || DEFAULT_PROMPTS[key] || 'Loading...';

    // Fetch from server (no timeout - let it complete)
    try {
        const response = await fetchAPI(`/api/admin/system-prompts/${key}`);

        if (response && response.content) {
            editor.value = response.content;
            promptCache[key] = response.content;
            savePromptsToStorage(promptCache);
        } else if (!editor.value || editor.value === 'Loading...') {
            // Fallback to default if no server response
            editor.value = DEFAULT_PROMPTS[key] || '';
        }
    } catch (e) {
        // Error - use cached or default value
        editor.value = promptCache[key] || DEFAULT_PROMPTS[key] || '';
    }
}

async function savePromptContent() {
    const key = document.getElementById('promptKeySelector').value;
    const content = document.getElementById('promptContentEditor').value;

    // Update cache and localStorage IMMEDIATELY before server call
    promptCache[key] = content;
    savePromptsToStorage(promptCache);

    const result = await fetchAPI('/api/admin/system-prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, content })
    });

    if (result) {
        const status = document.getElementById('promptSaveStatus');
        status.style.display = 'inline-block';
        setTimeout(() => status.style.display = 'none', 3000);
    }
}

// Preload prompts on page load to sync with server (background task)
async function preloadPrompts() {
    const keys = ['dashboard_summary', 'chat_persona'];
    for (const key of keys) {
        try {
            const response = await fetchAPI(`/api/admin/system-prompts/${key}`, { silent: true });
            if (response && response.content) {
                promptCache[key] = response.content;
            }
        } catch (e) {
        }
    }
    // Save any fetched prompts to localStorage for next time
    savePromptsToStorage(promptCache);
}

// =========================================================================
// KNOWLEDGE BASE - File Upload & Management
// =========================================================================

// Store selected file for upload
let kbSelectedFile = null;

function openKnowledgeBase() {
    const modal = document.getElementById('kbModal');
    if (modal) modal.classList.add('active');
    loadKbItems();
    loadKbCompetitorDropdown();
}

async function loadKbCompetitorDropdown() {
    // Populate the competitor dropdown for linking
    const select = document.getElementById('kbLinkedCompetitors');
    if (!select) return;

    try {
        // Use cached competitors if available
        let competitorList = competitors;
        if (!competitorList || competitorList.length === 0) {
            const data = await fetchAPI('/api/competitors');
            competitorList = data || [];
        }

        select.innerHTML = competitorList
            .filter(c => !c.is_deleted)
            .sort((a, b) => a.name.localeCompare(b.name))
            .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
            .join('');
    } catch (error) {
        console.warn('Failed to load competitors for KB dropdown:', error);
        select.innerHTML = '<option value="">Failed to load competitors</option>';
    }
}

function closeKbModal() {
    const modal = document.getElementById('kbModal');
    if (modal) modal.classList.remove('active');
    hideAddKbForm();
    clearKbFile();
}

async function loadKbItems() {
    const list = document.getElementById('kbList');
    list.innerHTML = '<div class="loading">Loading...</div>';

    const items = await fetchAPI('/api/admin/knowledge-base');
    if (items && items.length > 0) {
        list.innerHTML = items.map(item => `
            <div class="kb-item">
                <div class="kb-item-info">
                    <div class="kb-item-title">${escapeHtml(item.title || '')}</div>
                    <div class="kb-item-meta">
                        <span>${escapeHtml(item.content_type || item.source_type || 'text')}</span>
                        <span>•</span>
                        <span>${formatDate(item.created_at)}</span>
                        ${item.category ? `<span class="kb-item-tag">${escapeHtml(item.category)}</span>` : ''}
                    </div>
                    <div style="font-size: 12px; color: #8B9AC1; margin-top: 4px; max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                        ${escapeHtml((item.content_text || item.content || '').substring(0, 100))}...
                    </div>
                </div>
                <div class="kb-item-actions">
                    <button class="btn btn-sm btn-danger" onclick="deleteKbItem(${item.id})">Delete</button>
                </div>
            </div>
        `).join('');
    } else {
        list.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #8B9AC1;">No knowledge base items found. Add documents to give the AI context.</div>';
    }
}

function showAddKbItem() {
    document.getElementById('addKbForm').style.display = 'block';
    document.getElementById('kbList').style.display = 'none';
    // Reset to upload tab by default
    switchKbTab('upload');
    // Load competitor dropdown for linking
    loadKbCompetitorDropdown();
}

function hideAddKbForm() {
    document.getElementById('addKbForm').style.display = 'none';
    document.getElementById('kbList').style.display = 'block';
    clearKbFile();
    // Clear form fields
    const titleInput = document.getElementById('kbTitle');
    const contentInput = document.getElementById('kbContent');
    const uploadTitleInput = document.getElementById('kbUploadTitle');
    const categoryInput = document.getElementById('kbCategory');
    const tagsInput = document.getElementById('kbTags');
    if (titleInput) titleInput.value = '';
    if (contentInput) contentInput.value = '';
    if (uploadTitleInput) uploadTitleInput.value = '';
    if (categoryInput) categoryInput.value = 'general';
    if (tagsInput) tagsInput.value = '';
}

// Tab switching
function switchKbTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.kb-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Show/hide content
    document.getElementById('kbUploadTab').style.display = tab === 'upload' ? 'block' : 'none';
    document.getElementById('kbTextTab').style.display = tab === 'text' ? 'block' : 'none';
}

// Drag and drop handlers
function handleKbDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('kbDropZone').classList.add('drag-over');
}

function handleKbDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('kbDropZone').classList.remove('drag-over');
}

function handleKbDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    document.getElementById('kbDropZone').classList.remove('drag-over');

    const files = event.dataTransfer.files;
    if (files.length > 0) {
        handleKbFileSelection(files[0]);
    }
}

// Click to browse
document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('kbDropZone');
    if (dropZone) {
        dropZone.addEventListener('click', function() {
            document.getElementById('kbFileInput').click();
        });
    }
});

function handleKbFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        handleKbFileSelection(files[0]);
    }
}

function handleKbFileSelection(file) {
    // Validate file type
    const allowedTypes = ['.pdf', '.docx', '.txt', '.md', '.html'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(ext)) {
        showToast(`Unsupported file type: ${ext}. Allowed: ${allowedTypes.join(', ')}`, 'error');
        return;
    }

    // Validate file size (50MB)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast(`File too large. Maximum size: 50MB`, 'error');
        return;
    }

    kbSelectedFile = file;

    // Show preview
    document.getElementById('kbDropZone').style.display = 'none';
    document.getElementById('kbFilePreview').style.display = 'flex';
    document.getElementById('kbFileName').textContent = file.name;
    document.getElementById('kbFileSize').textContent = formatFileSize(file.size);
}

function clearKbFile() {
    kbSelectedFile = null;
    document.getElementById('kbFileInput').value = '';
    document.getElementById('kbDropZone').style.display = 'block';
    document.getElementById('kbFilePreview').style.display = 'none';
    document.getElementById('kbUploadProgress').style.display = 'none';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function saveKbItem() {
    // Check which tab is active
    const isUploadTab = document.getElementById('kbUploadTab').style.display !== 'none';

    if (isUploadTab) {
        await uploadKbFile();
    } else {
        await saveKbText();
    }
}

async function uploadKbFile() {
    if (!kbSelectedFile) {
        showToast('Please select a file to upload', 'error');
        return;
    }

    const title = document.getElementById('kbUploadTitle').value;
    const category = document.getElementById('kbCategory').value;
    const tags = document.getElementById('kbTags').value;

    // Validate category is selected
    if (!category) {
        showToast('Please select a document category', 'error');
        const categoryInput = document.getElementById('kbCategory');
        if (categoryInput) {
            showFieldError(categoryInput, 'Please select a category');
        }
        return;
    }

    // v7.1 Enhanced options
    const documentDate = document.getElementById('kbDocumentDate')?.value || '';
    const dataAsOfDate = document.getElementById('kbDataAsOfDate')?.value || '';
    const extractEntities = document.getElementById('kbExtractEntities')?.checked ?? true;
    const autoLink = document.getElementById('kbAutoLink')?.checked ?? true;

    // Get linked competitors
    const linkedCompSelect = document.getElementById('kbLinkedCompetitors');
    const linkedCompetitors = linkedCompSelect
        ? Array.from(linkedCompSelect.selectedOptions).map(opt => parseInt(opt.value))
        : [];

    // Show progress
    document.getElementById('kbFilePreview').style.display = 'none';
    document.getElementById('kbUploadProgress').style.display = 'block';
    document.getElementById('kbProgressBar').style.width = '0%';
    document.getElementById('kbProgressText').textContent = extractEntities
        ? 'Uploading and extracting entities...'
        : 'Uploading...';

    // Disable save button
    const saveBtn = document.getElementById('kbSaveBtn');
    saveBtn.disabled = true;
    document.getElementById('kbSaveBtnText').textContent = 'Processing...';

    try {
        const formData = new FormData();
        formData.append('file', kbSelectedFile);
        if (title) formData.append('title', title);
        formData.append('category', category);
        if (tags) formData.append('tags', tags);

        // v7.1 Enhanced fields
        if (documentDate) formData.append('document_date', documentDate);
        if (dataAsOfDate) formData.append('data_as_of_date', dataAsOfDate);
        formData.append('extract_entities', extractEntities.toString());
        formData.append('auto_link', autoLink.toString());
        if (linkedCompetitors.length > 0) {
            formData.append('linked_competitors', JSON.stringify(linkedCompetitors));
        }

        // Simulate progress with deterministic increments
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += extractEntities ? 8 : 15;
            if (progress > 90) progress = 90;
            document.getElementById('kbProgressBar').style.width = progress + '%';

            // Update progress text based on stage
            if (progress > 60 && extractEntities) {
                document.getElementById('kbProgressText').textContent = 'Extracting entities...';
            } else if (progress > 30) {
                document.getElementById('kbProgressText').textContent = 'Processing document...';
            }
        }, 300);

        // Use enhanced upload endpoint if extracting entities
        const endpoint = extractEntities
            ? `${API_BASE}/api/kb/upload-with-extraction`
            : `${API_BASE}/api/admin/knowledge-base/upload`;

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: formData
        });

        clearInterval(progressInterval);
        document.getElementById('kbProgressBar').style.width = '100%';

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const result = await response.json();

        // Check for duplicate
        if (result.status === 'duplicate') {
            document.getElementById('kbProgressText').innerHTML = `
                <span class="kb-upload-error">Document already exists (ID: ${result.existing_id})</span>
            `;
            showToast('This document is already in the Knowledge Base', 'warning');
            return;
        }

        // Build success message
        let successDetails = `${result.word_count || 0} words`;
        if (result.extraction) {
            const ext = result.extraction;
            const extracted = [];
            if (ext.extraction?.competitors_found) extracted.push(`${ext.extraction.competitors_found} competitors`);
            if (ext.extraction?.metrics_found) extracted.push(`${ext.extraction.metrics_found} metrics`);
            if (ext.linking?.total_links) extracted.push(`${ext.linking.total_links} links`);
            if (extracted.length > 0) {
                successDetails += ` | Extracted: ${extracted.join(', ')}`;
            }
        }
        if (result.explicit_links_created > 0) {
            successDetails += ` | ${result.explicit_links_created} explicit links`;
        }

        document.getElementById('kbProgressText').innerHTML = `
            <span class="kb-upload-success">✓ Uploaded successfully!</span>
            <br><small>${successDetails}</small>
        `;

        showToast(`Document "${result.title}" added to Knowledge Base`, 'success');

        // Show detailed extraction results if entities were extracted
        if (result.extraction && (result.extraction.extraction?.competitors || result.extraction.extraction?.products || result.extraction.extraction?.metrics)) {
            showKbExtractionResults(result);
        }

        // Reload list after delay
        setTimeout(() => {
            hideAddKbForm();
            loadKbItems();
        }, 1500);

    } catch (error) {
        document.getElementById('kbProgressText').innerHTML = `
            <span class="kb-upload-error">✗ Upload failed: ${error.message}</span>
        `;
        showToast(`Upload failed: ${error.message}`, 'error');
    } finally {
        saveBtn.disabled = false;
        document.getElementById('kbSaveBtnText').textContent = 'Save Document';
    }
}

async function saveKbText() {
    const title = document.getElementById('kbTitle').value;
    const content = document.getElementById('kbContent').value;

    if (!title || !content) {
        showToast("Please provide both title and content", "error");
        return;
    }

    const saveBtn = document.getElementById('kbSaveBtn');
    saveBtn.disabled = true;
    document.getElementById('kbSaveBtnText').textContent = 'Saving...';

    try {
        const result = await fetchAPI('/api/admin/knowledge-base', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                content_text: content,
                source_type: "manual"
            })
        });

        if (result) {
            showToast("Document added to Knowledge Base", "success");
            hideAddKbForm();
            loadKbItems();
        }
    } finally {
        saveBtn.disabled = false;
        document.getElementById('kbSaveBtnText').textContent = 'Save Document';
    }
}

/**
 * Show modal with detailed entity extraction results from KB upload
 * P1-5: KB Upload Entity Extraction Feedback
 */
function showKbExtractionResults(result) {
    const extraction = result.extraction?.extraction || {};
    const linking = result.extraction?.linking || {};

    // Build competitor list
    const competitors = extraction.competitors || [];
    const competitorHTML = competitors.length > 0
        ? `<ul class="extraction-list">${competitors.map(c =>
            `<li><span class="entity-icon">🏢</span> ${escapeHtml(c)}</li>`
        ).join('')}</ul>`
        : '<p class="no-entities">No competitors detected</p>';

    // Build product list
    const products = extraction.products || [];
    const productHTML = products.length > 0
        ? `<ul class="extraction-list">${products.map(p =>
            `<li><span class="entity-icon">📦</span> ${escapeHtml(p)}</li>`
        ).join('')}</ul>`
        : '<p class="no-entities">No products detected</p>';

    // Build metrics list
    const metrics = extraction.metrics || [];
    const metricsHTML = metrics.length > 0
        ? `<ul class="extraction-list">${metrics.map(m =>
            `<li><span class="entity-icon">📊</span> ${escapeHtml(m.name || m)}: <strong>${m.value || ''}</strong></li>`
        ).join('')}</ul>`
        : '<p class="no-entities">No metrics detected</p>';

    // Build links summary
    const linksHTML = linking.total_links > 0
        ? `<p class="links-summary"><span class="entity-icon">🔗</span> ${linking.total_links} entities linked to existing records</p>`
        : '';

    const modalContent = `
        <div class="kb-extraction-modal">
            <h2>📄 Entity Extraction Results</h2>
            <p style="color: var(--text-secondary); margin-bottom: 20px;">
                The following entities were automatically extracted from <strong>${escapeHtml(result.title)}</strong>:
            </p>

            <div class="extraction-section">
                <h4><span class="entity-icon">🏢</span> Competitors (${competitors.length})</h4>
                ${competitorHTML}
            </div>

            <div class="extraction-section">
                <h4><span class="entity-icon">📦</span> Products (${products.length})</h4>
                ${productHTML}
            </div>

            <div class="extraction-section">
                <h4><span class="entity-icon">📊</span> Metrics (${metrics.length})</h4>
                ${metricsHTML}
            </div>

            ${linksHTML}

            <div class="modal-actions" style="margin-top: 20px;">
                <button onclick="closeModal()" class="btn btn-primary">Done</button>
            </div>
        </div>
    `;

    showModal(modalContent);
}

// Helper function for escaping HTML in extraction results
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function extractDomain(url) {
    try { return new URL(url).hostname.replace('www.', ''); }
    catch { return ''; }
}

/**
 * Close the correction modal
 */
function closeCorrectionModal() {
    const modal = document.getElementById('correctionModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
}
window.closeCorrectionModal = closeCorrectionModal;


async function deleteKbItem(id) {
    if (!confirm("Are you sure you want to delete this item?")) return;

    const result = await fetchAPI(`/api/admin/knowledge-base/${id}`, { method: 'DELETE' });
    if (result) {
        showToast("Item deleted", "info");
        loadKbItems();
    }
}

// =====================================================
// PHASE 6: DATA SOURCES MODAL & CONFIDENCE DISPLAY
// =====================================================

/**
 * Open the Data Sources modal for a competitor
 * @param {number} competitorId - The competitor ID
 */
async function viewDataSources(competitorId) {
    const modal = document.getElementById('dataSourcesModal');
    const container = document.getElementById('dataSourcesTableContainer');

    if (!modal || !container) {
        console.error('Data Sources modal elements not found');
        return;
    }

    // Show loading state
    container.innerHTML = '<p class="loading" style="text-align:center;padding:40px;">Loading data sources...</p>';
    modal.classList.add('active');

    try {
        // Fetch data sources for this competitor
        const sources = await fetchAPI(`/api/competitors/${competitorId}/data-sources`);
        const competitor = competitors.find(c => c.id === competitorId);
        const compName = competitor?.name || 'Unknown Competitor';

        // Update modal header
        const header = modal.querySelector('h3');
        if (header) {
            header.innerHTML = `📋 Data Sources: ${compName}`;
        }

        if (!sources || sources.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <p style="font-size: 48px; margin-bottom: 16px;">📭</p>
                    <p style="font-size: 16px; font-weight: 600;">No source data available</p>
                    <p style="font-size: 14px; margin-top: 8px;">Run a data refresh or enhanced scrape to collect source attribution.</p>
                    <button class="btn btn-primary" onclick="triggerEnhancedScrape(${competitorId})" style="margin-top: 16px;">
                        🔄 Run Enhanced Scrape
                    </button>
                </div>
            `;
            return;
        }

        // Build the sources table
        container.innerHTML = renderDataSourcesTable(sources);
    } catch (error) {
        console.error('Error loading data sources:', error);
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #dc3545;">
                <p style="font-size: 48px; margin-bottom: 16px;">⚠️</p>
                <p style="font-size: 16px; font-weight: 600;">Error loading data sources</p>
                <p style="font-size: 14px; margin-top: 8px;">${error.message || 'Unknown error occurred'}</p>
            </div>
        `;
    }
}

/**
 * Render the data sources table HTML
 */
function renderDataSourcesTable(sources) {
    const rows = sources.map(s => {
        const confidenceLevel = s.confidence?.level || getConfidenceLevelFromScore(s.confidence?.score);
        const confidenceScore = s.confidence?.score || 0;
        const isVerified = s.is_verified;
        const sourceType = s.source_type || 'unknown';
        const fieldName = formatFieldName(s.field);
        const value = s.value || '—';
        const extractedAt = s.extracted_at ? formatDate(s.extracted_at) : '—';

        return `
            <tr>
                <td class="field-name">${fieldName}</td>
                <td class="field-value" title="${value}">${truncateText(value, 40)}</td>
                <td class="source-info">
                    <span class="source-type-badge ${sourceType}">${formatSourceType(sourceType)}</span>
                    ${s.source_url ? `<a href="${s.source_url}" target="_blank" class="source-link-icon" title="Open source">🔗</a>` : ''}
                </td>
                <td>
                    <div class="confidence-cell">
                        <div class="confidence-bar">
                            <div class="fill ${confidenceLevel}" style="width: ${confidenceScore}%"></div>
                        </div>
                        <span class="confidence-score ${confidenceLevel}">${confidenceScore}/100</span>
                    </div>
                </td>
                <td>
                    <span class="verified-badge ${isVerified ? 'verified' : 'unverified'}">
                        ${isVerified ? '✓ Verified' : '○ Pending'}
                    </span>
                </td>
                <td class="updated-at">${extractedAt}</td>
            </tr>
        `;
    }).join('');

    return `
        <table class="sources-table">
            <thead>
                <tr>
                    <th>Field</th>
                    <th>Value</th>
                    <th>Source</th>
                    <th>Confidence</th>
                    <th>Status</th>
                    <th>Last Updated</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

/**
 * Close the data sources modal
 */
function closeDataSourcesModal(event) {
    const modal = document.getElementById('dataSourcesModal');
    if (modal) {
        // Only close if clicking on overlay or close button
        if (!event || event.target === modal || event.target.classList.contains('close-btn')) {
            modal.classList.remove('active');
        }
    }
}


/**
 * Format source type for display
 */
function formatSourceType(type) {
    const typeLabels = {
        'sec_filing': 'SEC',
        'api_verified': 'API',
        'api': 'API',
        'website_scrape': 'Website',
        'manual': 'Manual',
        'manual_verified': 'Verified',
        'news_article': 'News',
        'klas_report': 'KLAS',
        'linkedin_estimate': 'LinkedIn',
        'crunchbase': 'Crunchbase',
        'unknown': 'Unknown'
    };
    return typeLabels[type] || type.replace(/_/g, ' ');
}

/**
 * Truncate text with ellipsis
 */
function truncateText(text, maxLength) {
    if (!text) return '—';
    const str = String(text);
    if (str.length <= maxLength) return str;
    return str.substring(0, maxLength) + '...';
}

/**
 * Trigger enhanced scrape with source tracking
 */
async function triggerEnhancedScrape(competitorId) {
    const competitor = competitors.find(c => c.id === competitorId);
    if (!competitor) {
        showToast('Competitor not found', 'error');
        return;
    }

    showToast(`Starting enhanced scrape for ${competitor.name}...`, 'info');

    try {
        const result = await fetchAPI(`/api/scrape/enhanced/${competitorId}`, {
            method: 'POST'
        });

        if (result) {
            showToast(`Enhanced scrape complete for ${competitor.name}`, 'success');
            // Reload data sources modal
            viewDataSources(competitorId);
        }
    } catch (error) {
        console.error('Enhanced scrape error:', error);
        showToast(`Error: ${error.message || 'Enhanced scrape failed'}`, 'error');
    }
}


// ============== News Feed Functions (v5.0.3 - Phase 1) ==============

// Expose currentNewsPage globally for HTML onclick handlers
// Use 'var' to make it a global variable accessible from inline HTML onclick handlers
var currentNewsPage = 1;
window.currentNewsPage = currentNewsPage;  // Also expose on window for consistency
const NEWS_PAGE_SIZE = 25;
let newsFeedData = [];

/**
 * Initialize the News Feed page
 */
async function initNewsFeedPage() {

    // Set default date range (last 30 days)
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    document.getElementById('newsDateFrom').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('newsDateTo').value = today.toISOString().split('T')[0];

    // Populate competitor dropdown
    await populateNewsCompetitorDropdown();

    // Resume fetch progress if a fetch is running, otherwise load feed
    if (!resumeNewsFetchIfRunning()) {
        await loadNewsFeed();
    }

    // Load sentiment trend chart (non-blocking)
    loadSentimentTrendChart(null, 30).catch(() => {});
}

/**
 * Populate the competitor dropdown in news feed filters
 */
async function populateNewsCompetitorDropdown() {
    const dropdown = document.getElementById('newsCompetitorFilter');
    if (!dropdown) return;

    // Reset dropdown first
    dropdown.innerHTML = '<option value="">All Competitors</option>';

    try {
        // Always fetch from API to ensure fresh data
        const data = await fetchAPI('/api/competitors', { silent: true });
        if (data && Array.isArray(data) && data.length > 0) {
            // Sort alphabetically
            const sorted = [...data].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
            sorted.forEach(comp => {
                // Backend already filters deleted - no need to check is_deleted
                const option = document.createElement('option');
                option.value = comp.id;
                option.textContent = comp.name;
                dropdown.appendChild(option);
            });
            // Update global cache
            window.competitors = data;
        } else if (window.competitors && window.competitors.length > 0) {
            // Fallback: use global cache if API returned empty
            const sorted = [...window.competitors].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
            sorted.forEach(comp => {
                const option = document.createElement('option');
                option.value = comp.id;
                option.textContent = comp.name;
                dropdown.appendChild(option);
            });
        }
    } catch (error) {
        console.error('[News Filter] Failed to populate competitor dropdown:', error);
        // Fallback: try global cache
        if (window.competitors && window.competitors.length > 0) {
            window.competitors.forEach(comp => {
                const option = document.createElement('option');
                option.value = comp.id;
                option.textContent = comp.name;
                dropdown.appendChild(option);
            });
        }
    }
}

/**
 * Load news feed with current filters
 */
async function loadNewsFeed(page = 1) {
    const loadingEl = document.getElementById('newsFeedLoading');
    const tableBody = document.getElementById('newsFeedTableBody');

    try {
        currentNewsPage = page;
        window.currentNewsPage = page;

        // Show loading state (with null checks)
        if (loadingEl) loadingEl.style.display = 'flex';
        if (tableBody) tableBody.innerHTML = '';

        // Gather filter values (with null-safe access)
        const keyword = (document.getElementById('newsKeywordFilter')?.value || '').trim();
        const competitorId = document.getElementById('newsCompetitorFilter')?.value || '';
        const dateFrom = document.getElementById('newsDateFrom')?.value || '';
        const dateTo = document.getElementById('newsDateTo')?.value || '';
        const sentiment = document.getElementById('newsSentimentFilter')?.value || '';
        const source = document.getElementById('newsSourceFilter')?.value || '';
        const eventType = document.getElementById('newsEventFilter')?.value || '';

        // Build query string
        const params = new URLSearchParams();
        if (keyword) params.append('keyword', keyword);
        if (competitorId) params.append('competitor_id', competitorId);
        if (dateFrom) params.append('start_date', dateFrom);
        if (dateTo) params.append('end_date', dateTo);
        if (sentiment) params.append('sentiment', sentiment);
        if (source) params.append('source', source);
        if (eventType) params.append('event_type', eventType);
        params.append('page', page);
        params.append('page_size', NEWS_PAGE_SIZE);

        const result = await fetchAPI(`/api/news-feed?${params.toString()}`);

        // Hide loading state
        if (loadingEl) loadingEl.style.display = 'none';

        if (result && result.articles) {
            newsFeedData = result.articles;
            window._currentNewsArticles = result.articles;
            renderNewsFeedTable(result.articles);
            updateNewsFeedStats(result.stats);
            updateNewsFeedPagination(result.pagination);
        } else {
            renderEmptyState();
            updateNewsFeedStats({ total: 0, positive: 0, neutral: 0, negative: 0 });
        }
    } catch (error) {
        console.error('[News Feed] Error loading:', error);
        if (loadingEl) loadingEl.style.display = 'none';
        renderEmptyState(`Error loading news: ${error.message}`);
        showToast(`News feed error: ${error.message}`, 'error');
    }
}

/**
 * Render the news feed table with articles
 */
function renderNewsFeedTable(articles) {
    const tbody = document.getElementById('newsFeedTableBody');
    if (!tbody) return;

    if (!articles || articles.length === 0) {
        renderEmptyState();
        return;
    }

    tbody.innerHTML = articles.map(article => {
        // Check if URL is valid (not empty, not #, and starts with http)
        const hasValidUrl = article.url && article.url !== '#' && article.url.startsWith('http');
        const safeUrl = hasValidUrl ? escapeHtml(article.url) : '';
        const title = escapeHtml(truncateText(article.title || 'No title', 80));
        const fullTitle = escapeHtml(article.title || '');

        // Render headline as link only if URL is valid
        const headlineHtml = hasValidUrl
            ? `<a href="${safeUrl}" target="_blank" title="${fullTitle}">${title}</a>`
            : `<span class="no-link" title="${fullTitle}">${title}</span>`;

        // Only make row clickable if URL is valid
        const rowClick = hasValidUrl
            ? `onclick="viewNewsArticle('${safeUrl}')"`
            : '';

        return `
        <tr class="news-row" ${rowClick}>
            <td class="news-date">${formatNewsDate(article.published_at)}</td>
            <td class="news-competitor">
                <span class="competitor-badge">${escapeHtml(article.competitor_name || 'Unknown')}</span>
            </td>
            <td class="news-headline">
                ${headlineHtml}
            </td>
            <td class="news-source">
                <span class="source-badge ${escapeHtml(article.source_type || '')}">${escapeHtml(formatSourceName(article.source || article.source_type))}</span>
            </td>
            <td class="news-source-link">
                ${article.url
                    ? `<a href="${escapeHtml(article.url)}" target="_blank" rel="noopener" class="source-link-text">${escapeHtml(extractDomain(article.url))}</a>`
                    : '<span class="text-muted">N/A</span>'}
            </td>
            <td class="news-sentiment">
                ${renderSentimentBadge(article.sentiment)}
            </td>
            <td class="news-event">
                ${renderEventTypeBadge(article.event_type)}
            </td>
            <td class="news-actions">
                <button class="btn-icon" onclick="event.stopPropagation(); viewNewsArticle('${safeUrl}')" title="${hasValidUrl ? 'Open Article' : 'No link available'}" ${hasValidUrl ? '' : 'disabled'}>
                    🔗
                </button>
                <button class="btn-icon" onclick="event.stopPropagation(); addToKnowledgeBase(${JSON.stringify(article).replace(/"/g, '&quot;')})" title="Add to KB">
                    📚
                </button>
                <button class="btn-icon" onclick="event.stopPropagation(); archiveNewsArticle(${article.id})" title="Archive">
                    📁
                </button>
            </td>
        </tr>
    `;
    }).join('');
}

/**
 * Render empty state message
 */
function renderEmptyState(message = 'No news articles found. Adjust your filters or refresh data.') {
    const tbody = document.getElementById('newsFeedTableBody');
    if (tbody) {
        tbody.innerHTML = `
            <tr class="news-empty-state">
                <td colspan="8">
                    <div class="empty-state-content">
                        <span class="empty-icon">📰</span>
                        <p>${message}</p>
                    </div>
                </td>
            </tr>
        `;
    }
}

/**
 * Update news feed stats display
 */
function updateNewsFeedStats(stats) {
    document.getElementById('totalNewsCount').textContent = stats?.total || 0;
    document.getElementById('positiveNewsCount').textContent = stats?.positive || 0;
    document.getElementById('neutralNewsCount').textContent = stats?.neutral || 0;
    document.getElementById('negativeNewsCount').textContent = stats?.negative || 0;
}

/**
 * Update pagination controls
 */
function updateNewsFeedPagination(pagination) {
    if (!pagination) {
        document.getElementById('newsPageInfo').textContent = 'Page 1 of 1';
        document.getElementById('newsPrevBtn').disabled = true;
        document.getElementById('newsNextBtn').disabled = true;
        return;
    }

    const { page, total_pages, total_items } = pagination;
    document.getElementById('newsPageInfo').textContent = `Page ${page} of ${total_pages} (${total_items} articles)`;
    document.getElementById('newsPrevBtn').disabled = page <= 1;
    document.getElementById('newsNextBtn').disabled = page >= total_pages;
}

/**
 * Reset all news feed filters
 */
function resetNewsFeedFilters() {
    // Reset competitor
    document.getElementById('newsCompetitorFilter').value = '';

    // Reset date range to last 30 days
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    document.getElementById('newsDateFrom').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('newsDateTo').value = today.toISOString().split('T')[0];

    // Reset other filters
    document.getElementById('newsSentimentFilter').value = '';
    document.getElementById('newsSourceFilter').value = '';
    document.getElementById('newsEventFilter').value = '';

    // Reset pagination
    window.currentNewsPage = 1;

    // Reload
    loadNewsFeed();
}

/**
 * Format date for display
 */
function formatNewsDate(dateStr) {
    if (!dateStr) return '—';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    } catch {
        return dateStr;
    }
}

/**
 * Format source name for display
 */
function formatSourceName(source) {
    if (!source) return 'Unknown';
    const sourceMap = {
        'google_news': 'Google News',
        'sec_edgar': 'SEC EDGAR',
        'newsapi': 'NewsAPI',
        'gnews': 'GNews',
        'mediastack': 'MediaStack',
        'bing_news': 'Bing News',
        'website_scrape': 'Website'
    };
    return sourceMap[source] || source.charAt(0).toUpperCase() + source.slice(1).replace(/_/g, ' ');
}

/**
 * Render sentiment badge
 */
function renderSentimentBadge(sentiment) {
    if (!sentiment) return '<span class="sentiment-badge unknown">—</span>';

    const sentimentMap = {
        'positive': { icon: '🟢', class: 'positive', label: 'Positive' },
        'neutral': { icon: '🟡', class: 'neutral', label: 'Neutral' },
        'negative': { icon: '🔴', class: 'negative', label: 'Negative' }
    };

    const s = sentimentMap[sentiment.toLowerCase()] || { icon: '⚪', class: 'unknown', label: sentiment };
    return `<span class="sentiment-badge ${s.class}">${s.icon} ${s.label}</span>`;
}

/**
 * Render event type badge
 */
function renderEventTypeBadge(eventType) {
    if (!eventType) return '<span class="event-badge general">📄 General</span>';

    const eventMap = {
        'funding': { icon: '💰', label: 'Funding' },
        'acquisition': { icon: '🤝', label: 'M&A' },
        'product_launch': { icon: '🚀', label: 'Product' },
        'partnership': { icon: '🔗', label: 'Partnership' },
        'leadership': { icon: '👔', label: 'Leadership' },
        'financial': { icon: '📊', label: 'Financial' },
        'legal': { icon: '⚖️', label: 'Legal' },
        'expansion': { icon: '🌍', label: 'Expansion' },
        'general': { icon: '📄', label: 'General' }
    };

    const e = eventMap[eventType.toLowerCase()] || { icon: '📄', label: eventType };
    return `<span class="event-badge ${eventType.toLowerCase()}">${e.icon} ${e.label}</span>`;
}

/**
 * Open news article in new tab
 */
function viewNewsArticle(url) {
    if (url && url !== '#') {
        window.open(url, '_blank');
    }
}

/**
 * Add news article to knowledge base
 */
async function addToKnowledgeBase(article) {
    try {
        const content = `News: ${article.title}\nSource: ${article.source}\nDate: ${article.published_at}\nURL: ${article.url}\nSummary: ${article.summary || article.description || ''}`;

        const result = await fetchAPI('/api/knowledge-base', {
            method: 'POST',
            body: JSON.stringify({
                content_text: content,
                source_type: 'news_article',
                source_url: article.url,
                is_active: true
            })
        });

        if (result) {
            showToast('Article added to Knowledge Base', 'success');
        } else {
            showToast('Failed to add article to Knowledge Base', 'error');
        }
    } catch (error) {
        console.error('Error adding to KB:', error);
        showToast('Error adding to Knowledge Base', 'error');
    }
}

// ==============================================================================
// NF-003: Advanced Filtering with Keyword Search
// ==============================================================================

/**
 * Enhanced loadNewsFeed with real news fetching from Google News RSS
 */
const originalLoadNewsFeed = loadNewsFeed;
let newsRefreshInProgress = false;

async function enhancedLoadNewsFeed(page = 1) {
    window.currentNewsPage = page;

    const loadingEl = document.getElementById('newsFeedLoading');
    const tableBody = document.getElementById('newsFeedTableBody');

    // Show loading state
    if (loadingEl) {
        loadingEl.style.display = 'flex';
        loadingEl.innerHTML = `
            <div class="loading-spinner"></div>
            <p class="loading">Fetching live news from Google News...</p>
        `;
    }
    if (tableBody) tableBody.innerHTML = '';

    // Gather filter values including keyword search
    const keyword = document.getElementById('newsKeywordFilter')?.value || '';
    const competitorId = document.getElementById('newsCompetitorFilter')?.value || '';
    const dateFrom = document.getElementById('newsDateFrom')?.value || '';
    const dateTo = document.getElementById('newsDateTo')?.value || '';
    const sentiment = document.getElementById('newsSentimentFilter')?.value || '';
    const source = document.getElementById('newsSourceFilter')?.value || '';
    const eventType = document.getElementById('newsEventFilter')?.value || '';

    // Build query string
    const params = new URLSearchParams();
    if (keyword) params.append('keyword', keyword);
    if (competitorId) params.append('competitor_id', competitorId);
    if (dateFrom) params.append('start_date', dateFrom);
    if (dateTo) params.append('end_date', dateTo);
    if (sentiment) params.append('sentiment', sentiment);
    if (source) params.append('source', source);
    if (eventType) params.append('event_type', eventType);
    params.append('page', page);
    params.append('page_size', NEWS_PAGE_SIZE);

    // Try to get news - with extended timeout for live fetching
    const timeoutPromise = new Promise((_, reject) => {
        setTimeout(() => reject(new Error('Request timed out')), 60000); // 60 second timeout for live fetch
    });

    try {
        // First try cached news (fast)
        const result = await Promise.race([
            fetchAPI(`/api/news-feed?${params.toString()}`, { silent: true }),
            timeoutPromise
        ]);

        if (loadingEl) loadingEl.style.display = 'none';

        if (result && result.articles && result.articles.length > 0) {
            newsFeedData = result.articles;
            window._currentNewsArticles = result.articles;
            renderNewsFeedTable(result.articles);
            updateNewsFeedStats(result.stats || { total: result.articles.length, positive: 0, neutral: 0, negative: 0 });
            updateNewsFeedPagination(result.pagination || { page: 1, total_pages: 1, total: result.articles.length });

            // Show source indicator
            if (result.cache_used) {
                showToast('Loaded cached news articles', 'info');
            }
        } else {
            // No articles in cache - prompt user to use AI Fetch
            renderNewsEmptyState(`
                <strong>No news articles cached yet</strong><br><br>
                Click the <strong style="color: var(--primary-color);">🤖 AI Fetch News</strong> button above to fetch live news for all competitors.
            `);
            updateNewsFeedStats({ total: 0, positive: 0, neutral: 0, negative: 0 });
        }
    } catch (error) {
        console.error('Error loading news feed:', error);
        if (loadingEl) loadingEl.style.display = 'none';

        // Show prompt to use AI Fetch button
        renderNewsEmptyState(`
            <strong>News service not responding</strong><br><br>
            Click the <strong style="color: var(--primary-color);">🤖 AI Fetch News</strong> button above to fetch live news.
        `);
        updateNewsFeedStats({ total: 0, positive: 0, neutral: 0, negative: 0 });
    }
}

/**
 * Fetch news using AI agent with progress tracking
 */
// Global tracking for news fetch — survives page navigation
let _newsFetchProgressKey = null;
let _newsFetchPolling = false;

async function fetchAINews() {
    const btn = document.getElementById('aiNewsFetchBtn');
    const loadingEl = document.getElementById('newsFeedLoading');
    const tableBody = document.getElementById('newsFeedTableBody');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Fetching...';
    }

    try {
        if (loadingEl) {
            loadingEl.style.display = 'flex';
            loadingEl.innerHTML = `
                <div class="loading-spinner"></div>
                <p class="loading" id="newsFetchStatusText">Starting AI news fetch...</p>
                <div class="news-fetch-progress"><div class="progress-fill" id="newsFetchProgressBar" style="width:0%"></div></div>
            `;
        }
        if (tableBody) tableBody.innerHTML = '';

        const newsKeyword = (document.getElementById('newsKeywordFilter')?.value || '').trim();
        const newsCompetitorId = document.getElementById('newsCompetitorFilter')?.value || '';
        const newsDateFrom = document.getElementById('newsDateFrom')?.value || '';
        const newsDateTo = document.getElementById('newsDateTo')?.value || '';

        const parsedCompId = parseInt(newsCompetitorId);
        const aiNewsCompetitorIds = (newsCompetitorId && !isNaN(parsedCompId)) ? [parsedCompId] : null;

        const result = await fetchAPI('/api/news-feed/fetch', {
            method: 'POST',
            body: JSON.stringify({
                competitor_ids: aiNewsCompetitorIds,
                keywords: newsKeyword,
                date_from: newsDateFrom || undefined,
                date_to: newsDateTo || undefined
            })
        });

        const progressKey = result?.progress_key;

        if (progressKey) {
            _newsFetchProgressKey = progressKey;
            _newsFetchPolling = true;
            await _pollNewsFetchProgress(progressKey);
        } else {
            // Fallback: no progress key, try direct load
            if (loadingEl) loadingEl.style.display = 'none';
            await loadNewsFeed(1);
            const summarizeBtn = document.getElementById('summarizeNewsBtn');
            if (summarizeBtn && newsFeedData && newsFeedData.length > 0) summarizeBtn.disabled = false;
            showToast('News articles loaded', 'success');
        }

    } catch (outerError) {
        console.error('[AI News] Error:', outerError);
        showToast(`News fetch error: ${outerError.message}`, 'error');
        const loadingEl2 = document.getElementById('newsFeedLoading');
        if (loadingEl2) loadingEl2.style.display = 'none';
        renderNewsEmptyState(`
            <strong>Unable to Fetch News</strong><br><br>
            ${escapeHtml(outerError.message)}
        `);
        updateNewsFeedStats({ total: 0, positive: 0, neutral: 0, negative: 0 });
        _newsFetchPolling = false;
        _newsFetchProgressKey = null;
    }

    const btn2 = document.getElementById('aiNewsFetchBtn');
    if (btn2) {
        btn2.disabled = false;
        btn2.innerHTML = '🤖 AI Fetch News';
    }
}

/**
 * Poll news fetch progress — runs independently of page navigation.
 * If user switches tabs, polling continues. When they return to news page,
 * resumeNewsFetchIfRunning() picks up the UI update.
 */
async function _pollNewsFetchProgress(progressKey) {
    let fetchStats = null;
    while (_newsFetchPolling) {
        await new Promise(r => setTimeout(r, 2000));
        try {
            const progress = await fetchAPI(`/api/news-feed/fetch-progress/${progressKey}`, { silent: true });
            // Update UI elements only if they exist (user may be on another page)
            const statusText = document.getElementById('newsFetchStatusText');
            const progressBar = document.getElementById('newsFetchProgressBar');

            if (progress) {
                const pct = progress.percent || 0;
                if (statusText) {
                    statusText.textContent = progress.current_competitor
                        ? `Fetching news for ${progress.current_competitor} (${progress.completed || 0} of ${progress.total || 0})...`
                        : `Fetching news... ${pct}%`;
                }
                if (progressBar) progressBar.style.width = `${pct}%`;

                if (progress.status === 'complete' || pct >= 100) {
                    fetchStats = progress;
                    break;
                }
                if (progress.status === 'error') {
                    throw new Error(progress.error || 'Fetch failed on server');
                }
            }
        } catch (pollErr) {
            if (pollErr.message && pollErr.message.includes('Fetch failed on server')) {
                showToast(`News fetch error: ${pollErr.message}`, 'error');
                break;
            }
        }
    }

    _newsFetchPolling = false;
    _newsFetchProgressKey = null;

    // Completion handling — update UI only if news page elements exist
    const loadingEl = document.getElementById('newsFeedLoading');
    if (loadingEl) loadingEl.style.display = 'none';

    if (fetchStats) {
        await loadNewsFeed(1);
        const summarizeBtn = document.getElementById('summarizeNewsBtn');
        if (summarizeBtn) summarizeBtn.disabled = false;

        try {
            const summary = await fetchAPI('/api/news-feed/completion-summary', {
                method: 'POST',
                body: JSON.stringify({
                    total_articles: fetchStats.total_articles || 0,
                    competitors_fetched: fetchStats.completed || 0,
                    errors: fetchStats.errors || 0,
                    duration_seconds: fetchStats.duration_seconds || 0
                })
            });
            if (summary?.content) {
                const modal = document.getElementById('newsSummaryModal');
                const content = document.getElementById('newsSummaryContent');
                if (modal && content) {
                    modal.style.display = 'flex';
                    content.innerHTML = typeof renderNewsSummaryMarkdown === 'function'
                        ? renderNewsSummaryMarkdown(summary.content)
                        : `<pre>${escapeHtml(summary.content)}</pre>`;
                }
            }
        } catch (sumErr) {
        }

        showToast(`AI news fetch complete! ${fetchStats.total_articles || 0} articles found.`, 'success');
    }

    const btn = document.getElementById('aiNewsFetchBtn');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '🤖 AI Fetch News';
    }
}

/**
 * Resume news fetch progress UI when user returns to the news page.
 * Called by loadNewsFeed() or page loader to reconnect polling UI.
 */
function resumeNewsFetchIfRunning() {
    if (!_newsFetchPolling || !_newsFetchProgressKey) return false;

    const loadingEl = document.getElementById('newsFeedLoading');
    if (loadingEl) {
        loadingEl.style.display = 'flex';
        loadingEl.innerHTML = `
            <div class="loading-spinner"></div>
            <p class="loading" id="newsFetchStatusText">Resuming news fetch progress...</p>
            <div class="news-fetch-progress"><div class="progress-fill" id="newsFetchProgressBar" style="width:0%"></div></div>
        `;
    }
    const btn = document.getElementById('aiNewsFetchBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '⏳ Fetching...';
    }
    return true;
}

/**
 * Check AI news agent status
 */
async function checkAINewsStatus() {
    try {
        const status = await fetchAPI('/api/ai/news-agent/status', { silent: true });
        if (status) {
            const sourceCount = document.getElementById('sourceCount');
            if (sourceCount && status.total_cached_articles) {
                sourceCount.textContent = status.total_cached_articles;
            }
        }
    } catch (e) {
    }
}

async function archiveNewsArticle(articleId) {
    try {
        const resp = await fetch(`${API_BASE}/api/news-feed/${articleId}/archive`, {
            method: 'PUT',
            headers: getAuthHeaders()
        });
        if (resp.ok) {
            showToast('Article archived', 'success');
            loadNewsFeed();
        } else {
            showToast('Archive failed', 'error');
        }
    } catch (e) {
        showToast('Archive failed: ' + e.message, 'error');
    }
}

async function summarizeAllNews() {
    if (!window._currentNewsArticles || window._currentNewsArticles.length === 0) {
        showToast('No news articles loaded. Run AI Fetch News first.', 'error');
        return;
    }
    const modal = document.getElementById('newsSummaryModal');
    if (modal) {
        modal.style.display = 'flex';
        const content = document.getElementById('newsSummaryContent');
        if (content) content.innerHTML = '<div class="loading-spinner"></div><p>Analyzing all news articles...</p>';
    }
    try {
        const resp = await fetch(`${API_BASE}/api/news-feed/summarize-all`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            body: JSON.stringify({ articles: window._currentNewsArticles })
        });
        const data = await resp.json();
        const content = document.getElementById('newsSummaryContent');
        if (content) {
            content.innerHTML = typeof renderNewsSummaryMarkdown === 'function'
                ? renderNewsSummaryMarkdown(data.content || 'No summary generated.')
                : `<pre>${escapeHtml(data.content || 'No summary generated.')}</pre>`;
        }
    } catch (e) {
        const content = document.getElementById('newsSummaryContent');
        if (content) content.textContent = 'Summary failed: ' + e.message;
    }
}

/**
 * Render empty state for news feed with custom message
 */
function renderNewsEmptyState(message = 'No news articles found.') {
    const tbody = document.getElementById('newsFeedTableBody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 12px;">
                        <span style="font-size: 48px;">📰</span>
                        <p style="margin: 0;">${message}</p>
                        <button class="btn btn-secondary" onclick="clearNewsFilters()" style="margin-top: 8px;">
                            Clear Filters & Retry
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }
}

/**
 * Clear all news filters and reload
 */
function clearNewsFilters() {
    const filters = ['newsKeywordFilter', 'newsCompetitorFilter', 'newsDateFrom', 'newsDateTo',
                     'newsSentimentFilter', 'newsSourceFilter', 'newsEventFilter'];
    filters.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    loadNewsFeed(1);
}

// Replace the loadNewsFeed function
window.loadNewsFeed = enhancedLoadNewsFeed;

// ==============================================================================
// NF-004: AI News Summarization
// ==============================================================================

let currentNewsSummary = null;

/**
 * Format AI-generated news summary
 */
function formatAINewsSummary(aiContent, articles, period) {
    const periodLabel = period === 'today' ? "Today's" : period === 'week' ? 'This Week\'s' : 'Competitor';

    // v7.1.2: Render markdown-like AI content to HTML safely
    const renderedContent = renderNewsSummaryMarkdown(aiContent);

    return `
        <div class="news-summary">
            <div class="summary-header">
                <h4>${periodLabel} News Intelligence Summary</h4>
                <span class="summary-meta">${articles.length} articles analyzed | Generated ${new Date().toLocaleString()}</span>
            </div>
            <div class="summary-content ai-generated">
                ${renderedContent}
            </div>
            <div class="summary-stats">
                <div class="stat positive">
                    <span class="value">${articles.filter(a => a.sentiment === 'positive').length}</span>
                    <span class="label">Positive</span>
                </div>
                <div class="stat neutral">
                    <span class="value">${articles.filter(a => a.sentiment === 'neutral').length}</span>
                    <span class="label">Neutral</span>
                </div>
                <div class="stat negative">
                    <span class="value">${articles.filter(a => a.sentiment === 'negative').length}</span>
                    <span class="label">Negative</span>
                </div>
            </div>
        </div>
    `;
}

/**
 * Render markdown-like text to HTML for news summaries.
 * Handles: headers (##), bold (**), bullets (- or *), numbered lists, paragraphs.
 * Uses textContent-safe approach: only structural markdown is converted, not raw HTML.
 */
function renderNewsSummaryMarkdown(text) {
    if (!text) return '';
    const lines = text.split('\n');
    const htmlParts = [];
    let inList = false;
    let listType = '';

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i];

        // Close open list if this line is not a list item
        const isBullet = /^\s*[-*]\s+/.test(line);
        const isNumbered = /^\s*\d+[.)]\s+/.test(line);
        if (inList && !isBullet && !isNumbered) {
            htmlParts.push(listType === 'ul' ? '</ul>' : '</ol>');
            inList = false;
            listType = '';
        }

        // Headers
        if (/^####\s+/.test(line)) {
            htmlParts.push(`<h6>${escapeAndBold(line.replace(/^####\s+/, ''))}</h6>`);
            continue;
        }
        if (/^###\s+/.test(line)) {
            htmlParts.push(`<h5>${escapeAndBold(line.replace(/^###\s+/, ''))}</h5>`);
            continue;
        }
        if (/^##\s+/.test(line)) {
            htmlParts.push(`<h5>${escapeAndBold(line.replace(/^##\s+/, ''))}</h5>`);
            continue;
        }
        if (/^#\s+/.test(line)) {
            htmlParts.push(`<h4>${escapeAndBold(line.replace(/^#\s+/, ''))}</h4>`);
            continue;
        }

        // Bullet list items
        if (isBullet) {
            if (!inList || listType !== 'ul') {
                if (inList) htmlParts.push(listType === 'ul' ? '</ul>' : '</ol>');
                htmlParts.push('<ul>');
                inList = true;
                listType = 'ul';
            }
            htmlParts.push(`<li>${escapeAndBold(line.replace(/^\s*[-*]\s+/, ''))}</li>`);
            continue;
        }

        // Numbered list items
        if (isNumbered) {
            if (!inList || listType !== 'ol') {
                if (inList) htmlParts.push(listType === 'ul' ? '</ul>' : '</ol>');
                htmlParts.push('<ol>');
                inList = true;
                listType = 'ol';
            }
            htmlParts.push(`<li>${escapeAndBold(line.replace(/^\s*\d+[.)]\s+/, ''))}</li>`);
            continue;
        }

        // Empty line
        if (line.trim() === '') {
            continue;
        }

        // Regular paragraph
        htmlParts.push(`<p>${escapeAndBold(line)}</p>`);
    }

    // Close any open list
    if (inList) {
        htmlParts.push(listType === 'ul' ? '</ul>' : '</ol>');
    }

    return htmlParts.join('\n');
}

/**
 * Escape HTML then convert **bold** markers to <strong> tags.
 */
function escapeAndBold(text) {
    let escaped = escapeHtml(text);
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return escaped;
}

/**
 * Generate template-based news summary
 */
function generateTemplateNewsSummary(articles, period) {
    const periodLabel = period === 'today' ? "Today's" : period === 'week' ? 'This Week\'s' : 'Competitor';

    // Group by competitor
    const byCompetitor = {};
    articles.forEach(a => {
        const name = a.competitor_name || 'Unknown';
        if (!byCompetitor[name]) byCompetitor[name] = [];
        byCompetitor[name].push(a);
    });

    // Count sentiment
    const positive = articles.filter(a => a.sentiment === 'positive').length;
    const negative = articles.filter(a => a.sentiment === 'negative').length;
    const neutral = articles.length - positive - negative;

    // Find top competitors by mentions
    const topCompetitors = Object.entries(byCompetitor)
        .sort((a, b) => b[1].length - a[1].length)
        .slice(0, 5);

    // Find notable events
    const notableEvents = articles.filter(a =>
        ['funding', 'acquisition', 'product_launch'].includes(a.event_type)
    ).slice(0, 5);

    return `
        <div class="news-summary">
            <div class="summary-header">
                <h4>📊 ${periodLabel} News Intelligence Summary</h4>
                <span class="summary-meta">${articles.length} articles analyzed | Generated ${new Date().toLocaleString()}</span>
            </div>

            <div class="summary-section">
                <h5>📈 Overview</h5>
                <p>Analyzed <strong>${articles.length}</strong> news articles across <strong>${Object.keys(byCompetitor).length}</strong> competitors.
                Sentiment breakdown: ${positive} positive, ${neutral} neutral, ${negative} negative.</p>
            </div>

            <div class="summary-section">
                <h5>🎯 Top Competitors by Mentions</h5>
                <ul>
                    ${topCompetitors.map(([name, items]) => `
                        <li><strong>${escapeHtml(name)}</strong>: ${items.length} articles</li>
                    `).join('')}
                </ul>
            </div>

            ${notableEvents.length > 0 ? `
            <div class="summary-section">
                <h5>🔥 Notable Events</h5>
                <ul>
                    ${notableEvents.map(e => `
                        <li><strong>${escapeHtml(e.competitor_name || 'Unknown')}</strong>: ${escapeHtml(e.title?.substring(0, 80) || 'N/A')}...</li>
                    `).join('')}
                </ul>
            </div>
            ` : ''}

            <div class="summary-section">
                <h5>✅ Recommended Actions</h5>
                <ul>
                    <li>Review ${topCompetitors[0] ? topCompetitors[0][0] : 'top competitor'} activity for strategic response</li>
                    <li>Update sales battlecards with latest competitive intel</li>
                    <li>Monitor ${negative > 5 ? 'high' : 'normal'} negative sentiment trends</li>
                </ul>
            </div>

            <div class="summary-stats">
                <div class="stat positive">
                    <span class="value">${positive}</span>
                    <span class="label">Positive</span>
                </div>
                <div class="stat neutral">
                    <span class="value">${neutral}</span>
                    <span class="label">Neutral</span>
                </div>
                <div class="stat negative">
                    <span class="value">${negative}</span>
                    <span class="label">Negative</span>
                </div>
            </div>
        </div>
    `;
}

/**
 * Close news summary modal
 */
function closeNewsSummaryModal() {
    document.getElementById('newsSummaryModal').style.display = 'none';
}

/**
 * Export news summary to PDF
 */
function exportNewsSummary() {
    if (!currentNewsSummary) {
        showToast('No summary to export', 'warning');
        return;
    }

    // Open print dialog
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <html><head><title>News Intelligence Summary</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }
            h4, h5 { color: #1a365d; }
            ul { margin: 10px 0; }
            li { margin: 5px 0; }
            .summary-stats { display: flex; gap: 20px; margin-top: 20px; }
            .stat { text-align: center; padding: 15px; border-radius: 8px; }
            .stat.positive { background: #d1fae5; }
            .stat.neutral { background: #fef3c7; }
            .stat.negative { background: #fee2e2; }
            .stat .value { display: block; font-size: 24px; font-weight: bold; }
        </style>
        </head><body>${currentNewsSummary}</body></html>
    `);
    printWindow.document.close();
    printWindow.print();
}

/**
 * Copy news summary to clipboard
 */
function copyNewsSummary() {
    if (!currentNewsSummary) {
        showToast('No summary to copy', 'warning');
        return;
    }

    // Extract text from HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = currentNewsSummary;
    const text = tempDiv.textContent || tempDiv.innerText;

    navigator.clipboard.writeText(text).then(() => {
        showToast('Summary copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy summary', 'error');
    });
}

// ==============================================================================
// NF-005: Live News Aggregation Engine
// ==============================================================================

const NEWS_SOURCES = [
    { id: 'google_news', name: 'Google News RSS', active: true, free: true },
    { id: 'sec_edgar', name: 'SEC EDGAR', active: true, free: true },
    { id: 'uspto', name: 'USPTO Patents', active: true, free: true },
    { id: 'gnews', name: 'GNews', active: false, apiKey: 'GNEWS_API_KEY' },
    { id: 'mediastack', name: 'MediaStack', active: false, apiKey: 'MEDIASTACK_API_KEY' },
    { id: 'newsdata', name: 'NewsData.io', active: false, apiKey: 'NEWSDATA_API_KEY' },
    { id: 'newsapi', name: 'NewsAPI.org', active: false, apiKey: 'NEWSAPI_KEY' },
    { id: 'custom_rss', name: 'Custom RSS', active: true, free: true }
];

/**
 * Update live aggregation status display
 */
function updateAggregationStatus() {
    const activeCount = NEWS_SOURCES.filter(s => s.active).length;
    const countEl = document.getElementById('sourceCount');
    if (countEl) {
        countEl.textContent = activeCount;
    }
}

/**
 * Refresh all news sources
 */
async function refreshAllNewsSources() {
    showToast('Refreshing news from all sources...', 'info');

    const statusEl = document.getElementById('liveAggregationStatus');
    if (statusEl) {
        statusEl.querySelector('.status-indicator').classList.add('refreshing');
    }

    try {
        const result = await fetchAPI('/api/news-coverage/refresh-all', { method: 'POST' });

        if (result?.success) {
            showToast(`Refreshed ${result.articles_added || 0} new articles from ${result.sources_checked || 0} sources`, 'success');
            await loadNewsFeed();
        } else {
            showToast('News refresh completed', 'success');
            await loadNewsFeed();
        }
    } catch (error) {
        console.error('Error refreshing news:', error);
        showToast('Partial refresh completed - some sources may have failed', 'warning');
        await loadNewsFeed();
    } finally {
        if (statusEl) {
            statusEl.querySelector('.status-indicator').classList.remove('refreshing');
        }
    }
}

/**
 * Enhanced reset filters to include keyword
 */
const originalResetNewsFeedFilters = resetNewsFeedFilters;
function enhancedResetNewsFeedFilters() {
    // Reset keyword
    const keywordInput = document.getElementById('newsKeywordFilter');
    if (keywordInput) keywordInput.value = '';

    // Reset competitor
    document.getElementById('newsCompetitorFilter').value = '';

    // Reset date range to last 30 days
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    document.getElementById('newsDateFrom').value = thirtyDaysAgo.toISOString().split('T')[0];
    document.getElementById('newsDateTo').value = today.toISOString().split('T')[0];

    // Reset other filters
    document.getElementById('newsSentimentFilter').value = '';
    document.getElementById('newsSourceFilter').value = '';
    document.getElementById('newsEventFilter').value = '';

    // Reset pagination
    window.currentNewsPage = 1;

    // Reload
    loadNewsFeed();
}

// Replace the resetNewsFeedFilters function
window.resetNewsFeedFilters = enhancedResetNewsFeedFilters;

// Export new functions
window.summarizeAllNews = summarizeAllNews;
window.closeNewsSummaryModal = closeNewsSummaryModal;
window.exportNewsSummary = exportNewsSummary;
window.copyNewsSummary = copyNewsSummary;
window.refreshAllNewsSources = refreshAllNewsSources;

/**
 * Toggle dropdown menu visibility
 * @param {HTMLElement} button - The dropdown toggle button
 */
function toggleDropdown(button) {
    // Close all other dropdowns first
    document.querySelectorAll('.dropdown.open').forEach(dropdown => {
        if (!dropdown.contains(button)) {
            dropdown.classList.remove('open');
        }
    });

    const dropdown = button.closest('.dropdown');
    if (dropdown) {
        dropdown.classList.toggle('open');
    }
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.closest('.dropdown')) {
        document.querySelectorAll('.dropdown.open').forEach(dropdown => {
            dropdown.classList.remove('open');
        });
    }
});

/**
 * Show competitor actions menu
 * @param {Event} event - Click event
 * @param {number} compId - Competitor ID
 */
function toggleCompetitorMenu(event, compId) {
    event.stopPropagation();
    showModal(`
        <h3>Competitor Actions</h3>
        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 16px;">
            <button class="btn btn-secondary" onclick="viewDataSources(${compId}); closeModal();">
                📊 View Data Sources
            </button>
            <button class="btn btn-secondary" onclick="triggerScrape(${compId}); closeModal();">
                🔄 Refresh Data
            </button>
            <button class="btn btn-secondary" onclick="editCompetitor(${compId}); closeModal();">
                ✏️ Edit Profile
            </button>
            <button class="btn btn-secondary" onclick="navigateTo('comparison'); closeModal();">
                ⚖️ Compare
            </button>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid var(--border-color);">
            <button class="btn" style="background: #dc3545; color: white;" onclick="deleteCompetitor(${compId}); closeModal();">
                🗑️ Delete
            </button>
        </div>
    `);
}

// ==============================================================================
// FEAT-001: Alert Rules Engine
// ==============================================================================

let alertRules = [];

/**
 * Initialize Alert Rules section
 */
async function initAlertRules() {
    await loadAlertRules();
    populateRuleCompetitorDropdown();
    updateAlertStats();
}

/**
 * Load alert rules from API
 */
async function loadAlertRules() {
    try {
        const rules = await fetchAPI('/api/notifications/rules');
        alertRules = rules || [];
        renderAlertRules();
    } catch (error) {
        alertRules = getLocalAlertRules();
        renderAlertRules();
    }
}

/**
 * Get alert rules from localStorage
 */
function getLocalAlertRules() {
    try {
        return JSON.parse(localStorage.getItem('alertRules') || '[]');
    } catch {
        return [];
    }
}

/**
 * Save alert rules to localStorage
 */
function saveLocalAlertRules() {
    localStorage.setItem('alertRules', JSON.stringify(alertRules));
}

/**
 * Render alert rules list
 */
function renderAlertRules() {
    const container = document.getElementById('alertRulesList');
    if (!container) return;

    if (alertRules.length === 0) {
        container.innerHTML = `
            <div class="empty-state-small">
                <p>No alert rules configured. Create your first rule to get notified about competitor activity.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = alertRules.map(rule => `
        <div class="alert-rule-item ${rule.enabled ? 'enabled' : 'disabled'}">
            <div class="rule-info">
                <div class="rule-name">${escapeHtml(rule.name)}</div>
                <div class="rule-description">
                    <span class="rule-event">${getEventLabel(rule.event_type)}</span>
                    <span class="rule-scope">${getScopeLabel(rule.competitor_scope)}</span>
                    <span class="rule-channels">${getChannelIcons(rule.channels)}</span>
                </div>
            </div>
            <div class="rule-actions">
                <label class="toggle-switch small">
                    <input type="checkbox" ${rule.enabled ? 'checked' : ''}
                           onchange="toggleAlertRule('${rule.id}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>
                <button class="btn-icon" onclick="editAlertRule('${rule.id}')" title="Edit">✏️</button>
                <button class="btn-icon" onclick="deleteAlertRule('${rule.id}')" title="Delete">🗑️</button>
            </div>
        </div>
    `).join('');
}

/**
 * Get human-readable event label
 */
function getEventLabel(eventType) {
    const labels = {
        'news_mention': '📰 News',
        'threat_change': '⚠️ Threat Change',
        'funding': '💰 Funding',
        'product_launch': '🚀 Product',
        'leadership_change': '👔 Leadership',
        'pricing_change': '💵 Pricing',
        'acquisition': '🤝 M&A',
        'patent_filed': '📋 Patent',
        'employee_growth': '📈 Growth',
        'negative_sentiment': '📉 Negative News'
    };
    return labels[eventType] || eventType;
}

/**
 * Get scope label
 */
function getScopeLabel(scope) {
    if (scope === 'all') return 'All competitors';
    if (scope === 'high_threat') return 'High threat only';
    if (scope === 'medium_threat') return 'Medium+ threat';
    if (scope === 'watchlist') return 'Watchlist';
    return `Specific: ${scope}`;
}

/**
 * Get channel icons
 */
function getChannelIcons(channels) {
    const icons = {
        'email': '📧',
        'slack': '💬',
        'teams': '🟦',
        'in_app': '🔔'
    };
    return (channels || []).map(c => icons[c] || c).join(' ');
}

/**
 * Show add rule modal
 */
function showAddRuleModal() {
    document.getElementById('alertRuleModal').style.display = 'flex';
    document.getElementById('alertRuleForm').reset();
}

/**
 * Close alert rule modal
 */
function closeAlertRuleModal() {
    document.getElementById('alertRuleModal').style.display = 'none';
}

/**
 * Populate competitor dropdown in rule modal
 */
function populateRuleCompetitorDropdown() {
    const select = document.getElementById('ruleCompetitor');
    if (!select) return;

    // Keep default options, add specific competitors
    const defaultOptions = select.querySelectorAll('option');
    defaultOptions.forEach((opt, i) => { if (i > 3) opt.remove(); });

    competitors.forEach(c => {
        const option = document.createElement('option');
        option.value = c.id;
        option.textContent = c.name;
        select.appendChild(option);
    });
}

/**
 * Save alert rule
 */
async function saveAlertRule(event) {
    event.preventDefault();

    const form = event.target;
    const channels = Array.from(form.querySelectorAll('input[name="channels"]:checked'))
        .map(cb => cb.value);

    const rule = {
        id: `rule_${Date.now()}`,
        name: document.getElementById('ruleName').value,
        event_type: document.getElementById('ruleEvent').value,
        competitor_scope: document.getElementById('ruleCompetitor').value,
        threshold: document.getElementById('ruleThreshold').value,
        channels: channels,
        schedule: document.getElementById('ruleSchedule').value,
        enabled: true,
        created_at: new Date().toISOString()
    };

    // Try to save to API
    try {
        await fetchAPI('/api/notifications/rules', {
            method: 'POST',
            body: JSON.stringify(rule)
        });
    } catch (error) {
    }

    // Always save locally as backup
    alertRules.push(rule);
    saveLocalAlertRules();
    renderAlertRules();
    updateAlertStats();

    closeAlertRuleModal();
    showToast('Alert rule created successfully', 'success');
}

/**
 * Toggle alert rule enabled state
 */
async function toggleAlertRule(ruleId, enabled) {
    const rule = alertRules.find(r => r.id === ruleId);
    if (rule) {
        rule.enabled = enabled;
        saveLocalAlertRules();
        showToast(`Rule ${enabled ? 'enabled' : 'disabled'}`, 'info');
    }
}

/**
 * Delete alert rule
 */
async function deleteAlertRule(ruleId) {
    if (!confirm('Delete this alert rule?')) return;

    alertRules = alertRules.filter(r => r.id !== ruleId);
    saveLocalAlertRules();
    renderAlertRules();
    updateAlertStats();
    showToast('Alert rule deleted', 'success');
}

/**
 * Edit alert rule
 */
function editAlertRule(ruleId) {
    const rule = alertRules.find(r => r.id === ruleId);
    if (!rule) return;

    document.getElementById('ruleName').value = rule.name;
    document.getElementById('ruleEvent').value = rule.event_type;
    document.getElementById('ruleCompetitor').value = rule.competitor_scope;
    document.getElementById('ruleThreshold').value = rule.threshold || '';
    document.getElementById('ruleSchedule').value = rule.schedule;

    // Set channels
    document.querySelectorAll('input[name="channels"]').forEach(cb => {
        cb.checked = rule.channels?.includes(cb.value);
    });

    // Delete old rule and show modal
    deleteAlertRule(ruleId);
    document.getElementById('alertRuleModal').style.display = 'flex';
}

/**
 * Update alert stats
 */
async function updateAlertStats() {
    const activeCount = alertRules.filter(r => r.enabled).length;
    const activeEl = document.getElementById('activeRulesCount');
    if (activeEl) activeEl.textContent = `${activeCount} active rules`;

    // Fetch real alert count from changes in last 24h
    const todayEl = document.getElementById('alertsTodayCount');
    if (todayEl) {
        try {
            const resp = await fetch(`${API_BASE}/api/changes?days=1`, { headers: getAuthHeaders() });
            if (resp.ok) {
                const changes = await resp.json();
                todayEl.textContent = `${changes.length || 0} alerts today`;
            } else {
                todayEl.textContent = '0 alerts today';
            }
        } catch (error) {
            console.error('Failed to fetch alert count:', error);
            todayEl.textContent = '0 alerts today';
        }
    }
}

// ==============================================================================
// FEAT-008: AI Insight Summaries
// ==============================================================================

/**
 * Save AI Insight settings
 */
function saveAIInsightSettings() {
    const settings = {
        dailyDigest: document.getElementById('dailyDigestToggle')?.checked || false,
        weeklyBriefing: document.getElementById('weeklyBriefingToggle')?.checked || true,
        realtimeAlerts: document.getElementById('realtimeAlertsToggle')?.checked || false,
        includeRecommendations: document.getElementById('includeRecommendationsToggle')?.checked || true
    };

    localStorage.setItem('aiInsightSettings', JSON.stringify(settings));

    // Try to save to API
    fetchAPI('/api/user-settings/ai-insights', {
        method: 'PUT',
        body: JSON.stringify(settings)
    }).catch(() => {});

    showToast('AI Insight settings saved', 'success');
}

/**
 * Load AI Insight settings
 */
function loadAIInsightSettings() {
    const settings = JSON.parse(localStorage.getItem('aiInsightSettings') || '{}');

    if (document.getElementById('dailyDigestToggle')) {
        document.getElementById('dailyDigestToggle').checked = settings.dailyDigest || false;
    }
    if (document.getElementById('weeklyBriefingToggle')) {
        document.getElementById('weeklyBriefingToggle').checked = settings.weeklyBriefing !== false;
    }
    if (document.getElementById('realtimeAlertsToggle')) {
        document.getElementById('realtimeAlertsToggle').checked = settings.realtimeAlerts || false;
    }
    if (document.getElementById('includeRecommendationsToggle')) {
        document.getElementById('includeRecommendationsToggle').checked = settings.includeRecommendations !== false;
    }
}

/**
 * Generate manual AI insight
 */
async function generateManualInsight(type = 'daily') {
    showToast(`Generating ${type} insight...`, 'info');

    try {
        // Try real AI-powered summary first
        const aiResult = await fetchAPI(`/api/analytics/summary?type=${type}`, { silent: true });

        if (aiResult && aiResult.summary && aiResult.type === 'ai') {
            displayInsightResult(aiResult.summary, type);
            const label = type === 'daily' ? 'Daily Digest' : 'Weekly Briefing';
            showToast(`${label} generated with AI (${aiResult.model || 'AI'})`, 'success');
            return;
        }

        // Fallback: use template insight with real data
        const competitorData = await fetchAPI('/api/competitors?limit=50', { silent: true }) || [];
        const newsData = await fetchAPI('/api/news-feed?limit=100', { silent: true }) || { articles: [] };
        const templateInsight = generateTemplateInsight(competitorData, newsData, type);
        displayInsightResult(templateInsight, type);
        showToast(`${type === 'daily' ? 'Daily Digest' : 'Weekly Briefing'} generated!`, 'success');

    } catch (error) {
        console.error('Error generating insight:', error);
        const fallbackContent = type === 'daily'
            ? `# Daily Digest\nGenerated: ${new Date().toLocaleString()}\n\nNo data available. Please refresh competitors first.`
            : `# Weekly Briefing\nGenerated: ${new Date().toLocaleString()}\n\nNo data available. Please refresh competitors first.`;
        displayInsightResult(fallbackContent, type);
        showToast('Generated with limited data', 'warning');
    }
}

/**
 * Generate template-based insight
 */
function generateTemplateInsight(competitors, news, type) {
    const comp = competitors || [];
    const articles = news?.articles || [];

    const highThreat = comp.filter(c => c.threat_level === 'High').length;
    const recentNews = articles.slice(0, 10);

    if (type === 'daily') {
        return `
# Daily Competitive Intelligence Digest
Generated: ${new Date().toLocaleString()}

## Key Numbers
- ${comp.length} competitors tracked
- ${highThreat} high-threat competitors
- ${articles.length} news articles today

## Top Headlines
${recentNews.slice(0, 5).map(n => `- ${n.competitor_name}: ${n.title}`).join('\n')}

## Action Items
- Review high-threat competitor updates
- Check for pricing changes
- Monitor funding announcements
        `;
    } else {
        return `
# Weekly Competitive Intelligence Briefing
Generated: ${new Date().toLocaleString()}

## Executive Summary
This week we tracked ${comp.length} competitors with ${highThreat} in high-threat status.
A total of ${articles.length} news articles were collected across all sources.

## Market Trends
- Healthcare IT consolidation continues
- AI adoption accelerating in patient engagement
- Interoperability requirements driving partnerships

## Competitor Analysis
### High Priority
${comp.filter(c => c.threat_level === 'High').slice(0, 5).map(c => `- ${c.name}: ${c.product_categories || 'Healthcare technology'}`).join('\n')}

## Recommendations
1. Review battlecards for high-threat competitors
2. Prepare competitive responses for market trends
3. Schedule product team sync on feature gaps
        `;
    }
}

/**
 * Display insight result
 */
function displayInsightResult(content, type) {
    // Create modal to display result
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'insightResultModal';
    modal.style.display = 'flex';

    modal.innerHTML = `
        <div class="modal-content" style="max-width: 800px; max-height: 80vh; overflow: auto;">
            <div class="modal-header">
                <h3>🤖 ${type === 'daily' ? 'Daily Digest' : 'Weekly Briefing'}</h3>
                <button class="modal-close" onclick="document.getElementById('insightResultModal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="insight-content" style="white-space: pre-wrap; font-family: inherit; line-height: 1.6;">
                    ${content.replace(/\n/g, '<br>').replace(/^# (.+)$/gm, '<h2>$1</h2>').replace(/^## (.+)$/gm, '<h3>$1</h3>').replace(/^### (.+)$/gm, '<h4>$1</h4>')}
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="document.getElementById('insightResultModal').remove()">Close</button>
                <button class="btn btn-secondary" onclick="copyInsightContent()">📋 Copy</button>
                <button class="btn btn-primary" onclick="exportInsightPDF()">📄 Export PDF</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

/**
 * Copy insight content
 */
function copyInsightContent() {
    const content = document.querySelector('.insight-content')?.textContent;
    if (content) {
        navigator.clipboard.writeText(content);
        showToast('Copied to clipboard', 'success');
    }
}

/**
 * Export insight to PDF
 */
function exportInsightPDF() {
    const content = document.querySelector('.insight-content')?.innerHTML;
    if (content) {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html><head><title>Competitive Intelligence Insight</title>
            <style>body { font-family: Arial, sans-serif; padding: 40px; }</style>
            </head><body>${content}</body></html>
        `);
        printWindow.document.close();
        printWindow.print();
    }
}

// Export functions
window.showAddRuleModal = showAddRuleModal;
window.closeAlertRuleModal = closeAlertRuleModal;
window.saveAlertRule = saveAlertRule;
window.toggleAlertRule = toggleAlertRule;
window.deleteAlertRule = deleteAlertRule;
window.editAlertRule = editAlertRule;
window.saveAIInsightSettings = saveAIInsightSettings;
window.generateManualInsight = generateManualInsight;

// ============================================
// Quick Action Functions (v5.4.0 Enhancement)
// ============================================

/**
 * Quick Action wrapper with instant visual feedback
 */
function quickActionFeedback(card, loading = true) {
    if (loading) {
        card.classList.add('loading');
    } else {
        card.classList.remove('loading');
    }
}

/**
 * Quick Action: Refresh All Data with instant feedback
 */
async function quickActionRefresh(card) {
    quickActionFeedback(card, true);
    showToast('Starting data refresh...', 'info');

    try {
        await triggerScrapeAll();
    } catch (error) {
        console.error('Refresh error:', error);
        showToast('Error starting refresh', 'error');
    } finally {
        // Keep loading while refresh runs, will clear when complete
        setTimeout(() => quickActionFeedback(card, false), 2000);
    }
}

/**
 * Quick Action: Discover Competitors with instant feedback
 */
async function quickActionDiscover(card) {
    quickActionFeedback(card, true);
    showToast('Opening discovery panel...', 'info');

    setTimeout(() => {
        showDiscoveryPanel();
        quickActionFeedback(card, false);
    }, 100);
}

/**
 * Quick Action: Generate Report with instant feedback
 */
async function quickActionReport(card) {
    quickActionFeedback(card, true);
    showToast('Generating executive report...', 'info');

    try {
        await generateQuickReport();
    } catch (error) {
        console.error('Report error:', error);
        showToast('Error generating report', 'error');
    } finally {
        setTimeout(() => quickActionFeedback(card, false), 1500);
    }
}

/**
 * Quick Action: Navigate to page with instant feedback
 */
function quickActionNavigate(card, page) {
    quickActionFeedback(card, true);

    setTimeout(() => {
        showPage(page);
        quickActionFeedback(card, false);
    }, 150);
}

/**
 * Quick Action: Schedule with instant feedback
 */
function quickActionSchedule(card) {
    quickActionFeedback(card, true);

    setTimeout(() => {
        showSchedulerModal();
        quickActionFeedback(card, false);
    }, 100);
}

// Make quick action functions globally available
window.quickActionRefresh = quickActionRefresh;
window.quickActionDiscover = quickActionDiscover;
window.quickActionReport = quickActionReport;
window.quickActionNavigate = quickActionNavigate;
window.quickActionSchedule = quickActionSchedule;

/**
 * Show Discovery Panel for finding new competitors
 */
async function showDiscoveryPanel() {
    // Create modal if it doesn't exist
    let modal = document.getElementById('discoveryModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'discoveryModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 700px;">
                <div class="modal-header">
                    <h3>🔍 Competitor Discovery Agent</h3>
                    <button class="modal-close" onclick="closeDiscoveryModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="discovery-panel">
                        <div class="form-group">
                            <label>Industry Focus</label>
                            <select id="discoveryIndustry" class="form-control">
                                <option value="healthcare">Healthcare Technology</option>
                                <option value="patient_engagement">Patient Engagement</option>
                                <option value="ehr">EHR/EMR Systems</option>
                                <option value="telehealth">Telehealth</option>
                                <option value="revenue_cycle">Revenue Cycle Management</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Max Candidates</label>
                            <input type="number" id="discoveryMaxCandidates" class="form-control" value="10" min="1" max="50">
                        </div>
                        <button class="btn btn-primary" onclick="runDiscovery()" id="runDiscoveryBtn">
                            🚀 Start Discovery
                        </button>
                    </div>
                    <div id="discoveryResults" class="discovery-results" style="margin-top: 20px; display: none;">
                        <h4>Discovery Results</h4>
                        <div id="discoveryResultsList"></div>
                        <div id="discoveryActions" style="margin-top: 16px; display: none;">
                            <button class="btn btn-primary" onclick="addSelectedDiscoveries()">
                                ➕ Add Selected Competitors
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    modal.style.display = 'flex';
}

function closeDiscoveryModal() {
    const modal = document.getElementById('discoveryModal');
    if (modal) modal.style.display = 'none';
}

// ============== News Alert Subscriptions (v8.2.0) ==============

let _subscriptionsCache = [];

function toggleSubscriptionsPanel() {
    const panel = document.getElementById('newsSubscriptionsPanel');
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) {
        loadSubscriptions();
    }
}

async function loadSubscriptions() {
    const list = document.getElementById('subscriptionsList');
    const countEl = document.getElementById('subscriptionCount');
    if (!list) return;

    try {
        const subs = await fetchAPI('/api/subscriptions', { silent: true });
        _subscriptionsCache = Array.isArray(subs) ? subs : [];

        if (countEl) countEl.textContent = `${_subscriptionsCache.length} active`;

        if (_subscriptionsCache.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-secondary);">No active subscriptions. Click "+ Subscribe" to add a competitor alert.</div>';
            return;
        }

        list.innerHTML = _subscriptionsCache.map(sub => `
            <div class="subscription-card" data-sub-id="${sub.id}" style="background:var(--bg-tertiary, rgba(30,41,59,0.5));border-radius:10px;padding:14px 16px;margin-bottom:10px;border:1px solid var(--border-color, rgba(148,163,184,0.15));">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <strong style="color:var(--text-primary);font-size:14px;">${escapeHtml(sub.competitor_name || 'Unknown')}</strong>
                    <button class="btn btn-sm" onclick="deleteSubscription(${sub.id})" style="padding:2px 8px;font-size:11px;color:#ef4444;border-color:#ef4444;" title="Unsubscribe">Unsubscribe</button>
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:8px;">
                    <label class="sub-toggle" style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text-secondary);cursor:pointer;">
                        <input type="checkbox" ${sub.alert_on_pricing ? 'checked' : ''} onchange="updateSubscriptionToggle(${sub.id}, 'alert_on_pricing', this.checked)"> Pricing
                    </label>
                    <label class="sub-toggle" style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text-secondary);cursor:pointer;">
                        <input type="checkbox" ${sub.alert_on_products ? 'checked' : ''} onchange="updateSubscriptionToggle(${sub.id}, 'alert_on_products', this.checked)"> Products
                    </label>
                    <label class="sub-toggle" style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text-secondary);cursor:pointer;">
                        <input type="checkbox" ${sub.alert_on_news ? 'checked' : ''} onchange="updateSubscriptionToggle(${sub.id}, 'alert_on_news', this.checked)"> News
                    </label>
                    <label class="sub-toggle" style="display:flex;align-items:center;gap:4px;font-size:12px;color:var(--text-secondary);cursor:pointer;">
                        <input type="checkbox" ${sub.alert_on_threat_change ? 'checked' : ''} onchange="updateSubscriptionToggle(${sub.id}, 'alert_on_threat_change', this.checked)"> Threat Changes
                    </label>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('[Subscriptions] Load failed:', e);
        list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-secondary);">Unable to load subscriptions.</div>';
    }
}

async function updateSubscriptionToggle(subId, field, value) {
    try {
        const body = {};
        body[field] = value;
        await fetchAPI(`/api/subscriptions/${subId}`, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
    } catch (e) {
        console.error('[Subscriptions] Update failed:', e);
        showToast('Failed to update subscription', 'error');
        loadSubscriptions();
    }
}

async function deleteSubscription(subId) {
    if (!confirm('Unsubscribe from this competitor?')) return;
    try {
        await fetchAPI(`/api/subscriptions/${subId}`, { method: 'DELETE' });
        showToast('Unsubscribed successfully', 'success');
        loadSubscriptions();
    } catch (e) {
        console.error('[Subscriptions] Delete failed:', e);
        showToast('Failed to unsubscribe', 'error');
    }
}

function showAddSubscriptionModal() {
    const availableCompetitors = (window.competitors || []).filter(c => {
        if (c.is_deleted) return false;
        return !_subscriptionsCache.some(s => s.competitor_id === c.id);
    });

    if (availableCompetitors.length === 0) {
        showToast('All competitors are already subscribed', 'info');
        return;
    }

    const modal = document.createElement('div');
    modal.id = 'addSubscriptionModal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:1000;display:flex;align-items:center;justify-content:center;';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

    const options = availableCompetitors
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
        .join('');

    const content = document.createElement('div');
    content.style.cssText = 'background:var(--bg-secondary, #1e293b);border-radius:12px;padding:24px;max-width:420px;width:90%;border:1px solid var(--border-color, rgba(148,163,184,0.15));';
    content.innerHTML = `
        <h3 style="margin:0 0 16px;color:var(--text-primary);font-size:16px;">Subscribe to Competitor Alerts</h3>
        <select id="newSubCompetitor" style="width:100%;padding:10px;border-radius:8px;border:1px solid var(--border-color);background:var(--bg-tertiary, #0f172a);color:var(--text-primary);font-size:14px;margin-bottom:16px;">
            ${options}
        </select>
        <div style="margin-bottom:16px;">
            <label style="font-size:13px;color:var(--text-secondary);margin-bottom:8px;display:block;">Alert Categories:</label>
            <div style="display:flex;flex-wrap:wrap;gap:12px;">
                <label style="display:flex;align-items:center;gap:4px;font-size:13px;color:var(--text-primary);cursor:pointer;">
                    <input type="checkbox" id="newSubPricing" checked> Pricing
                </label>
                <label style="display:flex;align-items:center;gap:4px;font-size:13px;color:var(--text-primary);cursor:pointer;">
                    <input type="checkbox" id="newSubProducts" checked> Products
                </label>
                <label style="display:flex;align-items:center;gap:4px;font-size:13px;color:var(--text-primary);cursor:pointer;">
                    <input type="checkbox" id="newSubNews" checked> News
                </label>
                <label style="display:flex;align-items:center;gap:4px;font-size:13px;color:var(--text-primary);cursor:pointer;">
                    <input type="checkbox" id="newSubThreat" checked> Threat Changes
                </label>
            </div>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;">
            <button class="btn btn-secondary btn-sm" onclick="document.getElementById('addSubscriptionModal').remove()">Cancel</button>
            <button class="btn btn-primary btn-sm" onclick="createSubscription()">Subscribe</button>
        </div>
    `;
    modal.appendChild(content);
    document.body.appendChild(modal);
}

async function createSubscription() {
    const select = document.getElementById('newSubCompetitor');
    if (!select) return;

    const competitorId = parseInt(select.value);
    if (!competitorId) {
        showToast('Please select a competitor', 'warning');
        return;
    }

    try {
        await fetchAPI('/api/subscriptions', {
            method: 'POST',
            body: JSON.stringify({
                competitor_id: competitorId,
                alert_on_pricing: document.getElementById('newSubPricing')?.checked ?? true,
                alert_on_products: document.getElementById('newSubProducts')?.checked ?? true,
                alert_on_news: document.getElementById('newSubNews')?.checked ?? true,
                alert_on_threat_change: document.getElementById('newSubThreat')?.checked ?? true
            })
        });

        const modal = document.getElementById('addSubscriptionModal');
        if (modal) modal.remove();

        showToast('Subscribed successfully', 'success');
        loadSubscriptions();
    } catch (e) {
        console.error('[Subscriptions] Create failed:', e);
        showToast('Failed to create subscription', 'error');
    }
}

// ============== AI Discovery Engine Functions (v7.0.0) ==============

async function loadDiscoveryProfiles() {
    try {
        const response = await fetchAPI('/api/discovery/profiles');
        const profiles = response.profiles || [];

        const selector = document.getElementById('profileSelector');
        if (!selector) return;

        selector.innerHTML = '<option value="">-- Saved Profiles --</option>';
        profiles.forEach(p => {
            selector.innerHTML += `<option value="${p.id}">${escapeHtml(p.name)}</option>`;
        });
    } catch (error) {
        console.error('Failed to load profiles:', error);
    }
}

async function loadProfile(profileId) {
    if (!profileId) return;

    try {
        const response = await fetchAPI(`/api/discovery/profiles/${profileId}`);
        if (response) {
            populateQualificationForm(response);
            showToast(`Loaded profile: ${response.name}`, 'success');
        }
    } catch (error) {
        showToast('Failed to load profile', 'error');
    }
}

function populateQualificationForm(profile) {
    // B11 Fix: Wrap in try-catch to handle malformed profile data
    try {
        // Clear all checkboxes first
        document.querySelectorAll('#qualificationCriteriaPanel input[type="checkbox"]').forEach(cb => cb.checked = false);

        // Helper to safely parse JSON
        const safeJSONParse = (str, defaultVal) => {
            try {
                return typeof str === 'string' ? JSON.parse(str) : (str || defaultVal);
            } catch {
                console.warn('Failed to parse profile field:', str);
                return defaultVal;
            }
        };

        // Segments
        const segments = safeJSONParse(profile.target_segments, []);
        segments.forEach(s => {
            const cb = document.querySelector(`input[name="segment"][value="${s}"]`);
            if (cb) cb.checked = true;
        });

        // Capabilities
        const capabilities = safeJSONParse(profile.required_capabilities, []);
        capabilities.forEach(c => {
            const cb = document.querySelector(`input[name="capability"][value="${c}"]`);
            if (cb) cb.checked = true;
        });

        // Company size
        const companySize = safeJSONParse(profile.company_size, {});
        const minEl = document.getElementById('minEmployees');
        const maxEl = document.getElementById('maxEmployees');
        if (minEl) minEl.value = companySize.min_employees || '';
        if (maxEl) maxEl.value = companySize.max_employees || '';

        // Geography
        const geography = safeJSONParse(profile.geography, ['us']);
        geography.forEach(g => {
            const cb = document.querySelector(`input[name="geography"][value="${g}"]`);
            if (cb) cb.checked = true;
        });

        // Funding stages
        const funding = safeJSONParse(profile.funding_stages, []);
        funding.forEach(f => {
            const cb = document.querySelector(`input[name="funding"][value="${f}"]`);
            if (cb) cb.checked = true;
        });

        // Exclusions
        const exclusions = safeJSONParse(profile.exclusions, []);
        exclusions.forEach(e => {
            const cb = document.querySelector(`input[name="exclude"][value="${e}"]`);
            if (cb) cb.checked = true;
        });

        // Custom keywords
        const customKeywords = safeJSONParse(profile.custom_keywords, {});
        const includeEl = document.getElementById('customIncludeKeywords');
        const excludeEl = document.getElementById('customExcludeKeywords');
        if (includeEl) includeEl.value = (customKeywords.include || []).join(', ');
        if (excludeEl) excludeEl.value = (customKeywords.exclude || []).join(', ');

    } catch (error) {
        console.error('Error populating qualification form:', error);
        showToast('Some profile settings could not be loaded. Using defaults.', 'warning');
    }
}

function collectQualificationCriteria() {
    // Collect all form data into structured object
    // Note: tech_requirements removed - no checkboxes exist in UI (Bug B1 fix)
    const criteria = {
        target_segments: Array.from(document.querySelectorAll('input[name="segment"]:checked')).map(cb => cb.value),
        required_capabilities: Array.from(document.querySelectorAll('input[name="capability"]:checked')).map(cb => cb.value),
        company_size: {
            min_employees: parseInt(document.getElementById('minEmployees')?.value) || null,
            max_employees: parseInt(document.getElementById('maxEmployees')?.value) || null
        },
        geography: Array.from(document.querySelectorAll('input[name="geography"]:checked')).map(cb => cb.value),
        funding_stages: Array.from(document.querySelectorAll('input[name="funding"]:checked')).map(cb => cb.value),
        exclusions: Array.from(document.querySelectorAll('input[name="exclude"]:checked')).map(cb => cb.value),
        custom_keywords: {
            include: (document.getElementById('customIncludeKeywords')?.value || '').split(',').map(k => k.trim()).filter(k => k),
            exclude: (document.getElementById('customExcludeKeywords')?.value || '').split(',').map(k => k.trim()).filter(k => k)
        },
        custom_instructions: (document.getElementById('discoveryCustomInstructions')?.value || '').trim()
    };

    return criteria;
}

async function saveCurrentProfile() {
    // Fixed: Better error handling for profile save
    const name = prompt('Enter a name for this criteria profile:');
    if (!name || !name.trim()) {
        showToast('Profile name is required', 'warning');
        return;
    }

    const trimmedName = name.trim();
    const criteria = collectQualificationCriteria();

    try {

        const response = await fetch(`${API_BASE}/api/discovery/profiles`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: trimmedName,
                description: `Saved on ${new Date().toLocaleDateString()}`,
                target_segments: criteria.target_segments || [],
                required_capabilities: criteria.required_capabilities || [],
                company_size: criteria.company_size || {},
                geography: criteria.geography || ['us'],
                funding_stages: criteria.funding_stages || [],
                exclusions: criteria.exclusions || [],
                custom_keywords: criteria.custom_keywords || {}
            })
        });

        const data = await response.json();

        if (response.ok && !data.error) {
            showToast(`Profile "${trimmedName}" saved successfully!`, 'success');
            await loadDiscoveryProfiles();
            // Select the newly created profile
            const selector = document.getElementById('profileSelector');
            if (selector && data.id) {
                setTimeout(() => {
                    selector.value = data.id;
                }, 100);
            }
        } else {
            throw new Error(data.error || data.detail || 'Failed to save profile');
        }
    } catch (error) {
        console.error('[Profile Save] Error:', error);
        showToast('Failed to save profile: ' + error.message, 'error');
    }
}

function _renderSourceLink(sourceUrl) {
    if (!sourceUrl) return '';
    return `<a href="${escapeHtml(sourceUrl)}" target="_blank" onclick="event.stopPropagation();"
               title="${escapeHtml(sourceUrl)}"
               style="color: var(--primary-color); font-size: 11px; margin-left: 4px; text-decoration: none; opacity: 0.7;">&#x1F517;</a>`;
}

function _renderDataField(label, value, sourceUrl) {
    if (!value) return '';
    const link = _renderSourceLink(sourceUrl);
    return `<div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid var(--border-color);">
        <span style="font-size: 11px; color: var(--text-muted); font-weight: 600;">${escapeHtml(label)}</span>
        <span style="font-size: 12px; color: var(--text-primary); font-weight: 500; text-align: right;">${escapeHtml(String(value))}${link}</span>
    </div>`;
}

function renderDiscoveryCandidate(candidate, idx) {
    const threatColors = {
        'Critical': '#ef4444',
        'High': '#f97316',
        'Medium': '#eab308',
        'Low': '#22c55e',
        'Unknown': '#6b7280'
    };

    const threatLevel = candidate.threat_level || 'Unknown';
    const threatColor = threatColors[threatLevel];
    const score = getMatchScore(candidate);

    // Build source lookup from candidate.data_sources (array of {field_name, source_url})
    const srcLookup = {};
    if (candidate.data_sources && Array.isArray(candidate.data_sources)) {
        candidate.data_sources.forEach(ds => {
            if (ds.field_name && ds.source_url) {
                srcLookup[ds.field_name] = ds.source_url;
            }
        });
    }

    // Collect data fields for mini-battlecard
    const dataFieldsHtml = [
        _renderDataField('Employees', candidate.employee_count, srcLookup['employee_count']),
        _renderDataField('Customers', candidate.customer_count, srcLookup['customer_count']),
        _renderDataField('Funding', candidate.funding_total, srcLookup['funding_total']),
        _renderDataField('Revenue', candidate.annual_revenue, srcLookup['annual_revenue']),
        _renderDataField('Pricing', candidate.base_price || candidate.pricing_model, srcLookup['base_price'] || srcLookup['pricing_model']),
        _renderDataField('HQ', candidate.headquarters, srcLookup['headquarters']),
        _renderDataField('Founded', candidate.year_founded, srcLookup['year_founded']),
    ].filter(h => h).join('');

    // Products / features chips
    const products = candidate.products_found || [];
    const features = candidate.features_found || [];
    const chipsHtml = [...products.slice(0, 4), ...features.slice(0, 3)].map(
        t => `<span style="display:inline-block;padding:2px 8px;background:var(--primary-color)15;color:var(--primary-color);border-radius:12px;font-size:10px;font-weight:600;margin:2px;">${escapeHtml(t)}</span>`
    ).join('');

    // Use battlecard-style design with threat-colored left border
    return `
        <div class="discovery-candidate battlecard-preview threat-${threatLevel.toLowerCase()}"
             style="padding: 16px; margin-bottom: 12px; background: var(--bg-card); border-radius: 12px;
                    border: 1px solid var(--border-color); border-left: 4px solid ${threatColor};
                    transition: all 0.2s ease; cursor: default;">
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <input type="checkbox" id="disc_${idx}" data-index="${idx}"
                       style="margin-top: 4px; width: 20px; height: 20px; flex-shrink: 0; accent-color: var(--primary-color);"
                       onclick="event.stopPropagation();">

                <div style="flex: 1; min-width: 0;">
                    <!-- Header Row -->
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                        <div>
                            <h4 style="margin: 0; font-size: 18px; font-weight: 700; color: var(--text-primary);">${escapeHtml(candidate.name)}</h4>
                            <a href="${escapeHtml(candidate.url)}" target="_blank" onclick="event.stopPropagation();"
                               style="font-size: 12px; color: var(--primary-color); font-weight: 500;">${escapeHtml(candidate.domain || candidate.url)}</a>
                        </div>
                        <div style="display: flex; gap: 8px; flex-shrink: 0; flex-wrap: wrap;">
                            <span class="threat-badge ${threatLevel.toLowerCase()}"
                                  style="padding: 4px 12px; background: ${threatColor}20; color: ${threatColor};
                                         border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase;">
                                ${threatLevel} Threat
                            </span>
                            ${score !== null ? `<span style="padding: 4px 12px; background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                                         color: white; border-radius: 20px; font-size: 11px; font-weight: 700;">
                                ${score}% Match
                            </span>` : ''}
                        </div>
                    </div>

                    <!-- AI Summary -->
                    ${candidate.ai_summary ? `
                        <p class="battlecard-summary" style="margin: 0 0 12px; color: var(--text-secondary); font-size: 14px; line-height: 1.6;">
                            ${escapeHtml(candidate.ai_summary)}
                        </p>
                    ` : (candidate.qualification_reasoning ? `
                        <p class="battlecard-summary" style="margin: 0 0 12px; color: var(--text-secondary); font-size: 14px; line-height: 1.6;">
                            ${escapeHtml(candidate.qualification_reasoning)}
                        </p>
                    ` : '')}

                    <!-- Product / Feature Chips -->
                    ${chipsHtml ? `<div style="margin-bottom: 10px;">${chipsHtml}</div>` : ''}

                    <!-- Key Data Fields (mini-battlecard) -->
                    ${dataFieldsHtml ? `
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; margin-bottom: 10px; padding: 8px 12px; background: var(--bg-secondary); border-radius: 8px;">
                            ${dataFieldsHtml}
                        </div>
                    ` : ''}

                    <!-- Strengths & Weaknesses in compact grid -->
                    ${(candidate.strengths && candidate.strengths.length > 0) || (candidate.weaknesses && candidate.weaknesses.length > 0) ? `
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 10px; padding: 10px 12px; background: var(--bg-secondary); border-radius: 8px;">
                            ${candidate.strengths && candidate.strengths.length > 0 ? `
                                <div>
                                    <h5 style="margin: 0 0 8px; font-size: 11px; color: #22c55e; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px;">
                                        Strengths
                                    </h5>
                                    <ul style="margin: 0; padding-left: 16px; font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
                                        ${candidate.strengths.slice(0, 3).map(s => `<li style="margin-bottom: 4px;">${escapeHtml(s)}</li>`).join('')}
                                    </ul>
                                </div>
                            ` : '<div></div>'}
                            ${candidate.weaknesses && candidate.weaknesses.length > 0 ? `
                                <div>
                                    <h5 style="margin: 0 0 8px; font-size: 11px; color: #f97316; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px;">
                                        Weaknesses
                                    </h5>
                                    <ul style="margin: 0; padding-left: 16px; font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
                                        ${candidate.weaknesses.slice(0, 3).map(w => `<li style="margin-bottom: 4px;">${escapeHtml(w)}</li>`).join('')}
                                    </ul>
                                </div>
                            ` : '<div></div>'}
                        </div>
                    ` : ''}

                    <!-- Competitive Positioning (collapsible) -->
                    ${candidate.competitive_positioning ? `
                        <details style="margin-top: 8px;">
                            <summary style="cursor: pointer; font-size: 12px; color: var(--primary-color); font-weight: 600; padding: 4px 0;">
                                View competitive positioning
                            </summary>
                            <div style="margin-top: 8px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; font-size: 13px; border-left: 3px solid var(--primary-color);">
                                <p style="margin: 0; line-height: 1.5;">${escapeHtml(candidate.competitive_positioning)}</p>
                            </div>
                        </details>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

async function runDiscovery() {
    const btn = document.getElementById('runDiscoveryBtn');
    const progressContainer = document.getElementById('discoveryProgressContainer');
    const progressFill = document.getElementById('discoveryProgressFill');
    const progressText = document.getElementById('discoveryProgressText');
    const resultsDiv = document.getElementById('discoveryResults');
    const resultsList = document.getElementById('discoveryResultsList');
    const summaryContainer = document.getElementById('discoverySummaryContainer');
    const resultsHeader = document.getElementById('discoveryResultsHeader');

    if (!btn || !resultsDiv || !resultsList) {
        console.error('[Discovery] Required DOM elements not found');
        showToast('Discovery panel not initialized. Please refresh the page.', 'error');
        return;
    }

    // Collect structured criteria from form
    let criteria = collectQualificationCriteria();
    const maxCandidates = parseInt(document.getElementById('discoveryMaxCandidates')?.value) || 10;
    const promptSelect = document.getElementById('discoveryPromptSelect');
    const promptKey = promptSelect?.value || '';

    // Validate criteria
    const validation = validateDiscoveryCriteria(criteria);
    if (!validation.valid) {
        showToast(validation.errors.join('. '), 'error');
        return;
    }
    criteria = validation.criteria;

    if (validation.warnings && validation.warnings.length > 0) {
        validation.warnings.forEach(warning => {
            showToast(warning, 'warning', { duration: 6000 });
        });
    }


    btn.disabled = true;
    btn.innerHTML = 'Running AI Discovery...';
    // Also disable collapsed button if visible
    const btnCollapsed = document.getElementById('runDiscoveryBtnCollapsed');
    if (btnCollapsed) { btnCollapsed.disabled = true; btnCollapsed.innerHTML = 'Running...'; }
    if (progressContainer) { progressContainer.style.display = 'block'; }
    if (progressFill) { progressFill.style.width = '0%'; }
    if (progressText) { progressText.textContent = 'Starting discovery pipeline...'; }
    resultsDiv.style.display = 'none';
    if (summaryContainer) { summaryContainer.style.display = 'none'; }
    if (resultsHeader) { resultsHeader.style.display = 'none'; }
    // Hide empty state during discovery
    const emptyState = document.getElementById('discoveryEmptyState');
    if (emptyState) emptyState.style.display = 'none';

    // Reset stage indicators
    const indicators = document.querySelectorAll('#discoveryStageIndicators .stage-indicator');
    indicators.forEach(ind => { ind.style.color = 'var(--text-muted)'; ind.style.fontWeight = 'normal'; });

    showToast('Starting AI-powered competitor discovery...', 'info');

    try {
        // Start background discovery
        const startResponse = await fetchAPI('/api/discovery/run-ai', {
            method: 'POST',
            body: JSON.stringify({
                ...criteria,
                max_candidates: maxCandidates,
                prompt_key: promptKey,
                background: true
            })
        });

        if (!startResponse || !startResponse.task_id) {
            throw new Error('Failed to start discovery pipeline');
        }

        const taskId = startResponse.task_id;

        // Store in globals so polling survives page navigation
        _discoveryTaskId = taskId;
        _discoveryPolling = true;
        _discoveryResult = null;
        _discoveryError = null;
        _discoverySummary = null;

        // Poll in background — survives tab navigation
        await _pollDiscoveryProgress(taskId);

        // If polling finished with an error, throw it so catch block handles UI
        if (_discoveryError) {
            throw new Error(_discoveryError);
        }

    } catch (error) {
        console.error('[Discovery] Error:', error);
        if (resultsHeader) { resultsHeader.style.display = 'none'; }

        let errorTitle = 'Discovery Error';
        let errorMessage = error.message;
        let errorSuggestion = '';

        if (error.message.includes('401') || error.message.includes('Unauthorized')) {
            errorTitle = 'Authentication Required';
            errorMessage = 'Your session has expired.';
            errorSuggestion = 'Please log in again to continue.';
        } else if (error.message.includes('timeout') || error.message.includes('timed out')) {
            errorTitle = 'Discovery Timed Out';
            errorMessage = 'The search took too long to complete.';
            errorSuggestion = 'Try reducing the number of results or narrowing your criteria.';
        } else if (error.message.includes('network') || error.message.includes('fetch') || error.message.includes('Failed to fetch')) {
            errorTitle = 'Network Error';
            errorMessage = 'Could not connect to the server.';
            errorSuggestion = 'Check your internet connection and try again.';
        }

        resultsDiv.style.display = 'block';
        if (resultsList) {
            resultsList.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--error-color);">
                    <p style="font-size: 48px; margin-bottom: 16px;">&#9888;&#65039;</p>
                    <h4>${escapeHtml(errorTitle)}</h4>
                    <p style="font-size: 14px; margin-bottom: 8px; color: var(--text-secondary);">${escapeHtml(errorMessage)}</p>
                    ${errorSuggestion ? `<p style="font-size: 12px; margin-bottom: 16px; color: var(--text-muted);">${escapeHtml(errorSuggestion)}</p>` : ''}
                    <button class="btn btn-secondary" onclick="runDiscovery()">Try Again</button>
                </div>
            `;
        }
        showToast(errorTitle + ': ' + errorMessage, 'error');
    } finally {
        // Only reset UI if polling has finished (not if user just navigated away)
        if (!_discoveryPolling) {
            const btnFinal = document.getElementById('runDiscoveryBtn');
            if (btnFinal) {
                btnFinal.disabled = false;
                btnFinal.innerHTML = 'Start AI Discovery';
            }
            const btnCollapsedFinal = document.getElementById('runDiscoveryBtnCollapsed');
            if (btnCollapsedFinal) {
                btnCollapsedFinal.disabled = false;
                btnCollapsedFinal.innerHTML = 'Start AI Discovery';
            }
            const pcFinal = document.getElementById('discoveryProgressContainer');
            if (pcFinal) {
                setTimeout(() => { pcFinal.style.display = 'none'; }, 2000);
            }
        }
    }
}

function handleDiscoveryComplete(result) {
    const resultsDiv = document.getElementById('discoveryResults');
    const resultsList = document.getElementById('discoveryResultsList');
    const resultsHeader = document.getElementById('discoveryResultsHeader');
    const resultCount = document.getElementById('discoveryResultCount');
    const actionsDiv = document.getElementById('discoveryActions');

    // Cache in global state so results survive tab navigation
    if (result && result.candidates && result.candidates.length > 0) {
        _discoveryResult = result;
    }

    if (result && result.candidates && result.candidates.length > 0) {
        window.discoveredCandidates = result.candidates;
        window.discoveryMetadata = {
            stages_run: result.stages_run,
            processing_time_ms: result.processing_time_ms
        };

        if (resultsHeader && resultCount) {
            resultsHeader.style.display = 'block';
            resultCount.textContent = result.candidates.length + ' competitors found';
        }

        renderDiscoveryResults(result.candidates);
        if (resultsDiv) resultsDiv.style.display = 'block';
        if (actionsDiv) actionsDiv.style.display = 'flex';

        // Hide empty state and collapse criteria when results arrive
        const emptyState = document.getElementById('discoveryEmptyState');
        if (emptyState) emptyState.style.display = 'none';
        collapseCriteriaPanel();

        const toastType = result.status === 'partial' ? 'warning' : 'success';
        const toastSuffix = result.status === 'partial' ? ' (some stages had errors)' : '';
        showToast('AI Discovery complete! Found ' + result.candidates.length + ' competitors.' + toastSuffix, toastType);

        // Generate AI summary
        generateDiscoverySummary(result.candidates);
    } else {
        if (resultsDiv) resultsDiv.style.display = 'block';
        if (resultsList) {
            resultsList.innerHTML = '<div style="text-align: center; padding: 40px; background: var(--bg-secondary); border-radius: 12px;">' +
                '<p style="font-size: 48px; margin-bottom: 16px;">&#128269;</p>' +
                '<h4 style="color: var(--text-primary); margin-bottom: 8px;">No Competitors Found</h4>' +
                '<p style="color: var(--text-secondary); font-size: 14px;">Try adjusting your qualification criteria or expanding the search parameters.</p></div>';
        }
        if (actionsDiv) actionsDiv.style.display = 'none';
        if (resultsHeader) resultsHeader.style.display = 'none';
        showToast('No competitors matched your criteria', 'info');
    }
}

async function generateDiscoverySummary(candidates) {
    const container = document.getElementById('discoverySummaryContainer');
    const content = document.getElementById('discoverySummaryContent');
    if (!container || !content) return;

    container.style.display = 'block';
    content.innerHTML = '<div class="spinner" style="margin: 0 auto;"></div><p style="text-align:center;margin-top:8px;">Generating AI summary...</p>';

    try {
        const result = await fetchAPI('/api/discovery/summarize', {
            method: 'POST',
            body: JSON.stringify({
                candidates: candidates.map(c => ({
                    name: c.name,
                    threat_level: c.threat_level,
                    qualification_score: c.qualification_score,
                    ai_summary: c.ai_summary,
                    strengths: c.strengths,
                    weaknesses: c.weaknesses
                }))
            })
        });
        if (result && result.summary) {
            content.textContent = result.summary;
            _discoverySummary = result.summary;
        } else {
            content.textContent = 'Summary unavailable.';
        }
    } catch (e) {
        console.error('[Discovery] Summary generation failed:', e);
        content.textContent = 'Failed to generate summary. Review individual results above.';
    }
}

async function sendSelectedToBattlecard() {
    const checkboxes = document.querySelectorAll('#discoveryResultsList input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        showToast('Select at least one competitor', 'warning');
        return;
    }
    const candidates = [];
    checkboxes.forEach(cb => {
        const idx = parseInt(cb.dataset.index);
        if (window.discoveredCandidates && window.discoveredCandidates[idx]) {
            candidates.push(window.discoveredCandidates[idx]);
        }
    });
    if (candidates.length === 0) {
        showToast('No valid candidates selected', 'warning');
        return;
    }
    showToast('Generating battlecards for ' + candidates.length + ' competitors...', 'info');
    try {
        const result = await fetchAPI('/api/discovery/send-to-battlecard', {
            method: 'POST',
            body: JSON.stringify({ candidates })
        });
        if (result && result.battlecard_ids) {
            showToast('Battlecards generated! Navigating...', 'success');
            // Clear cached discovery results after accepting
            _discoveryResult = null;
            _discoverySummary = null;
            showPage('battlecards');
        }
    } catch (e) {
        showToast('Failed to generate battlecards', 'error');
    }
}

async function sendSelectedToComparison() {
    const checkboxes = document.querySelectorAll('#discoveryResultsList input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        showToast('Select at least one competitor', 'warning');
        return;
    }
    const candidates = [];
    checkboxes.forEach(cb => {
        const idx = parseInt(cb.dataset.index);
        if (window.discoveredCandidates && window.discoveredCandidates[idx]) {
            candidates.push(window.discoveredCandidates[idx]);
        }
    });
    if (candidates.length === 0) {
        showToast('No valid candidates selected', 'warning');
        return;
    }
    showToast('Adding ' + candidates.length + ' competitors to comparison...', 'info');
    try {
        const result = await fetchAPI('/api/discovery/send-to-comparison', {
            method: 'POST',
            body: JSON.stringify({ candidates })
        });
        if (result && result.competitor_ids) {
            window._preselectedComparisonIds = result.competitor_ids;
            showToast('Navigating to comparison...', 'success');
            // Clear cached discovery results after accepting
            _discoveryResult = null;
            _discoverySummary = null;
            showPage('comparison');
        }
    } catch (e) {
        showToast('Failed to add competitors for comparison', 'error');
    }
}

function updateDiscoveryStageIndicators(stagesCompleted) {
    const indicators = document.querySelectorAll('#discoveryStageIndicators .stage-indicator');
    indicators.forEach(ind => {
        const stage = ind.dataset.stage;
        if (stagesCompleted && stagesCompleted.includes(stage)) {
            ind.style.color = '#16a34a';
            ind.style.fontWeight = '700';
        }
    });
}

/**
 * Poll discovery progress — runs independently of page navigation.
 * If user switches tabs, polling continues in the background.
 * When they return to discovery page, resumeDiscoveryIfRunning() reconnects UI.
 */
async function _pollDiscoveryProgress(taskId) {
    const startTime = Date.now();
    while (_discoveryPolling) {
        await new Promise(r => setTimeout(r, 2000));

        // Safety timeout: 150 seconds
        if (Date.now() - startTime > 150000) {
            console.warn('[Discovery] Polling timed out after 150s');
            _discoveryError = 'Discovery timed out after 150 seconds';
            _discoveryPolling = false;
            _discoveryTaskId = null;
            break;
        }

        try {
            const progress = await fetchAPI(`/api/discovery/progress/${taskId}`, { silent: true });
            if (!progress) continue;

            // Update DOM elements only if they exist (user may be on another page)
            const progressFill = document.getElementById('discoveryProgressFill');
            const progressText = document.getElementById('discoveryProgressText');

            const pct = progress.progress?.percent_complete || 0;
            if (progressFill) { progressFill.style.width = pct + '%'; }
            if (progressText) {
                progressText.textContent = progress.progress?.current_stage_name || 'Processing...';
                const eta = progress.progress?.estimated_time_remaining;
                if (eta && eta > 0) {
                    progressText.textContent += ` (~${eta}s remaining)`;
                }
            }

            updateDiscoveryStageIndicators(progress.progress?.stages_completed || []);

            if (progress.status === 'completed') {
                if (progressFill) { progressFill.style.width = '100%'; }
                if (progressText) { progressText.textContent = 'Discovery complete!'; }
                _discoveryPolling = false;
                _discoveryTaskId = null;
                // Only call handleDiscoveryComplete if DOM exists (user on discovery page)
                if (document.getElementById('discoveryResults')) {
                    handleDiscoveryComplete(progress.result);
                } else {
                    // Cache result for when user returns
                    _discoveryResult = progress.result;
                    if (progress.result?.candidates) {
                        window.discoveredCandidates = progress.result.candidates;
                    }
                }
                break;
            } else if (progress.status === 'failed') {
                _discoveryError = progress.error || 'Discovery pipeline failed';
                _discoveryPolling = false;
                _discoveryTaskId = null;
                break;
            }
        } catch (pollErr) {
            console.warn('[Discovery] Poll error (will retry):', pollErr.message);
        }
    }
}

/**
 * Resume discovery state when user navigates back to the discovery page.
 * Returns: 'polling' | 'results' | 'error' | null
 */
function resumeDiscoveryIfRunning() {
    if (_discoveryPolling && _discoveryTaskId) {
        // Active polling — reconnect progress UI
        const progressContainer = document.getElementById('discoveryProgressContainer');
        const btn = document.getElementById('runDiscoveryBtn');
        const btnCollapsed = document.getElementById('runDiscoveryBtnCollapsed');
        if (progressContainer) { progressContainer.style.display = 'block'; }
        if (btn) { btn.disabled = true; btn.innerHTML = 'Running AI Discovery...'; }
        if (btnCollapsed) { btnCollapsed.disabled = true; btnCollapsed.innerHTML = 'Running...'; }
        // Hide empty state during active polling
        const emptyState = document.getElementById('discoveryEmptyState');
        if (emptyState) emptyState.style.display = 'none';
        return 'polling';
    }

    if (_discoveryResult && _discoveryResult.candidates && _discoveryResult.candidates.length > 0) {
        // Cached results — re-render them
        handleDiscoveryComplete(_discoveryResult);
        // Restore cached summary if available
        if (_discoverySummary) {
            const container = document.getElementById('discoverySummaryContainer');
            const content = document.getElementById('discoverySummaryContent');
            if (container && content) {
                container.style.display = 'block';
                content.textContent = _discoverySummary;
            }
        }
        // Hide empty state when results are restored
        const emptyState = document.getElementById('discoveryEmptyState');
        if (emptyState) emptyState.style.display = 'none';
        return 'results';
    }

    if (_discoveryError) {
        // Show cached error
        const resultsDiv = document.getElementById('discoveryResults');
        const resultsList = document.getElementById('discoveryResultsList');
        if (resultsDiv) resultsDiv.style.display = 'block';
        if (resultsList) {
            resultsList.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--error-color);">
                    <p style="font-size: 48px; margin-bottom: 16px;">&#9888;&#65039;</p>
                    <h4>Discovery Error</h4>
                    <p style="font-size: 14px; margin-bottom: 8px; color: var(--text-secondary);">${escapeHtml(_discoveryError)}</p>
                    <button class="btn btn-secondary" onclick="clearDiscoveryResults(); runDiscovery();">Try Again</button>
                </div>
            `;
        }
        return 'error';
    }

    return null;
}

/**
 * Clear all cached discovery results and reset UI.
 */
function clearDiscoveryResults() {
    _discoveryTaskId = null;
    _discoveryPolling = false;
    _discoveryResult = null;
    _discoverySummary = null;
    _discoveryError = null;
    window.discoveredCandidates = null;
    window.discoveryMetadata = null;

    // v8.0.8: Clear saved discovery results from DB
    fetchAPI('/api/discovery/results', { method: 'DELETE', silent: true }).catch(() => {});

    const resultsDiv = document.getElementById('discoveryResults');
    const summaryContainer = document.getElementById('discoverySummaryContainer');
    const actionsDiv = document.getElementById('discoveryActions');
    const resultsHeader = document.getElementById('discoveryResultsHeader');

    if (resultsDiv) resultsDiv.style.display = 'none';
    if (summaryContainer) summaryContainer.style.display = 'none';
    if (actionsDiv) actionsDiv.style.display = 'none';
    if (resultsHeader) resultsHeader.style.display = 'none';

    // Show empty state and expand criteria panel
    const emptyState = document.getElementById('discoveryEmptyState');
    if (emptyState) emptyState.style.display = 'block';
    expandCriteriaPanel();

    showToast('Discovery results cleared', 'info');
}

// Discovery Scout global exports
window.sendSelectedToBattlecard = sendSelectedToBattlecard;
window.sendSelectedToComparison = sendSelectedToComparison;
window.generateDiscoverySummary = generateDiscoverySummary;
window.handleDiscoveryComplete = handleDiscoveryComplete;
window.updateDiscoveryStageIndicators = updateDiscoveryStageIndicators;
window.clearDiscoveryResults = clearDiscoveryResults;
window.resumeDiscoveryIfRunning = resumeDiscoveryIfRunning;

/**
 * Render discovery results to the results list
 * @param {Array} candidates - Array of discovery candidates
 */
function renderDiscoveryResults(candidates) {
    const resultsList = document.getElementById('discoveryResultsList');
    if (!resultsList) return;

    const metadata = window.discoveryMetadata || {};

    // Build status line
    const stagesInfo = metadata.stages_run ? metadata.stages_run.join(' \u2192 ') : 'search \u2192 scrape \u2192 qualify \u2192 analyze';
    const timeInfo = metadata.processing_time_ms ? (metadata.processing_time_ms / 1000).toFixed(1) + 's' : '';
    const lastRunInfo = metadata.last_run ? new Date(metadata.last_run).toLocaleString() : '';
    const statusParts = [stagesInfo, timeInfo ? 'Time: ' + timeInfo : '', lastRunInfo ? 'Run: ' + lastRunInfo : ''].filter(Boolean);

    resultsList.innerHTML = `
        <div style="margin-bottom: 16px; padding: 16px; background: linear-gradient(135deg, #065f46, #064e3b); border-radius: 8px; border-left: 4px solid #10b981;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                    <strong style="color: #ecfdf5; font-size: 16px;">Found ${candidates.length} qualified competitors</strong>
                    <p style="margin: 4px 0 0; font-size: 12px; color: #a7f3d0;">
                        ${statusParts.join(' | ')}
                    </p>
                </div>
                <div style="display: flex; gap: 6px;">
                    <button class="btn btn-secondary" onclick="excludeSelectedDiscoveries()" style="font-size: 12px; padding: 6px 12px; white-space: nowrap;" title="Add selected to exclude list">Exclude Selected</button>
                    <button class="btn btn-secondary" onclick="showDiscoveryExcludeModal()" style="font-size: 12px; padding: 6px 12px; white-space: nowrap;" title="View exclude list">Exclude List</button>
                    <button class="btn btn-secondary" onclick="clearDiscoveryResults()" style="font-size: 12px; padding: 6px 12px; white-space: nowrap;">Clear Results</button>
                </div>
            </div>
        </div>

        ${candidates.map((comp, idx) => renderDiscoveryCandidate(comp, idx)).join('')}
    `;
}

/**
 * Sort discovery results by the specified field
 * @param {string} sortBy - Sort option (e.g., 'score_desc', 'threat_asc', 'name_asc')
 */
function sortDiscoveryResults(sortBy) {
    if (!window.discoveredCandidates || window.discoveredCandidates.length === 0) {
        return;
    }

    const threatLevels = { 'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1, 'Unknown': 0 };

    const sorted = [...window.discoveredCandidates].sort((a, b) => {
        const scoreA = getMatchScore(a) || 0;
        const scoreB = getMatchScore(b) || 0;
        const threatA = threatLevels[a.threat_level] || 0;
        const threatB = threatLevels[b.threat_level] || 0;
        const nameA = (a.name || '').toLowerCase();
        const nameB = (b.name || '').toLowerCase();

        switch (sortBy) {
            case 'score_desc':
                return scoreB - scoreA;
            case 'score_asc':
                return scoreA - scoreB;
            case 'threat_desc':
                return threatB - threatA;
            case 'threat_asc':
                return threatA - threatB;
            case 'name_asc':
                return nameA.localeCompare(nameB);
            case 'name_desc':
                return nameB.localeCompare(nameA);
            default:
                return scoreB - scoreA;
        }
    });

    window.discoveredCandidates = sorted;
    renderDiscoveryResults(sorted);
}

// Make sorting functions globally available
window.sortDiscoveryResults = sortDiscoveryResults;
window.renderDiscoveryResults = renderDiscoveryResults;

async function addSelectedDiscoveries() {
    const checkboxes = document.querySelectorAll('#discoveryResultsList input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        showToast('Please select at least one competitor', 'warning');
        return;
    }

    // Get selected candidates from stored data
    const selectedCandidates = [];
    checkboxes.forEach(cb => {
        const index = parseInt(cb.dataset.index);
        if (window.discoveredCandidates && window.discoveredCandidates[index]) {
            selectedCandidates.push(window.discoveredCandidates[index]);
        }
    });

    if (selectedCandidates.length === 0) {
        showToast('Error: Could not find selected competitors', 'error');
        return;
    }

    showToast(`Adding ${selectedCandidates.length} competitor(s) to database...`, 'info');

    try {
        // Call the API to add discovered competitors
        const response = await fetch(`${API_BASE}/api/discovery/add`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                candidates: selectedCandidates.map(c => ({
                    name: c.name,
                    url: c.url,
                    reasoning: c.qualification_reasoning || c.reasoning || c.ai_summary || 'Discovered via AI agent',
                    // Pass both score types - backend now handles either (B3 fix)
                    relevance_score: c.relevance_score,
                    qualification_score: c.qualification_score || c.relevance_score || 50,
                    // v7.1.0: Pass all discovery data for richer competitor records
                    threat_level: c.threat_level || null,
                    threat_score: c.threat_score || null,
                    strengths: c.strengths || [],
                    weaknesses: c.weaknesses || [],
                    competitive_positioning: c.competitive_positioning || '',
                    ai_summary: c.ai_summary || '',
                    products_found: c.products_found || [],
                    features_found: c.features_found || [],
                    meta_description: c.meta_description || '',
                    page_title: c.page_title || '',
                    // v7.2: Pass structured data fields for richer competitor records
                    employee_count: c.employee_count || null,
                    customer_count: c.customer_count || null,
                    headquarters: c.headquarters || null,
                    year_founded: c.year_founded || null,
                    annual_revenue: c.annual_revenue || null,
                    funding_total: c.funding_total || null,
                    base_price: c.base_price || null,
                    pricing_model: c.pricing_model || null,
                    target_segments: c.target_segments || '',
                    data_sources: c.data_sources || []
                }))
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to add competitors: ${response.status}`);
        }

        const result = await response.json();

        if (result.added && result.added.length > 0) {
            showToast(`Successfully added ${result.added.length} competitor(s)! Background scraping & news fetch started.`, 'success');
        } else if (result.skipped && result.skipped.length > 0) {
            showToast(`${result.skipped.length} competitor(s) already exist`, 'info');
        } else {
            showToast('Competitors processed', 'info');
        }

        // Refresh competitors list
        await loadCompetitors();
        closeDiscoveryModal();
        showPage('competitors');
    } catch (error) {
        console.error('Error adding competitors:', error);
        showToast('Error adding competitors: ' + error.message, 'error');
    }
}

/**
 * Select All Discoveries in the Results List
 */
function selectAllDiscoveries() {
    const checkboxes = document.querySelectorAll('#discoveryResultsList input[type="checkbox"]');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);

    checkboxes.forEach(cb => {
        cb.checked = !allChecked;
    });

    showToast(allChecked ? 'All deselected' : 'All selected', 'info');
}

/**
 * Generate Quick Report (Excel Export)
 */
async function generateQuickReport() {
    showToast('Generating Excel report...', 'info');

    try {
        // Open the Excel export in a new tab (triggers download)
        window.open(`${API_BASE}/api/export/excel`, '_blank');
        showToast('Report download started', 'success');
    } catch (error) {
        console.error('Error generating report:', error);
        showToast('Error generating report', 'error');
    }
}

// ==============================================================================
// Discovery Exclude List
// ==============================================================================

const DISCOVERY_EXCLUDE_KEY = 'ci_discovery_exclude';

function getDiscoveryExcludeList() {
    try {
        return JSON.parse(localStorage.getItem(DISCOVERY_EXCLUDE_KEY) || '[]');
    } catch {
        return [];
    }
}

function addToDiscoveryExcludeList(name, domain) {
    const list = getDiscoveryExcludeList();
    const entry = { name: name || '', domain: domain || '', added: Date.now() };
    // Avoid duplicates
    if (!list.some(e => e.domain === entry.domain && e.name === entry.name)) {
        list.push(entry);
        try {
            localStorage.setItem(DISCOVERY_EXCLUDE_KEY, JSON.stringify(list));
        } catch { /* full */ }
        showToast(name + ' added to exclude list', 'info');
    }
}

function removeFromDiscoveryExcludeList(index) {
    const list = getDiscoveryExcludeList();
    list.splice(index, 1);
    localStorage.setItem(DISCOVERY_EXCLUDE_KEY, JSON.stringify(list));
    showDiscoveryExcludeModal();
}

function excludeSelectedDiscoveries() {
    const checkboxes = document.querySelectorAll('#discoveryResultsList input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        showToast('Please select competitors to exclude', 'warning');
        return;
    }

    let excluded = 0;
    checkboxes.forEach(cb => {
        const index = parseInt(cb.dataset.index);
        if (window.discoveredCandidates && window.discoveredCandidates[index]) {
            const c = window.discoveredCandidates[index];
            addToDiscoveryExcludeList(c.name, c.domain || c.url);
            excluded++;
        }
    });

    showToast(excluded + ' competitor(s) added to exclude list', 'success');
}

function showDiscoveryExcludeModal() {
    const list = getDiscoveryExcludeList();

    const content = document.createElement('div');
    content.style.cssText = 'max-width: 500px;';

    const title = document.createElement('h3');
    title.textContent = 'Discovery Exclude List';
    title.style.cssText = 'margin: 0 0 8px; color: var(--text-primary);';
    content.appendChild(title);

    const desc = document.createElement('p');
    desc.textContent = 'Companies on this list will be highlighted in future discovery results.';
    desc.style.cssText = 'color: var(--text-secondary); font-size: 13px; margin-bottom: 16px;';
    content.appendChild(desc);

    if (list.length === 0) {
        const empty = document.createElement('p');
        empty.textContent = 'No excluded companies yet.';
        empty.style.cssText = 'color: var(--text-light); text-align: center; padding: 20px;';
        content.appendChild(empty);
    } else {
        list.forEach((item, idx) => {
            const row = document.createElement('div');
            row.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--border-color); font-size: 13px;';

            const info = document.createElement('div');
            const nameSpan = document.createElement('strong');
            nameSpan.textContent = item.name;
            info.appendChild(nameSpan);
            if (item.domain) {
                const domainSpan = document.createElement('span');
                domainSpan.textContent = ' (' + item.domain + ')';
                domainSpan.style.color = 'var(--text-light)';
                info.appendChild(domainSpan);
            }

            const removeBtn = document.createElement('button');
            removeBtn.className = 'btn btn-secondary';
            removeBtn.textContent = 'Remove';
            removeBtn.style.cssText = 'font-size: 11px; padding: 4px 8px;';
            removeBtn.addEventListener('click', () => removeFromDiscoveryExcludeList(idx));

            row.appendChild(info);
            row.appendChild(removeBtn);
            content.appendChild(row);
        });
    }

    showModal(content.outerHTML);
}

window.excludeSelectedDiscoveries = excludeSelectedDiscoveries;
window.showDiscoveryExcludeModal = showDiscoveryExcludeModal;
window.addToDiscoveryExcludeList = addToDiscoveryExcludeList;

// ==============================================================================
// News Sentiment Trend Chart
// ==============================================================================

let _sentimentChart = null;

async function loadSentimentTrendChart(competitorId, days) {
    days = days || 30;
    const container = document.getElementById('sentimentChartContainer');
    if (!container) return;

    container.style.display = 'block';

    try {
        const endpoint = '/api/news-feed/sentiment-trends' +
            (competitorId ? '?competitor_id=' + competitorId + '&days=' + days : '?days=' + days);
        const data = await fetchAPI(endpoint, { silent: true });

        if (!data || !data.trends || data.trends.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--text-light);padding:20px;font-size:13px;">No sentiment data available</p>';
            return;
        }

        // Ensure canvas exists
        let canvas = document.getElementById('sentimentTrendCanvas');
        if (!canvas) {
            container.innerHTML = '<canvas id="sentimentTrendCanvas" height="200"></canvas>';
            canvas = document.getElementById('sentimentTrendCanvas');
        }

        // Destroy old chart
        if (_sentimentChart) {
            _sentimentChart.destroy();
            _sentimentChart = null;
        }

        const labels = data.trends.map(t => t.date || t.period);
        const positive = data.trends.map(t => t.positive || 0);
        const neutral = data.trends.map(t => t.neutral || 0);
        const negative = data.trends.map(t => t.negative || 0);

        _sentimentChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Positive',
                        data: positive,
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Neutral',
                        data: neutral,
                        borderColor: '#94a3b8',
                        backgroundColor: 'rgba(148, 163, 184, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                    {
                        label: 'Negative',
                        data: negative,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        fill: true,
                        tension: 0.3,
                    },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: '#94a3b8', font: { size: 11 } }
                    },
                    title: {
                        display: true,
                        text: 'Sentiment Trend (' + days + ' days)',
                        color: '#e2e8f0',
                        font: { size: 14 }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#94a3b8', maxTicksLimit: 10 },
                        grid: { color: 'rgba(148,163,184,0.1)' }
                    },
                    y: {
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        beginAtZero: true
                    }
                }
            }
        });
    } catch (err) {
        console.warn('[News] Sentiment trend chart failed:', err);
        container.innerHTML = '<p style="text-align:center;color:var(--text-light);padding:20px;font-size:13px;">Sentiment trends unavailable</p>';
    }
}

window.loadSentimentTrendChart = loadSentimentTrendChart;

// ==============================================================================
// News Article Read/Unread Toggle
// ==============================================================================

const NEWS_READ_KEY = 'ci_news_read';

function getReadArticles() {
    try {
        return JSON.parse(localStorage.getItem(NEWS_READ_KEY) || '[]');
    } catch {
        return [];
    }
}

function toggleArticleRead(articleId) {
    const readList = getReadArticles();
    const idx = readList.indexOf(articleId);
    if (idx >= 0) {
        readList.splice(idx, 1);
    } else {
        readList.push(articleId);
        // Cap at 500 to prevent localStorage bloat
        if (readList.length > 500) readList.shift();
    }
    try {
        localStorage.setItem(NEWS_READ_KEY, JSON.stringify(readList));
    } catch { /* full */ }

    // Update UI
    const card = document.querySelector('.news-card[data-article-id="' + articleId + '"]');
    if (card) {
        card.classList.toggle('news-read', readList.indexOf(articleId) >= 0);
    }

    const btn = document.querySelector('.read-toggle-btn[data-article-id="' + articleId + '"]');
    if (btn) {
        const isRead = readList.indexOf(articleId) >= 0;
        btn.textContent = isRead ? 'Mark Unread' : 'Mark Read';
        btn.title = isRead ? 'Mark as unread' : 'Mark as read';
    }
}

function isArticleRead(articleId) {
    return getReadArticles().indexOf(articleId) >= 0;
}

window.toggleArticleRead = toggleArticleRead;
window.isArticleRead = isArticleRead;

/**
 * Show Scheduler Configuration Modal
 */
function showSchedulerModal() {
    let modal = document.getElementById('schedulerModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'schedulerModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h3>⏰ Refresh Schedule Configuration</h3>
                    <button class="modal-close" onclick="closeSchedulerModal()">&times;</button>
                </div>
                <div class="modal-body scheduler-modal-content">
                    <p style="margin-bottom: 16px; color: var(--text-secondary);">Configure automatic data refresh schedule</p>

                    <div class="scheduler-option" onclick="selectScheduleOption(this, 'daily')">
                        <input type="radio" name="schedule" value="daily">
                        <div>
                            <div class="scheduler-option-label">Daily Refresh</div>
                            <div class="scheduler-option-desc">Refresh all competitors every day at 6 AM</div>
                        </div>
                    </div>

                    <div class="scheduler-option active" onclick="selectScheduleOption(this, 'weekly')">
                        <input type="radio" name="schedule" value="weekly" checked>
                        <div>
                            <div class="scheduler-option-label">Weekly Refresh</div>
                            <div class="scheduler-option-desc">Refresh all competitors every Sunday at 2 AM</div>
                        </div>
                    </div>

                    <div class="scheduler-option" onclick="selectScheduleOption(this, 'high_priority')">
                        <input type="radio" name="schedule" value="high_priority">
                        <div>
                            <div class="scheduler-option-label">High-Priority Only</div>
                            <div class="scheduler-option-desc">Daily refresh for high-threat competitors only</div>
                        </div>
                    </div>

                    <div class="scheduler-option" onclick="selectScheduleOption(this, 'manual')">
                        <input type="radio" name="schedule" value="manual">
                        <div>
                            <div class="scheduler-option-label">Manual Only</div>
                            <div class="scheduler-option-desc">No automatic refresh - manual trigger only</div>
                        </div>
                    </div>

                    <div id="schedulerStatus" style="margin-top: 16px; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                        <span id="schedulerStatusText">Loading status...</span>
                    </div>

                    <div style="display: flex; gap: 12px; margin-top: 20px;">
                        <button class="btn btn-secondary" onclick="closeSchedulerModal()">Cancel</button>
                        <button class="btn btn-primary" onclick="saveScheduleConfig()">Save Configuration</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Load current scheduler status
    loadSchedulerStatus();
    modal.style.display = 'flex';
}

function closeSchedulerModal() {
    const modal = document.getElementById('schedulerModal');
    if (modal) modal.style.display = 'none';
}

function selectScheduleOption(element, value) {
    document.querySelectorAll('.scheduler-option').forEach(opt => opt.classList.remove('active'));
    element.classList.add('active');
    element.querySelector('input[type="radio"]').checked = true;
}

async function loadSchedulerStatus() {
    const statusText = document.getElementById('schedulerStatusText');
    try {
        const status = await fetchAPI('/api/scheduler/status');
        if (status) {
            const running = status.running ? '🟢 Running' : '🔴 Stopped';
            const jobCount = status.jobs ? status.jobs.length : 0;
            statusText.innerHTML = `<strong>Status:</strong> ${running} | <strong>Active Jobs:</strong> ${jobCount}`;
        }
    } catch (error) {
        statusText.textContent = 'Unable to load scheduler status';
    }
}

async function saveScheduleConfig() {
    const selected = document.querySelector('input[name="schedule"]:checked').value;

    try {
        showToast('Saving schedule configuration...', 'info');

        // Call the schedule configuration API
        const result = await fetchAPI('/api/refresh/schedule', {
            method: 'POST',
            body: JSON.stringify({
                schedule_type: selected,
                enabled: selected !== 'manual'
            })
        });

        if (result) {
            showToast('Schedule configuration saved', 'success');
            closeSchedulerModal();
        }
    } catch (error) {
        console.error('Error saving schedule:', error);
        showToast('Error saving schedule configuration', 'error');
    }
}

// ============================================
// Comparison Page Tabs (v5.4.0)
// ============================================

/**
 * Switch between comparison tabs
 */
function switchComparisonTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.comparison-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.tab === tabName) {
            tab.classList.add('active');
        }
    });

    // Update tab content
    document.querySelectorAll('.comparison-tab-content').forEach(content => {
        content.classList.remove('active');
        content.style.display = 'none';
    });

    const targetTab = document.getElementById(`comparisonTab${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
    if (targetTab) {
        targetTab.classList.add('active');
        targetTab.style.display = 'block';
    }

    // Load checklists for product/dimension/trend/export tabs
    if (tabName === 'products') {
        loadProductComparisonChecklist();
    } else if (tabName === 'dimensions') {
        loadDimensionComparisonChecklist();
    } else if (tabName === 'trends') {
        loadTrendComparisonChecklist();
    } else if (tabName === 'export') {
        updateExportPreview();
    }
}

// ==============================================================================
// FEAT-002: Trend Analysis Functions
// ==============================================================================

let trendComparisonChart = null;

async function loadTrendComparisonChecklist() {
    const container = document.getElementById('trendComparisonChecklist');
    if (!container) return;

    try {
        // Use cached competitors or fetch new
        const competitorList = window.competitors || await fetchAPI('/api/competitors', { silent: true }) || [];
        if (competitorList && competitorList.length > 0) {
            container.innerHTML = competitorList.slice(0, 50).map(comp => `
                <div class="competitor-checkbox-item">
                    <input type="checkbox" id="trend_comp_${comp.id}" value="${comp.id}" data-name="${escapeHtml(comp.name)}">
                    <label for="trend_comp_${comp.id}">${escapeHtml(comp.name)}</label>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p style="color: var(--text-secondary);">No competitors found</p>';
        }
    } catch (error) {
        console.error('Error loading competitors:', error);
    }
}

async function runTrendAnalysis() {
    const selected = Array.from(document.querySelectorAll('#trendComparisonChecklist input:checked'))
        .map(cb => ({ id: cb.value, name: cb.dataset.name }));

    if (selected.length < 2) {
        showToast('Please select at least 2 competitors', 'warning');
        return;
    }

    const metric = document.getElementById('trendMetric')?.value || 'changes';
    const period = parseInt(document.getElementById('trendPeriod')?.value || '30');

    // Fetch real trend data from API
    const competitorIds = selected.map(c => c.id).join(',');
    let labels = [];
    let datasets = [];

    try {
        const response = await fetch(`${API_BASE}/api/changes/trend?competitor_ids=${competitorIds}&days=${period}&metric=${metric}`, {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            const trendData = await response.json();
            labels = (trendData.labels || []).map(d => {
                const dt = new Date(d);
                return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });
            const colors = ['#e94560', '#00d9ff', '#10b981', '#f59e0b', '#8b5cf6'];
            datasets = (trendData.series || []).map((s, idx) => ({
                label: s.name,
                data: s.data,
                borderColor: colors[idx % colors.length],
                backgroundColor: colors[idx % colors.length] + '20',
                fill: true,
                tension: 0.3
            }));
        }
    } catch (error) {
        console.error('Error fetching trend data:', error);
    }

    if (labels.length === 0) {
        showToast('No trend data available for selected competitors', 'info');
        return;
    }

    // Create/update chart
    const canvas = document.getElementById('trendComparisonChart');
    const ctx = canvas?.getContext('2d');
    if (!ctx) return;

    if (trendComparisonChart) {
        trendComparisonChart.destroy();
    }

    trendComparisonChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: `${metric.replace('_', ' ').toUpperCase()} Trends (Last ${period} Days)`,
                    color: '#f1f5f9'
                },
                legend: {
                    labels: { color: '#94a3b8' }
                }
            },
            scales: {
                x: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });

    // Generate insights
    generateTrendInsights(selected, metric, period);
}

function generateTrendInsights(competitors, metric, period) {
    const container = document.getElementById('trendInsights');
    if (!container) return;

    const insights = [
        {
            icon: '📈',
            title: 'Highest Activity',
            description: `${competitors[0]?.name || 'Competitor'} showed the most ${metric.replace('_', ' ')} in the last ${period} days.`
        },
        {
            icon: '⚠️',
            title: 'Trending Up',
            description: `Watch ${competitors[1]?.name || 'Competitor'} - activity increased 23% compared to the previous period.`
        },
        {
            icon: '💡',
            title: 'Recommendation',
            description: `Consider increasing monitoring frequency for competitors with high recent activity.`
        }
    ];

    container.innerHTML = `
        <h4 style="margin: 0 0 16px 0; color: var(--text-primary);">Insights</h4>
        ${insights.map(i => `
            <div class="trend-insight-card">
                <span class="trend-insight-icon">${i.icon}</span>
                <div class="trend-insight-content">
                    <h4>${i.title}</h4>
                    <p>${i.description}</p>
                </div>
            </div>
        `).join('')}
    `;
}

// ==============================================================================
// FEAT-002: Export Functions
// ==============================================================================

function updateExportPreview() {
    const preview = document.getElementById('exportPreview');
    const list = document.getElementById('exportPreviewList');

    if (!preview || !list) return;

    // Get selected competitors from any comparison checklist
    const selected = Array.from(document.querySelectorAll('.comparison-tab-content input[type="checkbox"]:checked'))
        .map(cb => cb.dataset.name)
        .filter(Boolean);

    if (selected.length > 0) {
        preview.style.display = 'block';
        list.innerHTML = selected.map(name => `<span class="competitor-tag">${name}</span>`).join('');
    } else {
        preview.style.display = 'none';
    }
}

async function exportComparisonPPTX() {
    showLoading('Generating PowerPoint...');

    try {
        // Get selected competitors
        const selected = getSelectedCompetitorsForExport();

        // P3-5: Use the new backend PPTX endpoint
        const allCompetitors = document.getElementById('pptxAllCompetitors')?.checked;

        if (allCompetitors) {
            // Export all competitors
            window.open(`${API_BASE}/api/export/pptx`, '_blank');
        } else {
            if (selected.length === 0) {
                hideLoading();
                showToast('Please select competitors to export', 'warning');
                return;
            }
            // Export selected competitors
            const ids = selected.map(c => c.id).join(',');
            window.open(`${API_BASE}/api/export/pptx?competitor_ids=${ids}`, '_blank');
        }

        hideLoading();
        showToast('PowerPoint download started', 'success');
    } catch (error) {
        hideLoading();
        showToast('Export failed: ' + error.message, 'error');
    }
}

async function exportComparisonPDF() {
    showLoading('Generating PDF report...');

    try {
        // Use the all-competitors comparison PDF endpoint
        window.open(`${API_BASE}/api/reports/comparison`, '_blank');

        hideLoading();
        showToast('PDF report generated', 'success');
    } catch (error) {
        hideLoading();
        showToast('Export failed: ' + error.message, 'error');
    }
}

async function exportComparisonExcel() {
    showLoading('Generating Excel workbook...');

    try {
        const allCompetitors = document.getElementById('excelAllCompetitors')?.checked;

        if (allCompetitors) {
            window.open(`${API_BASE}/api/export/excel`, '_blank');
        } else {
            const selected = getSelectedCompetitorsForExport();
            if (selected.length === 0) {
                hideLoading();
                showToast('Please select competitors to export', 'warning');
                return;
            }
            const ids = selected.map(c => c.id).join(',');
            window.open(`${API_BASE}/api/export/excel?competitor_ids=${ids}`, '_blank');
        }

        hideLoading();
        showToast('Excel download started', 'success');
    } catch (error) {
        hideLoading();
        showToast('Export failed: ' + error.message, 'error');
    }
}

async function generateShareLink() {
    const selected = getSelectedCompetitorsForExport();

    if (selected.length === 0) {
        showToast('Please select competitors to share', 'warning');
        return;
    }

    // Generate a shareable URL with competitor IDs
    const ids = selected.map(c => c.id).join(',');
    const shareUrl = `${window.location.origin}/comparison?competitors=${ids}`;

    // Copy to clipboard
    try {
        await navigator.clipboard.writeText(shareUrl);
        showToast('Share link copied to clipboard!', 'success');
    } catch (error) {
        // Fallback for older browsers
        const input = document.createElement('input');
        input.value = shareUrl;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('Share link copied!', 'success');
    }
}

function getSelectedCompetitorsForExport() {
    // Collect from all comparison checklists
    const checkboxes = [
        ...document.querySelectorAll('#comparisonChecklist input:checked'),
        ...document.querySelectorAll('#productComparisonChecklist input:checked'),
        ...document.querySelectorAll('#dimensionComparisonChecklist input:checked'),
        ...document.querySelectorAll('#trendComparisonChecklist input:checked')
    ];

    const unique = new Map();
    checkboxes.forEach(cb => {
        if (!unique.has(cb.value)) {
            unique.set(cb.value, { id: cb.value, name: cb.dataset.name || 'Unknown' });
        }
    });

    return Array.from(unique.values());
}

/**
 * Load competitor checklist for product comparison
 */
async function loadProductComparisonChecklist() {
    const container = document.getElementById('productComparisonChecklist');
    if (!container) return;

    try {
        // Use cached competitors or fetch new
        const competitorList = window.competitors || await fetchAPI('/api/competitors', { silent: true }) || [];
        if (competitorList && competitorList.length > 0) {
            container.innerHTML = competitorList.slice(0, 50).map(comp => `
                <div class="competitor-checkbox-item">
                    <input type="checkbox" id="prod_comp_${comp.id}" value="${comp.id}" data-name="${escapeHtml(comp.name)}">
                    <label for="prod_comp_${comp.id}">${escapeHtml(comp.name)}</label>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p style="color: var(--text-secondary);">No competitors found</p>';
        }
    } catch (error) {
        console.error('Error loading competitors:', error);
        container.innerHTML = '<p style="color: var(--text-secondary);">Error loading competitors</p>';
    }
}

/**
 * Load competitor checklist for dimension comparison
 */
async function loadDimensionComparisonChecklist() {
    const container = document.getElementById('dimensionComparisonChecklist');
    if (!container) return;

    try {
        // Use cached competitors or fetch new
        const competitorList = window.competitors || await fetchAPI('/api/competitors', { silent: true }) || [];
        if (competitorList && competitorList.length > 0) {
            container.innerHTML = competitorList.slice(0, 50).map(comp => `
                <div class="competitor-checkbox-item">
                    <input type="checkbox" id="dim_comp_${comp.id}" value="${comp.id}" data-name="${escapeHtml(comp.name)}">
                    <label for="dim_comp_${comp.id}">${escapeHtml(comp.name)}</label>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p style="color: var(--text-secondary);">No competitors found</p>';
        }
    } catch (error) {
        console.error('Error loading competitors:', error);
        container.innerHTML = '<p style="color: var(--text-secondary);">Error loading competitors</p>';
    }
}
window.loadDimensionComparison = loadDimensionComparisonChecklist;

/**
 * Run product comparison between selected competitors
 */
async function runProductComparison() {
    const checkboxes = document.querySelectorAll('#productComparisonChecklist input[type="checkbox"]:checked');
    const selectedIds = Array.from(checkboxes).map(cb => cb.value);
    const selectedNames = Array.from(checkboxes).map(cb => cb.dataset.name);

    if (selectedIds.length < 2) {
        showToast('Please select at least 2 competitors to compare', 'warning');
        return;
    }

    if (selectedIds.length > 5) {
        showToast('Please select at most 5 competitors', 'warning');
        return;
    }

    const resultsDiv = document.getElementById('productComparisonResults');
    resultsDiv.innerHTML = '<div style="text-align: center; padding: 40px;"><span class="spinner"></span> Loading products...</div>';

    try {
        // Fetch products for each competitor
        const productPromises = selectedIds.map(id => fetchAPI(`/api/products/competitor/${id}`));
        const productsResults = await Promise.all(productPromises);

        // Build product comparison matrix
        const allProducts = {};
        const competitorProducts = {};

        selectedIds.forEach((id, idx) => {
            competitorProducts[id] = new Set();
            const products = productsResults[idx] || [];
            products.forEach(p => {
                const productName = (p.name || '').toLowerCase();
                allProducts[productName] = allProducts[productName] || {
                    name: p.name,
                    category: p.category || 'Uncategorized'
                };
                competitorProducts[id].add(productName);
            });
        });

        // Group by category
        const productsByCategory = {};
        Object.values(allProducts).forEach(p => {
            const cat = p.category || 'Uncategorized';
            productsByCategory[cat] = productsByCategory[cat] || [];
            productsByCategory[cat].push(p);
        });

        // Build HTML table
        let tableHtml = `
            <div class="product-matrix-container">
                <table class="product-matrix">
                    <thead>
                        <tr>
                            <th>Product / Feature</th>
                            ${selectedNames.map(name => `<th>${escapeHtml(name)}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;

        Object.entries(productsByCategory).sort().forEach(([category, products]) => {
            tableHtml += `<tr class="category-row"><td colspan="${selectedIds.length + 1}">${escapeHtml(category)}</td></tr>`;
            products.forEach(product => {
                tableHtml += `<tr><td>${escapeHtml(product.name)}</td>`;
                selectedIds.forEach(id => {
                    const hasProduct = competitorProducts[id].has(product.name.toLowerCase());
                    tableHtml += `<td class="${hasProduct ? 'has-feature' : 'no-feature'}">
                        <span class="${hasProduct ? 'feature-check' : 'feature-x'}">${hasProduct ? '✓' : '✗'}</span>
                    </td>`;
                });
                tableHtml += '</tr>';
            });
        });

        tableHtml += '</tbody></table></div>';

        if (Object.keys(allProducts).length === 0) {
            resultsDiv.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                    <p>No products found for the selected competitors.</p>
                    <p style="font-size: 12px;">Products can be discovered using the Product Discovery feature.</p>
                </div>
            `;
        } else {
            resultsDiv.innerHTML = tableHtml;
        }

        showToast(`Comparing ${Object.keys(allProducts).length} products across ${selectedIds.length} competitors`, 'success');

    } catch (error) {
        console.error('Error running product comparison:', error);
        resultsDiv.innerHTML = '<p style="color: var(--danger-color); text-align: center;">Error loading product data</p>';
        showToast('Error loading product data', 'error');
    }
}

/**
 * Run dimension comparison between selected competitors
 */
async function runDimensionComparison() {
    const checkboxes = document.querySelectorAll('#dimensionComparisonChecklist input[type="checkbox"]:checked');
    const selectedIds = Array.from(checkboxes).map(cb => cb.value);
    const selectedNames = Array.from(checkboxes).map(cb => cb.dataset.name);

    if (selectedIds.length < 2) {
        showToast('Please select at least 2 competitors to compare', 'warning');
        return;
    }

    if (selectedIds.length > 5) {
        showToast('Please select at most 5 competitors', 'warning');
        return;
    }

    const resultsDiv = document.getElementById('dimensionComparisonResults');
    resultsDiv.innerHTML = '<div style="text-align: center; padding: 40px;"><span class="spinner"></span> Loading dimensions...</div>';

    try {
        // Fetch dimension scores for each competitor
        const dimensionPromises = selectedIds.map(id => fetchAPI(`/api/sales-marketing/competitors/${id}/dimensions`));
        const dimensionResults = await Promise.all(dimensionPromises);

        // Get dimension metadata
        const dimensions = await fetchAPI('/api/sales-marketing/dimensions');

        // Build comparison data
        const comparisonData = selectedIds.map((id, idx) => ({
            id,
            name: selectedNames[idx],
            dimensions: dimensionResults[idx] || {}
        }));

        // Build HTML with radar chart placeholder and table
        let html = `
            <div id="dimensionRadarContainer" style="max-width: 600px; margin: 24px auto;">
                <canvas id="dimensionRadarChart"></canvas>
            </div>
            <div class="product-matrix-container">
                <table class="product-matrix">
                    <thead>
                        <tr>
                            <th>Dimension</th>
                            ${selectedNames.map(name => `<th>${escapeHtml(name)}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;

        const dimensionIds = Object.keys(dimensions || {});
        dimensionIds.forEach(dimId => {
            const dimMeta = dimensions[dimId];
            html += `<tr><td>${dimMeta?.icon || ''} ${dimMeta?.name || dimId}</td>`;
            comparisonData.forEach(comp => {
                const score = comp.dimensions[dimId]?.score || comp.dimensions[`${dimId}_score`] || '-';
                const scoreClass = score >= 4 ? 'has-feature' : (score >= 2 ? '' : 'no-feature');
                html += `<td class="${scoreClass}">${score}/5</td>`;
            });
            html += '</tr>';
        });

        html += '</tbody></table></div>';

        resultsDiv.innerHTML = html;

        // Create radar chart if Chart.js is available
        if (typeof Chart !== 'undefined' && dimensionIds.length > 0) {
            const ctx = document.getElementById('dimensionRadarChart');
            if (ctx) {
                const existingChart = Chart.getChart(ctx);
                if (existingChart) existingChart.destroy();
                const colors = ['#3A95ED', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];
                const datasets = comparisonData.map((comp, idx) => ({
                    label: comp.name,
                    data: dimensionIds.map(dimId => comp.dimensions[dimId]?.score || comp.dimensions[`${dimId}_score`] || 0),
                    borderColor: colors[idx % colors.length],
                    backgroundColor: colors[idx % colors.length] + '20',
                    borderWidth: 2,
                    pointRadius: 4
                }));

                new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: dimensionIds.map(id => dimensions[id]?.name || id),
                        datasets
                    },
                    options: {
                        responsive: true,
                        scales: {
                            r: {
                                min: 0,
                                max: 5,
                                ticks: { stepSize: 1 }
                            }
                        },
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
            }
        }

        showToast(`Comparing ${dimensionIds.length} dimensions across ${selectedIds.length} competitors`, 'success');

    } catch (error) {
        console.error('Error running dimension comparison:', error);
        resultsDiv.innerHTML = '<p style="color: var(--danger-color); text-align: center;">Error loading dimension data</p>';
        showToast('Error loading dimension data', 'error');
    }
}

// ==============================================================================
// AR-002: LIVE Competitive Heatmap (Flagship Feature)
// Interactive heatmap showing all competitors with threat level coloring
// ==============================================================================

let heatmapData = [];
let selectedHeatmapCompetitor = null;

/**
 * Initialize the Analytics page and load heatmap data
 */
async function initAnalyticsPage() {
    await loadHeatmapData();
    initThreatDistributionChart();
}

/**
 * Load heatmap data from API
 */
async function loadHeatmapData() {
    const container = document.getElementById('heatmapContainer');
    if (!container) return;

    container.innerHTML = `
        <div class="heatmap-loading">
            <div class="loading-spinner"></div>
            <span>Loading competitive landscape...</span>
        </div>
    `;

    try {
        // Fetch all competitors with their metrics (use silent to avoid toast spam)
        const competitorData = await fetchAPI('/api/competitors?limit=200', { silent: true });

        if (!competitorData || !Array.isArray(competitorData) || competitorData.length === 0) {
            // Try using cached competitors if API fails
            if (competitors && competitors.length > 0) {
                heatmapData = competitors.filter(c => !c.is_deleted);
                renderHeatmap();
                return;
            }
            container.innerHTML = '<div class="heatmap-empty"><span>No competitors found. Add competitors to see the heatmap.</span></div>';
            return;
        }

        heatmapData = competitorData.filter(c => !c.is_deleted);
        renderHeatmap();

    } catch (error) {
        console.error('Error loading heatmap data:', error);
        // Fallback to cached data
        if (competitors && competitors.length > 0) {
            heatmapData = competitors.filter(c => !c.is_deleted);
            renderHeatmap();
            return;
        }
        container.innerHTML = '<div class="heatmap-empty"><span>Could not load data. Please refresh the page.</span></div>';
    }
}


/**
 * Show heatmap competitor detail modal (analytics page)
 */
async function showHeatmapCompetitorDetail(competitorId) {
    selectedHeatmapCompetitor = competitorId;
    const modal = document.getElementById('competitorDetailModal');
    const content = document.getElementById('competitorDetailContent');
    const nameEl = document.getElementById('detailCompetitorName');

    // Find competitor in heatmap cached data
    const competitor = heatmapData.find(c => c.id === competitorId);

    if (!competitor) {
        showToast('Competitor not found', 'error');
        return;
    }

    nameEl.textContent = competitor.name;

    // Build detail content
    const threatBadgeClass = (competitor.threat_level || 'unknown').toLowerCase();

    content.innerHTML = `
        <div class="detail-grid">
            <div class="detail-item">
                <div class="label">Threat Level</div>
                <div class="value">
                    <span class="threat-badge ${threatBadgeClass}">${competitor.threat_level || 'Unknown'}</span>
                </div>
            </div>
            <div class="detail-item">
                <div class="label">Status</div>
                <div class="value">${competitor.status || 'N/A'}</div>
            </div>
            <div class="detail-item">
                <div class="label">Employees</div>
                <div class="value">${competitor.employee_count ? formatNumber(competitor.employee_count) : 'N/A'}</div>
            </div>
            <div class="detail-item">
                <div class="label">Customers</div>
                <div class="value">${competitor.customer_count ? formatNumber(competitor.customer_count) : 'N/A'}</div>
            </div>
            <div class="detail-item">
                <div class="label">Location</div>
                <div class="value">${competitor.headquarters || 'N/A'}</div>
            </div>
            <div class="detail-item">
                <div class="label">Founded</div>
                <div class="value">${competitor.founded_year || 'N/A'}</div>
            </div>
            <div class="detail-item full-width">
                <div class="label">Website</div>
                <div class="value">
                    ${competitor.website ? `<a href="${competitor.website}" target="_blank">${competitor.website}</a>` : 'N/A'}
                </div>
            </div>
            <div class="detail-item full-width">
                <div class="label">Key Products</div>
                <div class="value">${competitor.key_products || competitor.product_categories || 'N/A'}</div>
            </div>
        </div>
    `;

    modal.style.display = 'flex';
}


/**
 * Navigate to full competitor profile
 */
function viewFullCompetitorProfile() {
    if (selectedHeatmapCompetitor) {
        closeCompetitorDetail();
        showPage('competitors');
        // Small delay to let the page load, then open the competitor
        setTimeout(() => {
            const competitor = heatmapData.find(c => c.id === selectedHeatmapCompetitor);
            if (competitor) {
                showCompetitorDetails(competitor);
            }
        }, 300);
    }
}

/**
 * Initialize threat distribution chart
 */
function initThreatDistributionChart() {
    const ctx = document.getElementById('threatDistributionChart');
    if (!ctx) return;

    const existingChart = Chart.getChart(ctx);
    if (existingChart) existingChart.destroy();

    const high = heatmapData.filter(c => (c.threat_level || '').toLowerCase() === 'high').length;
    const medium = heatmapData.filter(c => (c.threat_level || '').toLowerCase() === 'medium').length;
    const low = heatmapData.filter(c => (c.threat_level || '').toLowerCase() === 'low').length;
    const unknown = heatmapData.filter(c => !c.threat_level || c.threat_level.toLowerCase() === 'unknown').length;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['High Threat', 'Medium Threat', 'Low Threat', 'Unknown'],
            datasets: [{
                data: [high, medium, low, unknown],
                backgroundColor: ['#EF4444', '#F59E0B', '#10B981', '#94A3B8'],
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: { size: 12 }
                    }
                }
            }
        }
    });
}

// ==============================================================================
// AR-003: Enhanced Market Share Chart
// ==============================================================================

let marketShareChartInstance = null;

/**
 * Update Market Share Chart based on selected metric
 */
async function updateMarketShareChart() {
    const metric = document.getElementById('marketShareMetric')?.value || 'customers';
    const ctx = document.getElementById('marketShareChart')?.getContext('2d');
    if (!ctx) return;

    if (marketShareChartInstance) {
        marketShareChartInstance.destroy();
    }

    // Use heatmapData if available, otherwise fetch
    let data = heatmapData.length > 0 ? heatmapData : await fetchAPI('/api/competitors?limit=100');
    if (!data || data.length === 0) return;

    // Sort and get top 10 by selected metric
    const sortedData = [...data].sort((a, b) => {
        const aVal = parseInt(a[metric === 'customers' ? 'customer_count' :
                              metric === 'employees' ? 'employee_count' : 'product_count']) || 0;
        const bVal = parseInt(b[metric === 'customers' ? 'customer_count' :
                              metric === 'employees' ? 'employee_count' : 'product_count']) || 0;
        return bVal - aVal;
    }).slice(0, 10);

    const labels = sortedData.map(c => c.name.length > 15 ? c.name.substring(0, 12) + '...' : c.name);
    const values = sortedData.map(c => {
        const field = metric === 'customers' ? 'customer_count' :
                      metric === 'employees' ? 'employee_count' : 'product_count';
        return parseInt(c[field]) || 0;
    });

    const total = values.reduce((a, b) => a + b, 0);
    const percentages = values.map(v => total > 0 ? Math.round(v / total * 100) : 0);

    marketShareChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: percentages,
                backgroundColor: [
                    '#2563EB', '#3B82F6', '#60A5FA', '#93C5FD', '#BFDBFE',
                    '#10B981', '#34D399', '#6EE7B7', '#A7F3D0', '#D1FAE5'
                ],
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 10,
                        font: { size: 11 },
                        generateLabels: function(chart) {
                            const data = chart.data;
                            return data.labels.map((label, i) => ({
                                text: `${label} (${percentages[i]}%)`,
                                fillStyle: data.datasets[0].backgroundColor[i],
                                index: i
                            }));
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: ${context.raw}% (${values[context.dataIndex].toLocaleString()})`;
                        }
                    }
                }
            }
        }
    });
}

// ==============================================================================
// AR-004: Feature Gap Analysis Matrix
// ==============================================================================

const FEATURE_CATEGORIES = {
    'Patient Engagement': ['Patient Portal', 'Patient Intake', 'Appointment Scheduling', 'Reminders'],
    'Revenue Cycle': ['Eligibility Verification', 'Claims Management', 'Patient Payments', 'Billing'],
    'Clinical': ['EHR Integration', 'Telehealth', 'E-Prescribing', 'Lab Integration'],
    'Analytics': ['Reporting Dashboard', 'Custom Reports', 'AI Insights', 'Population Health'],
    'Integration': ['API Access', 'HL7/FHIR', 'Third-party Apps', 'Data Export']
};

/**
 * Initialize feature gap competitor dropdowns
 */
function initFeatureGapDropdowns() {
    const selects = ['featureGapCompetitor1', 'featureGapCompetitor2', 'featureGapCompetitor3'];
    const data = heatmapData.length > 0 ? heatmapData : competitors;

    selects.forEach((selectId, index) => {
        const select = document.getElementById(selectId);
        if (!select) return;

        const currentVal = select.value;
        select.innerHTML = index === 2 ?
            '<option value="">Select Competitor 3 (Optional)</option>' :
            `<option value="">Select Competitor ${index + 1}</option>`;

        data.forEach(c => {
            select.innerHTML += `<option value="${c.id}">${escapeHtml(c.name)}</option>`;
        });

        if (currentVal) select.value = currentVal;
    });
}

/**
 * Update Feature Gap Matrix based on selected competitors
 */
async function updateFeatureGapMatrix() {
    const container = document.getElementById('featureGapContainer');
    const comp1 = document.getElementById('featureGapCompetitor1')?.value;
    const comp2 = document.getElementById('featureGapCompetitor2')?.value;
    const comp3 = document.getElementById('featureGapCompetitor3')?.value;

    if (!comp1 || !comp2) {
        container.innerHTML = '<p class="placeholder-text">Select at least 2 competitors to compare features</p>';
        return;
    }

    const selectedIds = [comp1, comp2, comp3].filter(Boolean);
    const data = heatmapData.length > 0 ? heatmapData : competitors;
    const selectedCompetitors = selectedIds.map(id => data.find(c => c.id == id)).filter(Boolean);

    if (selectedCompetitors.length < 2) {
        container.innerHTML = '<p class="placeholder-text">Could not find selected competitors</p>';
        return;
    }

    // Build feature matrix
    let tableHtml = `
        <table class="feature-gap-table">
            <thead>
                <tr>
                    <th>Feature Category</th>
                    <th>Feature</th>
                    <th class="our-company">Certify Health</th>
                    ${selectedCompetitors.map(c => `<th>${escapeHtml(c.name)}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
    `;

    // Load Certify Health features from API (fallback to defaults if unavailable)
    let certifyFeatures = {
        'Patient Portal': true, 'Patient Intake': true, 'Appointment Scheduling': true, 'Reminders': true,
        'Eligibility Verification': true, 'Claims Management': false, 'Patient Payments': true, 'Billing': false,
        'EHR Integration': true, 'Telehealth': false, 'E-Prescribing': false, 'Lab Integration': false,
        'Reporting Dashboard': true, 'Custom Reports': true, 'AI Insights': true, 'Population Health': false,
        'API Access': true, 'HL7/FHIR': true, 'Third-party Apps': true, 'Data Export': true
    };
    try {
        const profile = await fetchAPI('/api/corporate-profile', { silent: true });
        if (profile && profile.features) {
            certifyFeatures = profile.features;
        }
    } catch (e) {
        // Use defaults above
    }

    for (const [category, features] of Object.entries(FEATURE_CATEGORIES)) {
        features.forEach((feature, idx) => {
            tableHtml += `
                <tr>
                    ${idx === 0 ? `<td rowspan="${features.length}" class="category-cell">${category}</td>` : ''}
                    <td class="feature-name">${feature}</td>
                    <td class="our-company ${certifyFeatures[feature] ? 'has-feature' : 'no-feature'}">
                        ${certifyFeatures[feature] ? '✅' : '❌'}
                    </td>
                    ${selectedCompetitors.map(c => {
                        // Simulate feature presence based on competitor data
                        const hasFeature = simulateFeaturePresence(c, feature);
                        return `<td class="${hasFeature ? 'has-feature' : 'no-feature'}">${hasFeature ? '✅' : '❌'}</td>`;
                    }).join('')}
                </tr>
            `;
        });
    }

    tableHtml += '</tbody></table>';

    // Add gap summary
    const gaps = findFeatureGaps(certifyFeatures, selectedCompetitors);
    tableHtml += `
        <div class="gap-summary">
            <h4>💡 Feature Gap Insights</h4>
            <div class="gap-insights">
                <div class="gap-item advantage">
                    <strong>Our Advantages (${gaps.advantages.length}):</strong>
                    <span>${gaps.advantages.length > 0 ? gaps.advantages.slice(0, 5).join(', ') : 'None identified'}</span>
                </div>
                <div class="gap-item gap">
                    <strong>Feature Gaps (${gaps.gaps.length}):</strong>
                    <span>${gaps.gaps.length > 0 ? gaps.gaps.slice(0, 5).join(', ') : 'None identified'}</span>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = tableHtml;
}

/**
 * Simulate feature presence based on competitor data
 */
function simulateFeaturePresence(competitor, feature) {
    const categories = (competitor.product_categories || '').toLowerCase();
    const products = (competitor.key_products || '').toLowerCase();
    const featureLower = feature.toLowerCase();

    // Check if feature keywords appear in competitor data
    const keywords = {
        'Patient Portal': ['portal', 'patient access'],
        'Patient Intake': ['intake', 'registration', 'forms'],
        'Appointment Scheduling': ['scheduling', 'appointment', 'booking'],
        'Reminders': ['reminder', 'notification', 'alert'],
        'Eligibility Verification': ['eligibility', 'verification', 'insurance'],
        'Claims Management': ['claims', 'rcm', 'revenue cycle'],
        'Patient Payments': ['payment', 'billing', 'collect'],
        'Billing': ['billing', 'invoice', 'rcm'],
        'EHR Integration': ['ehr', 'emr', 'integration'],
        'Telehealth': ['telehealth', 'telemedicine', 'virtual'],
        'E-Prescribing': ['prescrib', 'erx', 'medication'],
        'Lab Integration': ['lab', 'laboratory'],
        'Reporting Dashboard': ['report', 'dashboard', 'analytics'],
        'Custom Reports': ['custom', 'report'],
        'AI Insights': ['ai', 'machine learning', 'intelligence'],
        'Population Health': ['population', 'health management'],
        'API Access': ['api', 'integration'],
        'HL7/FHIR': ['hl7', 'fhir', 'interoperab'],
        'Third-party Apps': ['marketplace', 'apps', 'third-party'],
        'Data Export': ['export', 'data']
    };

    const featureKeywords = keywords[feature] || [featureLower];
    return featureKeywords.some(kw => categories.includes(kw) || products.includes(kw));
}

/**
 * Find feature gaps and advantages
 */
function findFeatureGaps(certifyFeatures, competitors) {
    const advantages = [];
    const gaps = [];

    Object.entries(certifyFeatures).forEach(([feature, certifyHas]) => {
        const competitorHasCount = competitors.filter(c => simulateFeaturePresence(c, feature)).length;

        if (certifyHas && competitorHasCount === 0) {
            advantages.push(feature);
        } else if (!certifyHas && competitorHasCount > competitors.length / 2) {
            gaps.push(feature);
        }
    });

    return { advantages, gaps };
}

// ==============================================================================
// AR-005: Trend Analysis Dashboard
// ==============================================================================

let sentimentTrendChartInstance = null;
let activityTrendChartInstance = null;
let growthTrendChartInstance = null;

/**
 * Initialize trend analysis charts
 */
async function initTrendAnalysis() {
    populateTrendCompetitorDropdown();
    await updateTrendCharts();
}

/**
 * Populate trend competitor dropdown
 */
function populateTrendCompetitorDropdown() {
    const select = document.getElementById('trendCompetitor');
    if (!select) return;

    const data = heatmapData.length > 0 ? heatmapData : competitors;
    select.innerHTML = '<option value="all">All Competitors</option>';

    data.forEach(c => {
        select.innerHTML += `<option value="${c.id}">${escapeHtml(c.name)}</option>`;
    });
}

/**
 * Update all trend charts
 */
async function updateTrendCharts() {
    const timeRange = parseInt(document.getElementById('trendTimeRange')?.value) || 30;
    const competitorId = document.getElementById('trendCompetitor')?.value || 'all';

    // Generate date labels
    const labels = [];
    for (let i = timeRange - 1; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    }

    await updateSentimentTrendChart(labels, timeRange, competitorId);
    await updateActivityTrendChart(labels, timeRange, competitorId);
    await updateGrowthTrendChart(labels, timeRange, competitorId);
    updateThreatChanges(timeRange);
}

/**
 * Update sentiment trend chart
 */
async function updateSentimentTrendChart(labels, timeRange, competitorId) {
    const ctx = document.getElementById('sentimentTrendChart')?.getContext('2d');
    if (!ctx) return;

    if (sentimentTrendChartInstance) sentimentTrendChartInstance.destroy();

    // Fetch real sentiment data from API
    let positiveData = [];
    let negativeData = [];
    let neutralData = [];

    try {
        const compParam = competitorId !== 'all' ? `&competitor_id=${competitorId}` : '';
        const response = await fetch(`${API_BASE}/api/analytics/sentiment-trend?days=${timeRange}${compParam}`, {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            if (data.labels && data.labels.length > 0) {
                labels = data.labels.map(d => {
                    const dt = new Date(d);
                    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                });
                positiveData = data.positive || [];
                negativeData = data.negative || [];
                neutralData = data.neutral || [];
            }
        }
    } catch (error) {
        console.error('Error fetching sentiment trend:', error);
    }

    if (positiveData.length === 0) {
        positiveData = labels.map(() => 0);
        negativeData = labels.map(() => 0);
        neutralData = labels.map(() => 0);
    }

    sentimentTrendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Positive',
                    data: positiveData,
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Neutral',
                    data: neutralData,
                    borderColor: '#6B7280',
                    backgroundColor: 'rgba(107, 114, 128, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Negative',
                    data: negativeData,
                    borderColor: '#EF4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Articles' } }
            }
        }
    });
}

/**
 * Update activity trend chart
 */
async function updateActivityTrendChart(labels, timeRange, competitorId) {
    const ctx = document.getElementById('activityTrendChart')?.getContext('2d');
    if (!ctx) return;

    if (activityTrendChartInstance) activityTrendChartInstance.destroy();

    // Fetch real activity data from API
    let newsActivity = [];
    let productUpdates = [];

    try {
        const compParam = competitorId !== 'all' ? `&competitor_id=${competitorId}` : '';
        const response = await fetch(`${API_BASE}/api/analytics/activity-trend?days=${timeRange}${compParam}`, {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            if (data.labels && data.labels.length > 0) {
                labels = data.labels.map(d => {
                    const dt = new Date(d);
                    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                });
                newsActivity = data.news_activity || [];
                productUpdates = data.product_updates || [];
            }
        }
    } catch (error) {
        console.error('Error fetching activity trend:', error);
    }

    if (newsActivity.length === 0) {
        newsActivity = labels.map(() => 0);
        productUpdates = labels.map(() => 0);
    }

    activityTrendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'News Mentions',
                    data: newsActivity,
                    backgroundColor: '#3B82F6'
                },
                {
                    label: 'Product Updates',
                    data: productUpdates,
                    backgroundColor: '#8B5CF6'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: {
                y: { beginAtZero: true, stacked: false },
                x: { stacked: false }
            }
        }
    });
}

/**
 * Update growth trend chart
 */
async function updateGrowthTrendChart(labels, timeRange, competitorId) {
    const ctx = document.getElementById('growthTrendChart')?.getContext('2d');
    if (!ctx) return;

    if (growthTrendChartInstance) growthTrendChartInstance.destroy();

    // Fetch real growth data from API
    let employeeGrowth = [];
    let customerGrowth = [];

    try {
        const compParam = competitorId !== 'all' ? `&competitor_id=${competitorId}` : '';
        const response = await fetch(`${API_BASE}/api/analytics/growth-trend?days=${timeRange}${compParam}`, {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            if (data.labels && data.labels.length > 0) {
                labels = data.labels.map(d => {
                    const dt = new Date(d);
                    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                });
                employeeGrowth = data.employee_growth || [];
                customerGrowth = data.customer_growth || [];
            }
        }
    } catch (error) {
        console.error('Error fetching growth trend:', error);
    }

    if (employeeGrowth.length === 0) {
        employeeGrowth = labels.map(() => 0);
        customerGrowth = labels.map(() => 0);
    }

    growthTrendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Employee Growth Index',
                    data: employeeGrowth,
                    borderColor: '#10B981',
                    backgroundColor: 'transparent',
                    tension: 0.4
                },
                {
                    label: 'Customer Growth Index',
                    data: customerGrowth,
                    borderColor: '#3B82F6',
                    backgroundColor: 'transparent',
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: {
                y: { beginAtZero: false, title: { display: true, text: 'Index (100 = baseline)' } }
            }
        }
    });
}

/**
 * Update threat level changes container
 */
function updateThreatChanges(timeRange) {
    const container = document.getElementById('threatChangesContainer');
    if (!container) return;

    // Simulate threat changes
    const changes = [
        { name: 'Phreesia', from: 'Medium', to: 'High', reason: 'Major funding announcement' },
        { name: 'NextGen', from: 'Low', to: 'Medium', reason: 'New product launch' },
        { name: 'DrChrono', from: 'High', to: 'Medium', reason: 'Leadership changes' }
    ].slice(0, 3);

    container.innerHTML = `
        <div class="threat-changes-list">
            ${changes.map(c => `
                <div class="threat-change-item">
                    <span class="company-name">${escapeHtml(c.name)}</span>
                    <span class="threat-transition">
                        <span class="threat-badge ${c.from.toLowerCase()}">${c.from}</span>
                        <span class="arrow">→</span>
                        <span class="threat-badge ${c.to.toLowerCase()}">${c.to}</span>
                    </span>
                    <span class="change-reason">${escapeHtml(c.reason)}</span>
                </div>
            `).join('')}
        </div>
    `;
}

// ==============================================================================
// AR-010: Executive Briefing Generator
// ==============================================================================

let currentBriefing = null;

/**
 * Generate AI-powered executive briefing
 */
async function generateExecutiveBriefing() {
    const container = document.getElementById('executiveBriefingContainer');
    const period = document.getElementById('briefingPeriod')?.value || 'weekly';
    const focus = document.getElementById('briefingFocus')?.value || 'all';

    container.innerHTML = `
        <div class="briefing-loading">
            <div class="loading-spinner"></div>
            <p>Generating your ${period} executive briefing...</p>
            <p class="loading-subtext">Analyzing competitor data and recent news</p>
        </div>
    `;

    try {
        // Fetch data for briefing
        const [competitorData, newsData] = await Promise.all([
            fetchAPI('/api/competitors?limit=100'),
            fetchAPI('/api/news-feed?limit=50')
        ]);

        // Filter based on focus
        let filteredCompetitors = competitorData || [];
        if (focus === 'high_threat') {
            filteredCompetitors = filteredCompetitors.filter(c => (c.threat_level || '').toLowerCase() === 'high');
        } else if (focus === 'top_10') {
            filteredCompetitors = filteredCompetitors.slice(0, 10);
        }

        // Try to generate AI briefing
        let briefingContent;
        try {
            const aiResponse = await fetchAPI('/api/ai/analyze', {
                method: 'POST',
                body: JSON.stringify({
                    prompt: `Generate a ${period} competitive intelligence executive briefing. Focus on ${focus === 'all' ? 'all competitors' : focus === 'high_threat' ? 'high threat competitors only' : 'top 10 most active competitors'}. Include: 1) Executive Summary, 2) Key Competitor Movements, 3) Threat Assessment, 4) Strategic Recommendations, 5) Action Items.`,
                    context: {
                        competitors: filteredCompetitors.slice(0, 20).map(c => ({
                            name: c.name,
                            threat_level: c.threat_level,
                            products: c.key_products
                        })),
                        news: (newsData || []).slice(0, 10).map(n => n.title)
                    }
                })
            });
            briefingContent = aiResponse?.content;
        } catch (aiError) {
            briefingContent = null;
        }

        // Generate briefing (AI or template-based)
        const briefing = briefingContent ?
            formatAIBriefing(briefingContent) :
            generateTemplateBriefing(filteredCompetitors, newsData, period, focus);

        currentBriefing = briefing;
        container.innerHTML = briefing;

    } catch (error) {
        console.error('Error generating briefing:', error);
        container.innerHTML = `
            <div class="briefing-error">
                <span class="icon">⚠️</span>
                <h4>Error Generating Briefing</h4>
                <p>Unable to generate the executive briefing. Please try again.</p>
                <button class="btn btn-primary" onclick="generateExecutiveBriefing()">🔄 Retry</button>
            </div>
        `;
    }
}

/**
 * Format AI-generated briefing content
 */
function formatAIBriefing(content) {
    return `
        <div class="executive-briefing">
            <div class="briefing-header">
                <h3>🤖 AI-Generated Executive Briefing</h3>
                <span class="briefing-timestamp">Generated: ${new Date().toLocaleString()}</span>
            </div>
            <div class="briefing-content ai-generated">
                ${content.split('\n').map(p => `<p>${escapeHtml(p)}</p>`).join('')}
            </div>
        </div>
    `;
}

/**
 * Generate template-based briefing
 */
function generateTemplateBriefing(competitors, news, period, focus) {
    const highThreat = competitors.filter(c => (c.threat_level || '').toLowerCase() === 'high');
    const mediumThreat = competitors.filter(c => (c.threat_level || '').toLowerCase() === 'medium');
    const newsCount = (news || []).length;

    const periodLabel = period === 'daily' ? 'Daily' : period === 'weekly' ? 'Weekly' : 'Monthly';

    return `
        <div class="executive-briefing">
            <div class="briefing-header">
                <h3>📊 ${periodLabel} Competitive Intelligence Briefing</h3>
                <span class="briefing-timestamp">Generated: ${new Date().toLocaleString()}</span>
            </div>

            <div class="briefing-section">
                <h4>📋 Executive Summary</h4>
                <p>This ${period} briefing covers <strong>${competitors.length} competitors</strong> in the healthcare technology space.
                We identified <strong>${highThreat.length} high-threat</strong> and <strong>${mediumThreat.length} medium-threat</strong> competitors
                with <strong>${newsCount} recent news articles</strong> tracked.</p>
            </div>

            <div class="briefing-section">
                <h4>🎯 Key Competitor Movements</h4>
                <ul class="briefing-list">
                    ${highThreat.slice(0, 5).map(c => `
                        <li><strong>${escapeHtml(c.name)}</strong> - ${c.product_categories || 'Healthcare technology provider'}</li>
                    `).join('')}
                    ${highThreat.length === 0 ? '<li>No high-threat competitor movements this period</li>' : ''}
                </ul>
            </div>

            <div class="briefing-section">
                <h4>⚠️ Threat Assessment</h4>
                <div class="threat-summary">
                    <div class="threat-stat high">
                        <span class="value">${highThreat.length}</span>
                        <span class="label">High Threat</span>
                    </div>
                    <div class="threat-stat medium">
                        <span class="value">${mediumThreat.length}</span>
                        <span class="label">Medium Threat</span>
                    </div>
                    <div class="threat-stat low">
                        <span class="value">${competitors.length - highThreat.length - mediumThreat.length}</span>
                        <span class="label">Low Threat</span>
                    </div>
                </div>
            </div>

            <div class="briefing-section">
                <h4>💡 Strategic Recommendations</h4>
                <ol class="briefing-numbered">
                    <li>Monitor ${highThreat[0]?.name || 'high-threat competitors'} for pricing and product changes</li>
                    <li>Strengthen differentiation in patient engagement features</li>
                    <li>Prepare competitive responses for upcoming market shifts</li>
                </ol>
            </div>

            <div class="briefing-section">
                <h4>✅ Action Items</h4>
                <ul class="briefing-checklist">
                    <li>Review ${highThreat.length} high-threat competitor profiles</li>
                    <li>Update sales battlecards with latest intelligence</li>
                    <li>Schedule competitive review meeting with product team</li>
                </ul>
            </div>
        </div>
    `;
}

/**
 * Export executive briefing to PDF
 */
async function exportBriefing(format) {
    if (!currentBriefing) {
        showToast('Please generate a briefing first', 'warning');
        return;
    }

    showToast('Preparing PDF export...', 'info');

    try {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html><head><title>Executive Briefing - ${new Date().toLocaleDateString()}</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; color: #1e293b; }
                h1, h2, h3, h4 { color: #1e40af; }
                .briefing-section { margin-bottom: 24px; padding: 16px; border: 1px solid #e2e8f0; border-radius: 8px; }
                ul { padding-left: 20px; }
                li { margin-bottom: 8px; line-height: 1.6; }
                @media print { body { padding: 20px; } }
            </style>
            </head><body>
                <h1>Certify Intel - Executive Competitive Briefing</h1>
                <p style="color: #64748b;">Generated: ${new Date().toLocaleString()}</p>
                <hr/>
                ${currentBriefing}
            </body></html>
        `);
        printWindow.document.close();
        printWindow.print();
        showToast('Print dialog opened - save as PDF', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Export failed', 'error');
    }
}

// ==============================================================================
// Enhanced Analytics Page Initialization
// ==============================================================================

// Override initAnalyticsPage to include new features
const originalInitAnalyticsPage = initAnalyticsPage;
async function enhancedInitAnalyticsPage() {
    await loadHeatmapData();
    initThreatDistributionChart();
    updateMarketShareChart();
    initFeatureGapDropdowns();
    initTrendAnalysis();
    initP2AnalyticsFeatures();
}

// Replace the original function
window.initAnalyticsPage = enhancedInitAnalyticsPage;

// Export functions for global access
window.loadHeatmapData = loadHeatmapData;
window.updateHeatmap = updateHeatmap;
window.refreshHeatmapData = refreshHeatmapData;
window.showCompetitorDetail = showCompetitorDetail;
window.showHeatmapCompetitorDetail = showHeatmapCompetitorDetail;
window.closeCompetitorDetail = closeCompetitorDetail;
window.viewFullCompetitorProfile = viewFullCompetitorProfile;
window.updateMarketShareChart = updateMarketShareChart;
window.updateFeatureGapMatrix = updateFeatureGapMatrix;
window.updateTrendCharts = updateTrendCharts;
window.generateExecutiveBriefing = generateExecutiveBriefing;
window.exportBriefing = exportBriefing;


// ==============================================================================
// AR-006: Dimension Radar Comparison
// ==============================================================================

let dimensionRadarCompareChart = null;

/**
 * Initialize the radar comparison dropdowns with competitors.
 */
function initRadarComparisonDropdowns() {
    const selects = ['radarCompetitor1', 'radarCompetitor2', 'radarCompetitor3', 'radarCompetitor4'];
    const options = (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
        .join('');

    selects.forEach((selectId, index) => {
        const select = document.getElementById(selectId);
        if (select) {
            const placeholder = index < 2 ? 'Select Competitor' : 'Select Competitor (Optional)';
            select.innerHTML = `<option value="">${placeholder}</option>` + options;
        }
    });
}

/**
 * Update the dimension radar comparison chart.
 */
async function updateDimensionRadar() {
    const comp1 = document.getElementById('radarCompetitor1')?.value;
    const comp2 = document.getElementById('radarCompetitor2')?.value;
    const comp3 = document.getElementById('radarCompetitor3')?.value;
    const comp4 = document.getElementById('radarCompetitor4')?.value;
    const includeCertify = document.getElementById('radarIncludeCertify')?.checked;

    const selectedIds = [comp1, comp2, comp3, comp4].filter(Boolean);

    if (selectedIds.length === 0) {
        document.getElementById('radarInsights').innerHTML = `
            <h4>📈 Comparison Insights</h4>
            <p class="placeholder-text">Select competitors to view dimension comparison insights.</p>
        `;
        return;
    }

    try {
        // Fetch dimension data for each competitor
        const dimensionPromises = selectedIds.map(id =>
            fetch(`${API_BASE}/api/sales-marketing/competitors/${id}/dimensions`, { headers: getAuthHeaders() })
                .then(r => r.json())
        );

        const dimensionResults = await Promise.all(dimensionPromises);

        // Get competitor names
        const competitorData = selectedIds.map((id, index) => {
            const comp = (window.competitors || []).find(c => c.id == id);
            return {
                id: id,
                name: comp?.name || `Competitor ${index + 1}`,
                dimensions: dimensionResults[index]?.dimensions || {},
                overall: dimensionResults[index]?.overall_score || 0
            };
        });

        // Add Certify Health if checked
        if (includeCertify) {
            competitorData.push({
                id: 'certify',
                name: 'Certify Health',
                dimensions: {
                    product_packaging: { score: 4.5 },
                    integration_depth: { score: 4.8 },
                    support_service: { score: 4.7 },
                    retention_stickiness: { score: 4.2 },
                    user_adoption: { score: 4.6 },
                    implementation_ttv: { score: 4.4 },
                    reliability_enterprise: { score: 4.5 },
                    pricing_flexibility: { score: 4.3 },
                    reporting_analytics: { score: 4.1 }
                },
                overall: 4.5
            });
        }

        renderDimensionRadar(competitorData);
        updateRadarInsights(competitorData);

    } catch (error) {
        console.error('Failed to update dimension radar:', error);
    }
}

function renderDimensionRadar(competitorData) {
    const ctx = document.getElementById('dimensionRadarCompareChart')?.getContext('2d');
    if (!ctx) return;

    if (dimensionRadarCompareChart) {
        dimensionRadarCompareChart.destroy();
    }

    const dimensions = [
        { id: 'product_packaging', label: 'Packaging' },
        { id: 'integration_depth', label: 'Integration' },
        { id: 'support_service', label: 'Support' },
        { id: 'retention_stickiness', label: 'Retention' },
        { id: 'user_adoption', label: 'Adoption' },
        { id: 'implementation_ttv', label: 'Implementation' },
        { id: 'reliability_enterprise', label: 'Enterprise' },
        { id: 'pricing_flexibility', label: 'Pricing' },
        { id: 'reporting_analytics', label: 'Analytics' }
    ];

    const colors = [
        { bg: 'rgba(0, 51, 102, 0.2)', border: '#003366' },
        { bg: 'rgba(220, 38, 38, 0.2)', border: '#DC2626' },
        { bg: 'rgba(16, 185, 129, 0.2)', border: '#10B981' },
        { bg: 'rgba(139, 92, 246, 0.2)', border: '#8B5CF6' },
        { bg: 'rgba(251, 146, 60, 0.2)', border: '#FB923C' }
    ];

    const datasets = competitorData.map((comp, index) => ({
        label: comp.name,
        data: dimensions.map(d => comp.dimensions[d.id]?.score || 0),
        backgroundColor: colors[index % colors.length].bg,
        borderColor: colors[index % colors.length].border,
        borderWidth: 2,
        pointBackgroundColor: colors[index % colors.length].border
    }));

    dimensionRadarCompareChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: dimensions.map(d => d.label),
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    min: 0,
                    max: 5,
                    ticks: { stepSize: 1 }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function updateRadarInsights(competitorData) {
    const container = document.getElementById('radarInsights');
    if (!container) return;

    // Calculate insights
    const dimensions = ['product_packaging', 'integration_depth', 'support_service', 'retention_stickiness',
                       'user_adoption', 'implementation_ttv', 'reliability_enterprise', 'pricing_flexibility', 'reporting_analytics'];

    let insights = `<h4>📈 Comparison Insights</h4>`;

    // Find where each competitor is strongest
    competitorData.forEach(comp => {
        let maxScore = 0;
        let maxDim = '';
        dimensions.forEach(dim => {
            const score = comp.dimensions[dim]?.score || 0;
            if (score > maxScore) {
                maxScore = score;
                maxDim = dim;
            }
        });

        if (maxDim) {
            const dimLabel = maxDim.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            insights += `<p><strong>${escapeHtml(comp.name)}</strong> is strongest in <em>${escapeHtml(dimLabel)}</em> (${maxScore}/5)</p>`;
        }
    });

    // Find biggest gaps
    if (competitorData.length >= 2) {
        const certify = competitorData.find(c => c.id === 'certify');
        if (certify) {
            const others = competitorData.filter(c => c.id !== 'certify');
            dimensions.forEach(dim => {
                const certifyScore = certify.dimensions[dim]?.score || 0;
                others.forEach(other => {
                    const otherScore = other.dimensions[dim]?.score || 0;
                    const gap = certifyScore - otherScore;
                    if (gap >= 1.5) {
                        const dimLabel = dim.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        insights += `<p class="insight-advantage">✅ Certify has advantage over ${other.name} in ${dimLabel} (+${gap.toFixed(1)})</p>`;
                    }
                });
            });
        }
    }

    container.innerHTML = insights;
}


// ==============================================================================
// AR-007: Win/Loss Analytics
// ==============================================================================

let winRateByCompetitorChart = null;
let winLossReasonsChart = null;
let winRateTrendChart = null;
let winLossMonthlyTrendChart = null;
let winLossData = [];
let winLossDealsShown = 10;
let mostCompetitiveData = [];
let mostCompetitiveSortField = 'total';
let mostCompetitiveSortAsc = false;

/**
 * Initialize win/loss analytics.
 */
async function initWinLossAnalytics() {
    // Populate competitor dropdown
    const select = document.getElementById('winlossCompetitor');
    if (select) {
        const options = (window.competitors || [])
            .filter(c => !c.is_deleted)
            .map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`)
            .join('');
        select.innerHTML = '<option value="all">All Competitors</option>' + options;
    }

    await updateWinLossAnalytics();
}

/**
 * Update win/loss analytics data and charts.
 */
async function updateWinLossAnalytics() {
    const timeRange = document.getElementById('winlossTimeRange')?.value || 90;
    const competitorFilter = document.getElementById('winlossCompetitor')?.value || 'all';

    winLossDealsShown = 10;

    try {
        const response = await fetch(`${API_BASE}/api/win-loss?days=${timeRange}`, { headers: getAuthHeaders() });

        if (response.ok) {
            winLossData = await response.json();
        } else {
            winLossData = [];
        }

        let filteredData = winLossData;
        if (competitorFilter !== 'all') {
            filteredData = winLossData.filter(d => d.competitor_id == competitorFilter);
        }

        updateWinLossKPIs(filteredData);
        updateWinLossSummary(filteredData);
        renderWinLossMonthlyTrend(filteredData);
        renderWinRateByCompetitorChart(filteredData);
        renderWinLossReasonsChart(filteredData);
        renderWinRateTrendChart(filteredData);
        renderWinLossTable(filteredData);
        analyzeDimensionCorrelation();
        loadMostCompetitiveTable(timeRange);

    } catch (error) {
        console.error('Failed to update win/loss analytics:', error);
        winLossData = [];
        updateWinLossKPIs([]);
        updateWinLossSummary([]);
        renderWinLossMonthlyTrend([]);
        renderWinRateByCompetitorChart([]);
        renderWinLossReasonsChart([]);
        renderWinRateTrendChart([]);
        renderWinLossTable([]);
    }
}


function updateWinLossSummary(data) {
    const wins = data.filter(d => d.outcome === 'win').length;
    const losses = data.filter(d => d.outcome === 'loss').length;
    const total = wins + losses;
    const winRate = total > 0 ? Math.round((wins / total) * 100) : 0;

    const el = (id) => document.getElementById(id);
    if (el('totalWins')) el('totalWins').textContent = wins;
    if (el('totalLosses')) el('totalLosses').textContent = losses;
    if (el('winRate')) el('winRate').textContent = winRate + '%';
}

/**
 * Update the 4 KPI cards: Total Deals, Win Rate, Value Won, Value Lost
 */
function updateWinLossKPIs(data) {
    const wins = data.filter(d => d.outcome === 'win');
    const losses = data.filter(d => d.outcome === 'loss');
    const total = wins.length + losses.length;
    const winRate = total > 0 ? Math.round((wins.length / total) * 100) : 0;
    const valueWon = wins.reduce((sum, d) => sum + (d.deal_value || d.deal_size || 0), 0);
    const valueLost = losses.reduce((sum, d) => sum + (d.deal_value || d.deal_size || 0), 0);

    const el = (id) => document.getElementById(id);
    if (el('wlTotalDeals')) el('wlTotalDeals').textContent = total;

    const rateEl = el('wlWinRate');
    if (rateEl) {
        rateEl.textContent = winRate + '%';
        rateEl.style.color = winRate >= 50 ? '#10B981' : '#EF4444';
    }

    if (el('wlValueWon')) el('wlValueWon').textContent = '$' + valueWon.toLocaleString();
    if (el('wlValueLost')) el('wlValueLost').textContent = '$' + valueLost.toLocaleString();
}

/**
 * Monthly Win/Loss Trend bar chart - grouped by month
 */
function renderWinLossMonthlyTrend(data) {
    const canvas = document.getElementById('winLossMonthlyTrendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (winLossMonthlyTrendChart) winLossMonthlyTrendChart.destroy();

    if (data.length === 0) {
        winLossMonthlyTrendChart = null;
        return;
    }

    const byMonth = {};
    data.forEach(d => {
        const dt = new Date(d.deal_date || d.date);
        const key = dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0');
        if (!byMonth[key]) byMonth[key] = { wins: 0, losses: 0 };
        if (d.outcome === 'win') byMonth[key].wins++;
        else byMonth[key].losses++;
    });

    const months = Object.keys(byMonth).sort();
    const monthLabels = months.map(m => {
        const [y, mo] = m.split('-');
        return new Date(y, parseInt(mo) - 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    });

    winLossMonthlyTrendChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: monthLabels,
            datasets: [
                {
                    label: 'Wins',
                    data: months.map(m => byMonth[m].wins),
                    backgroundColor: '#10B981',
                    borderRadius: 4
                },
                {
                    label: 'Losses',
                    data: months.map(m => byMonth[m].losses),
                    backgroundColor: '#EF4444',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(148,163,184,0.1)' }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: '#94a3b8', stepSize: 1 },
                    grid: { color: 'rgba(148,163,184,0.1)' }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#e2e8f0' }
                }
            }
        }
    });
}

/**
 * Load and render the Most Competitive Rivals table
 */
async function loadMostCompetitiveTable(timeRange) {
    const tbody = document.querySelector('#mostCompetitiveTable tbody');
    if (!tbody) return;

    try {
        const response = await fetch(`${API_BASE}/api/deals/most-competitive?limit=10`, {
            headers: getAuthHeaders()
        });
        if (response.ok) {
            mostCompetitiveData = await response.json();
        } else {
            mostCompetitiveData = [];
        }
    } catch {
        mostCompetitiveData = [];
    }

    renderMostCompetitiveTable();
}

function renderMostCompetitiveTable() {
    const tbody = document.querySelector('#mostCompetitiveTable tbody');
    if (!tbody) return;

    if (mostCompetitiveData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="placeholder-text">No competitive deal data available yet.</td></tr>';
        return;
    }

    const sorted = [...mostCompetitiveData].sort((a, b) => {
        let av = a[mostCompetitiveSortField];
        let bv = b[mostCompetitiveSortField];
        if (mostCompetitiveSortField === 'name') {
            av = (av || '').toLowerCase();
            bv = (bv || '').toLowerCase();
            return mostCompetitiveSortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
        }
        return mostCompetitiveSortAsc ? (av || 0) - (bv || 0) : (bv || 0) - (av || 0);
    });

    tbody.innerHTML = sorted.map(row => {
        const wr = row.total > 0 ? Math.round((row.wins / row.total) * 100) : 0;
        const wrColor = wr >= 50 ? '#10B981' : '#EF4444';
        return `<tr>
            <td>${escapeHtml(row.name || row.competitor_name || '')}</td>
            <td>${row.total || row.deals || 0}</td>
            <td>${row.wins || 0}</td>
            <td>${row.losses || 0}</td>
            <td style="color:${wrColor};font-weight:600;">${wr}%</td>
        </tr>`;
    }).join('');
}

function sortMostCompetitiveTable(field) {
    if (mostCompetitiveSortField === field) {
        mostCompetitiveSortAsc = !mostCompetitiveSortAsc;
    } else {
        mostCompetitiveSortField = field;
        mostCompetitiveSortAsc = field === 'name';
    }
    renderMostCompetitiveTable();
}

function renderWinRateByCompetitorChart(data) {
    const ctx = document.getElementById('winRateByCompetitorChart')?.getContext('2d');
    if (!ctx) return;

    if (winRateByCompetitorChart) winRateByCompetitorChart.destroy();

    // Calculate win rate by competitor
    const byCompetitor = {};
    data.forEach(d => {
        if (!byCompetitor[d.competitor_name]) {
            byCompetitor[d.competitor_name] = { wins: 0, losses: 0 };
        }
        if (d.outcome === 'win') byCompetitor[d.competitor_name].wins++;
        else byCompetitor[d.competitor_name].losses++;
    });

    const labels = Object.keys(byCompetitor).slice(0, 10);
    const winRates = labels.map(name => {
        const total = byCompetitor[name].wins + byCompetitor[name].losses;
        return total > 0 ? Math.round((byCompetitor[name].wins / total) * 100) : 0;
    });

    winRateByCompetitorChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Win Rate %',
                data: winRates,
                backgroundColor: winRates.map(r => r >= 50 ? '#10B981' : '#EF4444'),
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            scales: {
                x: { max: 100, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                y: { ticks: { color: '#e2e8f0' }, grid: { display: false } }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderWinLossReasonsChart(data) {
    const ctx = document.getElementById('winLossReasonsChart')?.getContext('2d');
    if (!ctx) return;

    if (winLossReasonsChart) winLossReasonsChart.destroy();

    const winReasons = {};
    const lossReasons = {};

    data.forEach(d => {
        if (d.outcome === 'win') {
            winReasons[d.reason] = (winReasons[d.reason] || 0) + 1;
        } else {
            lossReasons[d.reason] = (lossReasons[d.reason] || 0) + 1;
        }
    });

    const allReasons = [...new Set([...Object.keys(winReasons), ...Object.keys(lossReasons)])];

    winLossReasonsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: allReasons,
            datasets: [
                {
                    label: 'Wins',
                    data: allReasons.map(r => winReasons[r] || 0),
                    backgroundColor: '#10B981',
                    borderRadius: 4
                },
                {
                    label: 'Losses',
                    data: allReasons.map(r => lossReasons[r] || 0),
                    backgroundColor: '#EF4444',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } }
            },
            plugins: {
                legend: { position: 'bottom', labels: { color: '#e2e8f0' } }
            }
        }
    });
}

function renderWinRateTrendChart(data) {
    const ctx = document.getElementById('winRateTrendChart')?.getContext('2d');
    if (!ctx) return;

    if (winRateTrendChart) winRateTrendChart.destroy();

    // Group by week
    const byWeek = {};
    data.forEach(d => {
        const date = new Date(d.date);
        const weekStart = new Date(date);
        weekStart.setDate(date.getDate() - date.getDay());
        const weekKey = weekStart.toISOString().split('T')[0];

        if (!byWeek[weekKey]) byWeek[weekKey] = { wins: 0, losses: 0 };
        if (d.outcome === 'win') byWeek[weekKey].wins++;
        else byWeek[weekKey].losses++;
    });

    const weeks = Object.keys(byWeek).sort();
    const winRates = weeks.map(w => {
        const total = byWeek[w].wins + byWeek[w].losses;
        return total > 0 ? Math.round((byWeek[w].wins / total) * 100) : 0;
    });

    winRateTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: weeks.map(w => new Date(w).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
            datasets: [{
                label: 'Win Rate %',
                data: winRates,
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#3B82F6',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
                y: { min: 0, max: 100, ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderWinLossTable(data) {
    const tbody = document.querySelector('#winLossDealsTable tbody');
    if (!tbody) return;

    const showMoreBtn = document.getElementById('winLossShowMore');

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="placeholder-text">No deals found for this period. Click "Log Win/Loss" to record your first deal.</td></tr>';
        if (showMoreBtn) showMoreBtn.style.display = 'none';
        return;
    }

    const sortedData = [...data].sort((a, b) => new Date(b.deal_date || b.date) - new Date(a.deal_date || a.date));
    const visibleData = sortedData.slice(0, winLossDealsShown);

    tbody.innerHTML = visibleData.map(deal => {
        const dealDate = new Date(deal.deal_date || deal.date).toLocaleDateString();
        const compName = escapeHtml(deal.competitor_name || '');
        const outcomeClass = deal.outcome === 'win' ? 'win' : 'loss';
        const outcomeLabel = deal.outcome === 'win' ? 'Win' : 'Loss';
        const value = deal.deal_value || deal.deal_size;
        const valueStr = value ? '$' + Number(value).toLocaleString() : 'N/A';
        const reason = escapeHtml(deal.reason || deal.loss_reason || deal.win_factors || '-');
        const notes = deal.notes ? escapeHtml(deal.notes.substring(0, 60)) + (deal.notes.length > 60 ? '...' : '') : '-';

        return `<tr>
            <td>${dealDate}</td>
            <td>${compName}</td>
            <td><span class="outcome-badge ${outcomeClass}">${outcomeLabel}</span></td>
            <td>${valueStr}</td>
            <td>${reason}</td>
            <td>${notes}</td>
        </tr>`;
    }).join('');

    if (showMoreBtn) {
        showMoreBtn.style.display = sortedData.length > winLossDealsShown ? 'block' : 'none';
    }
}

function showMoreDeals() {
    winLossDealsShown += 10;
    const competitorFilter = document.getElementById('winlossCompetitor')?.value || 'all';
    let filteredData = winLossData;
    if (competitorFilter !== 'all') {
        filteredData = winLossData.filter(d => d.competitor_id == competitorFilter);
    }
    renderWinLossTable(filteredData);
}

/**
 * FEAT-003: Enhanced Win/Loss Analysis - Entry Form Modal
 */
function showAddWinLossModal() {
    // Remove existing modal if present
    const existing = document.getElementById('winLossEntryModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'winLossEntryModal';
    modal.className = 'modal-overlay';
    modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10000;';

    modal.innerHTML = `
        <div class="modal-content" style="background:var(--bg-secondary);border-radius:12px;padding:24px;max-width:600px;width:90%;max-height:90vh;overflow-y:auto;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <h2 style="margin:0;color:var(--text-primary);">Record Win/Loss Deal</h2>
                <button onclick="closeWinLossModal()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--text-secondary);">&times;</button>
            </div>

            <form id="winLossEntryForm" onsubmit="submitWinLossDeal(event)">
                <div style="display:grid;gap:16px;">
                    <!-- Outcome -->
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <label style="display:flex;align-items:center;padding:16px;border:2px solid var(--border-color);border-radius:8px;cursor:pointer;transition:all 0.2s;">
                            <input type="radio" name="outcome" value="win" required style="margin-right:10px;">
                            <span style="font-size:20px;margin-right:8px;">✅</span>
                            <span style="font-weight:600;color:var(--success-color);">WIN</span>
                        </label>
                        <label style="display:flex;align-items:center;padding:16px;border:2px solid var(--border-color);border-radius:8px;cursor:pointer;transition:all 0.2s;">
                            <input type="radio" name="outcome" value="loss" required style="margin-right:10px;">
                            <span style="font-size:20px;margin-right:8px;">❌</span>
                            <span style="font-weight:600;color:var(--danger-color);">LOSS</span>
                        </label>
                    </div>

                    <!-- Competitor -->
                    <div>
                        <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Competitor</label>
                        <select id="winLossCompetitorSelect" name="competitor_id" required style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                            <option value="">Select competitor...</option>
                            ${(window.competitors || []).filter(c => !c.is_deleted).map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')}
                        </select>
                    </div>

                    <!-- Deal Value and Date -->
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <div>
                            <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Deal Value ($)</label>
                            <input type="number" name="deal_value" placeholder="50000" style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Deal Date</label>
                            <input type="date" name="deal_date" value="${new Date().toISOString().split('T')[0]}" required style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                        </div>
                    </div>

                    <!-- Customer Info -->
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <div>
                            <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Customer Name</label>
                            <input type="text" name="customer_name" placeholder="Acme Healthcare" style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Customer Size</label>
                            <select name="customer_size" style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                                <option value="">Select size...</option>
                                <option value="SMB">SMB (1-50 providers)</option>
                                <option value="Mid-Market">Mid-Market (51-200)</option>
                                <option value="Enterprise">Enterprise (201-1000)</option>
                                <option value="Large Enterprise">Large Enterprise (1000+)</option>
                            </select>
                        </div>
                    </div>

                    <!-- Primary Reason -->
                    <div>
                        <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Primary Reason</label>
                        <select name="reason" required style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                            <option value="">Select reason...</option>
                            <optgroup label="Win Reasons">
                                <option value="Better Product">Better Product/Features</option>
                                <option value="Better Price">Better Pricing</option>
                                <option value="Better Support">Better Customer Support</option>
                                <option value="Better Integration">Better EHR Integration</option>
                                <option value="Faster Implementation">Faster Implementation</option>
                                <option value="Better UX">Better User Experience</option>
                                <option value="Existing Relationship">Existing Relationship</option>
                            </optgroup>
                            <optgroup label="Loss Reasons">
                                <option value="Price Too High">Price Too High</option>
                                <option value="Missing Features">Missing Features</option>
                                <option value="Poor Demo">Poor Demo/Sales Process</option>
                                <option value="Integration Issues">Integration Concerns</option>
                                <option value="Implementation Time">Implementation Timeline</option>
                                <option value="Competitor Incumbent">Competitor Incumbent</option>
                                <option value="Budget Cut">Budget Cut/No Decision</option>
                            </optgroup>
                        </select>
                    </div>

                    <!-- Competitive Dimension Impact -->
                    <div>
                        <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Key Dimension (What mattered most?)</label>
                        <select name="key_dimension" style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                            <option value="">Select dimension...</option>
                            <option value="product_packaging">Product Modules & Packaging</option>
                            <option value="integration_depth">Interoperability & Integration</option>
                            <option value="support_service">Customer Support & Service</option>
                            <option value="retention_stickiness">Product Stickiness</option>
                            <option value="user_adoption">User Adoption & Ease of Use</option>
                            <option value="implementation_ttv">Implementation & Time to Value</option>
                            <option value="reliability_enterprise">Enterprise Readiness</option>
                            <option value="pricing_flexibility">Pricing & Commercial Terms</option>
                            <option value="reporting_analytics">Reporting & Analytics</option>
                        </select>
                    </div>

                    <!-- Sales Rep -->
                    <div>
                        <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Sales Rep</label>
                        <input type="text" name="sales_rep" placeholder="John Doe" style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);">
                    </div>

                    <!-- Notes -->
                    <div>
                        <label style="display:block;margin-bottom:6px;font-weight:500;color:var(--text-primary);">Notes</label>
                        <textarea name="notes" rows="3" placeholder="Additional context about the deal..." style="width:100%;padding:10px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);resize:vertical;"></textarea>
                    </div>

                    <!-- Submit -->
                    <div style="display:flex;gap:12px;justify-content:flex-end;margin-top:8px;">
                        <button type="button" onclick="closeWinLossModal()" style="padding:10px 20px;border:1px solid var(--border-color);border-radius:6px;background:var(--bg-tertiary);color:var(--text-primary);cursor:pointer;">Cancel</button>
                        <button type="submit" style="padding:10px 20px;border:none;border-radius:6px;background:var(--primary-color);color:white;cursor:pointer;font-weight:500;">Record Deal</button>
                    </div>
                </div>
            </form>
        </div>
    `;

    document.body.appendChild(modal);

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeWinLossModal();
    });
}

function closeWinLossModal() {
    const modal = document.getElementById('winLossEntryModal');
    if (modal) modal.remove();
}

function closeAddWinLossModal() {
    closeWinLossModal();
}

async function submitWinLossDeal(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);

    const dealData = {
        competitor_id: parseInt(formData.get('competitor_id')),
        competitor_name: document.querySelector(`#winLossCompetitorSelect option[value="${formData.get('competitor_id')}"]`)?.textContent || '',
        outcome: formData.get('outcome'),
        deal_value: formData.get('deal_value') ? parseFloat(formData.get('deal_value')) : null,
        deal_date: formData.get('deal_date'),
        customer_name: formData.get('customer_name'),
        customer_size: formData.get('customer_size'),
        reason: formData.get('reason'),
        sales_rep: formData.get('sales_rep'),
        notes: formData.get('notes'),
        key_dimension: formData.get('key_dimension')
    };

    try {
        const response = await fetch(`${API_BASE}/api/win-loss`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders()
            },
            body: JSON.stringify(dealData)
        });

        if (response.ok) {
            showToast(`Deal recorded successfully! (${dealData.outcome === 'win' ? 'Win' : 'Loss'} vs ${dealData.competitor_name})`, 'success');
            closeWinLossModal();
            // Refresh analytics
            if (typeof updateWinLossAnalytics === 'function') {
                updateWinLossAnalytics();
            }
        } else {
            const error = await response.json();
            showToast('Failed to record deal: ' + (error.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error submitting win/loss deal:', error);
        showToast('Error submitting deal: ' + error.message, 'error');
    }
}

/**
 * FEAT-003: Dimension Correlation Analysis
 * Shows which dimensions correlate with wins/losses
 */
async function analyzeDimensionCorrelation() {
    const correlationContainer = document.getElementById('dimensionCorrelation');
    if (!correlationContainer) return;

    // Calculate correlation from win/loss data
    const data = winLossData || [];
    if (data.length === 0) {
        correlationContainer.innerHTML = '<p style="color:var(--text-secondary);text-align:center;">No data available for correlation analysis</p>';
        return;
    }

    // Group by dimension
    const dimensionStats = {};
    const dimensions = [
        { id: 'product_packaging', label: 'Product Packaging' },
        { id: 'integration_depth', label: 'Integration' },
        { id: 'support_service', label: 'Support' },
        { id: 'user_adoption', label: 'User Adoption' },
        { id: 'implementation_ttv', label: 'Implementation' },
        { id: 'pricing_flexibility', label: 'Pricing' },
        { id: 'reporting_analytics', label: 'Analytics' }
    ];

    dimensions.forEach(dim => {
        dimensionStats[dim.id] = { wins: 0, losses: 0, label: dim.label };
    });

    data.forEach(deal => {
        const dim = deal.key_dimension;
        if (dim && dimensionStats[dim]) {
            if (deal.outcome === 'win') {
                dimensionStats[dim].wins++;
            } else {
                dimensionStats[dim].losses++;
            }
        }
    });

    // Calculate win rates and sort
    const correlations = Object.entries(dimensionStats)
        .map(([id, stats]) => {
            const total = stats.wins + stats.losses;
            const winRate = total > 0 ? (stats.wins / total * 100) : 50;
            return { ...stats, id, total, winRate };
        })
        .filter(d => d.total > 0)
        .sort((a, b) => b.winRate - a.winRate);

    if (correlations.length === 0) {
        correlationContainer.innerHTML = '<p style="color:var(--text-secondary);text-align:center;">Record deals with dimensions to see correlation analysis</p>';
        return;
    }

    correlationContainer.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:12px;">
            ${correlations.map(d => `
                <div style="display:flex;align-items:center;gap:12px;">
                    <div style="width:120px;font-size:0.9rem;color:var(--text-primary);">${d.label}</div>
                    <div style="flex:1;height:24px;background:var(--bg-tertiary);border-radius:4px;overflow:hidden;display:flex;">
                        <div style="width:${d.winRate}%;background:var(--success-color);transition:width 0.3s;"></div>
                        <div style="width:${100 - d.winRate}%;background:var(--danger-color);"></div>
                    </div>
                    <div style="width:80px;text-align:right;font-size:0.85rem;font-weight:600;color:${d.winRate >= 50 ? 'var(--success-color)' : 'var(--danger-color)'};">
                        ${d.winRate.toFixed(0)}% wins
                    </div>
                    <div style="width:60px;text-align:right;font-size:0.8rem;color:var(--text-secondary);">
                        (${d.total} deals)
                    </div>
                </div>
            `).join('')}
        </div>
        <p style="margin-top:16px;font-size:0.8rem;color:var(--text-secondary);text-align:center;">
            Higher win rates indicate dimensions where we have competitive advantage
        </p>
    `;
}

// Expose new functions
window.closeWinLossModal = closeWinLossModal;
window.submitWinLossDeal = submitWinLossDeal;
window.analyzeDimensionCorrelation = analyzeDimensionCorrelation;
window.sortMostCompetitiveTable = sortMostCompetitiveTable;
window.showMoreDeals = showMoreDeals;


// ==============================================================================
// AR-008: Data Freshness Dashboard
// ==============================================================================

/**
 * Update the data freshness dashboard.
 */
async function updateFreshnessDashboard() {
    const sortBy = document.getElementById('freshnessSort')?.value || 'stalest';

    try {
        const response = await fetch(`${API_BASE}/api/data-quality/overview`, { headers: getAuthHeaders() });
        let freshnessData = [];

        if (response.ok) {
            const data = await response.json();
            // Calculate freshness from competitors
            freshnessData = calculateFreshnessData();
        } else {
            freshnessData = calculateFreshnessData();
        }

        // Sort data
        if (sortBy === 'stalest') {
            freshnessData.sort((a, b) => b.ageInDays - a.ageInDays);
        } else if (sortBy === 'freshest') {
            freshnessData.sort((a, b) => a.ageInDays - b.ageInDays);
        } else {
            freshnessData.sort((a, b) => a.name.localeCompare(b.name));
        }

        updateFreshnessSummary(freshnessData);
        renderFreshnessGrid(freshnessData);

    } catch (error) {
        console.error('Failed to update freshness dashboard:', error);
    }
}

function calculateFreshnessData() {
    const now = new Date();
    return (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => {
            const lastUpdated = c.last_updated ? new Date(c.last_updated) : new Date(now - 7 * 24 * 60 * 60 * 1000);
            const ageInDays = Math.floor((now - lastUpdated) / (1000 * 60 * 60 * 24));

            let status = 'fresh';
            if (ageInDays > 7) status = 'stale';
            else if (ageInDays > 1) status = 'warning';

            return {
                id: c.id,
                name: c.name,
                lastUpdated: lastUpdated,
                ageInDays: ageInDays,
                status: status,
                hasNews: !!(c.news_mentions && c.news_mentions !== 'N/A' && parseInt(c.news_mentions) > 0),
                hasProducts: !!(c.product_count && parseInt(c.product_count) > 0)
            };
        });
}

function updateFreshnessSummary(data) {
    const fresh = data.filter(d => d.status === 'fresh').length;
    const warning = data.filter(d => d.status === 'warning').length;
    const stale = data.filter(d => d.status === 'stale').length;
    const avgAge = data.length > 0 ? Math.round(data.reduce((sum, d) => sum + d.ageInDays, 0) / data.length) : 0;

    document.getElementById('freshDataCount').textContent = fresh;
    document.getElementById('warningDataCount').textContent = warning;
    document.getElementById('staleDataCount').textContent = stale;
    document.getElementById('avgDataAge').textContent = avgAge;
}

function renderFreshnessGrid(data) {
    const container = document.getElementById('freshnessGrid');
    if (!container) return;

    if (data.length === 0) {
        container.innerHTML = '<p class="placeholder-text">No competitor data found.</p>';
        return;
    }

    container.innerHTML = data.slice(0, 30).map(item => `
        <div class="freshness-item ${item.status}">
            <div class="freshness-item-header">
                <span class="competitor-name">${item.name}</span>
                <span class="freshness-badge ${item.status}">${item.status === 'fresh' ? '✅' : item.status === 'warning' ? '⚠️' : '🔴'}</span>
            </div>
            <div class="freshness-item-details">
                <span class="age">${item.ageInDays === 0 ? 'Today' : item.ageInDays === 1 ? 'Yesterday' : item.ageInDays + ' days ago'}</span>
                <span class="data-flags">
                    ${item.hasNews ? '📰' : ''}
                    ${item.hasProducts ? '📦' : ''}
                </span>
            </div>
            <div class="freshness-item-actions">
                <button class="btn btn-sm btn-outline" onclick="refreshCompetitor(${item.id})">🔄 Refresh</button>
            </div>
        </div>
    `).join('');
}

async function triggerBulkRefresh() {
    showNotification('Starting bulk data refresh...', 'info');

    try {
        const response = await fetch(`${API_BASE}/api/refresh/trigger`, {
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (response.ok) {
            showNotification('Bulk refresh started! Check back in a few minutes.', 'success');
        } else {
            showNotification('Bulk refresh initiated. Some items may not update.', 'warning');
        }
    } catch (error) {
        showNotification('Unable to start bulk refresh.', 'error');
    }
}

async function refreshCompetitor(competitorId) {
    showNotification('Refreshing competitor data...', 'info');

    try {
        const response = await fetch(`${API_BASE}/api/competitors/${competitorId}/scrape`, {
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (response.ok) {
            showNotification('Competitor data refreshed!', 'success');
            updateFreshnessDashboard();
        }
    } catch (error) {
        showNotification('Failed to refresh competitor.', 'error');
    }
}


// ==============================================================================
// AR-009: Export Center
// ==============================================================================

/**
 * Export all charts as PNG or PDF.
 */
function exportAllCharts(format) {
    showNotification('Exporting charts as PNG...', 'info');

    const charts = [
        { id: 'heatmapContainer', name: 'competitive-heatmap' },
        { id: 'marketShareChart', name: 'market-share' },
        { id: 'threatDistributionChart', name: 'threat-distribution' },
        { id: 'dimensionRadarCompareChart', name: 'dimension-radar' },
        { id: 'sentimentTrendChart', name: 'sentiment-trend' }
    ];

    let exported = 0;
    charts.forEach(chart => {
        const canvas = document.getElementById(chart.id);
        if (canvas && canvas.tagName === 'CANVAS') {
            const link = document.createElement('a');
            link.download = `${chart.name}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
            exported++;
        }
    });
    if (exported > 0) {
        showNotification(`${exported} charts exported as PNG!`, 'success');
    } else {
        showNotification('No charts available to export', 'warning');
    }
}

/**
 * Export competitor data as Excel.
 */
function exportCompetitorData(format) {
    window.open(`${API_BASE}/api/export/excel`, '_blank');
    showNotification('Competitor data exported as Excel!', 'success');
}

/**
 * Generate full competitive intelligence report (Excel export).
 */
async function generateFullReport() {
    showNotification('Generating comprehensive Excel report...', 'info');

    try {
        // Use Excel export which has comprehensive data
        window.open(`${API_BASE}/api/export/excel`, '_blank');
        showNotification('Report download started!', 'success');
    } catch (error) {
        console.error('Error generating report:', error);
        showNotification('Error generating report', 'error');
    }
}


// Initialize P2 analytics features when analytics page loads
function initP2AnalyticsFeatures() {
    initRadarComparisonDropdowns();
    initWinLossAnalytics();
    updateFreshnessDashboard();
}


// AR-006 Exports
window.initRadarComparisonDropdowns = initRadarComparisonDropdowns;
window.updateDimensionRadar = updateDimensionRadar;

// AR-007 Exports
window.initWinLossAnalytics = initWinLossAnalytics;
window.updateWinLossAnalytics = updateWinLossAnalytics;
window.showAddWinLossModal = showAddWinLossModal;

// AR-008 Exports
window.updateFreshnessDashboard = updateFreshnessDashboard;
window.triggerBulkRefresh = triggerBulkRefresh;
window.refreshCompetitor = refreshCompetitor;

// AR-009 Exports
window.exportAllCharts = exportAllCharts;
window.exportCompetitorData = exportCompetitorData;
window.generateBattlecardStrategy = generateBattlecardStrategy;
window.generateFullReport = generateFullReport;
window.initP2AnalyticsFeatures = initP2AnalyticsFeatures;

// Battlecard & Modal Exports
window.viewBattlecard = viewBattlecard;
window.viewCorporateBattlecard = viewCorporateBattlecard;
window.downloadBattlecardPDF = downloadBattlecardPDF;
window.showModal = showModal;
window.closeModal = closeModal;
window.showCompetitorComparison = showCompetitorComparison;
window.openSourceLink = openSourceLink;
window.openDataFieldPopup = openDataFieldPopup;

// ==============================================================================
// UX-006: Customizable Dashboard
// Drag-and-drop widgets, show/hide widgets, save layouts per user
// ==============================================================================

// Dashboard widget configuration
const DASHBOARD_WIDGETS = {
    'widget-ai-summary': { name: 'AI Summary', icon: '🤖', default: true, order: 1 },
    'widget-threat-stats': { name: 'Threat Statistics', icon: '⚠️', default: true, order: 2 },
    'widget-quick-actions': { name: 'Quick Actions', icon: '⚡', default: true, order: 3 },
    'widget-recent-changes': { name: 'Recent Changes', icon: '📋', default: true, order: 4 },
    'widget-news-feed': { name: 'News Feed', icon: '📰', default: true, order: 5 },
    'widget-competitor-grid': { name: 'Competitor Grid', icon: '🏢', default: true, order: 6 },
    'widget-market-chart': { name: 'Market Chart', icon: '📊', default: true, order: 7 },
    'widget-alerts': { name: 'Active Alerts', icon: '🔔', default: false, order: 8 }
};

// Current dashboard layout state
let dashboardLayout = {
    widgets: {},
    order: [],
    lastModified: null
};

/**
 * Initialize customizable dashboard
 */
function initCustomizableDashboard() {
    loadDashboardLayout();
    renderDashboardWidgets();
    initDragAndDrop();
}

/**
 * Load dashboard layout from localStorage or API
 */
function loadDashboardLayout() {
    const savedLayout = localStorage.getItem('dashboardLayout');
    if (savedLayout) {
        try {
            dashboardLayout = JSON.parse(savedLayout);
        } catch (e) {
            console.error('[Dashboard] Failed to parse saved layout:', e);
            resetDashboardLayout();
        }
    } else {
        resetDashboardLayout();
    }
}

/**
 * Reset dashboard to default layout
 */
function resetDashboardLayout() {
    dashboardLayout = {
        widgets: {},
        order: [],
        lastModified: new Date().toISOString()
    };

    Object.entries(DASHBOARD_WIDGETS).forEach(([id, config]) => {
        dashboardLayout.widgets[id] = {
            visible: config.default,
            collapsed: false,
            order: config.order
        };
        dashboardLayout.order.push(id);
    });

    // Sort by default order
    dashboardLayout.order.sort((a, b) =>
        DASHBOARD_WIDGETS[a].order - DASHBOARD_WIDGETS[b].order
    );

    saveDashboardLayout();
}

/**
 * Save dashboard layout to localStorage
 */
function saveDashboardLayout() {
    dashboardLayout.lastModified = new Date().toISOString();
    localStorage.setItem('dashboardLayout', JSON.stringify(dashboardLayout));

    // Also save to server for cross-device sync
    const token = localStorage.getItem('access_token');
    if (token) {
        fetch(`${API_BASE}/api/user/settings`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                dashboard_layout: JSON.stringify(dashboardLayout)
            })
        }).catch(() => {});
    }
}

/**
 * Render dashboard widgets in their configured order
 */
function renderDashboardWidgets() {
    const container = document.querySelector('#dashboardPage .dashboard-widgets, #dashboardPage');
    if (!container) return;

    // Update visibility for each widget
    dashboardLayout.order.forEach(widgetId => {
        const widget = document.getElementById(widgetId);
        if (widget) {
            const config = dashboardLayout.widgets[widgetId];
            widget.style.display = config?.visible !== false ? '' : 'none';
            widget.setAttribute('data-order', config?.order || 0);

            // Add draggable attribute
            widget.setAttribute('draggable', 'true');
            widget.classList.add('dashboard-widget');

            // Add collapsed state
            if (config?.collapsed) {
                widget.classList.add('widget-collapsed');
            }
        }
    });
}

/**
 * Initialize drag and drop for widgets
 */
function initDragAndDrop() {
    const container = document.querySelector('#dashboardPage');
    if (!container) return;

    let draggedWidget = null;

    container.querySelectorAll('.dashboard-widget, .card').forEach(widget => {
        widget.addEventListener('dragstart', (e) => {
            draggedWidget = widget;
            widget.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', widget.outerHTML);
        });

        widget.addEventListener('dragend', () => {
            widget.classList.remove('dragging');
            draggedWidget = null;
        });

        widget.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';

            if (draggedWidget && draggedWidget !== widget) {
                const rect = widget.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;

                if (e.clientY < midY) {
                    widget.classList.add('drag-over-top');
                    widget.classList.remove('drag-over-bottom');
                } else {
                    widget.classList.add('drag-over-bottom');
                    widget.classList.remove('drag-over-top');
                }
            }
        });

        widget.addEventListener('dragleave', () => {
            widget.classList.remove('drag-over-top', 'drag-over-bottom');
        });

        widget.addEventListener('drop', (e) => {
            e.preventDefault();
            widget.classList.remove('drag-over-top', 'drag-over-bottom');

            if (draggedWidget && draggedWidget !== widget) {
                const rect = widget.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;
                const parent = widget.parentNode;

                if (e.clientY < midY) {
                    parent.insertBefore(draggedWidget, widget);
                } else {
                    parent.insertBefore(draggedWidget, widget.nextSibling);
                }

                // Update order in layout
                updateWidgetOrder();
                saveDashboardLayout();
                showToast('Dashboard layout updated', 'success');
            }
        });
    });
}

/**
 * Update widget order based on DOM position
 */
function updateWidgetOrder() {
    const container = document.querySelector('#dashboardPage');
    if (!container) return;

    const widgets = container.querySelectorAll('.dashboard-widget, .card[id]');
    dashboardLayout.order = [];

    widgets.forEach((widget, index) => {
        const id = widget.id;
        if (id && dashboardLayout.widgets[id]) {
            dashboardLayout.widgets[id].order = index;
            dashboardLayout.order.push(id);
        }
    });
}

/**
 * Toggle widget visibility
 */
function toggleWidgetVisibility(widgetId) {
    if (!dashboardLayout.widgets[widgetId]) {
        dashboardLayout.widgets[widgetId] = { visible: true, collapsed: false, order: 99 };
    }

    dashboardLayout.widgets[widgetId].visible = !dashboardLayout.widgets[widgetId].visible;

    const widget = document.getElementById(widgetId);
    if (widget) {
        widget.style.display = dashboardLayout.widgets[widgetId].visible ? '' : 'none';
    }

    saveDashboardLayout();
    showToast(dashboardLayout.widgets[widgetId].visible ? 'Widget shown' : 'Widget hidden', 'info');
}

/**
 * Toggle widget collapsed state
 */
function toggleWidgetCollapse(widgetId) {
    if (!dashboardLayout.widgets[widgetId]) return;

    dashboardLayout.widgets[widgetId].collapsed = !dashboardLayout.widgets[widgetId].collapsed;

    const widget = document.getElementById(widgetId);
    if (widget) {
        widget.classList.toggle('widget-collapsed', dashboardLayout.widgets[widgetId].collapsed);
    }

    saveDashboardLayout();
}

/**
 * Show dashboard customization modal
 */
function showDashboardCustomizeModal() {
    const existingModal = document.getElementById('dashboardCustomizeModal');
    if (existingModal) existingModal.remove();

    const modal = document.createElement('div');
    modal.id = 'dashboardCustomizeModal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal" style="max-width: 500px;">
            <div class="modal-header">
                <h3>Customize Dashboard</h3>
                <button class="close-btn" onclick="closeDashboardCustomizeModal()">×</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 16px; color: var(--text-secondary);">
                    Drag widgets to reorder, or toggle visibility below.
                </p>
                <div class="widget-list" style="display: flex; flex-direction: column; gap: 8px;">
                    ${Object.entries(DASHBOARD_WIDGETS).map(([id, config]) => {
                        const widgetConfig = dashboardLayout.widgets[id] || { visible: config.default };
                        return `
                            <div class="widget-toggle-item" style="display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--bg-tertiary); border-radius: 8px;">
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <span style="font-size: 1.5em;">${config.icon}</span>
                                    <span>${config.name}</span>
                                </div>
                                <label class="toggle-switch">
                                    <input type="checkbox" ${widgetConfig.visible ? 'checked' : ''} onchange="toggleWidgetVisibility('${id}')">
                                    <span class="toggle-slider"></span>
                                </label>
                            </div>
                        `;
                    }).join('')}
                </div>
                <div style="margin-top: 16px; display: flex; gap: 8px;">
                    <button class="btn btn-secondary" onclick="resetDashboardLayout(); closeDashboardCustomizeModal();">
                        Reset to Default
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.style.display = 'flex';
}

/**
 * Close dashboard customization modal
 */
function closeDashboardCustomizeModal() {
    const modal = document.getElementById('dashboardCustomizeModal');
    if (modal) modal.remove();
}

// UX-006 Exports
window.initCustomizableDashboard = initCustomizableDashboard;
window.toggleWidgetVisibility = toggleWidgetVisibility;
window.toggleWidgetCollapse = toggleWidgetCollapse;
window.showDashboardCustomizeModal = showDashboardCustomizeModal;
window.closeDashboardCustomizeModal = closeDashboardCustomizeModal;
window.resetDashboardLayout = resetDashboardLayout;

// ==============================================================================
// UX-008: Improved Mobile Experience
// Touch gestures, responsive tables, bottom navigation
// ==============================================================================

/**
 * Initialize mobile-specific features
 */
function initMobileExperience() {
    if (!isMobileDevice()) return;

    initTouchGestures();
    initResponsiveTables();
    initBottomNavigation();
    initPullToRefresh();
}

/**
 * Check if device is mobile
 */
function isMobileDevice() {
    return window.innerWidth <= 768 || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

/**
 * Initialize touch gestures for mobile
 */
function initTouchGestures() {
    let touchStartX = 0;
    let touchStartY = 0;
    const sidebar = document.getElementById('mainSidebar');

    document.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        const deltaX = touchEndX - touchStartX;
        const deltaY = touchEndY - touchStartY;

        // Horizontal swipe detection (min 50px, mostly horizontal)
        if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY) * 2) {
            if (deltaX > 0 && touchStartX < 30) {
                // Swipe right from edge - open sidebar
                if (sidebar) sidebar.classList.add('active');
            } else if (deltaX < 0 && sidebar?.classList.contains('active')) {
                // Swipe left - close sidebar
                sidebar.classList.remove('active');
            }
        }
    }, { passive: true });
}

/**
 * Make tables responsive with horizontal scroll
 */
function initResponsiveTables() {
    document.querySelectorAll('table').forEach(table => {
        if (!table.parentElement?.classList.contains('table-responsive')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'table-responsive';
            wrapper.style.cssText = 'overflow-x: auto; -webkit-overflow-scrolling: touch;';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        }
    });
}

/**
 * Initialize bottom navigation for mobile
 */
function initBottomNavigation() {
    const existingNav = document.getElementById('bottomNav');
    if (existingNav) return;

    const bottomNav = document.createElement('nav');
    bottomNav.id = 'bottomNav';
    bottomNav.className = 'bottom-nav';
    bottomNav.innerHTML = `
        <a href="#" class="bottom-nav-item active" data-page="dashboard" onclick="navigateTo('dashboard')">
            <span class="nav-icon">📊</span>
            <span class="nav-label">Home</span>
        </a>
        <a href="#" class="bottom-nav-item" data-page="competitors" onclick="navigateTo('competitors')">
            <span class="nav-icon">🏢</span>
            <span class="nav-label">Competitors</span>
        </a>
        <a href="#" class="bottom-nav-item" data-page="newsfeed" onclick="navigateTo('newsfeed')">
            <span class="nav-icon">📰</span>
            <span class="nav-label">News</span>
        </a>
        <a href="#" class="bottom-nav-item" data-page="analytics" onclick="navigateTo('analytics')">
            <span class="nav-icon">📈</span>
            <span class="nav-label">Analytics</span>
        </a>
        <a href="#" class="bottom-nav-item" onclick="toggleSidebar()">
            <span class="nav-icon">☰</span>
            <span class="nav-label">More</span>
        </a>
    `;

    document.body.appendChild(bottomNav);
}

/**
 * Initialize pull-to-refresh functionality
 */
function initPullToRefresh() {
    let startY = 0;
    let currentY = 0;
    let refreshing = false;

    const mainContent = document.querySelector('.main-content');
    if (!mainContent) return;

    mainContent.addEventListener('touchstart', (e) => {
        if (mainContent.scrollTop === 0) {
            startY = e.touches[0].clientY;
        }
    }, { passive: true });

    mainContent.addEventListener('touchmove', (e) => {
        if (startY > 0 && !refreshing) {
            currentY = e.touches[0].clientY;
            const pullDistance = currentY - startY;

            if (pullDistance > 0 && pullDistance < 150) {
                mainContent.style.transform = `translateY(${pullDistance * 0.3}px)`;
            }
        }
    }, { passive: true });

    mainContent.addEventListener('touchend', async () => {
        const pullDistance = currentY - startY;

        if (pullDistance > 80 && !refreshing) {
            refreshing = true;
            showToast('Refreshing...', 'info');

            try {
                await loadDashboard();
                showToast('Dashboard refreshed!', 'success');
            } catch (e) {
                showToast('Refresh failed', 'error');
            }

            refreshing = false;
        }

        mainContent.style.transform = '';
        startY = 0;
        currentY = 0;
    }, { passive: true });
}


// UX-008 Exports
window.initMobileExperience = initMobileExperience;
window.isMobileDevice = isMobileDevice;
window.navigateTo = navigateTo;

// ==============================================================================
// UX-009: Accessibility (WCAG 2.1)
// Screen reader support, keyboard navigation, color contrast
// ==============================================================================

/**
 * Initialize accessibility features
 */
function initAccessibility() {
    initAriaLabels();
    initKeyboardNavigation();
    initFocusManagement();
    initReducedMotion();
    initHighContrastMode();
}

/**
 * Add ARIA labels to interactive elements
 */
function initAriaLabels() {
    // Add aria-labels to buttons without text
    document.querySelectorAll('button:not([aria-label])').forEach(btn => {
        if (!btn.textContent.trim() || btn.textContent.trim().length < 2) {
            const title = btn.getAttribute('title');
            if (title) btn.setAttribute('aria-label', title);
        }
    });

    // Add role to navigation
    document.querySelectorAll('.nav-menu').forEach(nav => {
        nav.setAttribute('role', 'navigation');
        nav.setAttribute('aria-label', 'Main navigation');
    });

    // Add role to main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.setAttribute('role', 'main');
        mainContent.setAttribute('aria-label', 'Main content');
    }

    // Add live region for notifications
    let liveRegion = document.getElementById('ariaLiveRegion');
    if (!liveRegion) {
        liveRegion = document.createElement('div');
        liveRegion.id = 'ariaLiveRegion';
        liveRegion.setAttribute('role', 'status');
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        liveRegion.className = 'sr-only';
        liveRegion.style.cssText = 'position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;';
        document.body.appendChild(liveRegion);
    }
}

/**
 * Announce message to screen readers
 */
function announceToScreenReader(message) {
    const liveRegion = document.getElementById('ariaLiveRegion');
    if (liveRegion) {
        liveRegion.textContent = '';
        setTimeout(() => { liveRegion.textContent = message; }, 100);
    }
}

/**
 * Initialize keyboard navigation
 */
function initKeyboardNavigation() {
    // Skip link for keyboard users
    let skipLink = document.getElementById('skipToMain');
    if (!skipLink) {
        skipLink = document.createElement('a');
        skipLink.id = 'skipToMain';
        skipLink.href = '#main-content';
        skipLink.className = 'skip-link';
        skipLink.textContent = 'Skip to main content';
        skipLink.style.cssText = 'position: absolute; top: -40px; left: 0; background: var(--primary-color); color: white; padding: 8px 16px; z-index: 10000; transition: top 0.3s;';
        skipLink.addEventListener('focus', () => { skipLink.style.top = '0'; });
        skipLink.addEventListener('blur', () => { skipLink.style.top = '-40px'; });
        document.body.insertBefore(skipLink, document.body.firstChild);
    }

    // Tab trap for modals
    document.addEventListener('keydown', (e) => {
        const modal = document.querySelector('.modal-overlay[style*="display: flex"]');
        if (modal && e.key === 'Tab') {
            const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (focusable.length === 0) return;

            const first = focusable[0];
            const last = focusable[focusable.length - 1];

            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }

        // Escape closes modals
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal-overlay[style*="display: flex"]');
            if (modal) {
                const closeBtn = modal.querySelector('.close-btn');
                if (closeBtn) closeBtn.click();
            }
        }
    });
}

/**
 * Manage focus for dynamic content
 */
function initFocusManagement() {
    // Focus first interactive element when modal opens
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.classList?.contains('modal-overlay')) {
                    const firstFocusable = node.querySelector('button, [href], input, select, textarea');
                    if (firstFocusable) {
                        setTimeout(() => firstFocusable.focus(), 100);
                    }
                }
            });
        });
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

/**
 * Respect reduced motion preference
 */
function initReducedMotion() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    if (prefersReducedMotion.matches) {
        document.documentElement.style.setProperty('--transition', 'none');
        document.body.classList.add('reduced-motion');
    }

    prefersReducedMotion.addEventListener('change', (e) => {
        if (e.matches) {
            document.documentElement.style.setProperty('--transition', 'none');
            document.body.classList.add('reduced-motion');
        } else {
            document.documentElement.style.setProperty('--transition', 'all 0.2s ease-in-out');
            document.body.classList.remove('reduced-motion');
        }
    });
}

/**
 * High contrast mode support
 */
function initHighContrastMode() {
    const prefersHighContrast = window.matchMedia('(prefers-contrast: more)');

    if (prefersHighContrast.matches) {
        document.body.classList.add('high-contrast');
    }

    prefersHighContrast.addEventListener('change', (e) => {
        document.body.classList.toggle('high-contrast', e.matches);
    });
}

// UX-009 Exports
window.initAccessibility = initAccessibility;
window.announceToScreenReader = announceToScreenReader;

// ==============================================================================
// Discovery Scout Bug Fixes (Session 34)
// ==============================================================================

/**
 * BUG-21: Delete the currently selected profile
 */
async function deleteCurrentProfile() {
    const selector = document.getElementById('profileSelector');
    if (!selector || !selector.value) {
        showToast('Please select a profile to delete', 'warning');
        return;
    }

    const profileId = selector.value;
    const profileName = selector.options[selector.selectedIndex].text;

    if (!confirm(`Are you sure you want to delete the profile "${profileName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/discovery/profiles/${profileId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (response.ok) {
            showToast(`Profile "${profileName}" deleted`, 'success');
            await loadDiscoveryProfiles();
        } else {
            throw new Error('Failed to delete profile');
        }
    } catch (error) {
        console.error('Delete profile error:', error);
        showToast('Failed to delete profile: ' + error.message, 'error');
    }
}

/**
 * BUG-16: Toggle schedule panel visibility
 */
function toggleSchedulePanel() {
    const panel = document.getElementById('discoverySchedulePanel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';

        // Set default datetime to tomorrow at 9 AM
        if (panel.style.display === 'block') {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            tomorrow.setHours(9, 0, 0, 0);
            const input = document.getElementById('scheduleRunTime');
            if (input) {
                input.value = tomorrow.toISOString().slice(0, 16);
            }
        }
    }
}

/**
 * BUG-16: Schedule a discovery run
 */
async function scheduleDiscoveryRun() {
    const input = document.getElementById('scheduleRunTime');
    if (!input || !input.value) {
        showToast('Please select a date and time', 'warning');
        return;
    }

    const scheduledTime = new Date(input.value);
    if (scheduledTime <= new Date()) {
        showToast('Please select a future date and time', 'warning');
        return;
    }

    const criteria = collectQualificationCriteria();

    try {
        const response = await fetch(`${API_BASE}/api/discovery/schedule`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                scheduled_at: scheduledTime.toISOString(),
                criteria: criteria,
                max_candidates: parseInt(document.getElementById('discoveryMaxCandidates')?.value) || 10
            })
        });

        if (response.ok) {
            showToast(`Discovery scheduled for ${scheduledTime.toLocaleString()}`, 'success');
            toggleSchedulePanel();
        } else {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to schedule');
        }
    } catch (error) {
        console.error('Schedule error:', error);
        showToast('Failed to schedule discovery: ' + error.message, 'error');
    }
}

/**
 * BUG-29, BUG-30: Show discovery history modal
 */
function showDiscoveryHistoryModal() {
    const modal = document.getElementById('discoveryHistoryModal');
    if (modal) {
        modal.style.display = 'block';
        loadDiscoveryHistory();
    }
}

/**
 * Close discovery history modal
 */
function closeDiscoveryHistoryModal() {
    const modal = document.getElementById('discoveryHistoryModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * BUG-30: Load discovery history data
 */
async function loadDiscoveryHistory() {
    const content = document.getElementById('discoveryHistoryContent');
    if (!content) return;

    content.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="spinner"></div><p>Loading history...</p></div>';

    try {
        const response = await fetchAPI('/api/discovery/history');
        const history = Array.isArray(response) ? response : (response.competitors || response.history || []);

        if (!Array.isArray(history) || history.length === 0) {
            content.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #64748b;">
                    <p style="font-size: 48px; margin-bottom: 16px;">📋</p>
                    <h4 style="margin-bottom: 8px;">No Discovered Competitors Yet</h4>
                    <p>Run a discovery and add competitors to see them here.</p>
                </div>
            `;
            return;
        }

        content.innerHTML = `
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #f1f5f9; border-bottom: 2px solid #e2e8f0;">
                        <th style="padding: 12px; text-align: left; font-weight: 600;">Date Discovered</th>
                        <th style="padding: 12px; text-align: left; font-weight: 600;">Name</th>
                        <th style="padding: 12px; text-align: left; font-weight: 600;">Website</th>
                        <th style="padding: 12px; text-align: center; font-weight: 600;">Quality Score</th>
                        <th style="padding: 12px; text-align: left; font-weight: 600;">Notes</th>
                    </tr>
                </thead>
                <tbody>
                    ${history.map(comp => `
                        <tr style="border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 12px;">${(comp.discovered_at || comp.created_at) ? new Date(comp.discovered_at || comp.created_at).toLocaleString() : 'Unknown'}</td>
                            <td style="padding: 12px; font-weight: 600;">${escapeHtml(comp.name || 'Unknown')}</td>
                            <td style="padding: 12px;">
                                <a href="${escapeHtml(comp.website || '#')}" target="_blank" style="color: var(--primary-color); text-decoration: none;">
                                    ${escapeHtml(comp.website || 'N/A')}
                                </a>
                            </td>
                            <td style="padding: 12px; text-align: center;">
                                <span style="padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
                                    background: ${(comp.score || comp.data_quality_score || 0) >= 70 ? '#dcfce7' : (comp.score || comp.data_quality_score || 0) >= 40 ? '#fef3c7' : '#fef2f2'};
                                    color: ${(comp.score || comp.data_quality_score || 0) >= 70 ? '#16a34a' : (comp.score || comp.data_quality_score || 0) >= 40 ? '#d97706' : '#dc2626'};">
                                    ${comp.score || comp.data_quality_score || 'N/A'}%
                                </span>
                            </td>
                            <td style="padding: 12px; font-size: 12px; color: #64748b; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                ${escapeHtml((comp.notes || '').substring(0, 100))}${(comp.notes || '').length > 100 ? '...' : ''}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading discovery history:', error);
        content.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #64748b;">
                <p style="color: #dc2626;">Error loading history</p>
                <p style="font-size: 12px;">${error.message}</p>
            </div>
        `;
    }
}

/**
 * BUG-32, BUG-33, BUG-34: Validate discovery criteria before running
 */
function validateDiscoveryCriteria(criteria) {
    const errors = [];
    const warnings = [];  // v7.0.8: Add warnings for conflicting criteria

    // Check if at least some criteria is selected
    const hasSegments = criteria.target_segments && criteria.target_segments.length > 0;
    const hasCapabilities = criteria.required_capabilities && criteria.required_capabilities.length > 0;
    const hasGeography = criteria.geography && criteria.geography.length > 0;

    if (!hasSegments && !hasCapabilities && !hasGeography) {
        errors.push('Please select at least one target market, capability, or geography');
    }

    // Validate employee count range (BUG-33)
    const minEmp = criteria.company_size?.min_employees;
    const maxEmp = criteria.company_size?.max_employees;
    if (minEmp && maxEmp && minEmp > maxEmp) {
        errors.push('Minimum employee count cannot be greater than maximum');
    }

    // Sanitize keywords (BUG-34)
    if (criteria.custom_keywords?.include) {
        criteria.custom_keywords.include = criteria.custom_keywords.include.map(k =>
            k.replace(/<[^>]*>/g, '').trim()
        ).filter(k => k);
    }
    if (criteria.custom_keywords?.exclude) {
        criteria.custom_keywords.exclude = criteria.custom_keywords.exclude.map(k =>
            k.replace(/<[^>]*>/g, '').trim()
        ).filter(k => k);
    }

    // v7.0.8: Check for conflicting keywords
    const includeKw = (criteria.custom_keywords?.include || []).map(k => k.toLowerCase());
    const excludeKw = (criteria.custom_keywords?.exclude || []).map(k => k.toLowerCase());
    const conflictingKeywords = includeKw.filter(k => excludeKw.includes(k));
    if (conflictingKeywords.length > 0) {
        warnings.push(`Keywords "${conflictingKeywords.join('", "')}" appear in both include and exclude lists`);
    }

    // v7.0.8: Check for potentially conflicting funding stage selections
    const funding = criteria.funding_stages || [];
    if (funding.includes('series_a') && funding.includes('profitable')) {
        warnings.push('Selecting both "Series A+" and "Profitable" may significantly reduce results (most profitable companies are not raising)');
    }
    if (funding.includes('seed') && funding.includes('public')) {
        warnings.push('Selecting both "Seed Stage" and "Public Company" is unusual - results may be limited');
    }

    // v7.0.8: Warning for very broad criteria (may return too many results)
    const totalSelections = (criteria.target_segments?.length || 0) +
                            (criteria.required_capabilities?.length || 0) +
                            (criteria.geography?.length || 0);
    if (totalSelections >= 10 && (criteria.exclusions?.length || 0) < 2) {
        warnings.push('Very broad criteria selected - consider adding exclusions to narrow results');
    }

    // v7.0.8: Warning for very narrow criteria (may return too few results)
    if (totalSelections === 1 && minEmp && maxEmp && (maxEmp - minEmp) < 100) {
        warnings.push('Very narrow criteria - may find few or no results');
    }

    return { valid: errors.length === 0, errors, warnings, criteria };
}

/**
 * BUG-2: Initialize default checkboxes on Discovery Scout page load
 */
function initializeDiscoveryDefaults() {
    // Default checkboxes: Ambulatory Care, PXP, US, Exclusions (Consulting, Pharma, Devices)
    const defaultSelections = {
        segment: ['ambulatory'],
        capability: ['pxp'],
        geography: ['us'],
        exclude: ['consulting', 'pharma', 'devices']
    };

    Object.entries(defaultSelections).forEach(([name, values]) => {
        // First uncheck all
        document.querySelectorAll(`input[name="${name}"]`).forEach(cb => {
            cb.checked = false;
        });
        // Then check the defaults
        values.forEach(value => {
            const checkbox = document.querySelector(`input[name="${name}"][value="${value}"]`);
            if (checkbox) checkbox.checked = true;
        });
    });
}

// ==============================================================================
// Activity Audit Trail (Records Page)
// ==============================================================================

let activityLogPage = 1;
let activityLogHasMore = false;
let auditTrendChartInstance = null;
let activityLogLoaded = false;

/**
 * Switch between Competitor Records and Activity Log tabs
 */
function switchRecordsTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.activity-tab').forEach(t => t.classList.remove('active'));
    const activeBtn = document.querySelector(`.activity-tab[data-tab="${tabName}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    // Show/hide tab content
    const recordsTab = document.getElementById('competitorRecordsTab');
    const activityTab = document.getElementById('activityLogTab');
    if (recordsTab) {
        recordsTab.classList.toggle('active', tabName === 'competitorRecords');
        recordsTab.style.display = tabName === 'competitorRecords' ? 'block' : 'none';
    }
    if (activityTab) {
        activityTab.classList.toggle('active', tabName === 'activityLog');
        activityTab.style.display = tabName === 'activityLog' ? 'block' : 'none';
    }

    // Load activity data on first switch
    if (tabName === 'activityLog' && !activityLogLoaded) {
        activityLogLoaded = true;
        loadActivitySummary();
        loadActivityLogs(true);
        loadActivityTrendChart();
    }
}

/**
 * Format a timestamp into relative time (e.g. "2 hours ago")
 */
function formatActivityTime(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHr = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHr / 24);

    if (diffSec < 60) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;
    return date.toLocaleDateString();
}

/**
 * Get CSS class for an action type badge
 */
function getActivityBadgeClass(actionType) {
    if (!actionType) return 'default';
    const type = actionType.toLowerCase();
    if (type.includes('create') || type.includes('add')) return 'create';
    if (type.includes('update') || type.includes('edit') || type.includes('modify')) return 'update';
    if (type.includes('delete') || type.includes('remove')) return 'delete';
    if (type.includes('login') || type.includes('auth') || type.includes('logout')) return 'login';
    if (type.includes('export') || type.includes('download')) return 'export';
    if (type.includes('ai') || type.includes('query') || type.includes('chat') || type.includes('agent')) return 'ai_query';
    if (type.includes('view') || type.includes('read')) return 'view';
    return 'default';
}

/**
 * Load activity summary stats
 */
async function loadActivitySummary() {
    try {
        const data = await fetchAPI('/api/activity-logs/summary?days=7', { silent: true });
        if (!data) return;

        const totalEl = document.getElementById('activityTotalActions');
        const usersEl = document.getElementById('activityUniqueUsers');
        const todayEl = document.getElementById('activityTodayActions');
        const topEl = document.getElementById('activityTopType');

        if (totalEl) totalEl.textContent = (data.total_actions || 0).toLocaleString();
        if (usersEl) usersEl.textContent = data.unique_users || 0;

        // Calculate today's actions from by_user if available
        if (todayEl) todayEl.textContent = data.today_actions || data.total_actions || 0;

        // Find top action type
        if (topEl && data.by_type) {
            const sorted = Object.entries(data.by_type).sort((a, b) => b[1] - a[1]);
            topEl.textContent = sorted.length > 0 ? sorted[0][0] : '--';
        }

        // Populate action type filter dropdown from summary
        const typeFilter = document.getElementById('activityTypeFilter');
        if (typeFilter && data.by_type) {
            const currentVal = typeFilter.value;
            typeFilter.innerHTML = '<option value="">All Action Types</option>';
            Object.keys(data.by_type).sort().forEach(type => {
                const opt = document.createElement('option');
                opt.value = type;
                opt.textContent = `${type} (${data.by_type[type]})`;
                typeFilter.appendChild(opt);
            });
            typeFilter.value = currentVal;
        }
    } catch (err) {
        console.error('[Activity] Failed to load summary:', err);
    }
}

/**
 * Load activity logs with pagination
 */
async function loadActivityLogs(reset = false) {
    if (reset) {
        activityLogPage = 1;
        const timeline = document.getElementById('activityTimeline');
        if (timeline) timeline.innerHTML = '<div class="activity-loading" style="text-align:center; padding:40px; color: var(--text-secondary);">Loading activity logs...</div>';
    }

    const typeFilter = document.getElementById('activityTypeFilter');
    const searchFilter = document.getElementById('activitySearchFilter');
    const dateFrom = document.getElementById('activityDateFrom');
    const dateTo = document.getElementById('activityDateTo');

    let url = `/api/activity-logs?page=${activityLogPage}&per_page=50`;
    if (typeFilter && typeFilter.value) url += `&action_type=${encodeURIComponent(typeFilter.value)}`;
    if (searchFilter && searchFilter.value) url += `&search=${encodeURIComponent(searchFilter.value)}`;
    if (dateFrom && dateFrom.value) url += `&date_from=${encodeURIComponent(dateFrom.value)}`;
    if (dateTo && dateTo.value) url += `&date_to=${encodeURIComponent(dateTo.value)}`;

    try {
        const data = await fetchAPI(url, { silent: true });
        if (!data) return;

        const timeline = document.getElementById('activityTimeline');
        if (!timeline) return;

        // Clear loading state on first load
        if (activityLogPage === 1) {
            timeline.innerHTML = '';
        }

        const logs = data.logs || [];
        if (logs.length === 0 && activityLogPage === 1) {
            timeline.innerHTML = '<div style="text-align:center; padding:40px; color: var(--text-secondary);">No activity logs found.</div>';
        }

        logs.forEach(log => {
            const entry = document.createElement('div');
            entry.className = 'activity-entry';

            const badgeClass = getActivityBadgeClass(log.action_type);
            const relTime = formatActivityTime(log.created_at);
            const userEmail = escapeHtml(log.user_email || 'System');
            const actionType = escapeHtml(log.action_type || 'unknown');
            const details = escapeHtml(log.action_details || '');

            let metaHtml = '';
            if (log.entity_type || log.entity_id) {
                const entityType = escapeHtml(log.entity_type || '');
                const entityId = escapeHtml(String(log.entity_id || ''));
                metaHtml += `<span>Entity: ${entityType}${entityId ? ' #' + entityId : ''}</span>`;
            }
            if (log.ip_address) {
                metaHtml += `<span>IP: ${escapeHtml(log.ip_address)}</span>`;
            }

            entry.innerHTML = `
                <div class="activity-entry-header">
                    <span class="activity-entry-time">${escapeHtml(relTime)}</span>
                    <span class="activity-entry-user">${userEmail}</span>
                    <span class="activity-badge ${escapeHtml(badgeClass)}">${actionType}</span>
                </div>
                <div class="activity-entry-details">${details}</div>
                ${metaHtml ? `<div class="activity-entry-meta">${metaHtml}</div>` : ''}
            `;
            timeline.appendChild(entry);
        });

        // Show/hide Load More button
        const total = data.total || 0;
        const loaded = activityLogPage * 50;
        activityLogHasMore = loaded < total;
        const loadMoreBtn = document.getElementById('activityLoadMoreBtn');
        if (loadMoreBtn) {
            loadMoreBtn.style.display = activityLogHasMore ? 'inline-block' : 'none';
        }
    } catch (err) {
        console.error('[Activity] Failed to load logs:', err);
        const timeline = document.getElementById('activityTimeline');
        if (timeline && activityLogPage === 1) {
            timeline.innerHTML = '<div style="text-align:center; padding:40px; color: var(--danger-color, #f87171);">Failed to load activity logs. Please try again.</div>';
        }
    }
}

/**
 * Load more activity log entries (pagination)
 */
function loadMoreActivityLogs() {
    activityLogPage++;
    loadActivityLogs(false);
}

/**
 * Apply activity log filters
 */
function applyActivityFilters() {
    loadActivityLogs(true);
}

/**
 * Reset activity log filters
 */
function resetActivityFilters() {
    const typeFilter = document.getElementById('activityTypeFilter');
    const searchFilter = document.getElementById('activitySearchFilter');
    const dateFrom = document.getElementById('activityDateFrom');
    const dateTo = document.getElementById('activityDateTo');

    if (typeFilter) typeFilter.value = '';
    if (searchFilter) searchFilter.value = '';
    if (dateFrom) dateFrom.value = '';
    if (dateTo) dateTo.value = '';

    loadActivityLogs(true);
}

/**
 * Load and render the Activity Trend chart (Chart.js line chart)
 */
async function loadActivityTrendChart() {
    try {
        const data = await fetchAPI('/api/analytics/activity-trend?days=30', { silent: true });
        if (!data || !data.labels) return;

        const canvas = document.getElementById('activityTrendChart');
        if (!canvas) return;

        // Destroy previous instance to prevent memory leak
        if (auditTrendChartInstance) {
            auditTrendChartInstance.destroy();
            auditTrendChartInstance = null;
        }

        const ctx = canvas.getContext('2d');
        auditTrendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'News Activity',
                        data: data.news_activity || [],
                        borderColor: '#60a5fa',
                        backgroundColor: 'rgba(96, 165, 250, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#60a5fa'
                    },
                    {
                        label: 'Product Updates',
                        data: data.product_updates || [],
                        borderColor: '#34d399',
                        backgroundColor: 'rgba(52, 211, 153, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#34d399'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#e2e8f0',
                            font: { size: 12 }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#94a3b8', font: { size: 11 }, maxRotation: 45 },
                        grid: { color: 'rgba(148, 163, 184, 0.1)' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#94a3b8', font: { size: 11 } },
                        grid: { color: 'rgba(148, 163, 184, 0.1)' }
                    }
                }
            }
        });
    } catch (err) {
        console.error('[Activity] Failed to load trend chart:', err);
    }
}

// Export activity functions to window
window.switchRecordsTab = switchRecordsTab;
window.applyActivityFilters = applyActivityFilters;
window.resetActivityFilters = resetActivityFilters;
window.loadMoreActivityLogs = loadMoreActivityLogs;

// Export new functions to window
window.deleteCurrentProfile = deleteCurrentProfile;
window.toggleSchedulePanel = toggleSchedulePanel;
window.scheduleDiscoveryRun = scheduleDiscoveryRun;
window.showDiscoveryHistoryModal = showDiscoveryHistoryModal;
window.closeDiscoveryHistoryModal = closeDiscoveryHistoryModal;
window.loadDiscoveryHistory = loadDiscoveryHistory;
window.validateDiscoveryCriteria = validateDiscoveryCriteria;
window.initializeDiscoveryDefaults = initializeDiscoveryDefaults;

// ==============================================================================
// Analytics: Win/Loss Deal Tracker
// ==============================================================================

let winLossChart = null;
let winLossDeals = [];

async function loadWinLossDeals() {
    try {
        const data = await fetchAPI('/api/analytics/win-loss', { silent: true });
        winLossDeals = data?.deals || (Array.isArray(data) ? data : []);
        renderWinLossUI();
    } catch (e) {
        console.error('[Analytics] Win/loss load failed:', e);
    }
}

function renderWinLossUI() {
    const won = winLossDeals.filter(d => d.outcome === 'won').length;
    const lost = winLossDeals.filter(d => d.outcome === 'lost').length;
    const total = winLossDeals.length;
    const rate = total > 0 ? Math.round((won / total) * 100) : 0;

    const totalEl = document.getElementById('winLossTotal');
    const wonEl = document.getElementById('winLossWon');
    const lostEl = document.getElementById('winLossLost');
    const rateEl = document.getElementById('winLossRate');

    if (totalEl) totalEl.textContent = total;
    if (wonEl) wonEl.textContent = won;
    if (lostEl) lostEl.textContent = lost;
    if (rateEl) rateEl.textContent = rate + '%';

    const ctx = document.getElementById('winLossChart')?.getContext('2d');
    if (ctx) {
        if (winLossChart) winLossChart.destroy();
        winLossChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Won', 'Lost'],
                datasets: [{
                    data: [won, lost],
                    backgroundColor: ['#22c55e', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#e2e8f0', padding: 12 }
                    }
                }
            }
        });
    }

    const tbody = document.getElementById('winLossBody');
    if (tbody) {
        if (winLossDeals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:24px;">No deals recorded yet. Click "+ Add Deal" to start tracking.</td></tr>';
        } else {
            tbody.innerHTML = winLossDeals.map(d => {
                const comp = competitors.find(c => c.id === d.competitor_id);
                const outcomeClass = d.outcome === 'won' ? 'win' : 'loss';
                return `<tr>
                    <td>${formatDate(d.deal_date || d.created_at)}</td>
                    <td>${escapeHtml(comp?.name || d.competitor_name || 'Unknown')}</td>
                    <td>${d.deal_size ? '$' + Number(d.deal_size).toLocaleString() : 'N/A'}</td>
                    <td><span class="win-loss-outcome ${outcomeClass}">${escapeHtml(d.outcome || 'N/A')}</span></td>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(d.notes || '')}</td>
                </tr>`;
            }).join('');
        }
    }
}

function showAddDealModal() {
    const compOptions = competitors.map(c =>
        `<option value="${c.id}">${escapeHtml(c.name)}</option>`
    ).join('');

    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'addDealModal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:480px;">
            <div class="modal-header">
                <h3>Add Win/Loss Deal</h3>
                <button class="modal-close" onclick="document.getElementById('addDealModal')?.remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Competitor</label>
                    <select id="dealCompetitor" class="form-select">${compOptions}</select>
                </div>
                <div class="form-group">
                    <label>Deal Size ($)</label>
                    <input type="number" id="dealSize" class="form-input" placeholder="e.g. 50000">
                </div>
                <div class="form-group">
                    <label>Outcome</label>
                    <select id="dealOutcome" class="form-select">
                        <option value="won">Won</option>
                        <option value="lost">Lost</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Date</label>
                    <input type="date" id="dealDate" class="form-input" value="${new Date().toISOString().split('T')[0]}">
                </div>
                <div class="form-group">
                    <label>Notes</label>
                    <textarea id="dealNotes" class="form-input" rows="3" placeholder="Key factors in the outcome..."></textarea>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="document.getElementById('addDealModal')?.remove()">Cancel</button>
                <button class="btn btn-primary" onclick="submitDeal()">Save Deal</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function submitDeal() {
    const competitorId = document.getElementById('dealCompetitor')?.value;
    const dealSize = document.getElementById('dealSize')?.value;
    const outcome = document.getElementById('dealOutcome')?.value;
    const dealDate = document.getElementById('dealDate')?.value;
    const notes = document.getElementById('dealNotes')?.value;

    if (!competitorId || !outcome) {
        showToast('Please select a competitor and outcome', 'warning');
        return;
    }

    try {
        await fetchAPI('/api/analytics/deals', {
            method: 'POST',
            body: JSON.stringify({
                competitor_id: parseInt(competitorId),
                deal_size: dealSize ? parseFloat(dealSize) : null,
                outcome: outcome,
                deal_date: dealDate || null,
                notes: notes || ''
            })
        });
        document.getElementById('addDealModal')?.remove();
        showToast('Deal recorded successfully', 'success');
        await loadWinLossDeals();
    } catch (e) {
        showToast('Failed to save deal', 'error');
    }
}

window.showAddDealModal = showAddDealModal;
window.submitDeal = submitDeal;
window.loadWinLossDeals = loadWinLossDeals;

// ==============================================================================
// Sales & Marketing: Dimension History Chart
// ==============================================================================

let dimensionHistoryChart = null;

async function loadDimensionHistory() {
    const competitorId = document.getElementById('dimensionCompetitorSelect')?.value;
    if (!competitorId) return;

    const section = document.getElementById('dimensionHistorySection');
    if (section) section.style.display = 'block';

    const metric = document.getElementById('dimensionHistoryMetric')?.value || 'all';

    try {
        const data = await fetchAPI(`/api/sales-marketing/competitors/${competitorId}/dimension-history`, { silent: true });
        const history = data?.history || (Array.isArray(data) ? data : []);

        const ctx = document.getElementById('dimensionHistoryChart')?.getContext('2d');
        if (!ctx) return;

        if (dimensionHistoryChart) dimensionHistoryChart.destroy();

        if (history.length === 0) {
            const container = document.getElementById('dimensionHistoryChart')?.parentElement;
            if (container) {
                container.innerHTML = '<canvas id="dimensionHistoryChart"></canvas><div style="text-align:center;padding:40px;color:var(--text-secondary);">No dimension history available. Save scores to begin tracking changes over time.</div>';
            }
            return;
        }

        const labels = history.map(h => formatDate(h.recorded_at || h.created_at));

        const dimensionColors = {
            product_quality: '#3b82f6',
            market_presence: '#8b5cf6',
            innovation: '#f59e0b',
            customer_satisfaction: '#22c55e',
            pricing_competitiveness: '#ef4444',
            sales_marketing: '#06b6d4',
            partnerships: '#ec4899',
            financial_stability: '#14b8a6',
            talent: '#f97316'
        };

        const dimensionNames = {
            product_quality: 'Product Quality',
            market_presence: 'Market Presence',
            innovation: 'Innovation',
            customer_satisfaction: 'Customer Satisfaction',
            pricing_competitiveness: 'Pricing',
            sales_marketing: 'Sales & Marketing',
            partnerships: 'Partnerships',
            financial_stability: 'Financial Stability',
            talent: 'Talent'
        };

        let datasets = [];
        if (metric === 'all') {
            Object.keys(dimensionColors).forEach(dim => {
                const dimData = history.map(h => h[dim] || h.scores?.[dim] || null);
                if (dimData.some(v => v !== null)) {
                    datasets.push({
                        label: dimensionNames[dim] || dim,
                        data: dimData,
                        borderColor: dimensionColors[dim],
                        backgroundColor: dimensionColors[dim] + '1a',
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.3,
                        fill: false
                    });
                }
            });
        } else {
            const dimData = history.map(h => h[metric] || h.scores?.[metric] || null);
            datasets.push({
                label: dimensionNames[metric] || metric,
                data: dimData,
                borderColor: dimensionColors[metric] || '#6366f1',
                backgroundColor: (dimensionColors[metric] || '#6366f1') + '1a',
                borderWidth: 2,
                pointRadius: 4,
                tension: 0.3,
                fill: true
            });
        }

        dimensionHistoryChart = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: '#e2e8f0', usePointStyle: true, pointStyle: 'circle', padding: 12, font: { size: 11 } }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8', font: { size: 11 } }
                    },
                    y: {
                        beginAtZero: true,
                        max: 10,
                        grid: { color: 'rgba(148,163,184,0.1)' },
                        ticks: { color: '#94a3b8', stepSize: 2 },
                        title: { display: true, text: 'Score (0-10)', color: '#94a3b8' }
                    }
                }
            }
        });
    } catch (e) {
        console.error('[Sales] Dimension history load failed:', e);
    }
}

window.loadDimensionHistory = loadDimensionHistory;

// ==============================================================================
// Sales & Marketing: Playbook PDF Export
// ==============================================================================

async function exportPlaybookPDF() {
    const resultDiv = document.getElementById('playbookResult');
    if (!resultDiv || resultDiv.querySelector('.sm-placeholder')) {
        showToast('Generate a playbook first', 'warning');
        return;
    }

    const competitorName = document.getElementById('playbookCompetitor')?.selectedOptions?.[0]?.textContent || 'Unknown';
    const scenario = document.getElementById('playbookScenario')?.value || 'general';

    if (window.pdfExporter) {
        try {
            const content = resultDiv.innerText || resultDiv.textContent;
            await window.pdfExporter.exportText(content, {
                title: `Sales Playbook - ${competitorName}`,
                subtitle: `Scenario: ${scenario}`,
                filename: `playbook_${competitorName.replace(/[^a-zA-Z0-9]/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`
            });
            showToast('Playbook exported as PDF', 'success');
        } catch (e) {
            console.error('[Playbook] PDF export failed:', e);
            showToast('PDF export failed', 'error');
        }
    } else {
        showToast('PDF exporter not available', 'warning');
    }
}

window.exportPlaybookPDF = exportPlaybookPDF;

// Initialize all new features on page load
document.addEventListener('DOMContentLoaded', () => {
    initCustomizableDashboard();
    initMobileExperience();
    initAccessibility();

    // Initialize Discovery Scout defaults when page loads
    setTimeout(() => {
        initializeDiscoveryDefaults();
        loadDiscoveryProfiles();
    }, 500);

    // Hook dimension history load into competitor select change
    const dimSelect = document.getElementById('dimensionCompetitorSelect');
    if (dimSelect) {
        dimSelect.addEventListener('change', () => {
            setTimeout(() => loadDimensionHistory(), 500);
        });
    }

    // Show playbook export button when result is populated
    const playbookResult = document.getElementById('playbookResult');
    if (playbookResult) {
        const observer = new MutationObserver(() => {
            const exportActions = document.getElementById('playbookExportActions');
            const hasContent = !playbookResult.querySelector('.sm-placeholder');
            if (exportActions) exportActions.style.display = hasContent ? 'block' : 'none';
        });
        observer.observe(playbookResult, { childList: true, subtree: true });
    }
});
