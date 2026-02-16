/**
 * Certify Intel - Enhanced Analytics Module
 * Advanced visualizations and market analysis
 */

// ============== Market Quadrant Analysis ==============

function renderMarketQuadrant() {
    const container = document.getElementById('marketQuadrantContainer');
    if (!container || !competitors.length) return;

    // Calculate quadrant positions from real DB data
    const quadrantData = competitors
        .map(comp => {
            // Parse customer count (X-axis: Market Share proxy)
            const customers = parseInt((comp.customer_count || '0').replace(/\D/g, '')) || 0;

            // Parse employee growth rate (Y-axis: Growth proxy)
            let growthRate = 0;
            if (comp.employee_growth_rate) {
                const growthStr = comp.employee_growth_rate.toString().replace('%', '');
                growthRate = parseFloat(growthStr);
            }

            // Exclude if both metrics are 0
            if (!customers && !growthRate) return null;

            return {
                name: comp.name,
                customers: customers,
                growthRate: isNaN(growthRate) ? 0 : growthRate,
                threat: comp.threat_level,
                website: comp.website || null
            };
        })
        .filter(d => d !== null);

    if (!quadrantData.length) {
        container.innerHTML = '<p class="empty-state">Not enough data for quadrant analysis. Competitors need customer_count and employee_growth_rate fields populated.</p>';
        return;
    }

    // Normalize X (Market Share) to 5-95 so points don't clip edges
    const maxCustomers = Math.max(...quadrantData.map(d => d.customers)) || 1;
    const maxGrowth = Math.max(...quadrantData.map(d => d.growthRate), 20); // at least 20% scale

    const plottedData = quadrantData.map(d => ({
        ...d,
        x: 5 + (d.customers / maxCustomers) * 90,
        y: 5 + (Math.min(Math.max(d.growthRate, 0), maxGrowth) / maxGrowth) * 90
    }));

    // Create quadrant chart with axis labels
    container.innerHTML = `
        <div style="position:relative;">
            <div style="position:absolute;left:-10px;top:50%;transform:rotate(-90deg) translateX(-50%);transform-origin:0 0;font-size:0.75em;color:#94a3b8;white-space:nowrap;">Growth Rate (%)</div>
            <div class="quadrant-chart" style="position: relative; width: 100%; height: 400px; border: 1px solid #334155; border-radius: 8px; overflow: hidden; background: #0f172a; margin-left:20px;">
                <!-- Quadrant labels -->
                <div style="position: absolute; top: 10px; left: 15px; font-weight: 600; color: #059669; font-size:0.85em;">Stars (High Share + High Growth)</div>
                <div style="position: absolute; top: 10px; right: 15px; font-weight: 600; color: #7c3aed; font-size:0.85em; text-align:right;">Question Marks (Low Share + High Growth)</div>
                <div style="position: absolute; bottom: 10px; left: 15px; font-weight: 600; color: #2563eb; font-size:0.85em;">Cash Cows (High Share + Low Growth)</div>
                <div style="position: absolute; bottom: 10px; right: 15px; font-weight: 600; color: #64748b; font-size:0.85em; text-align:right;">Dogs (Low Share + Low Growth)</div>

                <!-- Quadrant lines -->
                <div style="position: absolute; top: 50%; left: 0; right: 0; border-top: 2px dashed #334155;"></div>
                <div style="position: absolute; left: 50%; top: 0; bottom: 0; border-left: 2px dashed #334155;"></div>

                <!-- Data points -->
                ${plottedData.map(d => {
                    const size = Math.max(24, Math.min(48, Math.sqrt(d.customers) * 0.5));
                    const nameShort = d.name.length > 8 ? d.name.substring(0, 7) + '..' : d.name;
                    return `
                    <div class="quadrant-point"
                         style="position: absolute;
                                left: ${d.x}%;
                                bottom: ${d.y}%;
                                transform: translate(-50%, 50%);
                                width: ${size}px;
                                height: ${size}px;
                                border-radius: 50%;
                                background: ${getThreatColor(d.threat)};
                                opacity: 0.85;
                                cursor: pointer;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                font-size: 8px;
                                color: white;
                                font-weight: bold;
                                border: 2px solid rgba(255,255,255,0.3);"
                         onclick="${d.website ? `window.open('${escapeHtml(d.website)}','_blank','noopener')` : `showCompetitorDetail && showCompetitorDetail(${competitors.find(c=>c.name===d.name)?.id || 0})`}"
                         title="${escapeHtml(d.name)}: ${d.customers.toLocaleString()} customers, ${d.growthRate}% growth${d.website ? ' | Click to visit source' : ''}">
                        ${escapeHtml(nameShort)}
                    </div>`;
                }).join('')}
            </div>
            <div style="text-align:center;font-size:0.75em;color:#94a3b8;margin-top:4px;margin-left:20px;">Relative Market Share (Customer Count)</div>
        </div>
        <div class="quadrant-legend" style="display: flex; gap: 16px; justify-content: center; margin-top: 12px; flex-wrap: wrap;">
            <span style="display:flex;align-items:center;gap:5px;"><span style="width:12px;height:12px;border-radius:50%;background:#DC3545;"></span> High Threat</span>
            <span style="display:flex;align-items:center;gap:5px;"><span style="width:12px;height:12px;border-radius:50%;background:#FFC107;"></span> Medium Threat</span>
            <span style="display:flex;align-items:center;gap:5px;"><span style="width:12px;height:12px;border-radius:50%;background:#28A745;"></span> Low Threat</span>
            <span style="font-size:0.8em;color:#94a3b8;">(${quadrantData.length} competitors with data)</span>
        </div>
    `;
}

