document.addEventListener('DOMContentLoaded', () => {
    // ─── DOM references ──────────────────────────────────────
    const els = {
        agentsGrid: document.getElementById('agentsGrid'),
        onlineCount: document.getElementById('onlineCount'),
        totalRamDisplay: document.getElementById('totalRamDisplay'),
        lastUpdate: document.getElementById('lastUpdate'),
        footerTime: document.getElementById('footer-time'),
        creditsTotal: document.getElementById('credits-total'),
        creditsUsed: document.getElementById('credits-used'),
        creditsRemaining: document.getElementById('credits-remaining'),
        creditsPct: document.getElementById('credits-pct'),
        creditsBar: document.getElementById('credits-bar'),
        historyContent: document.getElementById('history-content'),
        agentsBadge: document.getElementById('agents-badge'),
        weekCostBadge: document.getElementById('weekCostBadge'),
        last24hDisplay: document.getElementById('last24hDisplay'),
        alertBanner: document.getElementById('alertBanner'),
        alertMessage: document.getElementById('alertMessage'),
        // Epic
        epicSessions: document.getElementById('epic-sessions'),
        epicMessages: document.getElementById('epic-messages'),
        epicTokens: document.getElementById('epic-tokens'),
        epicCost: document.getElementById('epic-cost'),
        epicDays: document.getElementById('epic-days'),
        epicScore: document.getElementById('epic-score'),
        // Activity
        activityContent: document.getElementById('activity-content'),
        // Gateway
        gatewayContent: document.getElementById('gateway-content'),
        // Tools
        toolsGrid: document.getElementById('toolsGrid'),
    };

    let dailyChart = null;
    let modelChart = null;

    // ─── Helpers ─────────────────────────────────────────────
    function fmtBytes(bytes) {
        if (bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
    }

    function fmtNumber(n) {
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
        if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
        return n.toLocaleString('es-MX');
    }

    function timeAgo(ts) {
        if (!ts) return '—';
        const now = Date.now() / 1000;
        let diff = now - ts;
        if (diff < 0 && ts > 1e15) diff = now - (ts / 1000);
        if (diff < 0) diff = 0;
        if (diff < 60) return 'ahora';
        if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
        if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
        return `hace ${Math.floor(diff / 86400)}d`;
    }

    function fmtDate(ts) {
        if (!ts) return '—';
        const d = new Date(ts * 1000);
        return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    }

    function fmtDuration(start, end) {
        if (!start) return '—';
        const now = Date.now() / 1000;
        const endTs = end || now;
        const diff = endTs - start;
        if (diff < 0) return '—';
        if (diff < 60) return `${Math.floor(diff)}s`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ${Math.floor(diff % 60)}s`;
        return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`;
    }

    function showAlert(message, type = 'warning') {
        els.alertBanner.className = `alert-banner ${type}`;
        els.alertMessage.textContent = message;
        els.alertBanner.classList.remove('hidden');
        setTimeout(() => els.alertBanner.classList.add('hidden'), 8000);
    }

    // ─── Agent Card ──────────────────────────────────────────
    function renderAgentCard(agent) {
        const memPct = agent.mem_pct || 0;
        const memUsed = fmtBytes(agent.mem_usage || 0);
        const memTotal = fmtBytes(agent.mem_limit || 0);
        return `
            <div class="agent-card ${agent.online ? 'online' : ''}" style="--color: ${agent.color}">
                <div class="agent-card-header">
                    <div class="agent-name">
                        <span class="agent-emoji">${agent.emoji}</span>
                        ${agent.name}
                    </div>
                    <div class="status-dot ${agent.online ? 'online' : 'offline'}"></div>
                </div>
                <div class="agent-stats">
                    <div class="stat-row">
                        <span class="stat-label-inline">CPU</span>
                        <span class="stat-value-inline">${agent.cpu}%</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: ${Math.min(agent.cpu, 100)}%; background: ${agent.online ? agent.color : 'var(--text-muted)'}"></div>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label-inline">RAM</span>
                        <span class="stat-value-inline">${memUsed} / ${memTotal} (${memPct}%)</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: ${Math.min(memPct, 100)}%; background: ${memPct > 80 ? 'var(--accent-red)' : agent.online ? agent.color : 'var(--text-muted)'}"></div>
                    </div>
                </div>
                <div class="agent-detail">
                    <span class="agent-uptime">${agent.uptime || '—'}</span>
                    <span class="agent-gateway" title="${agent.gateway}">${agent.online ? '✅ up' : '❌ down'}</span>
                </div>
            </div>
        `;
    }

    // ─── Fetch Agents ────────────────────────────────────────
    async function fetchAgents() {
        try {
            const resp = await fetch('/api/agents');
            const data = await resp.json();
            els.agentsGrid.innerHTML = data.agents.map(renderAgentCard).join('');
            els.onlineCount.querySelector('.stat-value').textContent = `${data.totals.online}/${data.totals.total}`;
            els.totalRamDisplay.querySelector('.stat-value').textContent = fmtBytes(data.totals.used_ram || 0);
            els.agentsBadge.textContent = `${data.totals.online} en línea`;
            els.lastUpdate.textContent = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch (e) {
            els.agentsGrid.innerHTML = '<div class="agent-card" style="grid-column:1/-1;text-align:center;padding:2rem">❌ Error al cargar agentes</div>';
        }
    }

    // ─── Fetch Credits ───────────────────────────────────────
    async function fetchCredits() {
        try {
            const resp = await fetch('/api/credits');
            const data = await resp.json();
            els.creditsTotal.textContent = `$${data.total.toFixed(2)}`;
            els.creditsUsed.textContent = `$${data.used.toFixed(2)}`;
            els.creditsRemaining.textContent = `$${data.remaining.toFixed(2)}`;
            const pct = data.percent_used || 0;
            els.creditsPct.textContent = `${pct}%`;
            els.creditsBar.style.width = `${Math.min(pct, 100)}%`;
            const barColor = pct > 75 ? 'var(--accent-red)' : pct > 50 ? 'var(--accent-orange)' : 'linear-gradient(90deg, var(--accent-green), var(--accent-orange))';
            els.creditsBar.style.background = barColor;
        } catch (e) {
            els.creditsTotal.textContent = '—';
            els.creditsUsed.textContent = '—';
            els.creditsRemaining.textContent = '—';
        }
    }

    // ─── History ──────────────────────────────────────────────
    async function fetchHistory() {
        try {
            const resp = await fetch('/api/history?limit=8');
            const data = await resp.json();
            let html = '';
            for (const [agentId, agentData] of Object.entries(data)) {
                const sessions = agentData.sessions || [];
                html += `<div class="agent-timeline">`;
                html += `<div class="timeline-header" style="color: ${agentData.color}">${agentData.emoji} ${agentData.name}</div>`;
                if (sessions.length === 0) {
                    html += `<div class="timeline-items"><div class="timeline-empty">Sin sesiones registradas</div></div>`;
                } else {
                    html += `<div class="timeline-items">`;
                    for (const s of sessions) {
                        const cost = s.cost_usd ? `$${s.cost_usd.toFixed(4)}` : '—';
                        html += `
                            <div class="timeline-item">
                                <div class="timeline-item-header">
                                    <span class="timeline-title">${s.title || 'Sin título'}</span>
                                    <span class="timeline-cost">${cost}</span>
                                </div>
                                <div class="timeline-meta">
                                    <span>📅 ${fmtDate(s.started_at)}</span>
                                    <span>⏱ ${fmtDuration(s.started_at, s.ended_at)}</span>
                                    ${s.message_count ? `<span>💬 ${s.message_count} msgs</span>` : ''}
                                    ${s.tool_call_count ? `<span>🔧 ${s.tool_call_count} tools</span>` : ''}
                                </div>
                            </div>
                        `;
                    }
                    html += `</div>`;
                }
                html += `</div>`;
            }
            els.historyContent.innerHTML = html;
        } catch (e) {
            els.historyContent.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:2rem">❌ Error al cargar historial</div>';
        }
    }

    // ─── Epic Stats ──────────────────────────────────────────
    async function fetchStats() {
        try {
            const resp = await fetch('/api/stats');
            const d = await resp.json();
            els.epicSessions.textContent = fmtNumber(d.sessions);
            els.epicMessages.textContent = fmtNumber(d.messages);
            els.epicTokens.textContent = fmtNumber(d.tokens);
            els.epicCost.textContent = `$${d.cost.toFixed(2)}`;
            els.epicDays.textContent = d.days_active;
            els.epicScore.textContent = d.titan_score || 0;
            els.last24hDisplay.querySelector('.stat-value').textContent = d.sessions_24h;
        } catch (e) { /* ignore */ }
    }

    // ─── Charts ──────────────────────────────────────────────
    async function fetchCharts() {
        try {
            const resp = await fetch('/api/analytics');
            const d = await resp.json();

            // Week cost badge
            if (d.week_cost > 0) {
                els.weekCostBadge.textContent = `📅 ${d.total_sessions} sesiones · $${d.week_cost.toFixed(2)}/semana`;
                els.weekCostBadge.style.display = 'inline-block';
            }

            // Tool cards
            let toolsHtml = '';
            for (const agent of ['titan', 'hermes', 'hermina']) {
                // We show tool call counts from the analytics merged data - total across all
            }
            // Tool calls per agent from stats - we can show total_tool_calls
            // Actually the tool call data per agent comes from analytics... let me use it simpler
            toolsHtml = '';
            const toolData = [
                { name: 'Titán', emoji: '🚀', count: 0, color: '#00d4ff' },
                { name: 'Hermes', emoji: '🤖', count: 0, color: '#a855f7' },
                { name: 'Hermina', emoji: '💜', count: 0, color: '#ec4899' },
            ];
            // We'll update tool calls from SSE per-agent data later
            els.toolsGrid.innerHTML = toolData.map(t => `
                <div class="tool-card">
                    <div class="tool-card-header">
                        <span class="tool-card-emoji">${t.emoji}</span>
                        <span class="tool-agent-name" style="color:${t.color}">${t.name}</span>
                    </div>
                    <div class="tool-value" id="tool-${t.name.toLowerCase()}">0</div>
                    <div class="tool-label">Tool calls</div>
                </div>
            `).join('');

            // ─── Daily Cost Chart ──────────────────────────
            const dailyCtx = document.getElementById('dailyCostChart');
            if (dailyCtx && d.daily_cost && d.daily_cost.length > 0) {
                const days = d.daily_cost.map(x => x.day.slice(5));
                const costs = d.daily_cost.map(x => x.cost);

                if (dailyChart) dailyChart.destroy();
                dailyChart = new Chart(dailyCtx, {
                    type: 'bar',
                    data: {
                        labels: days,
                        datasets: [{
                            label: 'Costo ($)',
                            data: costs,
                            backgroundColor: costs.map(c => c > 0.5
                                ? 'rgba(239, 68, 68, 0.6)'
                                : c > 0.1
                                    ? 'rgba(245, 158, 11, 0.6)'
                                    : 'rgba(34, 197, 94, 0.6)'),
                            borderColor: costs.map(c => c > 0.5
                                ? '#ef4444'
                                : c > 0.1
                                    ? '#f59e0b'
                                    : '#22c55e'),
                            borderWidth: 1,
                            borderRadius: 3,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                        },
                        scales: {
                            x: {
                                ticks: { color: '#5a5a70', font: { size: 9 }, maxTicksLimit: 15 },
                                grid: { color: 'rgba(42,42,58,0.5)' },
                            },
                            y: {
                                ticks: { color: '#5a5a70', font: { size: 9 }, callback: v => '$' + v.toFixed(2) },
                                grid: { color: 'rgba(42,42,58,0.5)' },
                                beginAtZero: true,
                            }
                        }
                    }
                });
            }

            // ─── Model Chart (Doughnut) ─────────────────────
            const modelCtx = document.getElementById('modelChart');
            if (modelCtx && d.models && d.models.length > 0) {
                const colors = ['#00d4ff', '#a855f7', '#ec4899', '#22c55e', '#f59e0b', '#ef4444'];
                const labels = d.models.map(m => {
                    const short = m.model.replace(/^[^/]+\//, '').split('-').slice(0, 2).join('-');
                    return short.length > 15 ? short.slice(0, 12) + '...' : short;
                });
                const values = d.models.map(m => m.cost);

                if (modelChart) modelChart.destroy();
                modelChart = new Chart(modelCtx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: colors.slice(0, labels.length),
                            borderColor: '#16161f',
                            borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: '#8888a0', font: { size: 9 }, padding: 8 }
                            },
                            tooltip: {
                                callbacks: {
                                    label: ctx => `$${ctx.parsed.toFixed(4)}`
                                }
                            }
                        }
                    }
                });
            }
        } catch (e) { /* ignore chart errors */ }
    }

    // ─── Activity Feed ───────────────────────────────────────
    async function fetchActivity() {
        try {
            const resp = await fetch('/api/activity?limit=10');
            const data = await resp.json();
            if (!data || data.length === 0) {
                els.activityContent.innerHTML = '<div class="activity-empty">Sin actividad reciente</div>';
                return;
            }
            let html = data.map(a => `
                <div class="activity-item">
                    <div class="activity-emoji">${a.emoji}</div>
                    <div class="activity-body">
                        <div class="activity-title" style="color:${a.color}">${a.agent_name}</div>
                        <div class="activity-desc">${a.description || a.title || 'Actividad'}</div>
                        <div class="activity-meta">
                            <span>⏱ ${timeAgo(a.timestamp)}</span>
                            ${a.cost_usd > 0 ? `<span>💰 $${a.cost_usd.toFixed(4)}</span>` : ''}
                            ${a.message_count ? `<span>💬 ${a.message_count}</span>` : ''}
                        </div>
                    </div>
                </div>
            `).join('');
            els.activityContent.innerHTML = html;
        } catch (e) {
            els.activityContent.innerHTML = '<div class="activity-empty">❌ Error al cargar actividad</div>';
        }
    }

    // ─── Gateway Health ──────────────────────────────────────
    async function fetchGateway() {
        try {
            const resp = await fetch('/api/gateway');
            const data = await resp.json();
            let html = '<div class="gateway-grid">';
            for (const [aid, g] of Object.entries(data)) {
                const isOnline = g.state === 'running';
                html += `
                    <div class="gateway-card ${isOnline ? 'online' : 'offline'}">
                        <div class="gateway-header">
                            <span>${g.emoji} ${g.name}</span>
                            <span class="gateway-state-dot ${isOnline ? 'online' : 'offline'}"></span>
                        </div>
                        <div class="gateway-detail">
                            <span>Estado: <strong>${g.state}</strong></span>
                            ${g.uptime ? `<span>⏱ ${g.uptime}</span>` : ''}
                            <span>🎯 ${g.active_agents} agentes activos</span>
                        </div>
                        <div class="gateway-platforms">
                            ${Object.entries(g.platforms).map(([name, p]) => `
                                <div class="gateway-platform">
                                    <span class="platform-name">${name}</span>
                                    <span class="platform-state ${p.state === 'connected' ? 'connected' : 'disconnected'}">
                                        ${p.state === 'connected' ? '✅' : '❌'} ${p.state}
                                        ${p.error ? `<span class="platform-error">· ${p.error}</span>` : ''}
                                    </span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            html += '</div>';
            els.gatewayContent.innerHTML = html;
        } catch (e) {
            els.gatewayContent.innerHTML = '<div class="gateway-loading">❌ Error al cargar gateways</div>';
        }
    }

    // ─── Update Tool Calls from Agents ───────────────────────
    function updateToolCalls(agents) {
        for (const a of agents) {
            const el = document.getElementById(`tool-${a.id}`);
            if (el) el.textContent = a.tool_calls_24h || 0;
        }
    }

    // ─── Footer time ─────────────────────────────────────────
    function updateFooterTime() {
        els.footerTime.textContent = new Date().toLocaleString('es-MX', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    // ─── Initial Load ────────────────────────────────────────
    fetchAgents();
    fetchCredits();
    fetchHistory();
    fetchStats();
    fetchCharts();
    fetchActivity();
    fetchGateway();
    updateFooterTime();

    // ─── SSE Stream ──────────────────────────────────────────
    let eventSource;

    function connectSSE() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/agents/stream');

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                els.agentsGrid.innerHTML = data.agents.map(renderAgentCard).join('');
                els.onlineCount.querySelector('.stat-value').textContent = `${data.totals.online}/${data.totals.total}`;
                els.totalRamDisplay.querySelector('.stat-value').textContent = fmtBytes(data.totals.used_ram || 0);
                els.agentsBadge.textContent = `${data.totals.online} en línea`;
                els.lastUpdate.textContent = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

                // Alert if agent offline
                const offline = data.agents.filter(a => !a.online);
                if (offline.length > 0) {
                    const names = offline.map(a => a.name).join(', ');
                    showAlert(`⚠️ ${names} está(n) fuera de línea`, 'danger');
                }
            } catch (e) { /* ignore */ }
        };

        eventSource.onerror = () => {
            eventSource.close();
            setTimeout(connectSSE, 3000);
        };
    }

    connectSSE();

    // ─── Periodic refreshes ──────────────────────────────────
    setInterval(fetchCredits, 30000);
    setInterval(fetchHistory, 30000);
    setInterval(fetchActivity, 15000);
    setInterval(fetchGateway, 30000);
    setInterval(fetchStats, 30000);
    setInterval(updateFooterTime, 1000);
});