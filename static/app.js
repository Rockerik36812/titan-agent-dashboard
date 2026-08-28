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
        epicSessions: document.getElementById('epic-sessions'),
        epicMessages: document.getElementById('epic-messages'),
        epicTokens: document.getElementById('epic-tokens'),
        epicCost: document.getElementById('epic-cost'),
        epicDays: document.getElementById('epic-days'),
        epicScore: document.getElementById('epic-score'),
        activityContent: document.getElementById('activity-content'),
        gatewayContent: document.getElementById('gateway-content'),
        toolsGrid: document.getElementById('toolsGrid'),
        connDot: document.getElementById('connDot'),
        connLabel: document.getElementById('connLabel'),
    };

    let dailyChart = null;
    let modelChart = null;
    let lastOfflineAlert = 0;
    let hasData = false; // true after first SSE push

    // ─── Helpers ─────────────────────────────────────────────
    function fmtBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
    }

    function fmtNumber(n) {
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
        if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
        return (n || 0).toLocaleString('es-MX');
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

    function setConnStatus(online) {
        if (els.connDot) {
            els.connDot.className = `conn-dot ${online ? 'live' : 'dead'}`;
            els.connLabel.textContent = online ? 'En vivo' : 'Reconectando...';
        }
    }

    // ─── Loading overlay ─────────────────────────────────────
    function removeLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.classList.add('fade-out');
            setTimeout(() => overlay.remove(), 500);
        }
    }

    // ─── Render functions ────────────────────────────────────
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
                    <span class="agent-gateway">${agent.online ? '✅ up' : '❌ down'}</span>
                </div>
            </div>
        `;
    }

    function updateAll(data) {
        // ── Timestamp ──
        if (data.ts) {
            els.lastUpdate.textContent = new Date(data.ts * 1000).toLocaleTimeString('es-MX', {
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }

        // ── Agents ──
        if (data.agents) {
            els.agentsGrid.innerHTML = data.agents.map(renderAgentCard).join('');
            const online = data.totals?.online ?? data.agents.filter(a => a.online).length;
            const total = data.totals?.total ?? data.agents.length;
            const onlineEl = els.onlineCount.querySelector('.stat-value');
            if (onlineEl) onlineEl.textContent = `${online}/${total}`;
            const ramEl = els.totalRamDisplay.querySelector('.stat-value');
            if (ramEl) ramEl.textContent = fmtBytes(data.totals?.used_ram || 0);
            els.agentsBadge.textContent = `${online} en línea`;

            const now = Date.now();
            data.agents.forEach(a => {
                if (!a.online && now - lastOfflineAlert > 60000) {
                    lastOfflineAlert = now;
                    showAlert(`⚠️ ${a.name} está fuera de línea`, 'danger');
                }
            });
        }

        // ── Credits ──
        if (data.credits) {
            const c = data.credits;
            els.creditsTotal.textContent = `$${c.total.toFixed(2)}`;
            els.creditsUsed.textContent = `$${c.used.toFixed(2)}`;
            els.creditsRemaining.textContent = `$${c.remaining.toFixed(2)}`;
            const pct = c.percent_used || 0;
            els.creditsPct.textContent = `${pct}%`;
            els.creditsBar.style.width = `${Math.min(pct, 100)}%`;
            els.creditsBar.style.background = pct > 75 ? 'var(--accent-red)' : pct > 50 ? 'var(--accent-orange)' : 'linear-gradient(90deg, var(--accent-green), var(--accent-orange))';

            if (c.remaining < 5 && c.remaining > 0) {
                showAlert(`⚠️ OpenRouter bajo: $${c.remaining.toFixed(2)} restantes`, 'warning');
            }
        }

        // ── Stats ──
        if (data.stats) {
            const s = data.stats;
            els.epicSessions.textContent = fmtNumber(s.sessions);
            els.epicMessages.textContent = fmtNumber(s.messages);
            els.epicTokens.textContent = fmtNumber(s.tokens);
            els.epicCost.textContent = `$${s.cost.toFixed(2)}`;
            els.epicDays.textContent = s.days_active;
            els.epicScore.textContent = s.titan_score || 0;
            const l24 = els.last24hDisplay.querySelector('.stat-value');
            if (l24) l24.textContent = s.sessions_24h;
        }

        // ── Analytics (Charts) ──
        if (data.analytics && data.analytics.daily_cost) {
            const d = data.analytics;
            if (d.week_cost > 0) {
                els.weekCostBadge.textContent = `📅 ${d.total_sessions} sesiones · $${d.week_cost.toFixed(2)}/semana`;
                els.weekCostBadge.style.display = 'inline-block';
            }

            const dailyCtx = document.getElementById('dailyCostChart');
            if (dailyCtx && d.daily_cost && d.daily_cost.length > 0) {
                const days = d.daily_cost.map(x => x.day.slice(5));
                const costs = d.daily_cost.map(x => x.cost);
                if (dailyChart) {
                    dailyChart.data.labels = days;
                    dailyChart.data.datasets[0].data = costs;
                    dailyChart.data.datasets[0].backgroundColor = costs.map(c => c > 0.5 ? 'rgba(239, 68, 68, 0.6)' : c > 0.1 ? 'rgba(245, 158, 11, 0.6)' : 'rgba(34, 197, 94, 0.6)');
                    dailyChart.data.datasets[0].borderColor = costs.map(c => c > 0.5 ? '#ef4444' : c > 0.1 ? '#f59e0b' : '#22c55e');
                    dailyChart.update('none');
                } else {
                    dailyChart = new Chart(dailyCtx, {
                        type: 'bar',
                        data: {
                            labels: days,
                            datasets: [{
                                label: 'Costo ($)', data: costs,
                                backgroundColor: costs.map(c => c > 0.5 ? 'rgba(239, 68, 68, 0.6)' : c > 0.1 ? 'rgba(245, 158, 11, 0.6)' : 'rgba(34, 197, 94, 0.6)'),
                                borderColor: costs.map(c => c > 0.5 ? '#ef4444' : c > 0.1 ? '#f59e0b' : '#22c55e'),
                                borderWidth: 1, borderRadius: 3,
                            }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: {
                                x: { ticks: { color: '#5a5a70', font: { size: 9 }, maxTicksLimit: 15 }, grid: { color: 'rgba(42,42,58,0.5)' } },
                                y: { ticks: { color: '#5a5a70', font: { size: 9 }, callback: v => '$' + v.toFixed(2) }, grid: { color: 'rgba(42,42,58,0.5)' }, beginAtZero: true }
                            }
                        }
                    });
                }
            }

            const modelCtx = document.getElementById('modelChart');
            if (modelCtx && d.models && d.models.length > 0) {
                const colors = ['#00d4ff', '#a855f7', '#ec4899', '#22c55e', '#f59e0b', '#ef4444'];
                const labels = d.models.map(m => {
                    const short = m.model.replace(/^[^/]+\//, '').split('-').slice(0, 2).join('-');
                    return short.length > 15 ? short.slice(0, 12) + '...' : short;
                });
                const values = d.models.map(m => m.cost);
                if (modelChart) {
                    modelChart.data.labels = labels;
                    modelChart.data.datasets[0].data = values;
                    modelChart.update('none');
                } else {
                    modelChart = new Chart(modelCtx, {
                        type: 'doughnut',
                        data: {
                            labels: labels,
                            datasets: [{
                                data: values,
                                backgroundColor: colors.slice(0, labels.length),
                                borderColor: '#16161f', borderWidth: 2,
                            }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom', labels: { color: '#8888a0', font: { size: 9 }, padding: 8 } },
                                tooltip: { callbacks: { label: ctx => `$${ctx.parsed.toFixed(4)}` } }
                            }
                        }
                    });
                }
            }
        }

        // ── Activity ──
        if (data.activity) {
            if (data.activity.length === 0) {
                els.activityContent.innerHTML = '<div class="activity-empty">Sin actividad reciente</div>';
            } else {
                els.activityContent.innerHTML = data.activity.slice(0, 10).map(a => `
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
            }
        }

        // ── Gateway ──
        if (data.gateways) {
            let html = '<div class="gateway-grid">';
            for (const [aid, g] of Object.entries(data.gateways)) {
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
        }

        // ── History ──
        if (data.history) {
            let html = '';
            for (const [agentId, agentData] of Object.entries(data.history)) {
                const sessions = agentData.sessions || [];
                html += `<div class="agent-timeline">`;
                html += `<div class="timeline-header" style="color: ${agentData.color}">${agentData.emoji} ${agentData.name}</div>`;
                if (sessions.length === 0) {
                    html += `<div class="timeline-items"><div class="timeline-empty">Sin sesiones</div></div>`;
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
                                </div>
                            </div>
                        `;
                    }
                    html += `</div>`;
                }
                html += `</div>`;
            }
            els.historyContent.innerHTML = html;
        }
    }

    function showAlert(message, type = 'warning') {
        els.alertBanner.className = `alert-banner ${type}`;
        els.alertMessage.textContent = message;
        els.alertBanner.classList.remove('hidden');
        setTimeout(() => els.alertBanner.classList.add('hidden'), 8000);
    }

    // ─── SSE Stream (real-time) ───────────────────────────────
    let eventSource = null;
    let reconnectTimer = null;

    function connectSSE() {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }

        eventSource = new EventSource('/api/stream');

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    console.warn('SSE error:', data.error);
                    return;
                }
                if (!hasData) {
                    hasData = true;
                    removeLoading();
                }
                setConnStatus(true);
                updateAll(data);
            } catch (e) { /* ignore parse errors */ }
        };

        eventSource.onerror = () => {
            setConnStatus(false);
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
            reconnectTimer = setTimeout(connectSSE, 2000);
        };
    }

    // ─── Footer time (local clock, never reloads) ────────────
    function tickClock() {
        const now = new Date();
        els.footerTime.textContent = now.toLocaleString('es-MX', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        requestAnimationFrame(() => setTimeout(tickClock, 1000));
    }

    // ─── Bootstrap ───────────────────────────────────────────
    connectSSE();
    tickClock();
});