function getThreatColor(threat) {
    switch (threat) {
        case 'High': return '#DC3545';
        case 'Medium': return '#FFC107';
        case 'Low': return '#28A745';
        default: return '#6C757D';
    }
}


// ============== Competitive Timeline ==============

async function renderCompetitorTimeline(competitorId) {
    const container = document.getElementById('timelineContainer');
    if (!container) return;

    container.innerHTML = '<p class="loading">Loading timeline...</p>';

    // Fetch changes for this competitor
    const result = await fetchAPI(`/api/changes?competitor_id=${competitorId}&days=365`);
    const changes = result?.changes || [];

    if (changes.length === 0) {
        container.innerHTML = '<p class="empty-state">No timeline events available</p>';
        return;
    }

    container.innerHTML = `
        <div class="timeline">
            ${changes.slice(0, 20).map(change => `
                <div class="timeline-item">
                    <div class="timeline-marker ${change.severity.toLowerCase()}"></div>
                    <div class="timeline-content">
                        <div class="timeline-date">${formatDate(change.detected_at)}</div>
                        <div class="timeline-title">${escapeHtml(change.change_type)}</div>
                        <div class="timeline-detail">
                            ${change.previous_value ? `${escapeHtml(change.previous_value)} → ` : ''}${escapeHtml(change.new_value || '')}
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}


// ============== Enhanced Battlecard with Insights ==============


