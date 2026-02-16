/**
 * Prompt Manager - Frontend Logic
 * Handles system prompts and user-saved custom prompts
 */

// Default prompt content
const DEFAULT_EXECUTIVE_SUMMARY_PROMPT = `You are Certify Health's competitive intelligence analyst. Generate a comprehensive, executive-level strategic summary using ONLY the LIVE data in this platform that you have access to:

**YOUR SUMMARY MUST INCLUDE:**:

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

**IMPORTANT:** Every claim must reference actual data provided. Do NOT make up or assume any information.`;

// Cache for user's saved prompts
let userSavedPrompts = [];

/**
 * Load system prompts into the editor
 */
async function loadSystemPrompts() {
    try {
        const summaryPrompt = await fetchAPI('/api/admin/system-prompts/dashboard_summary');

        if (summaryPrompt && summaryPrompt.content) {
            document.getElementById('summaryPromptInput').value = summaryPrompt.content;
        } else {
            document.getElementById('summaryPromptInput').value = DEFAULT_EXECUTIVE_SUMMARY_PROMPT;
        }

        // Also load user's saved prompts
        await refreshSavedPrompts();
    } catch (e) {
        console.error("Failed to load prompt:", e);
        document.getElementById('summaryPromptInput').value = DEFAULT_EXECUTIVE_SUMMARY_PROMPT;
    }
}

/**
 * Save the current prompt to the system (applies to current session)
 */
async function saveSystemPrompt(key) {
    const inputId = key === 'dashboard_summary' ? 'summaryPromptInput' : 'chatPersonaInput';
    const content = document.getElementById(inputId).value;

    try {
        const response = await fetchAPI('/api/admin/system-prompts', {
            method: 'POST',
            body: JSON.stringify({
                key: key,
                content: content
            })
        });

        if (response) {
            showToast('Prompt updated successfully', 'success');
            closePromptEditorModal();
        }
    } catch (e) {
        showToast('Error updating prompt: ' + e.message, 'error');
    }
}

/**
 * Close the prompt editor modal
 */
function closePromptEditorModal() {
    document.getElementById('promptEditorModal').style.display = 'none';
}

/**
 * Refresh the list of user's saved prompts
 */
async function refreshSavedPrompts() {
    try {
        const prompts = await fetchAPI('/api/user/prompts?prompt_type=executive_summary');
        userSavedPrompts = prompts || [];

        const select = document.getElementById('savedPromptsSelect');
        if (!select) return;

        // Clear existing options except the first one
        select.innerHTML = '<option value="">-- Select a saved prompt --</option>';

        // Add saved prompts
        userSavedPrompts.forEach(prompt => {
            const option = document.createElement('option');
            option.value = prompt.id;
            option.textContent = prompt.name + (prompt.is_default ? ' ⭐' : '');
            select.appendChild(option);
        });

        console.log('Loaded', userSavedPrompts.length, 'saved prompts');
    } catch (e) {
        console.error('Failed to load saved prompts:', e);
    }
}

/**
 * Load the selected prompt into the editor
 */
async function loadSelectedPrompt() {
    const select = document.getElementById('savedPromptsSelect');
    const promptId = select.value;

    if (!promptId) {
        showToast('Please select a prompt first', 'warning');
        return;
    }

    try {
        const prompt = await fetchAPI(`/api/user/prompts/${promptId}`);
        if (prompt && prompt.content) {
            document.getElementById('summaryPromptInput').value = prompt.content;
            showToast(`Loaded prompt: ${prompt.name}`, 'success');
        }
    } catch (e) {
        showToast('Error loading prompt: ' + e.message, 'error');
    }
}

/**
 * Delete the selected saved prompt
 */
async function deleteSelectedPrompt() {
    const select = document.getElementById('savedPromptsSelect');
    const promptId = select.value;

    if (!promptId) {
        showToast('Please select a prompt to delete', 'warning');
        return;
    }

    const selectedPrompt = userSavedPrompts.find(p => p.id == promptId);
    if (!selectedPrompt) return;

    if (!confirm(`Are you sure you want to delete "${selectedPrompt.name}"?`)) {
        return;
    }

    try {
        const result = await fetchAPI(`/api/user/prompts/${promptId}`, {
            method: 'DELETE'
        });

        if (result) {
            showToast('Prompt deleted successfully', 'success');
            await refreshSavedPrompts();
        }
    } catch (e) {
        showToast('Error deleting prompt: ' + e.message, 'error');
    }
}

/**
 * Save the current editor content as a new prompt
 */
async function saveAsNewPrompt() {
    const nameInput = document.getElementById('newPromptName');
    const name = nameInput.value.trim();

    if (!name) {
        showToast('Please enter a name for the prompt', 'warning');
        nameInput.focus();
        return;
    }

    const content = document.getElementById('summaryPromptInput').value;

    try {
        const result = await fetchAPI('/api/user/prompts', {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                prompt_type: 'executive_summary',
                content: content
            })
        });

        if (result) {
            showToast(`Prompt "${name}" saved successfully`, 'success');
            nameInput.value = '';
            await refreshSavedPrompts();

            // Select the newly created prompt
            const select = document.getElementById('savedPromptsSelect');
            select.value = result.id;
        }
    } catch (e) {
        showToast('Error saving prompt: ' + e.message, 'error');
    }
}

/**
 * Load the default system prompt
 */
function loadDefaultPrompt() {
    document.getElementById('summaryPromptInput').value = DEFAULT_EXECUTIVE_SUMMARY_PROMPT;
    showToast('Default prompt loaded', 'info');
}

/**
 * Update an existing saved prompt with current content
 */
async function updateSelectedPrompt() {
    const select = document.getElementById('savedPromptsSelect');
    const promptId = select.value;

    if (!promptId) {
        showToast('Please select a prompt to update', 'warning');
        return;
    }

    const content = document.getElementById('summaryPromptInput').value;

    try {
        const result = await fetchAPI(`/api/user/prompts/${promptId}`, {
            method: 'PUT',
            body: JSON.stringify({
                content: content
            })
        });

        if (result) {
            showToast('Prompt updated successfully', 'success');
        }
    } catch (e) {
        showToast('Error updating prompt: ' + e.message, 'error');
    }
}

/**
 * Set a prompt as the default for this user
 */
async function setPromptAsDefault(promptId) {
    try {
        const result = await fetchAPI(`/api/user/prompts/${promptId}/set-default`, {
            method: 'POST'
        });

        if (result) {
            showToast('Default prompt updated', 'success');
            await refreshSavedPrompts();
        }
    } catch (e) {
        showToast('Error setting default: ' + e.message, 'error');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('editPromptBtn');
    if (btn) {
        btn.addEventListener('click', () => {
            loadSystemPrompts();
            document.getElementById('promptEditorModal').style.display = 'flex';
        });
    }
});

// Make functions globally available
window.loadSystemPrompts = loadSystemPrompts;
window.saveSystemPrompt = saveSystemPrompt;
window.closePromptEditorModal = closePromptEditorModal;
window.refreshSavedPrompts = refreshSavedPrompts;
window.loadSelectedPrompt = loadSelectedPrompt;
window.deleteSelectedPrompt = deleteSelectedPrompt;
window.saveAsNewPrompt = saveAsNewPrompt;
window.loadDefaultPrompt = loadDefaultPrompt;
window.updateSelectedPrompt = updateSelectedPrompt;
window.setPromptAsDefault = setPromptAsDefault;
