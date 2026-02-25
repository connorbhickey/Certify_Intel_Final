/**
 * Certify Intel - API Module
 * Handles all API communication, authentication headers, and error handling.
 */

export const API_BASE = window.location.origin;

// ============== Authentication ==============

/**
 * Check if user is authenticated, redirect to login if not
 */
export function checkAuth() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login.html';
        return false;
    }
    return true;
}

/**
 * Logout user - clear token and redirect
 */
export function logout() {
    if (window._notificationIntervalId) {
        clearInterval(window._notificationIntervalId);
        window._notificationIntervalId = null;
    }
    localStorage.removeItem('access_token');
    window.location.href = '/login.html';
}

/**
 * Get authorization headers for API calls
 */
export function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// ============== API Error Handling ==============

/**
 * Custom API Error class for better error handling
 */
export class APIError extends Error {
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
export function getErrorMessage(status, endpoint) {
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

// Import showToast lazily to avoid circular dependency
let _showToast = null;
function getShowToast() {
    if (!_showToast) {
        _showToast = window.showToast || function(msg, type) {
            console.warn(`[Toast ${type}]: ${msg}`);
        };
    }
    return _showToast;
}

/**
 * Enhanced API fetch wrapper with better error handling
 */
export async function fetchAPI(endpoint, options = {}) {
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

            // Handle 401 Unauthorized
            if (response.status === 401) {
                console.warn(`[fetchAPI] 401 on ${endpoint} - token may be invalid`);
                if (!window._handling401) {
                    window._handling401 = true;
                    localStorage.removeItem('access_token');
                    setTimeout(() => {
                        window._handling401 = false;
                        window.location.href = '/login.html';
                    }, 500);
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
            if (error.name === 'AbortError') {
                return null;
            }

            // Retry logic for network errors
            if (attempt < retries && (error.name === 'TypeError' || error.status >= 500)) {
                await new Promise(resolve => setTimeout(resolve, retryDelay * (attempt + 1)));
                continue;
            }

            console.error(`API Error: ${endpoint}`, error);

            if (!silent) {
                const message = error instanceof APIError ? error.message : 'Network error. Please check your connection.';
                getShowToast()(message, 'error');
            }

            return null;
        }
    }
}

/**
 * Show persistent error banner at top of page
 */
export function showErrorBanner(message, options = {}) {
    const { action = null, dismissible = true } = options;

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
export function hideErrorBanner() {
    const banner = document.getElementById('errorBanner');
    if (banner) banner.remove();
}

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (!window.API_BASE) window.API_BASE = API_BASE;
if (!window.checkAuth) window.checkAuth = checkAuth;
if (!window.logout) window.logout = logout;
if (!window.getAuthHeaders) window.getAuthHeaders = getAuthHeaders;
if (!window.APIError) window.APIError = APIError;
if (!window.getErrorMessage) window.getErrorMessage = getErrorMessage;
if (!window.fetchAPI) window.fetchAPI = fetchAPI;
if (!window.showErrorBanner) window.showErrorBanner = showErrorBanner;
if (!window.hideErrorBanner) window.hideErrorBanner = hideErrorBanner;
