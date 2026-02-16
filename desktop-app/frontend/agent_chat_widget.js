/**
 * Certify Intel v7.0 - Agent Chat Widget
 * =======================================
 *
 * Floating AI chat widget that connects to the LangGraph agent orchestrator.
 * Features:
 * - Floating chat button with unread indicator
 * - Full chat interface with message history
 * - Agent routing visibility (shows which agent handled each query)
 * - Citation display with source links
 * - Cost and latency tracking display
 * - Keyboard shortcuts (Ctrl+K to open)
 * - Persistent session within page
 *
 * Dependencies:
 * - Requires fetchAPI() from app_v2.js
 * - Requires styles from styles.css (agent-chat-widget section)
 */

(function() {
    'use strict';

    // =========================================================================
    // Widget State
    // =========================================================================

    const state = {
        isOpen: false,
        isMinimized: false,
        messages: [],
        sessionId: generateSessionId(),
        isLoading: false,
        unreadCount: 0
    };

    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // =========================================================================
    // Widget HTML Template
    // =========================================================================

    function createWidgetHTML() {
        return `
            <div id="agentChatWidget" class="agent-chat-widget">
                <!-- Floating Button -->
                <button id="agentChatToggle" class="agent-chat-toggle" title="AI Assistant (Ctrl+K)">
                    <span class="agent-chat-icon">🤖</span>
                    <span id="agentChatBadge" class="agent-chat-badge" style="display: none;">0</span>
                </button>

                <!-- Chat Container -->
                <div id="agentChatContainer" class="agent-chat-container" style="display: none;">
                    <!-- Header -->
                    <div class="agent-chat-header">
                        <div class="agent-chat-header-left">
                            <span class="agent-chat-logo">🤖</span>
                            <div class="agent-chat-title">
                                <h4>AI Assistant</h4>
                                <span class="agent-chat-subtitle">Powered by LangGraph</span>
                            </div>
                        </div>
                        <div class="agent-chat-header-right">
                            <button class="agent-chat-minimize" id="agentChatMinimize" title="Minimize">−</button>
                            <button class="agent-chat-close" id="agentChatClose" title="Close">×</button>
                        </div>
                    </div>

                    <!-- Quick Actions -->
                    <div class="agent-chat-quick-actions">
                        <button class="quick-action-btn" data-query="What are the top threats?">
                            ⚡ Top Threats
                        </button>
                        <button class="quick-action-btn" data-query="Generate executive summary">
                            📊 Summary
                        </button>
                        <button class="quick-action-btn" data-query="Find emerging competitors">
                            🔍 Discovery
                        </button>
                        <button class="quick-action-btn" data-query="What's new in competitor news?">
                            📰 News
                        </button>
                    </div>

                    <!-- Messages Container -->
                    <div id="agentChatMessages" class="agent-chat-messages">
                        <div class="agent-chat-welcome">
                            <div class="welcome-icon">👋</div>
                            <h4>Hello! I'm your AI Assistant</h4>
                            <p>I can help you with competitive intelligence queries. Try asking about:</p>
                            <ul>
                                <li>Competitor threats and analysis</li>
                                <li>Sales battlecards</li>
                                <li>Market discovery</li>
                                <li>News and updates</li>
                            </ul>
                        </div>
                    </div>

                    <!-- Input Area -->
                    <div class="agent-chat-input-area">
                        <div class="agent-chat-input-wrapper">
                            <input
                                type="text"
                                id="agentChatInput"
                                class="agent-chat-input"
                                placeholder="Ask about competitors, threats, battlecards..."
                                autocomplete="off"
                            >
                            <button id="agentChatSend" class="agent-chat-send-btn" title="Send (Enter)">
                                <span>➤</span>
                            </button>
                        </div>
                        <div class="agent-chat-footer">
                            <span class="agent-chat-hint">Press Enter to send • Ctrl+K to toggle</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // =========================================================================
    // Message Rendering
    // =========================================================================

    function createMessageHTML(message) {
        const { role, content, agent, citations, cost, latency, timestamp } = message;
        const isUser = role === 'user';
        const timeStr = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        if (isUser) {
            return `
                <div class="agent-chat-message user-message">
                    <div class="message-content">
                        <p>${escapeHtml(content)}</p>
                    </div>
                    <div class="message-meta">
                        <span class="message-time">${timeStr}</span>
                    </div>
                </div>
            `;
        }

        // Assistant message with agent info and citations
        const agentBadge = agent ? `<span class="agent-badge agent-${agent}">${formatAgentName(agent)}</span>` : '';
        const citationsHTML = citations && citations.length > 0 ? createCitationsHTML(citations) : '';
        const metricsHTML = (cost !== undefined || latency !== undefined) ? `
            <div class="message-metrics">
                ${latency !== undefined ? `<span class="metric">⚡ ${Math.round(latency)}ms</span>` : ''}
                ${cost !== undefined && cost > 0 ? `<span class="metric">💰 $${cost.toFixed(4)}</span>` : ''}
            </div>
        ` : '';

        return `
            <div class="agent-chat-message assistant-message">
                <div class="message-header">
                    <span class="assistant-icon">🤖</span>
                    ${agentBadge}
                </div>
                <div class="message-content">
                    <p>${formatMarkdown(content)}</p>
                </div>
                ${citationsHTML}
                <div class="message-meta">
                    <span class="message-time">${timeStr}</span>
                    ${metricsHTML}
                </div>
            </div>
        `;
    }

    function createCitationsHTML(citations) {
        if (!citations || citations.length === 0) return '';

        const citationItems = citations.slice(0, 5).map((c, i) => {
            const sourceType = c.source_type || c.sourceType || 'unknown';
            const sourceId = c.source_id || c.sourceId || 'Source';
            const confidence = c.confidence !== undefined ? Math.round(c.confidence * 100) : null;

            return `
                <li class="citation-item">
                    <span class="citation-icon">${getSourceIcon(sourceType)}</span>
                    <span class="citation-text">${escapeHtml(sourceId)}</span>
                    ${confidence !== null ? `<span class="citation-confidence">${confidence}%</span>` : ''}
                </li>
            `;
        }).join('');

        return `
            <div class="message-citations">
                <div class="citations-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <span>📚 ${citations.length} source${citations.length > 1 ? 's' : ''}</span>
                    <span class="expand-icon">▶</span>
                </div>
                <ul class="citations-list">
                    ${citationItems}
                </ul>
            </div>
        `;
    }

    function getSourceIcon(sourceType) {
        const icons = {
            'knowledge_base': '📄',
            'competitor_database': '🏢',
            'discovered_competitor': '🔍',
            'news': '📰',
            'document': '📁',
            'manual': '✍️'
        };
        return icons[sourceType] || '📋';
    }

    function formatAgentName(agent) {
        const names = {
            'dashboard': '📊 Dashboard',
            'discovery': '🔍 Discovery',
            'battlecard': '🃏 Battlecard',
            'news': '📰 News',
            'analytics': '📈 Analytics',
            'validation': '✅ Validation',
            'records': '🏢 Records'
        };
        return names[agent] || agent;
    }

    function formatMarkdown(text) {
        if (!text) return '';
        // Basic markdown formatting
        return escapeHtml(text)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // =========================================================================
    // Page Context Detection
    // =========================================================================

    /**
     * Detect which page the user is currently on and map to an agent hint.
     * This allows the chat widget to route queries to the most appropriate agent
     * based on the current page context.
     */
    function getCurrentPageContext() {
        // Find the active page element (has class 'page active' or similar)
        const activePage = document.querySelector('.page.active');
        const pageId = activePage ? activePage.id.replace('Page', '') : 'dashboard';

        // Map pages to appropriate agent hints
        const pageToAgentHint = {
            'dashboard': 'dashboard',
            'competitors': 'dashboard',       // Competitor overview -> dashboard
            'battlecards': 'battlecard',
            'comparison': 'battlecard',       // Comparing competitors -> battlecard
            'analytics': 'analytics',
            'news': 'news',
            'newsfeed': 'news',
            'discovery': 'discovery',
            'sales-marketing': 'battlecard',  // S&M features -> battlecard
            'records': 'records',
            'validation': 'validation',
            'dataquality': 'validation',
            'settings': 'dashboard',
            'reports': 'analytics',
            'changes': 'dashboard'
        };

        // Get the currently selected competitor if any
        let selectedCompetitorId = null;
        let selectedCompetitorName = null;

        // Try to find selected competitor from various page contexts
        const battlecardCompetitor = document.querySelector('.battlecard-competitor-selector select');
        if (battlecardCompetitor && battlecardCompetitor.value) {
            selectedCompetitorId = parseInt(battlecardCompetitor.value);
        }

        // Check if there's a competitor detail view open
        const competitorDetailId = window.currentCompetitorId || null;
        if (competitorDetailId) {
            selectedCompetitorId = competitorDetailId;
        }

        // Look for competitor name in a visible title or header
        const competitorTitle = document.querySelector('.competitor-name, .battlecard-competitor-name');
        if (competitorTitle) {
            selectedCompetitorName = competitorTitle.textContent.trim();
        }

        return {
            current_page: pageId,
            agent_hint: pageToAgentHint[pageId] || 'dashboard',
            competitor_id: selectedCompetitorId,
            competitor_name: selectedCompetitorName
        };
    }

    // =========================================================================
    // Chat Logic
    // =========================================================================

    async function sendMessage(text) {
        if (!text || !text.trim() || state.isLoading) return;

        const message = text.trim();
        state.isLoading = true;

        // Add user message
        const userMessage = {
            role: 'user',
            content: message,
            timestamp: Date.now()
        };
        state.messages.push(userMessage);
        renderMessages();

        // Show loading indicator
        showLoadingIndicator();

        // Get page context for better agent routing
        const pageContext = getCurrentPageContext();

        try {
            // Call the agent query API with page context
            const response = await window.fetchAPI('/api/agents/query', {
                method: 'POST',
                body: JSON.stringify({
                    query: message,
                    session_id: state.sessionId,
                    context: pageContext
                })
            });

            hideLoadingIndicator();

            if (response) {
                const assistantMessage = {
                    role: 'assistant',
                    content: response.response || 'I received your message but couldn\'t generate a response.',
                    agent: response.agent,
                    citations: response.citations || [],
                    cost: response.cost_usd,
                    latency: response.latency_ms,
                    timestamp: Date.now()
                };
                state.messages.push(assistantMessage);
            } else {
                throw new Error('Empty response from agent');
            }
        } catch (error) {
            hideLoadingIndicator();
            console.error('[AgentChat] Error:', error);

            const errorMessage = {
                role: 'assistant',
                content: `I encountered an error: ${error.message || 'Unknown error'}. Please try again.`,
                timestamp: Date.now()
            };
            state.messages.push(errorMessage);
        }

        state.isLoading = false;
        renderMessages();
        scrollToBottom();
    }

    function showLoadingIndicator() {
        const messagesContainer = document.getElementById('agentChatMessages');
        if (!messagesContainer) return;

        const loadingEl = document.createElement('div');
        loadingEl.id = 'agentChatLoading';
        loadingEl.className = 'agent-chat-message assistant-message loading';
        loadingEl.innerHTML = `
            <div class="message-header">
                <span class="assistant-icon">🤖</span>
                <span class="loading-text">Thinking...</span>
            </div>
            <div class="loading-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        messagesContainer.appendChild(loadingEl);
        scrollToBottom();
    }

    function hideLoadingIndicator() {
        const loadingEl = document.getElementById('agentChatLoading');
        if (loadingEl) loadingEl.remove();
    }

    function renderMessages() {
        const messagesContainer = document.getElementById('agentChatMessages');
        if (!messagesContainer) return;

        if (state.messages.length === 0) {
            // Show welcome message
            messagesContainer.innerHTML = `
                <div class="agent-chat-welcome">
                    <div class="welcome-icon">👋</div>
                    <h4>Hello! I'm your AI Assistant</h4>
                    <p>I can help you with competitive intelligence queries. Try asking about:</p>
                    <ul>
                        <li>Competitor threats and analysis</li>
                        <li>Sales battlecards</li>
                        <li>Market discovery</li>
                        <li>News and updates</li>
                    </ul>
                </div>
            `;
            return;
        }

        messagesContainer.innerHTML = state.messages.map(m => createMessageHTML(m)).join('');
    }

    function scrollToBottom() {
        const messagesContainer = document.getElementById('agentChatMessages');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    // =========================================================================
    // Widget Controls
    // =========================================================================

    function toggleWidget() {
        state.isOpen = !state.isOpen;
        updateWidgetVisibility();
    }

    function openWidget() {
        state.isOpen = true;
        state.isMinimized = false;
        state.unreadCount = 0;
        updateWidgetVisibility();

        // Focus input
        setTimeout(() => {
            const input = document.getElementById('agentChatInput');
            if (input) input.focus();
        }, 100);
    }

    function closeWidget() {
        state.isOpen = false;
        updateWidgetVisibility();
    }

    function minimizeWidget() {
        state.isMinimized = true;
        updateWidgetVisibility();
    }

    function updateWidgetVisibility() {
        const container = document.getElementById('agentChatContainer');
        const badge = document.getElementById('agentChatBadge');

        if (container) {
            container.style.display = state.isOpen && !state.isMinimized ? 'flex' : 'none';
        }

        if (badge) {
            badge.style.display = state.unreadCount > 0 ? 'block' : 'none';
            badge.textContent = state.unreadCount;
        }
    }

    // =========================================================================
    // Event Handlers
    // =========================================================================

    function setupEventHandlers() {
        // Toggle button
        const toggleBtn = document.getElementById('agentChatToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', toggleWidget);
        }

        // Close button
        const closeBtn = document.getElementById('agentChatClose');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeWidget);
        }

        // Minimize button
        const minimizeBtn = document.getElementById('agentChatMinimize');
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', minimizeWidget);
        }

        // Send button
        const sendBtn = document.getElementById('agentChatSend');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                const input = document.getElementById('agentChatInput');
                if (input) {
                    sendMessage(input.value);
                    input.value = '';
                }
            });
        }

        // Input - Enter to send
        const input = document.getElementById('agentChatInput');
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage(input.value);
                    input.value = '';
                }
            });
        }

        // Quick action buttons
        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.getAttribute('data-query');
                if (query) {
                    sendMessage(query);
                }
            });
        });

        // Keyboard shortcut - Ctrl+K
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                toggleWidget();
            }
            // Escape to close
            if (e.key === 'Escape' && state.isOpen) {
                closeWidget();
            }
        });

        // Click outside to close
        document.addEventListener('click', (e) => {
            const widget = document.getElementById('agentChatWidget');
            if (state.isOpen && widget && !widget.contains(e.target)) {
                // Don't close if clicking on a modal or dropdown
                if (e.target.closest('.modal') || e.target.closest('.dropdown')) return;
                // closeWidget(); // Disabled - can be annoying
            }
        });
    }

    // =========================================================================
    // Initialization
    // =========================================================================

    function init() {
        // Check if widget already exists
        if (document.getElementById('agentChatWidget')) {
            console.log('[AgentChat] Widget already initialized');
            return;
        }

        // Wait for DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initWidget);
        } else {
            initWidget();
        }
    }

    function initWidget() {
        // Insert widget HTML
        const widgetHTML = createWidgetHTML();
        document.body.insertAdjacentHTML('beforeend', widgetHTML);

        // Setup event handlers
        setupEventHandlers();

        // Initial render
        renderMessages();

        console.log('[AgentChat] Widget initialized with session:', state.sessionId);
    }

    // Auto-initialize
    init();

    // Expose API for external access
    window.AgentChatWidget = {
        open: openWidget,
        close: closeWidget,
        toggle: toggleWidget,
        sendMessage: sendMessage
    };

})();
