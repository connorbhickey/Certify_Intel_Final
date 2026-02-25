/**
 * Certify Intel - Chat Widget Component
 * Reusable conversational AI chat widget (v7.2.0).
 */

import { escapeHtml } from '../core/utils.js';

// Registry of active chat widgets, keyed by containerId.
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
export function createChatWidget(containerId, config) {
    // Destroy any previous widget in this container
    if (_chatWidgetRegistry[containerId]) {
        _chatWidgetRegistry[containerId].destroy();
    }

    const container = document.getElementById(containerId);
    if (!container) {
        console.warn('[ChatWidget] Container not found:', containerId);
        return null;
    }

    // Use window.fetchAPI to avoid circular import with api.js
    const fetchAPI = window.fetchAPI;
    const showToast = window.showToast;

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

        if (role === 'user') {
            bubble.textContent = content;
        } else {
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

    function showLoadingIndicator() {
        removeEmptyState();
        const loadDiv = document.createElement('div');
        loadDiv.className = 'chat-loading';
        loadDiv.id = `chat-loading-${containerId}`;
        loadDiv.textContent = 'AI is thinking...';
        messagesArea.appendChild(loadDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    function hideLoadingIndicator() {
        const el = document.getElementById(`chat-loading-${containerId}`);
        if (el) el.remove();
    }

    async function loadHistory() {
        try {
            const data = await fetchAPI(`/api/chat/sessions/by-context/${encodeURIComponent(config.pageContext)}`, { silent: true });
            const session = data?.session || data;
            if (session && session.id && session.messages && session.messages.length > 0) {
                sessionId = session.id;
                conversationHistory = session.messages.map(m => ({
                    role: m.role,
                    content: m.content
                }));
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

        appendMessage('user', text);
        conversationHistory.push({ role: 'user', content: text });

        showLoadingIndicator();

        try {
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

            const payload = {
                message: text,
                session_id: sessionId,
                conversation_history: conversationHistory
            };
            if (config.competitorId) {
                payload.competitor_id = config.competitorId;
            }
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

            hideLoadingIndicator();

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
            hideLoadingIndicator();
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

// Expose on window for backward compatibility (conditional to avoid clobbering app_v2.js)
if (!window.createChatWidget) window.createChatWidget = createChatWidget;