async function viewEnhancedBattlecard(id) {
    const comp = competitors.find(c => c.id === id);
    if (!comp) return;

    // Show loading modal
    const loadingContent = `
        <div class="battlecard-full">
            <h2>🃏 ${comp.name} Battlecard</h2>
            <p class="loading">Generating AI Strategic Analysis...</p>
        </div>
    `;
    showModal(loadingContent);

    try {
        // Parallel fetch for comprehensive threat analysis + SWOT + News
        const [threatAnalysis, swot, news] = await Promise.all([
            fetchAPI(`/api/competitors/${id}/threat-analysis`),
            fetchAPI(`/api/competitors/${id}/swot`),
            fetchAPI(`/api/competitors/${id}/news?days=30`)
        ]);

        const content = `
            <div class="battlecard-full enhanced">
                <div class="battlecard-header" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e2e8f0; padding-bottom: 15px; margin-bottom: 20px;">
                    <div>
                        <h2 style="margin: 0; color: #1e293b;">🃏 ${comp.name}</h2>
                        <span class="threat-badge ${comp.threat_level?.toLowerCase() || 'medium'}">${comp.threat_level || 'Unknown'} Threat</span>
                    </div>
                    <div style="font-size: 0.9em; color: #64748b;">
                        Last Updated: ${new Date().toLocaleDateString()}
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 3fr 2fr; gap: 20px;">
                    <!-- Left Column: Strategy & SWOT -->
                    <div class="left-col">
                        <!-- AI SWOT Analysis -->
                        <div class="insight-section swot-section" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0; padding: 15px; margin-bottom: 20px;">
                            <h3 style="color: #3b82f6; display: flex; align-items: center; gap: 8px;">
                                🧠 AI Strategic Analysis (SWOT)
                            </h3>
                            <div class="swot-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                                <div class="swot-box strength">
                                    <strong style="color: #16a34a;">💪 Strengths</strong>
                                    <ul>${(swot.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>
                                </div>
                                <div class="swot-box weakness">
                                    <strong style="color: #dc2626;">🛑 Weaknesses</strong>
                                    <ul>${(swot.weaknesses || []).map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul>
                                </div>
                                <div class="swot-box opportunity">
                                    <strong style="color: #2563eb;">🚀 Opportunities</strong>
                                    <ul>${(swot.opportunities || []).map(o => `<li>${escapeHtml(o)}</li>`).join('')}</ul>
                                </div>
                                <div class="swot-box threat">
                                    <strong style="color: #d97706;">🛡️ Threats</strong>
                                    <ul>${(swot.threats || []).map(t => `<li>${escapeHtml(t)}</li>`).join('')}</ul>
                                </div>
                            </div>
                        </div>

                        <!-- AI Threat Score -->
                        <div class="insight-section">
                            <h3>🎯 Threat Assessment</h3>
                            ${threatAnalysis?.score ? `
                                <div class="threat-score-display" style="display: flex; align-items: center; gap: 15px; margin: 10px 0;">
                                    <div class="score-circle" style="width: 60px; height: 60px; border-radius: 50%; background: conic-gradient(${getThreatScoreColor(threatAnalysis.score)} ${threatAnalysis.score}%, #e5e7eb ${threatAnalysis.score}%); display: flex; align-items: center; justify-content: center;">
                                        <span style="background: white; width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">${threatAnalysis.score}</span>
                                    </div>
                                    <div>
                                        <strong>${threatAnalysis.level} Risk</strong>
                                        <p style="margin: 5px 0; color: #64748b; font-size: 0.9em;">${escapeHtml(threatAnalysis.reasoning)}</p>
                                    </div>
                                </div>
                            ` : '<p>Threat analysis unavailable</p>'}
                        </div>
                    </div>

                    <!-- Right Column: Stats & Facts -->
                    <div class="right-col">
                        <!-- Quick Facts -->
                        <div class="insight-section">
                            <h3>📊 Quick Facts</h3>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                                <div><strong>HQ:</strong> ${comp.headquarters || 'N/A'}</div>
                                <div><strong>Founded:</strong> ${comp.year_founded || 'N/A'}</div>
                                <div><strong>Funding:</strong> ${comp.funding_total || 'N/A'}</div>
                                <div><strong>Employees:</strong> ${comp.employee_count || 'N/A'}</div>
                            </div>
                        </div>

                        <!-- Recent News -->
                        <div class="insight-section">
                            <h3>📰 Recent Headlines</h3>
                            ${news?.articles?.length ? `
                                <ul style="padding-left: 20px; font-size: 0.9em;">${news.articles.slice(0, 3).map(a => `<li><a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">${escapeHtml(a.title)}</a> <span style="font-size:0.8em;color:#aaa">(${escapeHtml(a.source)})</span></li>`).join('')}</ul>
                            ` : '<p style="color: #94a3b8; font-style: italic;">No recent news found.</p>'}
                        </div>
                    </div>
                </div>

                <div style="margin-top: 20px; text-align: right;">
                    <button class="btn btn-primary" onclick="downloadBattlecard(${id})">📄 Download Report</button>
                    <button class="btn btn-secondary" onclick="closeModal()">Close</button>
                </div>
            </div>
        `;

        showModal(content);

    } catch (e) {
        showModal(`
            <div class="error-state">
                <h3>⚠️ Error Loading Battlecard</h3>
                <p>${e.message}</p>
                <button class="btn btn-secondary" onclick="closeModal()">Close</button>
            </div>
        `);
    }
}

function getThreatScoreColor(score) {
    if (score >= 70) return '#DC3545';
    if (score >= 40) return '#FFC107';
    return '#28A745';
}


// ============== Win/Loss Tracker (Real DB) ==============

// winLossData is declared in app_v2.js — reuse it here
if (typeof winLossData === 'undefined') var winLossData = [];

