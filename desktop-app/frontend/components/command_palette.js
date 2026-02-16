/**
 * Certify Intel - Command Palette (Ctrl+K)
 * Global search and quick navigation overlay.
 */
(function () {
    'use strict';

    let paletteOpen = false;
    let selectedIndex = 0;
    let searchResults = [];
    let recentSearches = JSON.parse(localStorage.getItem('ci_recentSearches') || '[]');
    let debounceTimer = null;
    let cachedCompetitors = null;
    let cachedCompetitorsAt = 0;
    const COMPETITOR_CACHE_TTL = 60000; // 1 minute

    // Page entries matching nav-item data-page values
    const PAGES = [
        { type: 'page', name: 'Dashboard', page: 'dashboard', icon: '\u{1F4CA}' },
        { type: 'page', name: 'Discovery Scout', page: 'discovered', icon: '\u{1F52E}' },
        { type: 'page', name: 'Battlecards', page: 'battlecards', icon: '\u{1F0CF}' },
        { type: 'page', name: 'Comparisons', page: 'comparison', icon: '\u2696\uFE0F' },
        { type: 'page', name: 'Live News', page: 'newsfeed', icon: '\u{1F4F0}' },
        { type: 'page', name: 'Analytics', page: 'analytics', icon: '\u{1F4C8}' },
        { type: 'page', name: 'Sales & Marketing', page: 'salesmarketing', icon: '\u{1F3AF}' },
        { type: 'page', name: 'Records', page: 'competitors', icon: '\u{1F3E2}' },
        { type: 'page', name: 'Validation', page: 'dataquality', icon: '\u2705' },
        { type: 'page', name: 'Settings', page: 'settings', icon: '\u2699\uFE0F' },
    ];

    const ACTIONS = [
        { type: 'action', name: 'Add Competitor', page: 'competitors', icon: '\u2795' },
        { type: 'action', name: 'Run Discovery', page: 'discovered', icon: '\u{1F680}' },
        { type: 'action', name: 'Generate Battlecard', page: 'battlecards', icon: '\u26A1' },
        { type: 'action', name: 'Export Excel', page: 'competitors', icon: '\u{1F4E5}' },
    ];

    // ---- DOM creation ----

    function createPaletteDOM() {
        if (document.getElementById('commandPaletteOverlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'commandPaletteOverlay';
        overlay.className = 'cmd-palette-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-label', 'Command palette');
        overlay.setAttribute('aria-modal', 'true');

        const container = document.createElement('div');
        container.className = 'cmd-palette';

        // Input row
        const inputRow = document.createElement('div');
        inputRow.className = 'cmd-palette-input-row';

        const searchIcon = document.createElement('span');
        searchIcon.className = 'cmd-palette-search-icon';
        searchIcon.setAttribute('aria-hidden', 'true');
        searchIcon.textContent = '\u{1F50D}';

        const input = document.createElement('input');
        input.id = 'cmdPaletteInput';
        input.className = 'cmd-palette-input';
        input.type = 'text';
        input.placeholder = 'Search pages, competitors, actions...';
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('aria-label', 'Command palette search');

        const kbd = document.createElement('kbd');
        kbd.className = 'cmd-palette-kbd';
        kbd.textContent = 'ESC';

        inputRow.appendChild(searchIcon);
        inputRow.appendChild(input);
        inputRow.appendChild(kbd);
        container.appendChild(inputRow);

        // Results
        const results = document.createElement('div');
        results.id = 'cmdPaletteResults';
        results.className = 'cmd-palette-results';
        results.setAttribute('role', 'listbox');
        container.appendChild(results);

        overlay.appendChild(container);
        document.body.appendChild(overlay);

        // Events
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closePalette();
        });

        input.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => onSearchInput(input.value.trim()), 150);
        });

        input.addEventListener('keydown', handleKeydown);
    }

    // ---- Open / Close ----

    function openPalette() {
        createPaletteDOM();
        const overlay = document.getElementById('commandPaletteOverlay');
        const input = document.getElementById('cmdPaletteInput');
        if (!overlay || !input) return;

        overlay.classList.add('visible');
        paletteOpen = true;
        input.value = '';
        selectedIndex = 0;
        renderDefaultResults();
        input.focus();
    }

    function closePalette() {
        const overlay = document.getElementById('commandPaletteOverlay');
        if (overlay) overlay.classList.remove('visible');
        paletteOpen = false;
        selectedIndex = 0;
        searchResults = [];
    }

    function togglePalette() {
        if (paletteOpen) {
            closePalette();
        } else {
            openPalette();
        }
    }

    // ---- Search logic ----

    function onSearchInput(query) {
        if (!query) {
            renderDefaultResults();
            return;
        }

        const q = query.toLowerCase();

        // Match pages
        const pageMatches = PAGES.filter(p => p.name.toLowerCase().includes(q));

        // Match actions
        const actionMatches = ACTIONS.filter(a => a.name.toLowerCase().includes(q));

        // Match competitors (from cache or fetch)
        fetchCompetitorMatches(q).then(competitorMatches => {
            searchResults = [];

            if (pageMatches.length) {
                searchResults.push({ type: 'group', label: 'Pages' });
                pageMatches.forEach(p => searchResults.push(p));
            }
            if (competitorMatches.length) {
                searchResults.push({ type: 'group', label: 'Competitors' });
                competitorMatches.forEach(c => searchResults.push(c));
            }
            if (actionMatches.length) {
                searchResults.push({ type: 'group', label: 'Actions' });
                actionMatches.forEach(a => searchResults.push(a));
            }

            if (!searchResults.length) {
                searchResults.push({ type: 'empty', name: 'No results found' });
            }

            selectedIndex = findFirstSelectableIndex(0);
            renderResults();
        });
    }

    function renderDefaultResults() {
        searchResults = [];

        if (recentSearches.length) {
            searchResults.push({ type: 'group', label: 'Recent' });
            recentSearches.slice(0, 5).forEach(r => searchResults.push(r));
        }

        searchResults.push({ type: 'group', label: 'Pages' });
        PAGES.forEach(p => searchResults.push(p));

        searchResults.push({ type: 'group', label: 'Actions' });
        ACTIONS.forEach(a => searchResults.push(a));

        selectedIndex = findFirstSelectableIndex(0);
        renderResults();
    }

    async function fetchCompetitorMatches(query) {
        if (query.length < 2) return [];

        try {
            const now = Date.now();
            if (!cachedCompetitors || now - cachedCompetitorsAt > COMPETITOR_CACHE_TTL) {
                const data = await fetchAPI('/api/competitors', { silent: true });
                if (data && Array.isArray(data)) {
                    cachedCompetitors = data;
                    cachedCompetitorsAt = now;
                }
            }

            if (!cachedCompetitors) return [];

            return cachedCompetitors
                .filter(c => c.name && c.name.toLowerCase().includes(query))
                .slice(0, 8)
                .map(c => ({
                    type: 'competitor',
                    name: c.name,
                    id: c.id,
                    icon: '\u{1F3E2}',
                    sub: c.website || '',
                }));
        } catch {
            return [];
        }
    }

    // ---- Rendering ----

    function renderResults() {
        const container = document.getElementById('cmdPaletteResults');
        if (!container) return;

        container.innerHTML = '';

        searchResults.forEach((item, idx) => {
            if (item.type === 'group') {
                const groupEl = document.createElement('div');
                groupEl.className = 'cmd-palette-group';
                groupEl.textContent = item.label;
                container.appendChild(groupEl);
                return;
            }

            if (item.type === 'empty') {
                const emptyEl = document.createElement('div');
                emptyEl.className = 'cmd-palette-empty';
                emptyEl.textContent = item.name;
                container.appendChild(emptyEl);
                return;
            }

            const el = document.createElement('div');
            el.className = 'cmd-palette-item';
            el.setAttribute('role', 'option');
            if (idx === selectedIndex) el.classList.add('selected');

            const icon = document.createElement('span');
            icon.className = 'cmd-palette-item-icon';
            icon.textContent = item.icon || '';

            const nameSpan = document.createElement('span');
            nameSpan.className = 'cmd-palette-item-name';
            nameSpan.textContent = item.name;

            const badge = document.createElement('span');
            badge.className = 'cmd-palette-item-badge';
            badge.textContent = item.type === 'competitor' ? 'Competitor' :
                item.type === 'page' ? 'Page' :
                    item.type === 'action' ? 'Action' :
                        item.type === 'recent' ? 'Recent' : '';

            el.appendChild(icon);
            el.appendChild(nameSpan);
            if (item.sub) {
                const subSpan = document.createElement('span');
                subSpan.className = 'cmd-palette-item-sub';
                subSpan.textContent = item.sub;
                el.appendChild(subSpan);
            }
            el.appendChild(badge);

            el.addEventListener('click', () => selectItem(idx));
            el.addEventListener('mouseenter', () => {
                selectedIndex = idx;
                updateSelection();
            });

            container.appendChild(el);
        });
    }

    function updateSelection() {
        const container = document.getElementById('cmdPaletteResults');
        if (!container) return;

        const items = container.querySelectorAll('.cmd-palette-item');
        let itemIdx = 0;
        searchResults.forEach((item, idx) => {
            if (item.type === 'group' || item.type === 'empty') return;
            if (items[itemIdx]) {
                items[itemIdx].classList.toggle('selected', idx === selectedIndex);
            }
            itemIdx++;
        });

        // Scroll selected into view
        const selectedEl = container.querySelector('.cmd-palette-item.selected');
        if (selectedEl) {
            selectedEl.scrollIntoView({ block: 'nearest' });
        }
    }

    // ---- Keyboard handling ----

    function handleKeydown(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closePalette();
            return;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = findNextSelectableIndex(selectedIndex, 1);
            updateSelection();
            return;
        }

        if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = findNextSelectableIndex(selectedIndex, -1);
            updateSelection();
            return;
        }

        if (e.key === 'Enter') {
            e.preventDefault();
            selectItem(selectedIndex);
            return;
        }
    }

    function findFirstSelectableIndex(start) {
        for (let i = start; i < searchResults.length; i++) {
            if (searchResults[i].type !== 'group' && searchResults[i].type !== 'empty') return i;
        }
        return 0;
    }

    function findNextSelectableIndex(current, direction) {
        let idx = current;
        const len = searchResults.length;
        if (len === 0) return 0;

        for (let i = 0; i < len; i++) {
            idx += direction;
            if (idx < 0) idx = len - 1;
            if (idx >= len) idx = 0;
            const item = searchResults[idx];
            if (item.type !== 'group' && item.type !== 'empty') return idx;
        }
        return current;
    }

    // ---- Selection / navigation ----

    function selectItem(idx) {
        const item = searchResults[idx];
        if (!item || item.type === 'group' || item.type === 'empty') return;

        // Save to recent
        addToRecent(item);

        closePalette();

        if (item.type === 'competitor' && item.id) {
            // Navigate to competitors page and trigger detail view
            if (typeof showPage === 'function') showPage('competitors');
            setTimeout(() => {
                if (typeof showCompetitorDetails === 'function') {
                    showCompetitorDetails(item.id);
                }
            }, 300);
            return;
        }

        if (item.page && typeof showPage === 'function') {
            showPage(item.page);
        }
    }

    function addToRecent(item) {
        const entry = {
            type: 'recent',
            name: item.name,
            page: item.page || (item.type === 'competitor' ? 'competitors' : null),
            icon: item.icon,
            id: item.id || null,
            originalType: item.type,
        };

        // Remove duplicate
        recentSearches = recentSearches.filter(r => !(r.name === entry.name && r.originalType === entry.originalType));
        recentSearches.unshift(entry);
        recentSearches = recentSearches.slice(0, 10);

        try {
            localStorage.setItem('ci_recentSearches', JSON.stringify(recentSearches));
        } catch {
            // localStorage full - ignore
        }
    }

    // ---- Init ----

    function initCommandPalette() {
        // Override the ctrl+k shortcut from keyboard.js
        if (typeof registerShortcut === 'function') {
            registerShortcut('ctrl+k', togglePalette, 'Command palette');
        }

        // Also listen globally as a safety net
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                // Only handle if keyboard.js didn't already
                if (!paletteOpen) {
                    e.preventDefault();
                    openPalette();
                }
            }
            // Close on Escape when open
            if (e.key === 'Escape' && paletteOpen) {
                closePalette();
            }
        });
    }

    // Auto-init
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCommandPalette);
    } else {
        initCommandPalette();
    }

    // Expose for external use
    window.openCommandPalette = openPalette;
    window.closeCommandPalette = closePalette;
    window.toggleCommandPalette = togglePalette;
})();
