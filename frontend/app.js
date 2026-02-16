/**
 * Certify Intel - ES6 Module Entry Point
 * Imports core modules and components, initializes the application.
 *
 * This file runs alongside app_v2.js during the migration period.
 * All modules attach their exports to window.* for backward compatibility
 * with existing onclick handlers and inline scripts.
 */

// ============== Core Modules ==============
import { escapeHtml, extractDomain, debounce, formatDate, formatFileSize,
         truncateText, formatFieldName, formatNewsDate, formatSourceName,
         formatActivityTime } from './core/utils.js';

import { API_BASE, checkAuth, logout, getAuthHeaders, APIError,
         getErrorMessage, fetchAPI, showErrorBanner, hideErrorBanner } from './core/api.js';

import { showPage, showPageError, initNavigation, navigateTo, toggleSidebar,
         saveNavigationState, restoreNavigationState, updateUrlHash,
         parseUrlHash, generateComparisonLink, copyComparisonLink } from './core/navigation.js';

import * as state from './core/state.js';

// ============== Components ==============
import { showToast, showNotification } from './components/toast.js';

import { showModal, closeModal, showLoading, hideLoading,
         updateLoadingText, setButtonLoading } from './components/modals.js';

import { createChatWidget } from './components/chat.js';

// ============== Module Initialization ==============
// All modules self-register on window.* via their own code.
// This entry point ensures they load in the right order.

console.log('[Certify Intel] ES6 modules loaded successfully');