function showWinLossModal() {
    const content = `
        <h2>🏆 Log Competitive Deal</h2>
        <form id="winLossForm" onsubmit="logWinLoss(event)">
            <div class="form-group">
                <label>Competitor</label>
                <select name="competitor_id" required>
                    ${competitors.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label>Customer Name</label>
                <input type="text" name="customer_name" required placeholder="e.g., Mercy Health System">
            </div>
            <div class="form-group">
                <label>Deal Value ($)</label>
                <input type="number" name="deal_value" placeholder="100000">
            </div>
            <div class="form-group">
                <label>Outcome</label>
                <select name="outcome" required>
                    <option value="Won">Won ✅</option>
                    <option value="Lost">Lost ❌</option>
                </select>
            </div>
            <div class="form-group">
                <label>Primary Reason</label>
                <select name="reason">
                    <option value="">N/A</option>
                    <option value="Price">Price</option>
                    <option value="Features">Features</option>
                    <option value="Integration">Integration</option>
                    <option value="Relationship">Existing Relationship</option>
                    <option value="Support">Support Concerns</option>
                    <option value="Other">Other</option>
                </select>
            </div>
            <div class="form-group">
                <label>Notes</label>
                <textarea name="notes" rows="3" placeholder="Additional context..."></textarea>
            </div>
            <button type="submit" class="btn btn-primary">Log Deal</button>
        </form>
    `;
    showModal(content);
}

