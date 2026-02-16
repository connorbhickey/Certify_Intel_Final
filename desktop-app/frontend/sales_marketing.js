/**
 * Certify Intel - Sales & Marketing Module JavaScript (v5.0.7)
 * Handles dimension scoring, battlecard generation, competitor comparison, and talking points.
 *
 * Integrates with existing app_v2.js and API endpoints in /api/sales-marketing/
 */

// ============== Constants ==============
const API_BASE = window.location.origin;

const SM_DIMENSIONS = [
    { id: 'product_packaging', name: 'Product Modules & Packaging', shortName: 'Packaging', icon: '📦' },
    { id: 'integration_depth', name: 'Interoperability & Integration', shortName: 'Integration', icon: '🔗' },
    { id: 'support_service', name: 'Customer Support & Service', shortName: 'Support', icon: '🎧' },
    { id: 'retention_stickiness', name: 'Retention & Product Stickiness', shortName: 'Retention', icon: '🔒' },
    { id: 'user_adoption', name: 'User Adoption & Ease of Use', shortName: 'Adoption', icon: '👥' },
    { id: 'implementation_ttv', name: 'Implementation & Time to Value', shortName: 'Implementation', icon: '⏱️' },
    { id: 'reliability_enterprise', name: 'Reliability & Enterprise Readiness', shortName: 'Reliability', icon: '🏢' },
    { id: 'pricing_flexibility', name: 'Pricing & Commercial Flexibility', shortName: 'Pricing', icon: '💰' },
    { id: 'reporting_analytics', name: 'Reporting & Analytics', shortName: 'Analytics', icon: '📊' }
];

const SM_SCORE_LABELS = {
    1: 'Major Weakness',
    2: 'Weakness',
    3: 'Neutral',
    4: 'Strength',
    5: 'Major Strength'
};

const SM_SCORE_COLORS = {
    1: '#dc3545',
    2: '#fd7e14',
    3: '#6c757d',
    4: '#28a745',
    5: '#198754'
};

// Current state
let currentDimensionData = {};
let dimensionRadarChart = null;

// ============== Tab Navigation ==============

function showSalesMarketingTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.sm-tab-content').forEach(tab => {
        tab.style.display = 'none';
        tab.classList.remove('active');
    });
    document.querySelectorAll('.sm-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const tab = document.getElementById('sm-' + tabName + 'Tab');
    if (tab) {
        tab.style.display = 'block';
        tab.classList.add('active');
    }

    // SM-002 FIX: Find and highlight the active button by tab name mapping
    const tabButtonMap = {
        'dimensions': 0,
        'dealintel': 1,
        'winthemes': 2,
        'objections': 3,
        'battlecards': 4,
        'comparison': 5,
        'talkingpoints': 6,
        'positioning': 7,
        'quicklookup': 8,
        'pricing': 9,
        'playbook': 10
    };
    const buttons = document.querySelectorAll('.sm-tab-btn');
    const buttonIndex = tabButtonMap[tabName];
    if (buttonIndex !== undefined && buttons[buttonIndex]) {
        buttons[buttonIndex].classList.add('active');
    }

    // Load data for specific tabs
    if (tabName === 'dimensions') {
        // Dimensions tab - data loaded on competitor select
    } else if (tabName === 'comparison') {
        // Initialize comparison - nothing to preload
    } else if (tabName === 'talkingpoints') {
        loadTalkingPointsDimensions();
    } else if (tabName === 'dealintel' || tabName === 'winthemes' || tabName === 'objections') {
        // New tabs - populate competitor dropdown
        initNewTabDropdowns(tabName);
    }
}

// ============== Initialization ==============

function initSalesMarketingModule() {
    // Populate all competitor dropdowns
    const selects = [
        'dimensionCompetitorSelect',
        'battlecardCompetitorSelect',
        'compareCompetitor1',
        'compareCompetitor2',
        'talkingPointsCompetitor',
        // New tabs (SM-004, SM-005, SM-007)
        'dealIntelCompetitorSelect',
        'winThemesCompetitorSelect',
        'objectionCompetitorSelect'
    ];

    // Use global competitors array from app_v2.js
    const competitorOptions = (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('');

    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select) {
            select.innerHTML = '<option value="">-- Select Competitor --</option>' + competitorOptions;
        }
    });

    // Populate dimensions dropdown for talking points
    loadTalkingPointsDimensions();

}

