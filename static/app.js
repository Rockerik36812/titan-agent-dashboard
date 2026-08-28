document.addEventListener('DOMContentLoaded', () => {
    const agentsGrid = document.getElementById('agentsGrid');
    const onlineCount = document.getElementById('onlineCount');
    const totalRamDisplay = document.getElementById('totalRamDisplay');
    const lastUpdate = document.getElementById('lastUpdate');
    const footerTime = document.getElementById('footer-time');
    const creditsTotal = document.getElementById('credits-total');
    const creditsUsed = document.getElementById('credits-used');
    const creditsRemaining = document.getElementById('credits-remaining');
    const creditsPct = document.getElementById('credits-pct');
    const creditsBar = document.getElementById('credits-bar');
    const historyContent = document.getElementById('history-content');
    const agentsBadge = document.getElementById('agents-badge');

    function fmtBytes(bytes) {
        if (bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
    }

    function timeAgo(timestamp) {
        if (!timestamp) return 'desconocido';
        const now = Date.now() / 1000;
        let diff = now - timestamp;
        if (diff < 0 && typeof timestamp === 'number' && timestamp > 1e15) {
            diff = now - (timestamp / 1000);
        }
        if (diff < 0) diff = 0;
        if (diff < 60) return 'hace un momento';
        if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
        if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
        return `hace ${Math.floor(diff / 86400)}d`;
    }

    function fmtDate(timestamp) {
        if (!timestamp) return '—';
        const d = new Date(timestamp * 1000);
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

    // Render agent card HTML
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

    // Fetch and render agents
    async function fetchAgents() {
        try {
            const resp = await fetch('/api/agents');
            const data = await resp.json();

            agentsGrid.innerHTML = data.agents.map(renderAgentCard).join('');
            onlineCount.querySelector('.stat-value').textContent = `${data.totals.online}/${data.totals.total}`;
            totalRamDisplay.querySelector('.stat-value').textContent = fmtBytes(data.totals.used_ram || 0);
            agentsBadge.textContent = `${data.totals.online} en línea`;
            lastUpdate.textContent = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch (e) {
            agentsGrid.innerHTML = '<div class="agent-card" style="grid-column:1/-1;text-align:center;padding:2rem">❌ Error al cargar agentes</div>';
        }
    }

    // Fetch credits
    async function fetchCredits() {
        try {
            const resp = await fetch('/api/credits');
            const data = await resp.json();

            creditsTotal.textContent = `$${data.total.toFixed(2)}`;
            creditsUsed.textContent = `$${data.used.toFixed(2)}`;
            creditsRemaining.textContent = `$${data.remaining.toFixed(2)}`;

            const pct = data.percent_used || 0;
            creditsPct.textContent = `${pct}%`;
            creditsBar.style.width = `${Math.min(pct, 100)}%`;

            // Color the bar based on consumption
            const barColor = pct > 75 ? 'var(--accent-red)' : pct > 50 ? 'var(--accent-orange)' : 'linear-gradient(90deg, var(--accent-green), var(--accent-orange))';
            creditsBar.style.background = barColor;
        } catch (e) {
            creditsTotal.textContent = '—';
            creditsUsed.textContent = '—';
            creditsRemaining.textContent = '—';
        }
    }

    // Fetch history
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

            historyContent.innerHTML = html;
        } catch (e) {
            historyContent.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:2rem">❌ Error al cargar historial</div>';
        }
    }

    // Update footer time
    function updateFooterTime() {
        footerTime.textContent = new Date().toLocaleString('es-MX', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    // Initial fetch
    fetchAgents();
    fetchCredits();
    fetchHistory();
    updateFooterTime();

    // SSE stream for agent data
    let eventSource;

    function connectSSE() {
        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/agents/stream');

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                agentsGrid.innerHTML = data.agents.map(renderAgentCard).join('');
                onlineCount.querySelector('.stat-value').textContent = `${data.totals.online}/${data.totals.total}`;
                totalRamDisplay.querySelector('.stat-value').textContent = fmtBytes(data.totals.used_ram || 0);
                agentsBadge.textContent = `${data.totals.online} en línea`;
                lastUpdate.textContent = new Date().toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            } catch (e) { /* ignore parse errors during reconnect */ }
        };

        eventSource.onerror = () => {
            eventSource.close();
            setTimeout(connectSSE, 3000);
        };
    }

    connectSSE();

    // Periodic refresh for credits and history (every 30s)
    setInterval(fetchCredits, 30000);
    setInterval(fetchHistory, 30000);
    setInterval(updateFooterTime, 1000);
});