async function logWinLoss(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    // Get competitor name from selection
    const compId = formData.get('competitor_id');
    const comp = competitors.find(c => c.id == compId);

    const payload = {
        competitor_id: compId,
        competitor_name: comp ? comp.name : 'Unknown',
        customer_name: formData.get('customer_name'),
        deal_value: formData.get('deal_value') ? parseFloat(formData.get('deal_value')) : null,
        outcome: formData.get('outcome'),
        reason: formData.get('reason'),
        notes: formData.get('notes')
    };

    try {
        await fetchAPI('/api/win-loss', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        showToast(`Deal logged successfully`, 'success');
        closeModal();
        await renderWinLossStats(); // Refresh from DB
    } catch (e) {
        showToast('Error logging deal: ' + e.message, 'error');
    }
}

async function renderWinLossStats() {
    const container = document.getElementById('winLossContainer');
    if (!container) return;

    try {
        // Fetch from Real DB
        winLossData = await fetchAPI('/api/win-loss');
    } catch (e) {
        console.error("Failed to load win/loss stats", e);
        winLossData = [];
    }

    const wins = winLossData.filter(d => d.outcome === 'Won').length || 0;
    const losses = winLossData.filter(d => d.outcome === 'Lost').length || 0;
    const total = wins + losses;
    const winRate = total > 0 ? Math.round((wins / total) * 100) : 0;

    // Loss reasons breakdown
    const lossReasons = {};
    winLossData.filter(d => d.outcome === 'Lost').forEach(d => {
        const reason = d.reason || 'Unknown';
        lossReasons[reason] = (lossReasons[reason] || 0) + 1;
    });

    container.innerHTML = `
        <div class="win-loss-stats" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
            <div style="text-align: center; padding: 20px; background: #dcfce7; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #16a34a;">${wins}</div>
                <div>Wins</div>
            </div>
            <div style="text-align: center; padding: 20px; background: #fee2e2; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #dc2626;">${losses}</div>
                <div>Losses</div>
            </div>
            <div style="text-align: center; padding: 20px; background: #e0f2fe; border-radius: 8px;">
                <div style="font-size: 2em; font-weight: bold; color: #0284c7;">${winRate}%</div>
                <div>Win Rate</div>
            </div>
        </div>
        ${losses > 0 ? `
            <h4>Loss Reasons</h4>
            <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                ${Object.entries(lossReasons).map(([reason, count]) => `
                    <span style="background: #fef2f2; padding: 5px 12px; border-radius: 20px; color: #b91c1c;">
                        ${escapeHtml(reason)}: ${count}
                    </span>
                `).join('')}
            </div>
        ` : ''}
        
        <h4 style="margin-top:20px;">Recent Deals</h4>
        <div style="max-height: 200px; overflow-y: auto;">
            ${winLossData.slice(0, 5).map(d => {
                const comp = competitors.find(c => c.id == d.competitor_id || c.name === d.competitor_name);
                const compLink = comp && comp.website
                    ? `<a href="${escapeHtml(comp.website)}" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline dotted;">${escapeHtml(d.competitor_name)}</a>`
                    : escapeHtml(d.competitor_name || '');
                const dealDate = d.deal_date ? new Date(d.deal_date).toLocaleDateString() : '';
                const dealVal = d.deal_value ? `$${Number(d.deal_value).toLocaleString()}` : '';
                return `
                <div style="padding: 10px; border-bottom: 1px solid #eee; font-size: 0.9em; display: flex; justify-content: space-between;">
                    <div>
                        <strong>${compLink}</strong> - ${escapeHtml(d.customer_name || 'Confidential')}
                        ${dealVal ? `<span style="color:#64748b;margin-left:8px;">${dealVal}</span>` : ''}
                        ${dealDate ? `<span style="color:#94a3b8;margin-left:8px;font-size:0.85em;">${dealDate}</span>` : ''}
                        ${d.reason ? `<span style="color:#94a3b8;margin-left:8px;font-size:0.85em;">Reason: ${escapeHtml(d.reason)}</span>` : ''}
                        <div style="color: #666;">${escapeHtml(d.notes || '')}</div>
                    </div>
                    <div style="font-weight: bold; color: ${d.outcome === 'Won' ? '#16a34a' : '#dc2626'};">
                        ${d.outcome}
                    </div>
                </div>`;
            }).join('')}
        </div>

        <button class="btn btn-primary" style="margin-top: 15px;" onclick="showWinLossModal()">+ Log New Deal</button>
    `;
}


// ============== Webhooks Management (Real DB) ==============

async function showWebhookSettings() {
    let webhooks = [];
    try {
        webhooks = await fetchAPI('/api/webhooks');
    } catch (e) {
        console.error("Failed to fetch webhooks", e);
    }

    const content = `
        <h2>🔗 Webhook Configuration</h2>
        <p style="color: #64748b; margin-bottom: 20px;">Configure webhooks to receive real-time notifications on competitor changes.</p>
        
        <form id="webhookForm" onsubmit="addWebhook(event)">
            <div class="form-group">
                <label>Webhook Name</label>
                <input type="text" name="name" required placeholder="e.g., Slack Alert">
            </div>
            <div class="form-group">
                <label>Webhook URL</label>
                <input type="url" name="url" required placeholder="https://hooks.slack.com/...">
            </div>
            <div class="form-group">
                <label>Event Types</label>
                <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                    <label><input type="checkbox" name="events" value="price.changed"> Price Changes</label>
                    <label><input type="checkbox" name="events" value="threat_level.changed"> Threat Level</label>
                    <label><input type="checkbox" name="events" value="competitor.created"> New Competitor</label>
                    <label><input type="checkbox" name="events" value="news.alert"> News Alert</label>
                    <label><input type="checkbox" name="events" value="deal.won"> Deal Won</label>
                    <label><input type="checkbox" name="events" value="deal.lost"> Deal Lost</label>
                </div>
            </div>
            <button type="submit" class="btn btn-primary">Add Webhook</button>
        </form>
        
        <h3 style="margin-top: 20px;">Active Webhooks</h3>
        <div id="webhookList">
            ${webhooks.length ? webhooks.map((w) => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: #f8fafc; border-radius: 8px; margin-top: 10px;">
                    <div>
                        <strong>${escapeHtml(w.name)}</strong>
                        <div style="font-family: monospace; font-size: 0.8em; color: #666;">${escapeHtml(w.url)}</div>
                        <div style="color: #64748b; font-size: 0.9em; margin-top: 5px;">Events: ${escapeHtml(w.event_types)}</div>
                    </div>
                    <button class="btn btn-secondary" onclick="removeWebhook(${parseInt(w.id) || 0})">Remove</button>
                </div>
            `).join('') : '<p class="empty-state">No webhooks configured</p>'}
        </div>
    `;
    showModal(content);
}

async function addWebhook(event) {
    event.preventDefault();
    const form = event.target;
    const name = form.querySelector('input[name="name"]').value;
    const url = form.querySelector('input[name="url"]').value;
    const events = Array.from(form.querySelectorAll('input[name="events"]:checked')).map(cb => cb.value);

    if (events.length === 0) {
        showToast('Please select at least one event type', 'warning');
        return;
    }

    try {
        await fetchAPI('/api/webhooks', {
            method: 'POST',
            body: JSON.stringify({
                name: name,
                url: url,
                event_types: events.join(',')
            })
        });
        showToast('Webhook added successfully', 'success');
        showWebhookSettings(); // Refresh modal
    } catch (e) {
        showToast('Error adding webhook: ' + e.message, 'error');
    }
}

async function removeWebhook(id) {
    if (!confirm('Delete this webhook?')) return;
    try {
        await fetchAPI(`/api/webhooks/${id}`, { method: 'DELETE' });
        showToast('Webhook removed', 'info');
        showWebhookSettings();
    } catch (e) {
        showToast('Error removing webhook: ' + e.message, 'error');
    }
}


// Initialize enhanced features
document.addEventListener('DOMContentLoaded', () => {
    // Load win/loss data
    renderWinLossStats();
});