// Initialize new tab dropdowns if not already populated
function initNewTabDropdowns(tabName) {
    const dropdownMap = {
        'dealintel': 'dealIntelCompetitorSelect',
        'winthemes': 'winThemesCompetitorSelect',
        'objections': 'objectionCompetitorSelect'
    };

    const selectId = dropdownMap[tabName];
    if (!selectId) return;

    const select = document.getElementById(selectId);
    if (!select || select.options.length > 1) return; // Already populated

    const competitorOptions = (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('');

    select.innerHTML = '<option value="">-- Select Competitor --</option>' + competitorOptions;
}

function loadTalkingPointsDimensions() {
    const dimSelect = document.getElementById('talkingPointsDimension');
    if (dimSelect) {
        dimSelect.innerHTML = '<option value="">All Dimensions</option>' +
            SM_DIMENSIONS.map(d => `<option value="${d.id}">${d.icon} ${d.shortName}</option>`).join('');
    }
}

// ============== Dimension Scorecard ==============

async function loadCompetitorDimensions() {
    const competitorId = document.getElementById('dimensionCompetitorSelect').value;
    if (!competitorId) {
        document.getElementById('dimensionGrid').innerHTML =
            '<p class="sm-placeholder">Select a competitor to view and edit their 9-dimension scorecard.</p>';
        document.getElementById('dimensionProfileSummary').style.display = 'none';
        return;
    }

    try {
        showLoading('Loading dimension scores...');

        const response = await fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        currentDimensionData = data;

        // Update profile summary
        updateDimensionSummary(data);

        // Render dimension grid
        renderDimensionGrid(data);

        hideLoading();
    } catch (error) {
        console.error('Failed to load dimensions:', error);
        hideLoading();
        showNotification('Failed to load dimension scores', 'error');
    }
}

function updateDimensionSummary(data) {
    const summary = document.getElementById('dimensionProfileSummary');
    summary.style.display = 'flex';

    document.getElementById('smOverallScore').textContent =
        data.overall_score ? data.overall_score.toFixed(1) + '/5' : 'Not Scored';
    document.getElementById('smStrengthCount').textContent = data.strengths?.length || 0;
    document.getElementById('smWeaknessCount').textContent = data.weaknesses?.length || 0;

    const priorityEl = document.getElementById('smSalesPriority');
    priorityEl.textContent = data.sales_priority || 'Not Set';
    priorityEl.className = 'sm-summary-value sm-priority-' + (data.sales_priority || 'low').toLowerCase();
}

function renderDimensionGrid(data) {
    const grid = document.getElementById('dimensionGrid');

    grid.innerHTML = SM_DIMENSIONS.map(dim => {
        const dimData = data.dimensions?.[dim.id] || {};
        const score = dimData.score || 0;
        const evidence = dimData.evidence || '';
        const updated = dimData.updated_at ? new Date(dimData.updated_at).toLocaleDateString() : '';

        return `
            <div class="sm-dimension-card" data-dimension="${dim.id}">
                <div class="sm-dimension-header">
                    <span class="sm-dimension-icon">${dim.icon}</span>
                    <span class="sm-dimension-name">${dim.name}</span>
                </div>
                <div class="sm-dimension-score">
                    ${renderScoreSelector(dim.id, score)}
                </div>
                <div class="sm-dimension-evidence">
                    <textarea
                        placeholder="Enter evidence and sources for this score..."
                        id="evidence-${dim.id}"
                        class="form-control"
                        rows="3"
                    >${evidence}</textarea>
                </div>
                <div class="sm-dimension-footer">
                    <span class="sm-dimension-meta">
                        ${updated ? `Updated: ${updated}` : 'Not scored yet'}
                    </span>
                    <div style="display:flex;gap:6px;">
                        <button class="btn btn-sm btn-secondary" onclick="showDimensionHistory('${dim.id}', '${dim.name}')" title="View score history">
                            History
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="saveDimensionScore('${dim.id}')">
                            Save
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderScoreSelector(dimensionId, currentScore) {
    return `<div class="sm-score-selector">` +
        [1, 2, 3, 4, 5].map(score => `
            <button
                class="sm-score-btn ${score === currentScore ? 'active' : ''}"
                onclick="selectDimensionScore('${dimensionId}', ${score})"
                title="${SM_SCORE_LABELS[score]}"
                style="${score === currentScore ? `background-color: ${SM_SCORE_COLORS[score]}; color: white;` : ''}"
            >
                ${score}
            </button>
        `).join('') +
    `</div>`;
}

function selectDimensionScore(dimensionId, score) {
    const card = document.querySelector(`[data-dimension="${dimensionId}"]`);
    if (!card) return;

    // Remove active class from all buttons
    card.querySelectorAll('.sm-score-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.style.backgroundColor = '';
        btn.style.color = '';
    });

    // Set active on selected
    const selectedBtn = card.querySelector(`.sm-score-btn:nth-child(${score})`);
    if (selectedBtn) {
        selectedBtn.classList.add('active');
        selectedBtn.style.backgroundColor = SM_SCORE_COLORS[score];
        selectedBtn.style.color = 'white';
    }
}

async function saveDimensionScore(dimensionId) {
    const competitorId = document.getElementById('dimensionCompetitorSelect').value;
    if (!competitorId) {
        showNotification('Please select a competitor first', 'error');
        return;
    }

    const card = document.querySelector(`[data-dimension="${dimensionId}"]`);
    const activeBtn = card.querySelector('.sm-score-btn.active');
    const evidence = document.getElementById(`evidence-${dimensionId}`).value;

    if (!activeBtn) {
        showNotification('Please select a score (1-5)', 'error');
        return;
    }

    const score = parseInt(activeBtn.textContent);

    try {
        const response = await fetch(
            `/api/sales-marketing/competitors/${competitorId}/dimensions/${dimensionId}?user_email=${encodeURIComponent(getCurrentUserEmail())}`,
            {
                method: 'PUT',
                headers: {
                    ...getAuthHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    dimension_id: dimensionId,
                    score: score,
                    evidence: evidence,
                    source: 'manual',
                    confidence: 'medium'
                })
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        showNotification(`${getDimensionName(dimensionId)} saved (Score: ${score})`, 'success');

        // Refresh to update summary
        await loadCompetitorDimensions();

    } catch (error) {
        console.error('Failed to save dimension:', error);
        showNotification('Failed to save dimension score', 'error');
    }
}

async function saveAllDimensions() {
    const competitorId = document.getElementById('dimensionCompetitorSelect').value;
    if (!competitorId) {
        showNotification('Please select a competitor first', 'error');
        return;
    }

    const updates = [];

    SM_DIMENSIONS.forEach(dim => {
        const card = document.querySelector(`[data-dimension="${dim.id}"]`);
        if (!card) return;

        const activeBtn = card.querySelector('.sm-score-btn.active');
        const evidence = document.getElementById(`evidence-${dim.id}`).value;

        if (activeBtn) {
            updates.push({
                dimension_id: dim.id,
                score: parseInt(activeBtn.textContent),
                evidence: evidence,
                source: 'manual',
                confidence: 'medium'
            });
        }
    });

    if (updates.length === 0) {
        showNotification('No dimensions have scores selected', 'warning');
        return;
    }

    try {
        showLoading('Saving all dimensions...');

        const response = await fetch(
            `/api/sales-marketing/competitors/${competitorId}/dimensions/bulk-update?user_email=${encodeURIComponent(getCurrentUserEmail())}`,
            {
                method: 'POST',
                headers: {
                    ...getAuthHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updates)
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        hideLoading();

        showNotification(`Saved ${result.successful} dimension(s)`, 'success');

        // Refresh
        await loadCompetitorDimensions();

    } catch (error) {
        hideLoading();
        console.error('Failed to save dimensions:', error);
        showNotification('Failed to save dimensions', 'error');
    }
}

async function aiSuggestDimensions() {
    const competitorId = document.getElementById('dimensionCompetitorSelect').value;
    if (!competitorId) {
        showNotification('Please select a competitor first', 'error');
        return;
    }

    try {
        showLoading('AI analyzing competitor data...');

        const response = await fetch(
            `/api/sales-marketing/competitors/${competitorId}/dimensions/ai-suggest`,
            {
                method: 'POST',
                headers: getAuthHeaders()
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        hideLoading();

        if (!data.suggestions || Object.keys(data.suggestions).length === 0) {
            showNotification('No AI suggestions available - not enough data', 'warning');
            return;
        }

        // Apply suggestions to the UI
        Object.entries(data.suggestions).forEach(([dimId, suggestion]) => {
            if (suggestion.score) {
                selectDimensionScore(dimId, suggestion.score);
            }
            if (suggestion.evidence) {
                const evidenceField = document.getElementById(`evidence-${dimId}`);
                if (evidenceField && !evidenceField.value) {
                    evidenceField.value = suggestion.evidence;
                }
            }
        });

        showNotification(`AI suggested ${Object.keys(data.suggestions).length} dimension score(s)`, 'success');

    } catch (error) {
        hideLoading();
        console.error('AI suggestion failed:', error);
        showNotification('AI suggestion failed', 'error');
    }
}

// ============== Dynamic Battlecards ==============

async function generateDynamicBattlecard() {
    const competitorId = document.getElementById('battlecardCompetitorSelect').value;
    const battlecardType = document.getElementById('battlecardType').value;

    if (!competitorId) {
        showNotification('Please select a competitor', 'error');
        return;
    }

    const container = document.getElementById('dynamicBattlecardContent');
    container.innerHTML = '<div class="sm-loading">Generating battlecard...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/sales-marketing/battlecards/generate`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                competitor_id: parseInt(competitorId),
                battlecard_type: battlecardType
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderDynamicBattlecard(data);

    } catch (error) {
        console.error('Failed to generate battlecard:', error);
        container.innerHTML = '<p class="sm-error">Failed to generate battlecard. Please try again.</p>';
        showNotification('Battlecard generation failed', 'error');
    }
}

function renderDynamicBattlecard(data) {
    const container = document.getElementById('dynamicBattlecardContent');

    const sectionsHtml = data.sections.map(section => {
        let contentHtml = '';

        if (typeof section.content === 'string') {
            contentHtml = `<p>${section.content}</p>`;
        } else if (Array.isArray(section.content)) {
            contentHtml = '<ul>' + section.content.map(item => {
                if (typeof item === 'object') {
                    return '<li>' + Object.entries(item)
                        .map(([k, v]) => `<strong>${formatLabel(k)}:</strong> ${v}`)
                        .join('<br>') + '</li>';
                }
                return `<li>${item}</li>`;
            }).join('') + '</ul>';
        } else if (typeof section.content === 'object') {
            contentHtml = '<div class="sm-facts-grid">' +
                Object.entries(section.content)
                    .map(([k, v]) => `<div class="sm-fact"><span class="sm-fact-label">${formatLabel(k)}</span><span class="sm-fact-value">${v}</span></div>`)
                    .join('') +
                '</div>';
        }

        return `
            <div class="sm-battlecard-section">
                <h4>${escapeHtml(section.title)}</h4>
                ${contentHtml}
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div class="sm-battlecard">
            <div class="sm-battlecard-header">
                <h3>${escapeHtml(data.title)}</h3>
                <div class="sm-battlecard-actions">
                    ${data.id ? `
                        <button class="btn btn-secondary" onclick="exportBattlecardMarkdown(${data.id})">
                            📝 Export Markdown
                        </button>
                        <button class="btn btn-primary" onclick="exportBattlecardPDF(${data.id})">
                            📄 Export PDF
                        </button>
                    ` : ''}
                </div>
            </div>
            <div class="sm-battlecard-meta">
                <span>Type: ${escapeHtml(data.battlecard_type)}</span>
                <span>Generated: ${new Date(data.generated_at).toLocaleString()}</span>
            </div>
            <div class="sm-battlecard-body">
                ${sectionsHtml}
            </div>
        </div>
    `;
}

async function exportBattlecardPDF(battlecardId) {
    window.open(`/api/sales-marketing/battlecards/${battlecardId}/pdf`, '_blank');
}

async function exportBattlecardMarkdown(battlecardId) {
    window.open(`/api/sales-marketing/battlecards/${battlecardId}/markdown`, '_blank');
}

// ============== Competitor Comparison ==============

async function loadDimensionComparison() {
    const comp1 = document.getElementById('compareCompetitor1').value;
    const comp2 = document.getElementById('compareCompetitor2').value;

    if (!comp1 || !comp2) {
        showNotification('Please select two competitors to compare', 'error');
        return;
    }

    if (comp1 === comp2) {
        showNotification('Please select different competitors', 'error');
        return;
    }

    try {
        showLoading('Loading comparison...');

        const response = await fetch(`${API_BASE}/api/sales-marketing/compare/dimensions`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                competitor_ids: [parseInt(comp1), parseInt(comp2)]
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        hideLoading();

        renderComparisonRadarChart(data);
        renderComparisonDetails(data);

    } catch (error) {
        hideLoading();
        console.error('Comparison failed:', error);
        showNotification('Failed to load comparison', 'error');
    }
}

function renderComparisonRadarChart(data) {
    const ctx = document.getElementById('dimensionRadarChart').getContext('2d');

    // Destroy existing chart
    if (dimensionRadarChart) {
        dimensionRadarChart.destroy();
    }

    const labels = SM_DIMENSIONS.map(d => d.shortName);
    const datasets = data.competitors.map((comp, i) => ({
        label: comp.name,
        data: SM_DIMENSIONS.map(d => comp.dimensions[d.id]?.score || 0),
        borderColor: i === 0 ? '#2F5496' : '#22c55e',
        backgroundColor: i === 0 ? 'rgba(47, 84, 150, 0.2)' : 'rgba(34, 197, 94, 0.2)',
        borderWidth: 2,
        pointRadius: 4
    }));

    dimensionRadarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                r: {
                    min: 0,
                    max: 5,
                    ticks: {
                        stepSize: 1,
                        display: true
                    },
                    pointLabels: {
                        font: { size: 11 }
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                }
            }
        }
    });
}

function renderComparisonDetails(data) {
    const container = document.getElementById('comparisonDetails');

    // Find advantages and weaknesses
    const comp1 = data.competitors[0];
    const comp2 = data.competitors[1];

    let detailsHtml = '<div class="sm-comparison-grid">';

    SM_DIMENSIONS.forEach(dim => {
        const score1 = comp1.dimensions[dim.id]?.score || 0;
        const score2 = comp2.dimensions[dim.id]?.score || 0;
        const diff = score1 - score2;

        let indicator = '';
        if (diff > 0) indicator = `<span class="sm-indicator sm-better">${comp1.name} +${diff}</span>`;
        else if (diff < 0) indicator = `<span class="sm-indicator sm-worse">${comp2.name} +${Math.abs(diff)}</span>`;
        else indicator = '<span class="sm-indicator sm-even">Even</span>';

        detailsHtml += `
            <div class="sm-comparison-row">
                <span class="sm-dim-icon">${dim.icon}</span>
                <span class="sm-dim-name">${dim.shortName}</span>
                <span class="sm-score">${score1 || '-'}</span>
                <span class="sm-vs">vs</span>
                <span class="sm-score">${score2 || '-'}</span>
                ${indicator}
            </div>
        `;
    });

    detailsHtml += '</div>';
    container.innerHTML = detailsHtml;
}

async function compareVsCertify() {
    const comp1 = document.getElementById('compareCompetitor1').value;
    if (!comp1) {
        showNotification('Please select a competitor in the first dropdown', 'error');
        return;
    }

    try {
        showLoading('Comparing vs Certify Health...');

        const response = await fetch(`${API_BASE}/api/sales-marketing/compare/${comp1}/vs-certify`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        hideLoading();

        // Transform to comparison format
        const comparisonData = {
            competitors: [
                {
                    name: data.competitor.name,
                    dimensions: Object.fromEntries(
                        Object.entries(data.competitor.scores).map(([k, v]) => [k, { score: v }])
                    )
                },
                {
                    name: 'Certify Health',
                    dimensions: Object.fromEntries(
                        Object.entries(data.certify_health.scores).map(([k, v]) => [k, { score: v }])
                    )
                }
            ]
        };

        renderComparisonRadarChart(comparisonData);
        renderCertifyComparisonDetails(data);

    } catch (error) {
        hideLoading();
        console.error('Certify comparison failed:', error);
        showNotification('Failed to load Certify comparison', 'error');
    }
}

function renderCertifyComparisonDetails(data) {
    const container = document.getElementById('comparisonDetails');

    let html = `
        <div class="sm-certify-comparison">
            <h4>Competitive Analysis vs ${data.competitor.name}</h4>

            <div class="sm-advantages">
                <h5>Our Advantages (${data.advantages.length})</h5>
                ${data.advantages.length ? data.advantages.map(a => `
                    <div class="sm-advantage-item">
                        <span class="sm-adv-dim">${a.dimension}</span>
                        <span class="sm-adv-scores">Certify: ${a.certify_score} vs ${a.competitor_score}</span>
                        <span class="sm-adv-gap">+${a.gap} advantage</span>
                    </div>
                `).join('') : '<p>No clear advantages identified</p>'}
            </div>

            <div class="sm-challenges">
                <h5>Challenges (${data.challenges.length})</h5>
                ${data.challenges.length ? data.challenges.map(c => `
                    <div class="sm-challenge-item">
                        <span class="sm-ch-dim">${c.dimension}</span>
                        <span class="sm-ch-scores">Certify: ${c.certify_score} vs ${c.competitor_score}</span>
                        <span class="sm-ch-gap">-${c.gap} gap</span>
                    </div>
                `).join('') : '<p>No significant challenges identified</p>'}
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// ============== Talking Points ==============

async function loadTalkingPoints() {
    const competitorId = document.getElementById('talkingPointsCompetitor').value;
    if (!competitorId) {
        document.getElementById('talkingPointsList').innerHTML =
            '<p class="sm-placeholder">Select a competitor to view talking points organized by dimension.</p>';
        return;
    }

    const dimensionId = document.getElementById('talkingPointsDimension').value || '';
    const pointType = document.getElementById('talkingPointsType').value || '';

    try {
        let url = `/api/sales-marketing/competitors/${competitorId}/talking-points?`;
        if (dimensionId) url += `dimension_id=${dimensionId}&`;
        if (pointType) url += `point_type=${pointType}&`;

        const response = await fetch(url, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderTalkingPoints(data.talking_points);

    } catch (error) {
        console.error('Failed to load talking points:', error);
        showNotification('Failed to load talking points', 'error');
    }
}

function renderTalkingPoints(points) {
    const container = document.getElementById('talkingPointsList');

    if (!points || points.length === 0) {
        container.innerHTML = `
            <div class="sm-empty-state">
                <p>No talking points found for this selection.</p>
                <button class="btn btn-primary" onclick="showAddTalkingPointModal()">
                    ➕ Add First Talking Point
                </button>
            </div>
        `;
        return;
    }

    // Group by dimension
    const byDimension = {};
    points.forEach(p => {
        if (!byDimension[p.dimension_id]) {
            byDimension[p.dimension_id] = [];
        }
        byDimension[p.dimension_id].push(p);
    });

    let html = '';
    Object.entries(byDimension).forEach(([dimId, dimPoints]) => {
        const dim = SM_DIMENSIONS.find(d => d.id === dimId) || { icon: '?', name: dimId };

        html += `
            <div class="sm-tp-dimension">
                <h4>${dim.icon} ${dim.name}</h4>
                <div class="sm-tp-list">
                    ${dimPoints.map(p => `
                        <div class="sm-talking-point sm-tp-${p.point_type}">
                            <div class="sm-tp-header">
                                <span class="sm-tp-type">${formatPointType(p.point_type)}</span>
                                ${p.effectiveness_score ? `
                                    <span class="sm-tp-effectiveness" title="Effectiveness">
                                        ${'★'.repeat(p.effectiveness_score)}${'☆'.repeat(5 - p.effectiveness_score)}
                                    </span>
                                ` : ''}
                            </div>
                            <p class="sm-tp-content">${p.content}</p>
                            ${p.context ? `<p class="sm-tp-context">Context: ${p.context}</p>` : ''}
                            <div class="sm-tp-footer">
                                <span class="sm-tp-meta">By ${p.created_by} on ${new Date(p.created_at).toLocaleDateString()}</span>
                                <button class="btn btn-sm btn-secondary" onclick="deleteTalkingPoint(${p.id})">Delete</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function showAddTalkingPointModal() {
    const competitorId = document.getElementById('talkingPointsCompetitor').value;
    if (!competitorId) {
        showNotification('Please select a competitor first', 'error');
        return;
    }

    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'addTalkingPointModal';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>Add Talking Point</h3>
                <button class="modal-close" onclick="document.getElementById('addTalkingPointModal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Dimension</label>
                    <select id="newTpDimension" class="form-select">
                        ${SM_DIMENSIONS.map(d => `<option value="${d.id}">${d.icon} ${d.name}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label>Type</label>
                    <select id="newTpType" class="form-select">
                        <option value="strength">Strength</option>
                        <option value="weakness">Weakness</option>
                        <option value="objection">Objection</option>
                        <option value="counter">Counter-Point</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Talking Point</label>
                    <textarea id="newTpContent" class="form-control" rows="3" placeholder="Enter the talking point..."></textarea>
                </div>
                <div class="form-group">
                    <label>Context (Optional)</label>
                    <input type="text" id="newTpContext" class="form-control" placeholder="When to use this talking point">
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="document.getElementById('addTalkingPointModal').remove()">Cancel</button>
                <button class="btn btn-primary" onclick="saveTalkingPoint()">Save</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

async function saveTalkingPoint() {
    const competitorId = document.getElementById('talkingPointsCompetitor').value;
    const dimensionId = document.getElementById('newTpDimension').value;
    const pointType = document.getElementById('newTpType').value;
    const content = document.getElementById('newTpContent').value;
    const context = document.getElementById('newTpContext').value;

    if (!content.trim()) {
        showNotification('Please enter the talking point content', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sales-marketing/talking-points?user_email=${encodeURIComponent(getCurrentUserEmail())}`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                competitor_id: parseInt(competitorId),
                dimension_id: dimensionId,
                point_type: pointType,
                content: content.trim(),
                context: context.trim() || null
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        document.getElementById('addTalkingPointModal').remove();
        showNotification('Talking point added', 'success');
        loadTalkingPoints();

    } catch (error) {
        console.error('Failed to save talking point:', error);
        showNotification('Failed to save talking point', 'error');
    }
}

async function deleteTalkingPoint(pointId) {
    if (!confirm('Delete this talking point?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/sales-marketing/talking-points/${pointId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        showNotification('Talking point deleted', 'success');
        loadTalkingPoints();

    } catch (error) {
        console.error('Failed to delete talking point:', error);
        showNotification('Failed to delete talking point', 'error');
    }
}

// ============== Utility Functions ==============

function getDimensionName(dimensionId) {
    const dim = SM_DIMENSIONS.find(d => d.id === dimensionId);
    return dim ? dim.name : dimensionId;
}

function formatLabel(label) {
    return label.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatPointType(type) {
    const labels = {
        strength: '💪 Strength',
        weakness: '⚠️ Weakness',
        objection: '🤔 Objection',
        counter: '🔄 Counter'
    };
    return labels[type] || type;
}

function getCurrentUserEmail() {
    // Try to get from localStorage or return default
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    return user.email || 'system@certifyhealth.com';
}

function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
}

function showLoading(message) {
    // Use existing loading mechanism from app_v2.js if available
    if (typeof window.showLoadingOverlay === 'function') {
        window.showLoadingOverlay(message);
    }
}

function hideLoading() {
    if (typeof window.hideLoadingOverlay === 'function') {
        window.hideLoadingOverlay();
    }
}

function showNotification(message, type) {
    // Use existing notification mechanism from app_v2.js if available
    if (typeof window.showNotification === 'function') {
        window.showNotification(message, type);
    } else {
        alert(message);
    }
}

// ============== Battlecard Page Dimension Widget (v5.0.7) ==============

/**
 * Initialize the dimension widget on the Battlecard page.
 * Called when the battlecards page loads.
 */
async function initBattlecardDimensionWidget() {
    const select = document.getElementById('battlecardDimensionCompetitor');
    if (!select) return;

    try {
        const response = await fetch(`${API_BASE}/api/competitors`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) return;

        const competitors = await response.json();

        select.innerHTML = '<option value="">-- Select Competitor for Dimensions --</option>';
        competitors.forEach(c => {
            const option = document.createElement('option');
            option.value = c.id;
            option.textContent = `${c.name} (${c.threat_level || 'Unknown'} Threat)`;
            select.appendChild(option);
        });

    } catch (error) {
        console.error('Failed to load competitors for dimension widget:', error);
    }
}

/**
 * Load and display dimension scores for the selected competitor in the widget.
 */
async function loadBattlecardDimensionWidget() {
    const competitorId = document.getElementById('battlecardDimensionCompetitor').value;
    const container = document.getElementById('battlecardDimensionScores');

    if (!competitorId) {
        container.innerHTML = '<p class="sm-placeholder">Select a competitor to see their dimension scores</p>';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderDimensionWidget(data);

    } catch (error) {
        console.error('Failed to load dimension widget:', error);
        container.innerHTML = '<p class="sm-placeholder">Failed to load dimension scores</p>';
    }
}

/**
 * Render the compact dimension scores widget.
 */
function renderDimensionWidget(data) {
    const container = document.getElementById('battlecardDimensionScores');

    const dimensions = data.dimensions || {};
    const overall = data.overall_score;

    let html = '<div class="dimension-widget-grid">';

    // Overall score badge
    if (overall) {
        html += `
            <div class="dimension-widget-overall">
                <span class="widget-overall-label">Overall</span>
                <span class="widget-overall-score">${overall.toFixed(1)}/5</span>
            </div>
        `;
    }

    // Compact dimension scores
    SM_DIMENSIONS.forEach(dim => {
        const dimData = dimensions[dim.id] || {};
        const score = dimData.score;
        const scoreColor = score ? SM_SCORE_COLORS[score] : '#ccc';
        const scoreLabel = score ? SM_SCORE_LABELS[score] : 'Not Scored';

        html += `
            <div class="dimension-widget-item" title="${dim.name}: ${scoreLabel}">
                <span class="widget-dim-icon">${dim.icon}</span>
                <span class="widget-dim-name">${dim.shortName}</span>
                <span class="widget-dim-score" style="background-color: ${scoreColor}">
                    ${score || '-'}
                </span>
            </div>
        `;
    });

    html += '</div>';

    // Quick actions
    html += `
        <div class="dimension-widget-actions">
            <button class="btn btn-sm btn-secondary" onclick="showPage('salesmarketing'); setTimeout(() => {
                document.getElementById('dimensionCompetitorSelect').value = '${data.competitor_id}';
                loadCompetitorDimensions();
            }, 100);">
                📊 View Full Scorecard
            </button>
            <button class="btn btn-sm btn-primary" onclick="showPage('salesmarketing'); setTimeout(() => {
                showSalesMarketingTab('battlecards');
                document.getElementById('battlecardCompetitorSelect').value = '${data.competitor_id}';
            }, 100);">
                ⚔️ Generate Dimension Battlecard
            </button>
        </div>
    `;

    container.innerHTML = html;
}

// ============== SM-004: Competitive Win Themes Generator ==============

/**
 * Generate AI-powered win themes for a specific competitor.
 * Shows why we typically win against this competitor.
 */
async function generateWinThemes(competitorId = null) {
    const id = competitorId || document.getElementById('winThemesCompetitorSelect')?.value;
    if (!id) {
        showNotification('Please select a competitor', 'warning');
        return;
    }

    const container = document.getElementById('winThemesContent');
    if (container) {
        container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Generating win themes with AI...</div>';
    }

    try {
        const response = await fetch(`${API_BASE}/api/sales-marketing/competitors/${id}/win-themes`, {
            method: 'POST',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderWinThemes(data);

    } catch (error) {
        console.error('Failed to generate win themes:', error);
        if (container) {
            container.innerHTML = `
                <div class="error-message">
                    <p>Failed to generate win themes. ${error.message}</p>
                    <button class="btn btn-secondary" onclick="generateWinThemes()">Try Again</button>
                </div>
            `;
        }
    }
}

function renderWinThemes(data) {
    const container = document.getElementById('winThemesContent');
    if (!container) return;

    const themes = data.themes || [];
    const competitor = data.competitor_name || 'Competitor';

    let html = `
        <div class="win-themes-header">
            <h3>Why We Win Against ${competitor}</h3>
            <p class="win-themes-subtitle">AI-generated based on competitive analysis, win/loss data, and dimension scores</p>
        </div>
        <div class="win-themes-grid">
    `;

    themes.forEach((theme, index) => {
        const icon = theme.icon || ['🏆', '💪', '🎯', '🚀', '✨'][index % 5];
        html += `
            <div class="win-theme-card">
                <div class="win-theme-icon">${icon}</div>
                <h4 class="win-theme-title">${theme.title}</h4>
                <p class="win-theme-description">${theme.description}</p>
                <div class="win-theme-evidence">
                    <strong>Key Evidence:</strong>
                    <ul>
                        ${(theme.evidence || []).map(e => `<li>${e}</li>`).join('')}
                    </ul>
                </div>
                <div class="win-theme-tags">
                    ${(theme.dimensions || []).map(d => `<span class="dimension-tag">${d}</span>`).join('')}
                </div>
            </div>
        `;
    });

    html += `
        </div>
        <div class="win-themes-actions">
            <button class="btn btn-primary" onclick="copyWinThemesToClipboard()">
                📋 Copy to Clipboard
            </button>
            <button class="btn btn-secondary" onclick="exportWinThemesToSlides()">
                📊 Export to Slides
            </button>
        </div>
    `;

    container.innerHTML = html;
}

function copyWinThemesToClipboard() {
    const container = document.getElementById('winThemesContent');
    const text = container?.innerText || '';
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Win themes copied to clipboard!', 'success');
    });
}

function exportWinThemesToSlides() {
    showNotification('Export to slides coming soon!', 'info');
}


// ============== SM-005: Objection Handler Tool ==============

let objectionDatabase = [];

/**
 * Load objection database for a competitor.
 */
async function loadObjections(competitorId = null) {
    const id = competitorId || document.getElementById('objectionCompetitorSelect')?.value;
    const container = document.getElementById('objectionsList');

    if (!id) {
        if (container) {
            container.innerHTML = '<p class="sm-placeholder">Select a competitor to view objections and responses.</p>';
        }
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/sales-marketing/competitors/${id}/objections`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            // If endpoint doesn't exist yet, show placeholder
            if (response.status === 404) {
                renderObjectionsPlaceholder();
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        objectionDatabase = data.objections || [];
        renderObjections();

    } catch (error) {
        console.error('Failed to load objections:', error);
        renderObjectionsPlaceholder();
    }
}

function renderObjectionsPlaceholder() {
    const container = document.getElementById('objectionsList');
    if (!container) return;

    // Show common objections with placeholder responses
    const commonObjections = [
        {
            category: 'Pricing',
            objection: 'Your solution is more expensive than competitors',
            response: 'Focus on total cost of ownership (TCO). Our implementation is faster, support is included, and there are no hidden fees. Calculate ROI over 3 years.',
            effectiveness: 85
        },
        {
            category: 'Features',
            objection: 'Competitor X has feature Y that you lack',
            response: 'Understand the actual use case. Often our platform addresses the underlying need differently. Demonstrate our approach and gather feedback.',
            effectiveness: 78
        },
        {
            category: 'Integration',
            objection: 'How do you integrate with our existing systems?',
            response: 'We have pre-built integrations with 50+ EHR/PM systems. Our API is fully documented. Implementation team handles custom integrations.',
            effectiveness: 92
        },
        {
            category: 'Experience',
            objection: 'Competitor has been in the market longer',
            response: 'Modern platform built on latest technology. Faster innovation cycles. No legacy debt. Customer success metrics often exceed established players.',
            effectiveness: 72
        }
    ];

    objectionDatabase = commonObjections;
    renderObjections();
}

function renderObjections() {
    const container = document.getElementById('objectionsList');
    if (!container) return;

    const searchTerm = document.getElementById('objectionSearch')?.value?.toLowerCase() || '';
    const categoryFilter = document.getElementById('objectionCategory')?.value || '';

    let filtered = objectionDatabase;

    if (searchTerm) {
        filtered = filtered.filter(o =>
            o.objection.toLowerCase().includes(searchTerm) ||
            o.response.toLowerCase().includes(searchTerm)
        );
    }

    if (categoryFilter) {
        filtered = filtered.filter(o => o.category === categoryFilter);
    }

    if (filtered.length === 0) {
        container.innerHTML = '<p class="sm-placeholder">No objections found matching your criteria.</p>';
        return;
    }

    let html = '<div class="objections-grid">';

    filtered.forEach((obj, index) => {
        const effectivenessColor = obj.effectiveness >= 80 ? '#28a745' :
                                   obj.effectiveness >= 60 ? '#ffc107' : '#dc3545';

        html += `
            <div class="objection-card">
                <div class="objection-header">
                    <span class="objection-category">${obj.category}</span>
                    <span class="objection-effectiveness" style="color: ${effectivenessColor}">
                        ${obj.effectiveness}% effective
                    </span>
                </div>
                <div class="objection-content">
                    <p class="objection-text"><strong>Objection:</strong> "${obj.objection}"</p>
                    <p class="objection-response"><strong>Response:</strong> ${obj.response}</p>
                </div>
                <div class="objection-actions">
                    <button class="btn btn-sm btn-secondary" onclick="copyObjectionResponse(${index})">
                        📋 Copy Response
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="getAIEnhancedResponse(${index})">
                        🤖 Enhance with AI
                    </button>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.innerHTML = html;
}

function copyObjectionResponse(index) {
    const obj = objectionDatabase[index];
    if (obj) {
        navigator.clipboard.writeText(obj.response).then(() => {
            showNotification('Response copied to clipboard!', 'success');
        });
    }
}

async function getAIEnhancedResponse(index) {
    const obj = objectionDatabase[index];
    if (!obj) return;

    showNotification('Generating AI-enhanced response...', 'info');

    try {
        const competitorId = document.getElementById('objectionCompetitorSelect')?.value;
        const response = await fetch(`${API_BASE}/api/ai/enhance-objection-response`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                competitor_id: competitorId,
                objection: obj.objection,
                current_response: obj.response
            })
        });

        if (!response.ok) {
            throw new Error('AI enhancement not available');
        }

        const data = await response.json();
        obj.response = data.enhanced_response;
        renderObjections();
        showNotification('Response enhanced with AI!', 'success');

    } catch (error) {
        showNotification('AI enhancement not available - using standard response', 'info');
    }
}

function searchObjections() {
    renderObjections();
}


// ============== SM-007: Deal Intelligence Dashboard ==============

let dealIntelData = null;

/**
 * Load deal intelligence for a specific competitor.
 */
async function loadDealIntelligence(competitorId = null) {
    const id = competitorId || document.getElementById('dealIntelCompetitorSelect')?.value;
    const container = document.getElementById('dealIntelContent');

    if (!id) {
        if (container) {
            container.innerHTML = '<p class="sm-placeholder">Select a competitor to see deal intelligence.</p>';
        }
        return;
    }

    try {
        container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Loading deal intelligence...</div>';

        // Fetch multiple data sources in parallel
        const [dimensionsRes, newsRes, competitorRes] = await Promise.all([
            fetch(`${API_BASE}/api/sales-marketing/competitors/${id}/dimensions`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/competitors/${id}/news?limit=5`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/competitors/${id}`, { headers: getAuthHeaders() })
        ]);

        const dimensions = await dimensionsRes.json();
        const news = await newsRes.json();
        const competitor = await competitorRes.json();

        dealIntelData = { dimensions, news, competitor };
        renderDealIntelligence();

    } catch (error) {
        console.error('Failed to load deal intelligence:', error);
        container.innerHTML = '<p class="error-message">Failed to load deal intelligence. Please try again.</p>';
    }
}

function renderDealIntelligence() {
    const container = document.getElementById('dealIntelContent');
    if (!container || !dealIntelData) return;

    const { dimensions, news, competitor } = dealIntelData;
    const dimData = dimensions.dimensions || {};

    // Find strengths and weaknesses
    const strengths = [];
    const weaknesses = [];

    SM_DIMENSIONS.forEach(dim => {
        const score = dimData[dim.id]?.score;
        if (score >= 4) {
            strengths.push({ ...dim, score, evidence: dimData[dim.id]?.evidence || '' });
        } else if (score && score <= 2) {
            weaknesses.push({ ...dim, score, evidence: dimData[dim.id]?.evidence || '' });
        }
    });

    let html = `
        <div class="deal-intel-header">
            <h3>Deal Intelligence: ${competitor.name}</h3>
            <span class="threat-badge threat-${(competitor.threat_level || 'medium').toLowerCase()}">
                ${competitor.threat_level || 'Medium'} Threat
            </span>
        </div>

        <div class="deal-intel-grid">
            <!-- Competitor Quick Facts -->
            <div class="deal-intel-card">
                <h4>📊 Quick Facts</h4>
                <div class="quick-facts-list">
                    <div class="quick-fact"><span>Founded</span><span>${competitor.year_founded || 'N/A'}</span></div>
                    <div class="quick-fact"><span>Employees</span><span>${competitor.employee_count || 'N/A'}</span></div>
                    <div class="quick-fact"><span>Funding</span><span>${competitor.funding_total || 'N/A'}</span></div>
                    <div class="quick-fact"><span>G2 Rating</span><span>${competitor.g2_rating || 'N/A'}</span></div>
                </div>
            </div>

            <!-- Their Strengths -->
            <div class="deal-intel-card card-warning">
                <h4>⚠️ Their Strengths (Watch Out)</h4>
                ${strengths.length > 0 ? `
                    <ul class="intel-list">
                        ${strengths.map(s => `
                            <li>
                                <strong>${s.icon} ${s.shortName}</strong> (Score: ${s.score}/5)
                                ${s.evidence ? `<p class="intel-evidence">${s.evidence}</p>` : ''}
                            </li>
                        `).join('')}
                    </ul>
                ` : '<p class="text-muted">No major strengths identified</p>'}
            </div>

            <!-- Their Weaknesses -->
            <div class="deal-intel-card card-success">
                <h4>🎯 Their Weaknesses (Attack Here)</h4>
                ${weaknesses.length > 0 ? `
                    <ul class="intel-list">
                        ${weaknesses.map(w => `
                            <li>
                                <strong>${w.icon} ${w.shortName}</strong> (Score: ${w.score}/5)
                                ${w.evidence ? `<p class="intel-evidence">${w.evidence}</p>` : ''}
                            </li>
                        `).join('')}
                    </ul>
                ` : '<p class="text-muted">No major weaknesses identified - proceed with caution</p>'}
            </div>

            <!-- Recent News -->
            <div class="deal-intel-card">
                <h4>📰 Recent News</h4>
                ${news.length > 0 ? `
                    <ul class="news-list">
                        ${news.slice(0, 5).map(n => `
                            <li>
                                <a href="${n.url}" target="_blank">${n.title}</a>
                                <span class="news-date">${new Date(n.published_at || n.fetched_at).toLocaleDateString()}</span>
                            </li>
                        `).join('')}
                    </ul>
                ` : '<p class="text-muted">No recent news available</p>'}
            </div>
        </div>

        <div class="deal-intel-actions">
            <button class="btn btn-primary" onclick="generateQuickBattlecard()">
                ⚔️ Generate Quick Battlecard
            </button>
            <button class="btn btn-secondary" onclick="generateWinThemes()">
                🏆 Get Win Themes
            </button>
            <button class="btn btn-secondary" onclick="loadObjections()">
                💬 See Objection Responses
            </button>
        </div>
    `;

    container.innerHTML = html;
}

async function generateQuickBattlecard() {
    const competitorId = document.getElementById('dealIntelCompetitorSelect')?.value;
    if (!competitorId) return;

    // Navigate to battlecards tab with this competitor pre-selected
    showSalesMarketingTab('battlecards');
    setTimeout(() => {
        document.getElementById('battlecardCompetitorSelect').value = competitorId;
        generateDynamicBattlecard();
    }, 100);
}


// ============== Export for Global Access ==============

window.initSalesMarketingModule = initSalesMarketingModule;
window.showSalesMarketingTab = showSalesMarketingTab;
window.loadCompetitorDimensions = loadCompetitorDimensions;
window.selectDimensionScore = selectDimensionScore;
window.saveDimensionScore = saveDimensionScore;
window.saveAllDimensions = saveAllDimensions;
window.aiSuggestDimensions = aiSuggestDimensions;
window.generateDynamicBattlecard = generateDynamicBattlecard;
window.exportBattlecardPDF = exportBattlecardPDF;
window.exportBattlecardMarkdown = exportBattlecardMarkdown;
window.loadDimensionComparison = loadDimensionComparison;
window.compareVsCertify = compareVsCertify;
window.loadTalkingPoints = loadTalkingPoints;
window.showAddTalkingPointModal = showAddTalkingPointModal;
window.saveTalkingPoint = saveTalkingPoint;
window.deleteTalkingPoint = deleteTalkingPoint;
window.initBattlecardDimensionWidget = initBattlecardDimensionWidget;
window.loadBattlecardDimensionWidget = loadBattlecardDimensionWidget;
// SM-004: Win Themes Generator
window.generateWinThemes = generateWinThemes;
window.copyWinThemesToClipboard = copyWinThemesToClipboard;
window.exportWinThemesToSlides = exportWinThemesToSlides;
// SM-005: Objection Handler
window.loadObjections = loadObjections;
window.searchObjections = searchObjections;
window.copyObjectionResponse = copyObjectionResponse;
window.getAIEnhancedResponse = getAIEnhancedResponse;
// SM-007: Deal Intelligence Dashboard
window.loadDealIntelligence = loadDealIntelligence;
window.generateQuickBattlecard = generateQuickBattlecard;


// ============== SM-006: Competitive Positioning Matrix ==============

let positioningChart = null;
let positioningData = [];

/**
 * Load and display the competitive positioning matrix.
 * Shows competitors on a scatter plot with configurable X/Y axes.
 */
async function loadPositioningMatrix() {
    const container = document.getElementById('positioningInsights');
    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Loading positioning data...</div>';

    try {
        // Fetch all competitor dimension data
        const response = await fetch(`${API_BASE}/api/sales-marketing/dimensions/all`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            // Fallback: fetch competitors and their dimensions individually
            const competitorsRes = await fetch(`${API_BASE}/api/competitors`, { headers: getAuthHeaders() });
            const competitors = await competitorsRes.json();

            positioningData = [];
            for (const comp of competitors.slice(0, 30)) { // Limit to top 30 for performance
                try {
                    const dimRes = await fetch(`${API_BASE}/api/sales-marketing/competitors/${comp.id}/dimensions`, {
                        headers: getAuthHeaders()
                    });
                    if (dimRes.ok) {
                        const dimData = await dimRes.json();
                        positioningData.push({
                            id: comp.id,
                            name: comp.name,
                            threat_level: comp.threat_level || 'medium',
                            dimensions: dimData.dimensions || {},
                            overall_score: dimData.overall_score || 3
                        });
                    }
                } catch (e) {
                    /* skip competitor for positioning */
                }
            }
        } else {
            positioningData = await response.json();
        }

        updatePositioningMatrix();

    } catch (error) {
        console.error('Failed to load positioning data:', error);
        container.innerHTML = '<p class="error-message">Failed to load positioning data. Please try again.</p>';
    }
}

function updatePositioningMatrix() {
    const xAxis = document.getElementById('positioningXAxis')?.value || 'pricing_flexibility';
    const yAxis = document.getElementById('positioningYAxis')?.value || 'product_packaging';
    const bubbleSize = document.getElementById('positioningBubbleSize')?.value || 'threat';

    const ctx = document.getElementById('positioningMatrixChart')?.getContext('2d');
    if (!ctx) return;

    // Destroy existing chart
    if (positioningChart) {
        positioningChart.destroy();
    }

    // Prepare data points
    const dataPoints = positioningData.map(comp => {
        const xScore = comp.dimensions?.[xAxis]?.score || 3;
        const yScore = comp.dimensions?.[yAxis]?.score || 3;

        let radius = 10;
        if (bubbleSize === 'threat') {
            radius = comp.threat_level === 'high' ? 20 : comp.threat_level === 'medium' ? 14 : 8;
        } else if (bubbleSize === 'overall') {
            radius = (comp.overall_score || 3) * 4;
        }

        let color = '#6c757d';
        if (comp.threat_level === 'high') color = '#dc3545';
        else if (comp.threat_level === 'medium') color = '#fd7e14';
        else if (comp.threat_level === 'low') color = '#28a745';

        return {
            x: xScore,
            y: yScore,
            r: radius,
            label: comp.name,
            backgroundColor: color + '99',
            borderColor: color,
            id: comp.id
        };
    });

    // Add Certify Health marker (position ourselves favorably)
    dataPoints.push({
        x: 4.5,
        y: 4.5,
        r: 15,
        label: 'Certify Health',
        backgroundColor: '#003366',
        borderColor: '#003366',
        isCertify: true
    });

    positioningChart = new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                data: dataPoints,
                backgroundColor: dataPoints.map(d => d.backgroundColor),
                borderColor: dataPoints.map(d => d.borderColor),
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    min: 0,
                    max: 6,
                    title: {
                        display: true,
                        text: getAxisLabel(xAxis),
                        font: { weight: 'bold' }
                    },
                    grid: { color: '#eee' }
                },
                y: {
                    min: 0,
                    max: 6,
                    title: {
                        display: true,
                        text: getAxisLabel(yAxis),
                        font: { weight: 'bold' }
                    },
                    grid: { color: '#eee' }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const point = dataPoints[context.dataIndex];
                            return `${point.label}: ${getAxisLabel(xAxis)}=${point.x}, ${getAxisLabel(yAxis)}=${point.y}`;
                        }
                    }
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const point = dataPoints[elements[0].index];
                    if (point.id) {
                        showCompetitorPositioningDetail(point.id, point.label);
                    }
                }
            }
        }
    });

    // Update insights
    updatePositioningInsights(xAxis, yAxis);
}

function getAxisLabel(dimensionId) {
    const dim = SM_DIMENSIONS.find(d => d.id === dimensionId);
    return dim ? dim.shortName : dimensionId;
}

function updatePositioningInsights(xAxis, yAxis) {
    const container = document.getElementById('positioningInsights');

    // Calculate quadrant distributions
    const highHigh = positioningData.filter(c =>
        (c.dimensions?.[xAxis]?.score || 3) >= 3.5 && (c.dimensions?.[yAxis]?.score || 3) >= 3.5
    );
    const lowLow = positioningData.filter(c =>
        (c.dimensions?.[xAxis]?.score || 3) < 3 && (c.dimensions?.[yAxis]?.score || 3) < 3
    );
    const threats = positioningData.filter(c => c.threat_level === 'high');

    container.innerHTML = `
        <div class="positioning-insights-grid">
            <div class="insight-card">
                <div class="insight-icon">🎯</div>
                <div class="insight-content">
                    <h4>Premium Quadrant</h4>
                    <p>${highHigh.length} competitors with high ${getAxisLabel(xAxis)} and ${getAxisLabel(yAxis)}</p>
                </div>
            </div>
            <div class="insight-card">
                <div class="insight-icon">⚠️</div>
                <div class="insight-content">
                    <h4>High Threats</h4>
                    <p>${threats.length} competitors marked as high threat</p>
                </div>
            </div>
            <div class="insight-card">
                <div class="insight-icon">💡</div>
                <div class="insight-content">
                    <h4>Opportunity Zone</h4>
                    <p>${lowLow.length} competitors weak on both dimensions</p>
                </div>
            </div>
            <div class="insight-card">
                <div class="insight-icon">★</div>
                <div class="insight-content">
                    <h4>Certify Position</h4>
                    <p>Strong positioning in premium quadrant</p>
                </div>
            </div>
        </div>
    `;
}

function showCompetitorPositioningDetail(competitorId, competitorName) {
    showNotification(`Loading details for ${competitorName}...`, 'info');
    // Navigate to Deal Intel tab with this competitor
    document.getElementById('dealIntelCompetitorSelect').value = competitorId;
    showSalesMarketingTab('dealintel');
    loadDealIntelligence();
}

function exportPositioningMatrix() {
    const canvas = document.getElementById('positioningMatrixChart');
    if (canvas) {
        const link = document.createElement('a');
        link.download = 'competitive-positioning-matrix.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
        showNotification('Positioning matrix exported!', 'success');
    }
}


// ============== SM-008: Quick Competitive Lookup ==============

let quickLookupCache = {};

/**
 * Perform a quick AI-powered lookup for a competitor.
 */
async function performQuickLookup() {
    const competitorId = document.getElementById('quickLookupCompetitor')?.value;
    if (!competitorId) {
        showNotification('Please select a competitor', 'warning');
        return;
    }

    const container = document.getElementById('quickLookupResult');
    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Generating AI briefing...</div>';

    try {
        // Fetch all available data for this competitor
        const [competitorRes, dimensionsRes, newsRes] = await Promise.all([
            fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/competitors/${competitorId}/news?limit=5`, { headers: getAuthHeaders() })
        ]);

        const competitor = await competitorRes.json();
        const dimensions = await dimensionsRes.json();
        const news = await newsRes.json();

        // Try to get AI summary if available
        let aiSummary = null;
        try {
            const aiRes = await fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/quick-lookup`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            if (aiRes.ok) {
                aiSummary = await aiRes.json();
            }
        } catch (e) {
            /* AI summary not available, using template */
        }

        renderQuickLookupResult(competitor, dimensions, news, aiSummary);

    } catch (error) {
        console.error('Quick lookup failed:', error);
        container.innerHTML = '<p class="error-message">Failed to perform lookup. Please try again.</p>';
    }
}

function renderQuickLookupResult(competitor, dimensions, news, aiSummary) {
    const container = document.getElementById('quickLookupResult');
    const dimData = dimensions.dimensions || {};

    // Find strengths and weaknesses
    const strengths = [];
    const weaknesses = [];
    SM_DIMENSIONS.forEach(dim => {
        const score = dimData[dim.id]?.score;
        if (score >= 4) strengths.push({ ...dim, score, evidence: dimData[dim.id]?.evidence });
        else if (score && score <= 2) weaknesses.push({ ...dim, score, evidence: dimData[dim.id]?.evidence });
    });

    const summaryText = aiSummary?.summary || generateTemplateSummary(competitor, strengths, weaknesses);

    container.innerHTML = `
        <div class="quick-lookup-card">
            <div class="lookup-header">
                <div class="lookup-company-info">
                    <h2>${competitor.name}</h2>
                    <span class="threat-badge threat-${(competitor.threat_level || 'medium').toLowerCase()}">${competitor.threat_level || 'Medium'} Threat</span>
                </div>
                <div class="lookup-actions">
                    <button class="btn btn-secondary btn-sm" onclick="copyLookupToClipboard()">📋 Copy</button>
                    <button class="btn btn-primary btn-sm" onclick="generatePlaybookForCompetitor('${competitor.id}')">📖 Generate Playbook</button>
                </div>
            </div>

            <div class="lookup-summary">
                <h3>🤖 AI Briefing</h3>
                <p>${summaryText}</p>
            </div>

            <div class="lookup-grid">
                <div class="lookup-section">
                    <h4>⚠️ Watch Out For (Their Strengths)</h4>
                    ${strengths.length > 0 ? `
                        <ul class="lookup-list">
                            ${strengths.map(s => `
                                <li>
                                    <strong>${s.icon} ${s.shortName}</strong> (${s.score}/5)
                                    ${s.evidence ? `<span class="evidence">${s.evidence}</span>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<p class="text-muted">No major strengths identified</p>'}
                </div>

                <div class="lookup-section">
                    <h4>🎯 Attack Here (Their Weaknesses)</h4>
                    ${weaknesses.length > 0 ? `
                        <ul class="lookup-list attack-points">
                            ${weaknesses.map(w => `
                                <li>
                                    <strong>${w.icon} ${w.shortName}</strong> (${w.score}/5)
                                    ${w.evidence ? `<span class="evidence">${w.evidence}</span>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<p class="text-muted">No major weaknesses identified</p>'}
                </div>

                <div class="lookup-section">
                    <h4>📊 Key Metrics</h4>
                    <div class="metrics-grid">
                        <div class="metric"><label>Founded</label><span>${competitor.year_founded || 'N/A'}</span></div>
                        <div class="metric"><label>Employees</label><span>${competitor.employee_count || 'N/A'}</span></div>
                        <div class="metric"><label>Funding</label><span>${competitor.funding_total || 'N/A'}</span></div>
                        <div class="metric"><label>Overall Score</label><span>${dimensions.overall_score?.toFixed(1) || 'N/A'}/5</span></div>
                    </div>
                </div>

                <div class="lookup-section">
                    <h4>📰 Recent News</h4>
                    ${news && news.length > 0 ? `
                        <ul class="news-list compact">
                            ${news.slice(0, 3).map(n => `
                                <li>
                                    <a href="${n.url}" target="_blank">${n.title}</a>
                                    <span class="date">${new Date(n.published_at || n.fetched_at).toLocaleDateString()}</span>
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<p class="text-muted">No recent news</p>'}
                </div>
            </div>
        </div>
    `;
}

function generateTemplateSummary(competitor, strengths, weaknesses) {
    const name = competitor.name;
    const strengthsList = strengths.map(s => s.shortName.toLowerCase()).join(', ');
    const weaknessesList = weaknesses.map(w => w.shortName.toLowerCase()).join(', ');

    let summary = `${name} is a ${competitor.threat_level || 'medium'}-threat competitor in the healthcare technology space.`;

    if (strengths.length > 0) {
        summary += ` They are particularly strong in ${strengthsList}.`;
    }
    if (weaknesses.length > 0) {
        summary += ` Key areas to attack include ${weaknessesList}.`;
    }

    summary += ` When competing against ${name}, focus on demonstrating our superior value proposition in their weak areas while preparing responses for their strengths.`;

    return summary;
}

async function quickLookupCategory(category) {
    const competitorId = document.getElementById('quickLookupCompetitor')?.value;
    if (!competitorId) {
        showNotification('Please select a competitor first', 'warning');
        return;
    }

    const container = document.getElementById('quickLookupResult');
    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Loading...</div>';

    try {
        let content = '';
        const competitor = await fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() }).then(r => r.json());

        if (category === 'strengths' || category === 'weaknesses') {
            const dimensions = await fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions`, { headers: getAuthHeaders() }).then(r => r.json());
            const dimData = dimensions.dimensions || {};
            const items = [];

            SM_DIMENSIONS.forEach(dim => {
                const score = dimData[dim.id]?.score;
                if (category === 'strengths' && score >= 4) {
                    items.push({ ...dim, score, evidence: dimData[dim.id]?.evidence });
                } else if (category === 'weaknesses' && score && score <= 2) {
                    items.push({ ...dim, score, evidence: dimData[dim.id]?.evidence });
                }
            });

            const title = category === 'strengths' ? '⚠️ Their Strengths (Watch Out)' : '🎯 Their Weaknesses (Attack Here)';
            content = `
                <div class="category-result">
                    <h3>${title} - ${competitor.name}</h3>
                    ${items.length > 0 ? `
                        <ul class="lookup-list ${category === 'weaknesses' ? 'attack-points' : ''}">
                            ${items.map(i => `
                                <li>
                                    <strong>${i.icon} ${i.shortName}</strong> (Score: ${i.score}/5)
                                    ${i.evidence ? `<p class="evidence">${i.evidence}</p>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    ` : `<p class="text-muted">No major ${category} identified</p>`}
                </div>
            `;
        } else if (category === 'news') {
            const news = await fetch(`${API_BASE}/api/competitors/${competitorId}/news?limit=10`, { headers: getAuthHeaders() }).then(r => r.json());
            content = `
                <div class="category-result">
                    <h3>📰 Recent News - ${competitor.name}</h3>
                    ${news && news.length > 0 ? `
                        <ul class="news-list">
                            ${news.map(n => `
                                <li>
                                    <a href="${n.url}" target="_blank">${n.title}</a>
                                    <span class="date">${new Date(n.published_at || n.fetched_at).toLocaleDateString()}</span>
                                    ${n.sentiment ? `<span class="sentiment ${n.sentiment}">${n.sentiment}</span>` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<p class="text-muted">No recent news available</p>'}
                </div>
            `;
        } else if (category === 'pricing') {
            content = `
                <div class="category-result">
                    <h3>💰 Pricing Intel - ${competitor.name}</h3>
                    <div class="pricing-intel-grid">
                        <div class="intel-item"><label>Pricing Model</label><span>${competitor.pricing_model || 'Unknown'}</span></div>
                        <div class="intel-item"><label>Price Range</label><span>${competitor.price_range || 'Unknown'}</span></div>
                        <div class="intel-item"><label>Has Free Tier</label><span>${competitor.has_free_tier ? 'Yes' : 'No'}</span></div>
                        <div class="intel-item"><label>Typical Discount</label><span>15-25% (estimated)</span></div>
                    </div>
                    <div class="pricing-notes">
                        <h4>Competitive Pricing Notes</h4>
                        <ul>
                            <li>They typically compete on price in enterprise deals</li>
                            <li>Watch for aggressive multi-year discounting</li>
                            <li>Implementation costs often hidden in initial quotes</li>
                        </ul>
                    </div>
                </div>
            `;
        } else if (category === 'objections') {
            content = `
                <div class="category-result">
                    <h3>💬 Common Objections - ${competitor.name}</h3>
                    <div class="objection-quick-list">
                        <div class="objection-item">
                            <strong>"${competitor.name} has been in the market longer"</strong>
                            <p class="response">Modern platform built on latest technology. Faster innovation cycles. Customer success metrics often exceed established players.</p>
                        </div>
                        <div class="objection-item">
                            <strong>"${competitor.name} is cheaper"</strong>
                            <p class="response">Focus on TCO over 3 years. Our implementation is faster, support is included, and no hidden fees.</p>
                        </div>
                        <div class="objection-item">
                            <strong>"We already use ${competitor.name}"</strong>
                            <p class="response">Understand pain points with current solution. Offer seamless migration path and ROI analysis.</p>
                        </div>
                    </div>
                    <button class="btn btn-secondary" onclick="showSalesMarketingTab('objections'); document.getElementById('objectionCompetitorSelect').value='${competitorId}'; loadObjections();">
                        View All Objections →
                    </button>
                </div>
            `;
        }

        container.innerHTML = content;
    } catch (error) {
        console.error('Category lookup failed:', error);
        container.innerHTML = '<p class="error-message">Failed to load category data.</p>';
    }
}

function copyLookupToClipboard() {
    const container = document.getElementById('quickLookupResult');
    const text = container?.innerText || '';
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Briefing copied to clipboard!', 'success');
    });
}


// ============== SM-009: Pricing Comparison Calculator ==============

let pricingIntelData = {};

/**
 * Calculate and display pricing comparison.
 */
async function calculatePricing() {
    const users = parseInt(document.getElementById('pricingUsers')?.value) || 100;
    const contractLength = parseInt(document.getElementById('pricingContractLength')?.value) || 3;
    const implementation = document.getElementById('pricingImplementation')?.value || 'standard';
    const support = document.getElementById('pricingSupport')?.value || 'premium';

    const competitor1Id = document.getElementById('pricingCompetitor1')?.value;
    const competitor2Id = document.getElementById('pricingCompetitor2')?.value;
    const competitor3Id = document.getElementById('pricingCompetitor3')?.value;

    const container = document.getElementById('pricingComparisonResult');

    if (!competitor1Id) {
        container.innerHTML = '<p class="sm-placeholder">Select at least one competitor to compare pricing.</p>';
        return;
    }

    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Calculating pricing...</div>';

    try {
        // Fetch competitor data
        const competitors = [];
        for (const id of [competitor1Id, competitor2Id, competitor3Id].filter(Boolean)) {
            const res = await fetch(`${API_BASE}/api/competitors/${id}`, { headers: getAuthHeaders() });
            if (res.ok) {
                competitors.push(await res.json());
            }
        }

        // Calculate pricing for each (using estimates based on available data)
        const pricingComparisons = competitors.map(comp => calculateCompetitorPricing(comp, users, contractLength, implementation, support));

        // Add Certify Health pricing
        const certifyPricing = calculateCertifyPricing(users, contractLength, implementation, support);

        renderPricingComparison(certifyPricing, pricingComparisons, users, contractLength);

    } catch (error) {
        console.error('Pricing calculation failed:', error);
        container.innerHTML = '<p class="error-message">Failed to calculate pricing. Please try again.</p>';
    }
}

function calculateCompetitorPricing(competitor, users, years, implementation, support) {
    // Base pricing estimates based on typical SaaS healthcare pricing
    const basePPU = getBasePricePerUser(competitor);
    const implMultiplier = { basic: 0.5, standard: 1.0, enterprise: 2.0 }[implementation] || 1.0;
    const supportMultiplier = { standard: 1.0, premium: 1.2, dedicated: 1.5 }[support] || 1.0;

    const annualLicense = users * basePPU * 12 * supportMultiplier;
    const implementationCost = annualLicense * 0.3 * implMultiplier;
    const annualSupport = annualLicense * 0.15;
    const hiddenCosts = annualLicense * 0.1; // Training, integrations, etc.

    const totalTCO = (annualLicense * years) + implementationCost + (annualSupport * years) + (hiddenCosts * years);
    const annualTCO = totalTCO / years;

    return {
        name: competitor.name,
        id: competitor.id,
        annualLicense: Math.round(annualLicense),
        implementationCost: Math.round(implementationCost),
        annualSupport: Math.round(annualSupport),
        hiddenCosts: Math.round(hiddenCosts),
        totalTCO: Math.round(totalTCO),
        annualTCO: Math.round(annualTCO),
        pricePerUser: Math.round(annualTCO / users / 12)
    };
}

function getBasePricePerUser(competitor) {
    // Estimate base price based on competitor profile
    const name = competitor.name.toLowerCase();

    // Premium tier competitors
    if (name.includes('epic') || name.includes('cerner') || name.includes('oracle')) {
        return 150;
    }
    // Mid-tier competitors
    if (name.includes('athena') || name.includes('allscripts') || name.includes('nextgen')) {
        return 100;
    }
    // Value tier competitors
    if (name.includes('practice') || name.includes('kareo') || name.includes('drchrono')) {
        return 50;
    }
    // Default mid-tier
    return 75;
}

function calculateCertifyPricing(users, years, implementation, support) {
    const basePPU = 65; // Competitive pricing
    const implMultiplier = { basic: 0.3, standard: 0.6, enterprise: 1.2 }[implementation] || 0.6;
    const supportMultiplier = { standard: 1.0, premium: 1.1, dedicated: 1.3 }[support] || 1.1;

    const annualLicense = users * basePPU * 12 * supportMultiplier;
    const implementationCost = annualLicense * 0.2 * implMultiplier; // Lower implementation
    const annualSupport = 0; // Included in license
    const hiddenCosts = 0; // Transparent pricing

    const totalTCO = (annualLicense * years) + implementationCost;
    const annualTCO = totalTCO / years;

    return {
        name: 'Certify Health',
        isCertify: true,
        annualLicense: Math.round(annualLicense),
        implementationCost: Math.round(implementationCost),
        annualSupport: 0,
        hiddenCosts: 0,
        totalTCO: Math.round(totalTCO),
        annualTCO: Math.round(annualTCO),
        pricePerUser: Math.round(annualTCO / users / 12)
    };
}

function renderPricingComparison(certifyPricing, competitorPricing, users, years) {
    const container = document.getElementById('pricingComparisonResult');
    const allPricing = [certifyPricing, ...competitorPricing];
    const lowestTCO = Math.min(...allPricing.map(p => p.totalTCO));

    let html = `
        <div class="pricing-comparison-grid">
            <div class="pricing-summary">
                <h3>💰 ${years}-Year TCO Comparison (${users} users)</h3>
            </div>
            <div class="pricing-cards">
    `;

    allPricing.forEach(pricing => {
        const isLowest = pricing.totalTCO === lowestTCO;
        const savings = certifyPricing.totalTCO < pricing.totalTCO ?
            pricing.totalTCO - certifyPricing.totalTCO : 0;

        html += `
            <div class="pricing-card ${pricing.isCertify ? 'certify-card' : ''} ${isLowest ? 'lowest-price' : ''}">
                <div class="pricing-card-header">
                    <h4>${pricing.name}</h4>
                    ${isLowest ? '<span class="badge-lowest">Lowest TCO</span>' : ''}
                </div>
                <div class="pricing-total">
                    <span class="currency">$</span>
                    <span class="amount">${formatCurrency(pricing.totalTCO)}</span>
                    <span class="period">${years}-year TCO</span>
                </div>
                <div class="pricing-breakdown">
                    <div class="breakdown-item">
                        <span>Annual License</span>
                        <span>$${formatCurrency(pricing.annualLicense)}/yr</span>
                    </div>
                    <div class="breakdown-item">
                        <span>Implementation</span>
                        <span>$${formatCurrency(pricing.implementationCost)}</span>
                    </div>
                    <div class="breakdown-item">
                        <span>Annual Support</span>
                        <span>${pricing.annualSupport > 0 ? '$' + formatCurrency(pricing.annualSupport) + '/yr' : 'Included'}</span>
                    </div>
                    <div class="breakdown-item">
                        <span>Hidden Costs</span>
                        <span>${pricing.hiddenCosts > 0 ? '$' + formatCurrency(pricing.hiddenCosts) + '/yr' : 'None'}</span>
                    </div>
                </div>
                <div class="pricing-per-user">
                    <strong>$${pricing.pricePerUser}</strong> per user/month
                </div>
                ${!pricing.isCertify && savings > 0 ? `
                    <div class="savings-callout">
                        Save <strong>$${formatCurrency(savings)}</strong> with Certify Health
                    </div>
                ` : ''}
            </div>
        `;
    });

    html += `
            </div>
        </div>
        <div class="pricing-actions">
            <button class="btn btn-secondary" onclick="exportPricingComparison()">📊 Export Comparison</button>
            <button class="btn btn-primary" onclick="generatePricingProposal()">📝 Generate Proposal</button>
        </div>
    `;

    container.innerHTML = html;
}

function formatCurrency(num) {
    return num.toLocaleString('en-US');
}

function exportPricingComparison() {
    showNotification('Exporting pricing comparison...', 'info');
    // Would export to Excel/PDF
    setTimeout(() => showNotification('Export feature coming soon!', 'info'), 1000);
}

function generatePricingProposal() {
    showNotification('Generating pricing proposal...', 'info');
    setTimeout(() => showNotification('Proposal generator coming soon!', 'info'), 1000);
}


// ============== SM-010: Sales Playbook Generator ==============

let playbookContext = null;

/**
 * Update the playbook context summary when competitor is selected.
 */
async function updatePlaybookContext() {
    const competitorId = document.getElementById('playbookCompetitor')?.value;
    const container = document.getElementById('playbookContextSummary');

    if (!competitorId) {
        container.innerHTML = '<p class="sm-placeholder">Select a competitor to see context summary.</p>';
        return;
    }

    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Loading context...</div>';

    try {
        const [competitorRes, dimensionsRes] = await Promise.all([
            fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions`, { headers: getAuthHeaders() })
        ]);

        const competitor = await competitorRes.json();
        const dimensions = await dimensionsRes.json();

        playbookContext = { competitor, dimensions };

        const dimData = dimensions.dimensions || {};
        const strengths = SM_DIMENSIONS.filter(d => (dimData[d.id]?.score || 0) >= 4);
        const weaknesses = SM_DIMENSIONS.filter(d => {
            const score = dimData[d.id]?.score;
            return score && score <= 2;
        });

        container.innerHTML = `
            <div class="context-summary">
                <div class="context-item">
                    <span class="label">Competitor:</span>
                    <strong>${competitor.name}</strong>
                    <span class="threat-badge threat-${(competitor.threat_level || 'medium').toLowerCase()}">${competitor.threat_level || 'Medium'}</span>
                </div>
                <div class="context-item">
                    <span class="label">Their Strengths:</span>
                    <span>${strengths.length > 0 ? strengths.map(s => s.icon + ' ' + s.shortName).join(', ') : 'None identified'}</span>
                </div>
                <div class="context-item">
                    <span class="label">Their Weaknesses:</span>
                    <span>${weaknesses.length > 0 ? weaknesses.map(w => w.icon + ' ' + w.shortName).join(', ') : 'None identified'}</span>
                </div>
                <div class="context-item">
                    <span class="label">Overall Score:</span>
                    <strong>${dimensions.overall_score?.toFixed(1) || 'N/A'}/5</strong>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load context:', error);
        container.innerHTML = '<p class="error-message">Failed to load competitor context.</p>';
    }
}

/**
 * Generate the sales playbook content.
 */
async function generatePlaybook() {
    const competitorId = document.getElementById('playbookCompetitor')?.value;
    const scenario = document.getElementById('playbookScenario')?.value;
    const contentType = document.getElementById('playbookType')?.value;
    const dealContext = document.getElementById('playbookDealContext')?.value?.trim() || '';

    if (!competitorId) {
        showNotification('Please select a competitor', 'warning');
        return;
    }

    const container = document.getElementById('playbookResult');
    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Generating playbook content...</div>';

    try {
        // Try AI endpoint first
        let content = null;
        try {
            const body = {
                competitor_id: competitorId,
                scenario: scenario,
                content_type: contentType
            };
            if (dealContext) body.deal_context = dealContext;

            const aiRes = await fetch(`${API_BASE}/api/sales-marketing/playbook/generate`, {
                method: 'POST',
                headers: {
                    ...getAuthHeaders(),
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            });

            if (aiRes.ok) {
                content = await aiRes.json();
            }
        } catch (e) {
            /* AI playbook not available, using template */
        }

        // Fall back to template-based generation
        if (!content) {
            content = generatePlaybookTemplate(playbookContext, scenario, contentType);
        }

        renderPlaybookResult(content, contentType);

    } catch (error) {
        console.error('Playbook generation failed:', error);
        container.innerHTML = '<p class="error-message">Failed to generate playbook. Please try again.</p>';
    }
}

function generatePlaybookTemplate(context, scenario, contentType) {
    if (!context) return { content: 'Please select a competitor first.' };

    const competitor = context.competitor;
    const dimData = context.dimensions?.dimensions || {};

    const strengths = SM_DIMENSIONS.filter(d => (dimData[d.id]?.score || 0) >= 4).map(d => d.shortName);
    const weaknesses = SM_DIMENSIONS.filter(d => {
        const score = dimData[d.id]?.score;
        return score && score <= 2;
    }).map(d => d.shortName);

    const templates = {
        call_script: {
            title: `Discovery Call Script - vs ${competitor.name}`,
            content: `
## Discovery Call Script
**Competitor:** ${competitor.name} | **Scenario:** ${getScenarioLabel(scenario)}

### Opening (2 minutes)
"Thanks for taking the time today. I understand you're currently [evaluating options/using ${competitor.name}].
I'd love to learn more about your challenges and see if there's a fit."

### Discovery Questions (10 minutes)
1. "What's driving your evaluation of solutions right now?"
2. "What's working well with your current approach?"
3. "What would you change if you could?"
${weaknesses.length > 0 ? `4. "How important is ${weaknesses[0]} to your team?" (Their weakness)` : ''}
${strengths.length > 0 ? `5. "Tell me about your experience with ${strengths[0]}." (Their strength - gather intel)` : ''}

### Pain Point Exploration
${weaknesses.map(w => `- Probe on **${w}**: "${competitor.name} is known to struggle here. How has that impacted you?"`).join('\n')}

### Value Proposition Bridge
"Based on what you've shared, here's where we typically differentiate..."
${weaknesses.map(w => `- **${w}**: "We've invested heavily in this area because..."
`).join('')}

### Competitive Positioning
${strengths.length > 0 ? `
**When they mention ${competitor.name}'s ${strengths[0]}:**
"That's a fair point. However, consider..."
` : ''}

### Next Steps (3 minutes)
"I'd recommend a focused demo on [specific area]. Who else should be involved?"
            `
        },
        email_initial: {
            title: `Initial Outreach Email - vs ${competitor.name}`,
            content: `
## Initial Outreach Email
**Subject:** Quick question about your ${competitor.name} experience

---

Hi [Name],

I noticed you're currently using ${competitor.name} for [use case]. I've been speaking with several [industry] leaders who've made the switch to Certify Health, and they've shared some interesting insights.

${weaknesses.length > 0 ? `Many mentioned challenges with ${weaknesses.join(' and ')}, which seem to be common pain points. ` : ''}

Would you be open to a 15-minute call to share what we're seeing in the market? I promise it'll be worth your time - even if we're not a fit, I can share some valuable competitive intel.

Best,
[Your name]

P.S. - I can also share our ${competitor.name} comparison guide that several of your peers have found helpful.

---

**Follow-up if no response (3 days):**

Subject: Re: Quick question about your ${competitor.name} experience

[Name],

Wanted to quickly follow up on my previous note. I understand ${competitor.name} can be sticky, but many of our customers found the transition smoother than expected.

If timing isn't right now, no worries - I'm happy to stay in touch.

Best,
[Your name]
            `
        },
        email_followup: {
            title: `Post-Demo Follow-up - vs ${competitor.name}`,
            content: `
## Post-Demo Follow-up Email
**Subject:** Following up - Certify Health vs ${competitor.name} comparison

---

Hi [Name],

Thank you for the great conversation yesterday! I enjoyed learning about [specific pain point discussed].

As promised, here's a summary of what we discussed:

**Key Differentiators:**
${weaknesses.map((w, i) => `${i + 1}. **${w}**: [Specific point from demo]`).join('\n')}

**Your Priorities:**
- [Priority 1 from call]
- [Priority 2 from call]

**Next Steps:**
- [ ] Schedule technical deep-dive with your team
- [ ] Provide references from similar organizations
- [ ] Share pricing proposal

Let me know what questions came up after you had time to reflect. Happy to schedule a follow-up call with your broader team.

Best,
[Your name]
            `
        },
        objection_response: {
            title: `Objection Responses - ${competitor.name}`,
            content: `
## Objection Response Guide
**Competitor:** ${competitor.name}

---

### "We're already using ${competitor.name}"
**Response:** "That's exactly why I called. Many of our best customers came from ${competitor.name}. The switching cost is lower than you might think, and the ROI is typically visible within [timeframe]. What's your contract renewal date?"

### "${competitor.name} is cheaper"
**Response:** "Let's look at total cost of ownership. ${competitor.name}'s base price often doesn't include [hidden costs]. When you factor in implementation, training, and ongoing support, our customers typically see 15-20% lower TCO over 3 years."

${strengths.length > 0 ? `
### "${competitor.name} has better ${strengths[0]}"
**Response:** "That's a common perception. However, [counter-argument with specific evidence]. Would you like to see a side-by-side comparison from one of our customers who evaluated both?"
` : ''}

${weaknesses.map(w => `
### If they're frustrated with ${w}
**Response:** "That's something we hear often from ${competitor.name} users. Our approach to ${w} is fundamentally different because [explanation]. This has resulted in [metric/benefit] for customers like [reference]."
`).join('')}

### "We need to think about it"
**Response:** "Absolutely, this is an important decision. What specific areas would you like more information on? I can also connect you with [reference customer] who went through a similar evaluation."
            `
        },
        value_prop: {
            title: `Value Proposition - vs ${competitor.name}`,
            content: `
## Value Proposition Summary
**When Competing Against:** ${competitor.name}

---

### Our Core Differentiators
${weaknesses.map((w, i) => `
**${i + 1}. ${w}**
- Their limitation: [specific limitation]
- Our advantage: [specific capability]
- Customer proof point: [quote or metric]
`).join('')}

### Messaging Framework

**For Technical Buyers:**
"Unlike ${competitor.name}, our platform [technical differentiator]. This means [technical benefit]."

**For Business Buyers:**
"While ${competitor.name} focuses on [their focus], we prioritize [our focus]. This translates to [business benefit]."

**For Executive Sponsors:**
"Organizations choosing Certify Health over ${competitor.name} typically see [ROI metric] within [timeframe]. Here's why..."

### Win Story Template
"[Customer name] was evaluating ${competitor.name} when they discovered our [key differentiator]. After a [timeframe] evaluation, they chose Certify Health because [reasons]. Today, they've achieved [results]."
            `
        },
        executive_summary: {
            title: `Executive Summary - ${competitor.name} Competitive Analysis`,
            content: `
## Executive Summary
**${competitor.name} Competitive Analysis**

---

### Company Overview
- **Name:** ${competitor.name}
- **Threat Level:** ${competitor.threat_level || 'Medium'}
- **Founded:** ${competitor.year_founded || 'Unknown'}
- **Employees:** ${competitor.employee_count || 'Unknown'}

### Competitive Position
- **Overall Score:** ${context.dimensions?.overall_score?.toFixed(1) || 'N/A'}/5
- **Key Strengths:** ${strengths.join(', ') || 'None identified'}
- **Key Weaknesses:** ${weaknesses.join(', ') || 'None identified'}

### How to Win
${weaknesses.length > 0 ? weaknesses.map(w => `1. Attack on **${w}** - they consistently underperform here`).join('\n') : '- Focus on overall value proposition'}

### How to Defend
${strengths.length > 0 ? strengths.map(s => `1. Be prepared for **${s}** comparisons - have proof points ready`).join('\n') : '- Standard competitive positioning applies'}

### Recommended Resources
- Battlecard: [Link to battlecard]
- Customer References: [List 2-3 relevant references]
- Case Studies: [List relevant case studies]
            `
        }
    };

    return templates[contentType] || { title: 'Playbook Content', content: 'Content type not supported.' };
}

function getScenarioLabel(scenario) {
    const labels = {
        displacement: 'Competitive Displacement',
        headtohead: 'Head-to-Head Evaluation',
        incumbent: 'Defending as Incumbent',
        followup: 'Post-Demo Follow-up',
        objection: 'Handling Objection'
    };
    return labels[scenario] || scenario;
}

function renderPlaybookResult(content, contentType) {
    const container = document.getElementById('playbookResult');
    const escHtml = typeof escapeHtml === 'function' ? escapeHtml : (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

    // Safe markdown-to-HTML conversion for AI-generated content
    let formattedContent = escHtml(content.content || '');
    formattedContent = formattedContent
        .replace(/^### (.*$)/gim, '<h4 class="playbook-section-heading">$1</h4>')
        .replace(/^## (.*$)/gim, '<h3 class="playbook-section-heading">$1</h3>')
        .replace(/^# (.*$)/gim, '<h3 class="playbook-section-heading">$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^\s*[-*]\s(.*?)$/gm, '<li>$1</li>')
        .replace(/^\s*\d+\.\s(.*?)$/gm, '<li>$1</li>');
    if (formattedContent.includes('<li>')) {
        formattedContent = formattedContent.replace(/((<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
    }
    formattedContent = formattedContent.replace(/\n\n/g, '<br>');

    container.innerHTML = `
        <div class="playbook-output">
            <div class="playbook-output-header">
                <h3>${escHtml(content.title || 'Sales Playbook')}</h3>
                <div class="playbook-output-actions">
                    <button class="btn btn-secondary btn-sm" onclick="copyPlaybookToClipboard()">📋 Copy</button>
                    <button class="btn btn-secondary btn-sm" onclick="downloadPlaybook()">📥 Download</button>
                    <button class="btn btn-secondary btn-sm" onclick="printPlaybook()">🖨️ Print</button>
                    <button class="btn btn-primary btn-sm" onclick="regeneratePlaybook()">🔄 Regenerate</button>
                </div>
            </div>
            <div class="playbook-content markdown-body" id="playbookContentBody">
                ${formattedContent}
            </div>
        </div>
    `;
}

function copyPlaybookToClipboard() {
    const container = document.querySelector('.playbook-content');
    const text = container?.innerText || '';
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Playbook copied to clipboard!', 'success');
    });
}

function downloadPlaybook() {
    const container = document.querySelector('.playbook-content');
    const text = container?.innerText || '';
    const blob = new Blob([text], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sales-playbook.md';
    a.click();
    URL.revokeObjectURL(url);
    showNotification('Playbook downloaded!', 'success');
}

function printPlaybook() {
    const content = document.getElementById('playbookContentBody');
    if (!content) return;
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
        <!DOCTYPE html><html><head><title>Sales Playbook</title>
        <style>body{font-family:system-ui,sans-serif;padding:40px;max-width:800px;margin:0 auto;color:#1e293b;}
        h3,h4{color:#1e293b;margin-top:24px;}ul{margin:8px 0;}li{margin:4px 0;}
        .playbook-section-heading{border-bottom:2px solid #e2e8f0;padding-bottom:6px;margin-top:28px;}</style>
        </head><body>${content.innerHTML}</body></html>
    `);
    printWindow.document.close();
    printWindow.print();
}

function regeneratePlaybook() {
    generatePlaybook();
}

function generatePlaybookForCompetitor(competitorId) {
    document.getElementById('playbookCompetitor').value = competitorId;
    showSalesMarketingTab('playbook');
    updatePlaybookContext();
}


// ============== Tab Navigation Update ==============

// Update showSalesMarketingTab to handle new tabs
const originalShowSalesMarketingTab = showSalesMarketingTab;
window.showSalesMarketingTab = function(tabName) {
    // Hide all tabs
    document.querySelectorAll('.sm-tab-content').forEach(tab => {
        tab.style.display = 'none';
        tab.classList.remove('active');
    });
    document.querySelectorAll('.sm-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const tab = document.getElementById('sm-' + tabName + 'Tab');
    if (tab) {
        tab.style.display = 'block';
        tab.classList.add('active');
    }

    // Update button highlighting
    const tabButtonMap = {
        'dimensions': 0,
        'dealintel': 1,
        'winthemes': 2,
        'objections': 3,
        'battlecards': 4,
        'comparison': 5,
        'talkingpoints': 6,
        'positioning': 7,
        'quicklookup': 8,
        'pricing': 9,
        'playbook': 10
    };
    const buttons = document.querySelectorAll('.sm-tab-btn');
    const buttonIndex = tabButtonMap[tabName];
    if (buttonIndex !== undefined && buttons[buttonIndex]) {
        buttons[buttonIndex].classList.add('active');
    }

    // Load data for specific tabs
    if (tabName === 'positioning') {
        loadPositioningMatrix();
    } else if (tabName === 'quicklookup') {
        initQuickLookupDropdown();
    } else if (tabName === 'pricing') {
        initPricingDropdowns();
    } else if (tabName === 'playbook') {
        initPlaybookDropdown();
    } else if (tabName === 'dimensions') {
        // Dimensions tab - data loaded on competitor select
    } else if (tabName === 'comparison') {
        // Initialize comparison - nothing to preload
    } else if (tabName === 'talkingpoints') {
        loadTalkingPointsDimensions();
    } else if (tabName === 'dealintel' || tabName === 'winthemes' || tabName === 'objections') {
        initNewTabDropdowns(tabName);
    }
};

function initQuickLookupDropdown() {
    const select = document.getElementById('quickLookupCompetitor');
    if (!select || select.options.length > 1) return;

    const competitorOptions = (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('');
    select.innerHTML = '<option value="">-- Select Competitor --</option>' + competitorOptions;
}

function initPricingDropdowns() {
    const selects = ['pricingCompetitor1', 'pricingCompetitor2', 'pricingCompetitor3'];
    const competitorOptions = (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('');

    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select && select.options.length <= 1) {
            select.innerHTML = '<option value="">-- Select Competitor --</option>' + competitorOptions;
        }
    });
}

function initPlaybookDropdown() {
    const select = document.getElementById('playbookCompetitor');
    if (!select || select.options.length > 1) return;

    const competitorOptions = (window.competitors || [])
        .filter(c => !c.is_deleted)
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('');
    select.innerHTML = '<option value="">-- Select Competitor --</option>' + competitorOptions;
}


// ============== P2 Exports ==============

// SM-006: Competitive Positioning Matrix
window.loadPositioningMatrix = loadPositioningMatrix;
window.updatePositioningMatrix = updatePositioningMatrix;
window.exportPositioningMatrix = exportPositioningMatrix;
window.showCompetitorPositioningDetail = showCompetitorPositioningDetail;

// SM-008: Quick Competitive Lookup
window.performQuickLookup = performQuickLookup;
window.quickLookupCategory = quickLookupCategory;
window.copyLookupToClipboard = copyLookupToClipboard;

// SM-009: Pricing Comparison Calculator
window.calculatePricing = calculatePricing;
window.exportPricingComparison = exportPricingComparison;
window.generatePricingProposal = generatePricingProposal;

// SM-010: Sales Playbook Generator
window.updatePlaybookContext = updatePlaybookContext;
window.generatePlaybook = generatePlaybook;
window.copyPlaybookToClipboard = copyPlaybookToClipboard;
window.downloadPlaybook = downloadPlaybook;
window.regeneratePlaybook = regeneratePlaybook;
window.generatePlaybookForCompetitor = generatePlaybookForCompetitor;

// Dropdown initializers
window.initQuickLookupDropdown = initQuickLookupDropdown;
window.initPricingDropdowns = initPricingDropdowns;
window.initPlaybookDropdown = initPlaybookDropdown;


// ============== BC-004, BC-006, BC-007: Deal Room Enhancements ==============

let dealRoomCurrentTab = 'overview';
let dealRoomData = null;

/**
 * Show a specific Deal Room sub-tab.
 */
function showDealRoomTab(tabName) {
    dealRoomCurrentTab = tabName;

    // Hide all deal room content
    document.querySelectorAll('.deal-room-content').forEach(content => {
        content.style.display = 'none';
        content.classList.remove('active');
    });

    // Remove active from all buttons
    document.querySelectorAll('.deal-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab content
    const tabContent = document.getElementById(`dealRoom-${tabName}Tab`);
    if (tabContent) {
        tabContent.style.display = 'block';
        tabContent.classList.add('active');
    }

    // Highlight active button
    const buttonIndex = { 'overview': 0, 'news': 1, 'pricing': 2, 'export': 3 }[tabName];
    const buttons = document.querySelectorAll('.deal-tab-btn');
    if (buttonIndex !== undefined && buttons[buttonIndex]) {
        buttons[buttonIndex].classList.add('active');
    }

    // Load tab-specific data
    const competitorId = document.getElementById('dealIntelCompetitorSelect')?.value;
    if (competitorId) {
        if (tabName === 'news') {
            loadDealRoomNews(competitorId);
        } else if (tabName === 'pricing') {
            loadDealRoomPricing(competitorId);
        } else if (tabName === 'export') {
            loadDealRoomExport(competitorId);
        }
    }
}

/**
 * BC-004: Load News & Updates for Deal Room.
 */
async function loadDealRoomNews(competitorId) {
    const container = document.getElementById('dealRoomNewsContent');
    if (!container) return;

    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Loading news and updates...</div>';

    try {
        const [newsRes, competitorRes] = await Promise.all([
            fetch(`${API_BASE}/api/competitors/${competitorId}/news?limit=20`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() })
        ]);

        const news = await newsRes.json();
        const competitor = await competitorRes.json();

        renderDealRoomNews(news, competitor);

    } catch (error) {
        console.error('Failed to load deal room news:', error);
        container.innerHTML = '<p class="error-message">Failed to load news. Please try again.</p>';
    }
}

function renderDealRoomNews(news, competitor) {
    const container = document.getElementById('dealRoomNewsContent');
    if (!container) return;

    // Group news by category/sentiment
    const positiveNews = (news || []).filter(n => n.sentiment === 'positive');
    const negativeNews = (news || []).filter(n => n.sentiment === 'negative');
    const neutralNews = (news || []).filter(n => !n.sentiment || n.sentiment === 'neutral');

    let html = `
        <div class="deal-room-news">
            <div class="news-header">
                <h3>📰 News & Updates for ${competitor.name}</h3>
                <p class="news-summary">${news?.length || 0} articles in the last 30 days</p>
            </div>

            <div class="news-filters">
                <button class="news-filter-btn active" onclick="filterDealRoomNews('all')">All (${news?.length || 0})</button>
                <button class="news-filter-btn" onclick="filterDealRoomNews('positive')">Positive (${positiveNews.length})</button>
                <button class="news-filter-btn" onclick="filterDealRoomNews('negative')">Negative (${negativeNews.length})</button>
                <button class="news-filter-btn" onclick="filterDealRoomNews('neutral')">Neutral (${neutralNews.length})</button>
            </div>

            <div class="news-timeline" id="dealRoomNewsTimeline">
    `;

    if (news && news.length > 0) {
        news.forEach(article => {
            const sentimentClass = article.sentiment || 'neutral';
            const sentimentIcon = article.sentiment === 'positive' ? '📈' :
                                   article.sentiment === 'negative' ? '📉' : '➖';
            const date = new Date(article.published_at || article.fetched_at);

            html += `
                <div class="news-timeline-item" data-sentiment="${sentimentClass}">
                    <div class="timeline-date">
                        <span class="day">${date.getDate()}</span>
                        <span class="month">${date.toLocaleString('default', { month: 'short' })}</span>
                    </div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <span class="sentiment-badge ${sentimentClass}">${sentimentIcon} ${sentimentClass}</span>
                            <span class="source">${article.source || 'News'}</span>
                        </div>
                        <h4><a href="${article.url}" target="_blank">${article.title}</a></h4>
                        ${article.summary ? `<p class="summary">${article.summary}</p>` : ''}
                    </div>
                </div>
            `;
        });
    } else {
        html += '<p class="sm-placeholder">No recent news articles found for this competitor.</p>';
    }

    html += `
            </div>

            <div class="news-actions">
                <button class="btn btn-secondary" onclick="refreshCompetitorNews('${competitor.id}')">
                    🔄 Refresh News
                </button>
                <button class="btn btn-secondary" onclick="exportNewsToEmail()">
                    📧 Email Summary
                </button>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function filterDealRoomNews(filter) {
    const items = document.querySelectorAll('.news-timeline-item');
    items.forEach(item => {
        if (filter === 'all' || item.dataset.sentiment === filter) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });

    // Update active button
    document.querySelectorAll('.news-filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
}

async function refreshCompetitorNews(competitorId) {
    showNotification('Refreshing news...', 'info');
    await loadDealRoomNews(competitorId);
    showNotification('News refreshed!', 'success');
}

function exportNewsToEmail() {
    showNotification('Email export coming soon!', 'info');
}

/**
 * BC-006: Load Pricing Intelligence for Deal Room.
 */
async function loadDealRoomPricing(competitorId) {
    const container = document.getElementById('dealRoomPricingContent');
    if (!container) return;

    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Loading pricing intelligence...</div>';

    try {
        const competitorRes = await fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() });
        const competitor = await competitorRes.json();

        renderDealRoomPricing(competitor);

    } catch (error) {
        console.error('Failed to load pricing intel:', error);
        container.innerHTML = '<p class="error-message">Failed to load pricing. Please try again.</p>';
    }
}

function renderDealRoomPricing(competitor) {
    const container = document.getElementById('dealRoomPricingContent');
    if (!container) return;

    // Estimate pricing based on competitor profile
    const basePPU = getBasePricePerUser(competitor);
    const pricingModel = competitor.pricing_model || 'Subscription';
    const priceRange = competitor.price_range || '$50-150 per user/month (estimated)';

    html = `
        <div class="deal-room-pricing">
            <div class="pricing-header">
                <h3>💰 Pricing Intelligence for ${competitor.name}</h3>
            </div>

            <div class="pricing-intel-sections">
                <div class="pricing-intel-section">
                    <h4>📊 Pricing Overview</h4>
                    <div class="intel-grid">
                        <div class="intel-row">
                            <span class="label">Pricing Model</span>
                            <span class="value">${pricingModel}</span>
                        </div>
                        <div class="intel-row">
                            <span class="label">Price Range</span>
                            <span class="value">${priceRange}</span>
                        </div>
                        <div class="intel-row">
                            <span class="label">Estimated Base</span>
                            <span class="value">~$${basePPU}/user/month</span>
                        </div>
                        <div class="intel-row">
                            <span class="label">Free Trial</span>
                            <span class="value">${competitor.has_free_tier ? 'Yes' : 'Unlikely'}</span>
                        </div>
                    </div>
                </div>

                <div class="pricing-intel-section">
                    <h4>🎯 Discount Patterns</h4>
                    <div class="discount-patterns">
                        <div class="pattern-item">
                            <span class="pattern-label">Multi-Year Deal</span>
                            <span class="pattern-value">15-25% discount</span>
                        </div>
                        <div class="pattern-item">
                            <span class="pattern-label">Volume (100+ users)</span>
                            <span class="pattern-value">10-20% discount</span>
                        </div>
                        <div class="pattern-item">
                            <span class="pattern-label">End of Quarter</span>
                            <span class="pattern-value">5-15% additional</span>
                        </div>
                        <div class="pattern-item warning">
                            <span class="pattern-label">Hidden Costs</span>
                            <span class="pattern-value">Implementation, training, integrations</span>
                        </div>
                    </div>
                </div>

                <div class="pricing-intel-section">
                    <h4>⚔️ How to Win on Price</h4>
                    <ul class="win-tactics">
                        <li><strong>Focus on TCO:</strong> Calculate total cost over 3 years including hidden fees</li>
                        <li><strong>Value, not price:</strong> Emphasize ROI and time-to-value</li>
                        <li><strong>Bundle smartly:</strong> Include support and training in base price</li>
                        <li><strong>Reference competitors:</strong> Show pricing comparisons from similar deals</li>
                    </ul>
                </div>

                <div class="pricing-intel-section">
                    <h4>📝 Competitive Pricing Notes</h4>
                    <div class="pricing-notes-area">
                        <textarea id="pricingNotes" class="form-control" rows="4" placeholder="Add notes from competitive deals, customer feedback, etc..."></textarea>
                        <button class="btn btn-secondary btn-sm" onclick="savePricingNotes('${competitor.id}')">
                            💾 Save Notes
                        </button>
                    </div>
                </div>
            </div>

            <div class="pricing-actions">
                <button class="btn btn-primary" onclick="document.getElementById('pricingCompetitor1').value='${competitor.id}'; showSalesMarketingTab('pricing'); calculatePricing();">
                    📊 Open Pricing Calculator
                </button>
                <button class="btn btn-secondary" onclick="exportPricingIntel()">
                    📥 Export Intel
                </button>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function savePricingNotes(competitorId) {
    const notes = document.getElementById('pricingNotes')?.value;
    if (notes) {
        localStorage.setItem(`pricing_notes_${competitorId}`, notes);
        showNotification('Pricing notes saved!', 'success');
    }
}

function exportPricingIntel() {
    showNotification('Export feature coming soon!', 'info');
}

/**
 * BC-007: Load Export Package for Deal Room.
 */
async function loadDealRoomExport(competitorId) {
    const container = document.getElementById('dealRoomExportContent');
    if (!container) return;

    container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div>Preparing export options...</div>';

    try {
        const competitorRes = await fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() });
        const competitor = await competitorRes.json();

        renderDealRoomExport(competitor);

    } catch (error) {
        console.error('Failed to load export options:', error);
        container.innerHTML = '<p class="error-message">Failed to load export options. Please try again.</p>';
    }
}

function renderDealRoomExport(competitor) {
    const container = document.getElementById('dealRoomExportContent');
    if (!container) return;

    const html = `
        <div class="deal-room-export">
            <div class="export-header">
                <h3>📥 Export Package for ${competitor.name}</h3>
                <p>Generate comprehensive deal materials with one click</p>
            </div>

            <div class="export-options">
                <div class="export-option-card">
                    <div class="export-icon">📄</div>
                    <h4>Complete Deal Package</h4>
                    <p>PDF with all intel, battlecard, pricing, and objection responses</p>
                    <div class="export-contents">
                        <label><input type="checkbox" checked> Company Overview</label>
                        <label><input type="checkbox" checked> Dimension Scorecard</label>
                        <label><input type="checkbox" checked> Strengths & Weaknesses</label>
                        <label><input type="checkbox" checked> Win Themes</label>
                        <label><input type="checkbox" checked> Objection Responses</label>
                        <label><input type="checkbox" checked> Pricing Intel</label>
                        <label><input type="checkbox" checked> Recent News</label>
                    </div>
                    <button class="btn btn-primary" onclick="generateCompleteDealPackage('${competitor.id}')">
                        📦 Generate Package
                    </button>
                </div>

                <div class="export-option-card">
                    <div class="export-icon">⚔️</div>
                    <h4>Quick Battlecard</h4>
                    <p>One-page PDF battlecard for sales meetings</p>
                    <button class="btn btn-secondary" onclick="exportQuickBattlecard('${competitor.id}')">
                        📄 Export PDF
                    </button>
                </div>

                <div class="export-option-card">
                    <div class="export-icon">📊</div>
                    <h4>PowerPoint Slides</h4>
                    <p>Ready-to-present competitive analysis slides</p>
                    <button class="btn btn-secondary" onclick="exportToSlides('${competitor.id}')">
                        📊 Export PPTX
                    </button>
                </div>

                <div class="export-option-card">
                    <div class="export-icon">📧</div>
                    <h4>Email Summary</h4>
                    <p>Formatted email with key competitive points</p>
                    <button class="btn btn-secondary" onclick="exportToEmail('${competitor.id}')">
                        ✉️ Copy to Email
                    </button>
                </div>

                <div class="export-option-card">
                    <div class="export-icon">📋</div>
                    <h4>Slack/Teams Update</h4>
                    <p>Quick competitive update for team channels</p>
                    <button class="btn btn-secondary" onclick="exportToSlack('${competitor.id}')">
                        💬 Format for Slack
                    </button>
                </div>

                <div class="export-option-card">
                    <div class="export-icon">📑</div>
                    <h4>Excel Data Export</h4>
                    <p>Raw competitive data for analysis</p>
                    <button class="btn btn-secondary" onclick="exportToExcel('${competitor.id}')">
                        📑 Export Excel
                    </button>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
}

async function generateCompleteDealPackage(competitorId) {
    showNotification('Generating complete deal package...', 'info');

    try {
        // Fetch all data
        const [competitorRes, dimensionsRes, newsRes] = await Promise.all([
            fetch(`${API_BASE}/api/competitors/${competitorId}`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions`, { headers: getAuthHeaders() }),
            fetch(`${API_BASE}/api/competitors/${competitorId}/news?limit=10`, { headers: getAuthHeaders() })
        ]);

        const competitor = await competitorRes.json();
        const dimensions = await dimensionsRes.json();
        const news = await newsRes.json();

        // Generate PDF content
        const content = generateDealPackageContent(competitor, dimensions, news);

        // Download as text file (PDF generation would require a backend endpoint)
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${competitor.name.replace(/\s+/g, '_')}_Deal_Package.md`;
        a.click();
        URL.revokeObjectURL(url);

        showNotification('Deal package downloaded!', 'success');

    } catch (error) {
        console.error('Failed to generate deal package:', error);
        showNotification('Failed to generate package. Please try again.', 'error');
    }
}

function generateDealPackageContent(competitor, dimensions, news) {
    const dimData = dimensions.dimensions || {};
    const strengths = SM_DIMENSIONS.filter(d => (dimData[d.id]?.score || 0) >= 4);
    const weaknesses = SM_DIMENSIONS.filter(d => {
        const score = dimData[d.id]?.score;
        return score && score <= 2;
    });

    let content = `# Competitive Deal Package: ${competitor.name}
Generated: ${new Date().toLocaleString()}

---

## Company Overview
- **Name:** ${competitor.name}
- **Threat Level:** ${competitor.threat_level || 'Medium'}
- **Founded:** ${competitor.year_founded || 'Unknown'}
- **Employees:** ${competitor.employee_count || 'Unknown'}
- **Website:** ${competitor.website || 'N/A'}

---

## Dimension Scorecard (Overall: ${dimensions.overall_score?.toFixed(1) || 'N/A'}/5)

`;

    SM_DIMENSIONS.forEach(dim => {
        const data = dimData[dim.id] || {};
        content += `### ${dim.icon} ${dim.name}
- **Score:** ${data.score || 'Not rated'}/5
- **Evidence:** ${data.evidence || 'No evidence recorded'}

`;
    });

    content += `---

## Key Strengths (Watch Out)
${strengths.length > 0 ? strengths.map(s => `- ${s.icon} ${s.shortName}: ${dimData[s.id]?.evidence || 'Strong in this area'}`).join('\n') : 'No major strengths identified'}

---

## Key Weaknesses (Attack Here)
${weaknesses.length > 0 ? weaknesses.map(w => `- ${w.icon} ${w.shortName}: ${dimData[w.id]?.evidence || 'Weak in this area'}`).join('\n') : 'No major weaknesses identified'}

---

## Recent News
${news && news.length > 0 ? news.map(n => `- [${n.title}](${n.url}) - ${new Date(n.published_at || n.fetched_at).toLocaleDateString()}`).join('\n') : 'No recent news available'}

---

## Recommended Strategy
1. Focus messaging on areas where they are weak
2. Be prepared to address their strengths with counter-points
3. Use recent news for conversation starters
4. Calculate TCO to show pricing advantage

---

*Generated by Certify Intel Competitive Intelligence Platform*
`;

    return content;
}

function exportQuickBattlecard(competitorId) {
    // Navigate to battlecards and trigger export
    showSalesMarketingTab('battlecards');
    setTimeout(() => {
        document.getElementById('battlecardCompetitorSelect').value = competitorId;
        generateDynamicBattlecard();
        setTimeout(() => exportBattlecardPDF(), 500);
    }, 100);
}

function exportToSlides(competitorId) {
    showNotification('PowerPoint export coming soon!', 'info');
}

function exportToEmail(competitorId) {
    const content = `Subject: Competitive Intel Update - ${document.getElementById('dealIntelCompetitorSelect')?.selectedOptions[0]?.text || 'Competitor'}

Hi team,

Here's a quick competitive update:

[Key points from Deal Room would go here]

Best,
[Your name]
`;
    navigator.clipboard.writeText(content).then(() => {
        showNotification('Email content copied to clipboard!', 'success');
    });
}

function exportToSlack(competitorId) {
    const name = document.getElementById('dealIntelCompetitorSelect')?.selectedOptions[0]?.text || 'Competitor';
    const content = `*🎯 Competitive Intel Update: ${name}*

*Key Points:*
• [Add key strength/weakness]
• [Add recent news item]
• [Add recommended action]

_Generated by Certify Intel_`;

    navigator.clipboard.writeText(content).then(() => {
        showNotification('Slack message copied to clipboard!', 'success');
    });
}

function exportToExcel(competitorId) {
    window.open(`/api/export/competitor/${competitorId}/excel`, '_blank');
}

// Update loadDealIntelligence to also load sub-tab data
const originalLoadDealIntelligence = window.loadDealIntelligence || loadDealIntelligence;

// ==============================================================================
// SM-HIST: Dimension Score History
// ==============================================================================

let dimensionHistoryChart = null;

/**
 * Show a modal with the score history chart for a specific dimension.
 * @param {string} dimensionId - The dimension ID (e.g., 'product_packaging')
 * @param {string} dimensionName - Display name for the dimension
 */
async function showDimensionHistory(dimensionId, dimensionName) {
    const competitorId = document.getElementById('dimensionCompetitorSelect')?.value;
    if (!competitorId) {
        showNotification('Please select a competitor first', 'warning');
        return;
    }

    // Remove existing modal
    const existing = document.getElementById('dimensionHistoryModal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'dimensionHistoryModal';
    modal.className = 'modal-overlay';
    modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:10000;';

    const safeTitle = escapeHtml(dimensionName);
    modal.innerHTML = `
        <div class="modal-content" style="background:var(--bg-secondary);border-radius:12px;padding:24px;max-width:700px;width:90%;max-height:80vh;overflow-y:auto;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                <h3 style="margin:0;color:var(--text-primary);">Score History: ${safeTitle}</h3>
                <button onclick="closeDimensionHistoryModal()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--text-secondary);">&times;</button>
            </div>
            <div id="dimensionHistoryChartContainer" style="position:relative;height:300px;">
                <div style="text-align:center;padding:60px 0;color:var(--text-muted);">Loading history...</div>
            </div>
            <div id="dimensionHistoryTable" style="margin-top:16px;"></div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeDimensionHistoryModal();
    });

    // Fetch history data
    try {
        const data = await fetch(`${API_BASE}/api/sales-marketing/competitors/${competitorId}/dimensions/${dimensionId}/history`, {
            headers: { 'Authorization': 'Bearer ' + localStorage.getItem('access_token') }
        });

        const chartContainer = document.getElementById('dimensionHistoryChartContainer');
        if (!chartContainer) return;

        if (!data.ok) {
            chartContainer.innerHTML = '<div style="text-align:center;padding:60px 0;color:var(--text-muted);">No history data available yet. Scores are recorded when you save changes.</div>';
            return;
        }

        const history = await data.json();
        const entries = Array.isArray(history) ? history : (history.history || []);

        if (entries.length === 0) {
            chartContainer.innerHTML = '<div style="text-align:center;padding:60px 0;color:var(--text-muted);">No history data available yet. Scores are recorded when you save changes.</div>';
            return;
        }

        // Sort by date ascending
        entries.sort((a, b) => new Date(a.recorded_at || a.created_at || a.date) - new Date(b.recorded_at || b.created_at || b.date));

        const labels = entries.map(e => {
            const d = new Date(e.recorded_at || e.created_at || e.date);
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        const scores = entries.map(e => e.score || e.new_score || 0);

        // Create canvas
        chartContainer.innerHTML = '<canvas id="dimensionHistoryCanvas"></canvas>';

        if (dimensionHistoryChart) {
            dimensionHistoryChart.destroy();
            dimensionHistoryChart = null;
        }

        const canvas = document.getElementById('dimensionHistoryCanvas');
        if (!canvas) return;

        dimensionHistoryChart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Score',
                    data: scores,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5,
                    pointBackgroundColor: '#3b82f6',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        min: 0,
                        max: 5,
                        ticks: { color: '#94a3b8', stepSize: 1 },
                        grid: { color: 'rgba(148,163,184,0.1)' }
                    },
                    x: {
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148,163,184,0.1)' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });

        // Render history table
        const tableContainer = document.getElementById('dimensionHistoryTable');
        if (tableContainer && entries.length > 0) {
            tableContainer.innerHTML = `
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border-color);">
                            <th style="text-align:left;padding:8px;color:var(--text-secondary);">Date</th>
                            <th style="text-align:center;padding:8px;color:var(--text-secondary);">Score</th>
                            <th style="text-align:left;padding:8px;color:var(--text-secondary);">Evidence</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${entries.slice().reverse().slice(0, 20).map(e => {
                            const d = new Date(e.recorded_at || e.created_at || e.date);
                            const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                            const score = e.score || e.new_score || 0;
                            const evidence = e.evidence || e.notes || '';
                            const color = SM_SCORE_COLORS[score] || '#6c757d';
                            return `<tr style="border-bottom:1px solid var(--border-color);">
                                <td style="padding:8px;color:var(--text-primary);">${escapeHtml(dateStr)}</td>
                                <td style="text-align:center;padding:8px;"><span style="background:${color};color:white;padding:2px 8px;border-radius:4px;font-weight:600;">${score}</span></td>
                                <td style="padding:8px;color:var(--text-secondary);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(evidence)}</td>
                            </tr>`;
                        }).join('')}
                    </tbody>
                </table>
            `;
        }

    } catch (err) {
        console.error('[SM] Failed to load dimension history:', err);
        const chartContainer = document.getElementById('dimensionHistoryChartContainer');
        if (chartContainer) {
            chartContainer.innerHTML = '<div style="text-align:center;padding:60px 0;color:var(--text-muted);">Failed to load history data.</div>';
        }
    }
}

function closeDimensionHistoryModal() {
    if (dimensionHistoryChart) {
        dimensionHistoryChart.destroy();
        dimensionHistoryChart = null;
    }
    const modal = document.getElementById('dimensionHistoryModal');
    if (modal) modal.remove();
}

// ============== BC P2 Exports ==============

window.showDimensionHistory = showDimensionHistory;
window.closeDimensionHistoryModal = closeDimensionHistoryModal;
window.showDealRoomTab = showDealRoomTab;
window.loadDealRoomNews = loadDealRoomNews;
window.filterDealRoomNews = filterDealRoomNews;
window.refreshCompetitorNews = refreshCompetitorNews;
window.exportNewsToEmail = exportNewsToEmail;
window.loadDealRoomPricing = loadDealRoomPricing;
window.savePricingNotes = savePricingNotes;
window.exportPricingIntel = exportPricingIntel;
window.loadDealRoomExport = loadDealRoomExport;
window.generateCompleteDealPackage = generateCompleteDealPackage;
window.exportQuickBattlecard = exportQuickBattlecard;
window.exportToSlides = exportToSlides;
window.exportToEmail = exportToEmail;
window.exportToSlack = exportToSlack;
window.exportToExcel = exportToExcel;
