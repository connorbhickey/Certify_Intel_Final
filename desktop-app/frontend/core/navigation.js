/**
 * Certify Intel - Navigation Module
 * Page routing, sidebar navigation, URL hash handling, and state preservation.
 */

import { debounce } from './utils.js';

// ============== Navigation State ==============

const NAV_STATE_KEY = 'certify_intel_nav_state';

/**
 * Save navigation state to localStorage
 */
export function saveNavigationState(pageName, additionalState = {}) {
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
    updateUrlHash(pageName, additionalState);
}

/**
 * Restore navigation state from localStorage
 */
export function restoreNavigationState() {
    const hashState = parseUrlHash();
    if (hashState.page) {
        return hashState;
    }

    try {
        const saved = localStorage.getItem(NAV_STATE_KEY);
        if (saved) {
            const state = JSON.parse(saved);
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
 * Update URL hash for shareable links
 */
export function updateUrlHash(pageName, additionalState = {}) {
    let hash = `#${pageName}`;

    if (pageName === 'comparison' && additionalState.compareIds) {
        hash += `?compare=${additionalState.compareIds.join(',')}`;
    }

    if (additionalState.competitorId) {
        hash += `${hash.includes('?') ? '&' : '?'}competitor=${additionalState.competitorId}`;
    }

    if (window.location.hash !== hash) {
        history.replaceState(null, '', hash);
    }
}

/**
 * Parse URL hash for shared links
 */
export function parseUrlHash() {
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
 * Generate shareable comparison link
 */
export function generateComparisonLink(competitorIds) {
    const baseUrl = window.location.origin + window.location.pathname;
    return `${baseUrl}#comparison?compare=${competitorIds.join(',')}`;
}

/**
 * Copy comparison link to clipboard
 */
export async function copyComparisonLink() {
    const selectedIds = Array.from(document.querySelectorAll('.comparison-checkbox:checked'))
        .map(cb => parseInt(cb.dataset.id))
        .filter(id => !isNaN(id));

    if (selectedIds.length < 2) {
        window.showToast('Select at least 2 competitors to share', 'warning');
        return;
    }

    const link = generateComparisonLink(selectedIds);

    try {
        await navigator.clipboard.writeText(link);
        window.showToast('Comparison link copied to clipboard!', 'success');
    } catch (err) {
        const textArea = document.createElement('textarea');
        textArea.value = link;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        window.showToast('Comparison link copied!', 'success');
    }
}

/**
 * Show error message on a page
 */
export function showPageError(pageId, message) {
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
        retryBtn.addEventListener('click', function() { window.showPage(retryPage); });
        errorDiv.appendChild(heading);
        errorDiv.appendChild(desc);
        errorDiv.appendChild(retryBtn);
        page.prepend(errorDiv);
    }
}

/**
 * Main page routing function.
 * Delegates to page-specific load functions which remain in app_v2.js for now.
 */
export function showPage(pageName) {
    // Step 1: Remove 'active' from ALL nav items first
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    // Step 2: Add 'active' to the matching nav item
    const activeNav = document.querySelector(`.nav-item[data-page="${pageName}"]`);
    if (activeNav) {
        activeNav.classList.add('active');
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

    // Save navigation state
    if (typeof saveNavigationState === 'function') {
        saveNavigationState(pageName);
    }

    // Clear any previous page errors
    if (targetPage) {
        const prevError = targetPage.querySelector('.page-error');
        if (prevError) prevError.remove();
    }

    // Load page-specific data with error boundaries
    // Page load functions are on window.* from app_v2.js
    switch (pageName) {
        case 'dashboard':
            try {
                window.loadDashboard?.()?.catch?.(err => { console.error('[showPage] Dashboard load failed:', err); showPageError('dashboardPage', err.message); });
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('dashboard', 'dashboardPromptSelect');
            } catch (error) {
                console.error('[showPage] Dashboard load failed:', error);
                showPageError('dashboardPage', error.message);
            }
            break;
        case 'competitors':
            try {
                window.loadCompetitors?.()?.catch?.(err => { console.error('[showPage] Competitors load failed:', err); showPageError('competitorsPage', err.message); });
                window.initRecordsExport?.();
            } catch (error) {
                console.error('[showPage] Competitors load failed:', error);
                showPageError('competitorsPage', error.message);
            }
            break;
        case 'changes':
            try {
                window.loadChanges?.()?.catch?.(err => { console.error('[showPage] Changes load failed:', err); showPageError('changesPage', err.message); });
            } catch (error) {
                console.error('[showPage] Changes load failed:', error);
                showPageError('changesPage', error.message);
            }
            break;
        case 'comparison':
            try {
                window.loadComparisonOptions?.()?.catch?.(err => { console.error('[showPage] Comparison load failed:', err); showPageError('comparisonPage', err.message); });
            } catch (error) {
                console.error('[showPage] Comparison load failed:', error);
                showPageError('comparisonPage', error.message);
            }
            break;
        case 'analytics':
            try {
                window.loadAnalytics?.()?.catch?.(err => { console.error('[showPage] Analytics load failed:', err); showPageError('analyticsPage', err.message); });
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('competitor', 'competitorPromptSelect');
                window.initAnalyticsExport?.();
            } catch (error) {
                console.error('[showPage] Analytics load failed:', error);
                showPageError('analyticsPage', error.message);
            }
            break;
        case 'marketmap':
            try {
                window.loadMarketMap?.();
            } catch (error) {
                console.error('[showPage] MarketMap load failed:', error);
                showPageError('marketmapPage', error.message);
            }
            break;
        case 'battlecards':
            try {
                window.loadBattlecards?.()?.catch?.(err => { console.error('[showPage] Battlecards load failed:', err); showPageError('battlecardsPage', err.message); });
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('battlecards', 'battlecardPromptSelect');
                window.resumeVerificationIfRunning?.();
                window.initBattlecardsExport?.();
            } catch (error) {
                console.error('[showPage] Battlecards load failed:', error);
                showPageError('battlecardsPage', error.message);
            }
            break;
        case 'discovered':
            try {
                window.loadDiscovered?.()?.catch?.(err => { console.error('[showPage] Discovery load failed:', err); showPageError('discoveredPage', err.message); });
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('discovery', 'discoveryPromptSelect');
                if (typeof window.createChatWidget === 'function') {
                    window.createChatWidget('discoveryChatContainer', {
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
                window.loadDataQuality?.()?.catch?.(err => { console.error('[showPage] DataQuality load failed:', err); showPageError('dataqualityPage', err.message); });
                window.loadDataConflicts?.()?.catch?.(err => { console.error('[showPage] DataConflicts load failed:', err); });
            } catch (error) {
                console.error('[showPage] DataQuality load failed:', error);
                showPageError('dataqualityPage', error.message);
            }
            break;
        case 'newsfeed':
            try {
                window.initNewsFeedPage?.()?.catch?.(err => { console.error('[showPage] NewsFeed load failed:', err); showPageError('newsfeedPage', err.message); });
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('news', 'newsPromptSelect');
            } catch (error) {
                console.error('[showPage] NewsFeed load failed:', error);
                showPageError('newsfeedPage', error.message);
            }
            break;
        case 'salesmarketing':
            try {
                if (typeof window.initSalesMarketingModule === 'function') {
                    window.initSalesMarketingModule();
                }
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('battlecards', 'battlecardPromptSelect');
            } catch (error) {
                console.error('[showPage] SalesMarketing load failed:', error);
                showPageError('salesmarketingPage', error.message);
            }
            break;
        case 'settings':
            try {
                window.loadSettings?.()?.catch?.(err => { console.error('[showPage] Settings load failed:', err); showPageError('settingsPage', err.message); });
                window.initKnowledgeBaseStatus?.()?.catch?.(err => { console.error('[showPage] KB status load failed:', err); });
                if (typeof window.initPromptSelector === 'function') window.initPromptSelector('knowledge_base', 'kbPromptSelect');
            } catch (error) {
                console.error('[showPage] Settings load failed:', error);
                showPageError('settingsPage', error.message);
            }
            break;
        case 'verification':
            try {
                window.loadVerificationQueue?.()?.catch?.(err => { console.error('[showPage] Verification load failed:', err); showPageError('verificationPage', err.message); });
            } catch (error) {
                console.error('[showPage] Verification load failed:', error);
                showPageError('verificationPage', error.message);
            }
            break;
    }
}

/**
 * Initialize sidebar navigation click handlers
 */
export function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            showPage(page);
        });
    });

    // Filter event listeners
    document.getElementById('filterThreat')?.addEventListener('change', () => window.filterCompetitors?.());
    document.getElementById('filterStatus')?.addEventListener('change', () => window.filterCompetitors?.());
    document.getElementById('filterSeverity')?.addEventListener('change', () => window.loadChanges?.());
    document.getElementById('filterDays')?.addEventListener('change', () => window.loadChanges?.());
    document.getElementById('filterCompany')?.addEventListener('change', () => window.loadChanges?.());

    // Search
    document.getElementById('globalSearch')?.addEventListener('input', debounce((e) => window.handleSearch?.(e), 300));
}

/**
 * Navigate to a specific page (alias used by mobile nav)
 */
export function navigateTo(pageName) {
    showPage(pageName);
}

/**
 * Toggle sidebar collapsed state
 */
export function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const main = document.querySelector('.main-content');
    if (sidebar) sidebar.classList.toggle('collapsed');
    if (main) main.classList.toggle('sidebar-collapsed');
}

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (!window.showPage) window.showPage = showPage;
if (!window.showPageError) window.showPageError = showPageError;
if (!window.initNavigation) window.initNavigation = initNavigation;
if (!window.navigateTo) window.navigateTo = navigateTo;
if (!window.toggleSidebar) window.toggleSidebar = toggleSidebar;
if (!window.saveNavigationState) window.saveNavigationState = saveNavigationState;
if (!window.restoreNavigationState) window.restoreNavigationState = restoreNavigationState;
if (!window.updateUrlHash) window.updateUrlHash = updateUrlHash;
if (!window.parseUrlHash) window.parseUrlHash = parseUrlHash;
if (!window.generateComparisonLink) window.generateComparisonLink = generateComparisonLink;
if (!window.copyComparisonLink) window.copyComparisonLink = copyComparisonLink;
