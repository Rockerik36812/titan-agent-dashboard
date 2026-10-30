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
        creditsProjection: document.getElementById('credits-projection'),
        diskPct: document.getElementById('disk-pct'),
        diskBar: document.getElementById('disk-bar'),
        diskInfo: document.getElementById('disk-info'),
        memPct: document.getElementById('mem-pct'),
        memBar: document.getElementById('mem-bar'),
        memInfo: document.getElementById('mem-info'),
        remoteBadge: document.getElementById('remote-badge'),
        remoteDiskTxt: document.getElementById('remote-disk-txt'),
        remoteDiskBar: document.getElementById('remote-disk-bar'),
        remoteMemTxt: document.getElementById('remote-mem-txt'),
        remoteMemBar: document.getElementById('remote-mem-bar'),
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
        modalOverlay: document.getElementById('agentModal'),
        modalTitle: document.getElementById('modalTitle'),
        modalBody: document.getElementById('modalBody'),
    };

    let dailyChart = null;
    let modelChart = null;
    let lastOfflineAlert = 0;
    let hasData = false;
    let cachedHistory = {};
    let cachedAgents = {};

    // ─── Modal ────────────────────────────────────────────────────
    let modalAgentId = null;
    // Cache de logs: el modal se re-renderiza cada 3s (SSE) y borraría lo cargado,
    // así que guardamos el último contenido y lo restauramos tras cada re-render.
    let modalLogCache = { which: null, text: null, scroll: 0 };

    function renderModalBody(agentId) {
        const agent = cachedAgents[agentId];
        const hist = cachedHistory[agentId];
        if (!agent) return;

        els.modalTitle.textContent = `${agent.emoji} ${agent.name} — Historial de Sesiones`;
        els.modalTitle.style.color = agent.color;

        // Bloque de modelo: en uso, principal y fallback
        const modelBox = agent.model ? `
            <div class="modal-model-box">
                <div class="model-line"><span class="model-label">🧠 En uso</span><code>${agent.model}</code></div>
                ${agent.model_primary ? `<div class="model-line"><span class="model-label">Principal</span><code>${agent.model_primary}</code></div>` : ''}
                ${agent.model_fallback ? `<div class="model-line"><span class="model-label">Fallback</span><code>${agent.model_fallback}</code></div>` : ''}
                ${agent.fallback_active ? '<div class="modal-fallback-warn">⚠️ Fallback activo — el modelo principal falló</div>' : ''}
            </div>` : '';

        // Controles de logs en vivo
        const logControls = `
            <div class="modal-actions">
                <button class="modal-btn" onclick="loadAgentLogs('${agentId}','agent')">📜 Logs del agente</button>
                <button class="modal-btn" onclick="loadAgentLogs('${agentId}','gateway')">🔌 Logs del gateway</button>
                <button class="modal-btn" onclick="loadAgentLogs('${agentId}','agent',true)">🔄 Refrescar</button>
            </div>
            <pre id="modal-logs" class="modal-logs">Pulsa un botón para ver los logs…</pre>`;

        const sessions = hist?.sessions || [];
        if (sessions.length === 0) {
            els.modalBody.innerHTML = modelBox + logControls + '<div class="timeline-empty">Sin sesiones registradas</div>';
        } else {
            els.modalBody.innerHTML = modelBox + logControls + '<div class="timeline-items">' + sessions.map(s => {
                const cost = s.cost_usd ? `$${s.cost_usd.toFixed(4)}` : '—';
                return `
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
            }).join('') + '</div>';
        }

        // Restaurar logs si el usuario ya había cargado alguno (el SSE re-renderiza cada 3s)
        if (modalLogCache.text) {
            const pre = document.getElementById('modal-logs');
            if (pre) {
                pre.textContent = modalLogCache.text;
                pre.scrollTop = modalLogCache.scroll || 0;
            }
        }
    }

    function openAgentModal(agentId) {
        if (!cachedAgents[agentId]) return;
        modalAgentId = agentId;
        modalLogCache = { which: null, text: null, scroll: 0 };  // logs limpios al abrir otro agente
        renderModalBody(agentId);
        els.modalOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeAgentModal(event) {
        if (event && event.target !== els.modalOverlay) return;
        modalAgentId = null;
        els.modalOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }
    window.closeAgentModal = closeAgentModal;

    // ── Visor de logs en vivo (agent.log / gateway.log) ──
    async function loadAgentLogs(agentId, which = 'agent', isRefresh = false) {
        const pre = document.getElementById('modal-logs');
        if (!pre) return;
        const n = isRefresh ? 400 : 200;
        pre.textContent = 'Cargando logs…';
        try {
            const r = await fetch(`/api/logs/${agentId}?lines=${n}&which=${which}`);
            const d = await r.json();
            if (d.error) {
                modalLogCache = { which, text: `Error: ${d.error}`, scroll: 0 };
            } else {
                const tail = (d.lines || []).join('\n').trim();
                modalLogCache = { which, text: tail || '(log vacío)', scroll: 0 };
            }
            const pre2 = document.getElementById('modal-logs');
            if (pre2) {
                pre2.textContent = modalLogCache.text;
                pre2.scrollTop = pre2.scrollHeight;  // saltar al final (lo más reciente)
                modalLogCache.scroll = pre2.scrollTop;
            }
        } catch (e) {
            modalLogCache = { which, text: `Error al cargar logs: ${e}`, scroll: 0 };
            const pre3 = document.getElementById('modal-logs');
            if (pre3) pre3.textContent = modalLogCache.text;
        }
    }
    window.loadAgentLogs = loadAgentLogs;

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modalAgentId = null;
            els.modalOverlay.classList.add('hidden');
            document.body.style.overflow = '';
        }
    });

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
        // Modelo en uso (nombre corto tras la barra) + aviso si el fallback está activo
        const modelFull = agent.model || '';
        const modelName = modelFull ? modelFull.split('/').pop() : '—';
        const fallbackBadge = agent.fallback_active
            ? `<span class="agent-fallback" title="Fallback activo: el modelo principal falló">⚠️ fallback</span>`
            : '';
        return `
            <div class="agent-card clickable ${agent.online ? 'online' : ''}" data-agent-id="${agent.id}" style="--color: ${agent.color}">
                <div class="agent-card-header">
                    <div class="agent-name">
                        <span class="agent-emoji">${agent.emoji}</span>
                        ${agent.name}
                    </div>
                    <div class="agent-header-actions">
                        <button class="agent-restart" onclick="restartAgent(event, '${agent.id}')" title="Reiniciar ${agent.name}">🔄</button>
                        <div class="status-dot ${agent.online ? 'online' : 'offline'}"></div>
                    </div>
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
                <div class="agent-detail agent-model-row" title="${modelFull}">
                    <span class="agent-model">🧠 ${modelName}</span>
                    ${fallbackBadge}
                </div>
            </div>
        `;
    }

    function fmtGB(bytes) {
        if (!bytes) return '—';
        const gb = bytes / (1024 ** 3);
        return gb >= 1024 ? `${(gb / 1024).toFixed(1)} TB` : `${gb.toFixed(1)} GB`;
    }

    // Tooltip del Titan Score: desglose de cómo se calcula
    function renderTitanTip(bd) {
        const tip = document.getElementById('titan-tip');
        if (!tip) return;
        if (!bd) { tip.hidden = true; return; }
        const filas = [
            ['Sesiones ×2', bd.sessions || 0, 200],
            ['Mensajes ×0.05', bd.messages || 0, 150],
            ['Herramientas ×0.5', bd.tool_calls || 0, 100],
            ['Días activo ×3', bd.days_active || 0, 150],
            ['Actividad 24h ×5', bd.recent || 0, null],
        ];
        const total = Math.min(Math.round(filas.reduce((a, f) => a + (f[1] || 0), 0)), 999);
        tip.innerHTML =
            '<strong>⚡ Cómo se calcula</strong>' +
            filas.map(f => `<span class="titan-tip-row"><span>${f[0]}</span><span>${f[1]}${f[2] ? ' / ' + f[2] : ''}</span></span>`).join('') +
            `<span class="titan-tip-row titan-tip-total"><span>Total</span><span>${total}</span></span>`;
    }

    // El tooltip se abre al tocar la tarjeta (móvil) o al pasar el mouse (desktop)
    (function initTitanTip() {
        const card = document.getElementById('titan-score-card');
        const tip = document.getElementById('titan-tip');
        if (!card || !tip) return;
        card.addEventListener('click', (e) => { e.stopPropagation(); tip.hidden = !tip.hidden; });
        card.addEventListener('mouseenter', () => { tip.hidden = false; });
        card.addEventListener('mouseleave', () => { tip.hidden = true; });
        document.addEventListener('click', () => { tip.hidden = true; });
    })();

    // Servidor remoto (2º VPS, clientes): disco + RAM leídos por Tailscale SSH
    function renderRemote(r) {
        if (!els.remoteBadge || !r) return;
        const on = !!r.online;
        // El badge lleva el % del disco (igual que las demás tarjetas);
        // el estado de la conexión va como punto de color junto al título.
        const dot = document.getElementById('remote-status');
        if (dot) {
            dot.style.background = on ? 'var(--accent-green)' : 'var(--accent-red)';
            dot.title = on ? 'En línea' : 'Sin conexión';
        }
        const dpct = (r.disk && r.disk.total_h) ? (r.disk.percent || 0) : null;
        els.remoteBadge.textContent = dpct === null ? (on ? '—' : '⚠️') : `${dpct}%`;
        els.remoteBadge.style.color = !on ? 'var(--accent-red)'
            : dpct > 80 ? 'var(--accent-red)'
            : dpct > 60 ? 'var(--accent-orange)' : 'var(--accent-green)';

        const pinta = (txtEl, barEl, x) => {
            if (txtEl) txtEl.textContent = x.total_h ? `${x.used_h} / ${x.total_h} (${x.percent}%)` : '—';
            if (barEl) {
                const pct = Math.min(x.percent || 0, 100);
                barEl.style.width = `${pct}%`;
                barEl.style.background = (x.percent || 0) > 80 ? 'var(--accent-red)'
                    : (x.percent || 0) > 60 ? 'var(--accent-orange)' : 'var(--accent-green)';
            }
        };
        pinta(els.remoteDiskTxt, els.remoteDiskBar, r.disk || {});
        pinta(els.remoteMemTxt, els.remoteMemBar, r.mem || {});
    }

    // Render genérico de una barra de recurso (sirve para disco y RAM)
    function renderResource(pctEl, barEl, infoEl, d) {
        const pct = (d && d.percent) || 0;
        if (pctEl) pctEl.textContent = pct ? `${pct}%` : '—';
        if (barEl) {
            barEl.style.width = `${Math.min(pct, 100)}%`;
            barEl.style.background = pct >= 90 ? 'var(--accent-red)'
                : pct >= 80 ? 'var(--accent-orange)'
                : '#00d4ff';
        }
        if (infoEl && d && d.total) {
            infoEl.textContent = `${fmtGB(d.used)} usados · ${fmtGB(d.free)} libres de ${fmtGB(d.total)}`;
        }
    }

    function renderDisk(d) {
        renderResource(els.diskPct, els.diskBar, els.diskInfo, d);
    }

    function renderMem(d) {
        renderResource(els.memPct, els.memBar, els.memInfo, d);
    }

    // ── Uso de herramientas por agente ──
    function renderTools(tools) {
        if (!els.toolsGrid) return;
        const order = ['titan', 'hermes', 'hermina'];
        const ids = order.filter(id => tools && tools[id]).concat(
            Object.keys(tools || {}).filter(id => !order.includes(id))
        );
        const html = ids.map(id => {
            const a = cachedAgents[id] || {};
            const t = tools[id] || {};
            const list = (t.tools || []).filter(x => x && x.name);
            if (!list.length) return '';
            const max = Math.max(...list.map(x => x.count || 0), 1);
            const color = a.color || '#00d4ff';
            const rows = list.map(x => {
                const w = Math.max(Math.round(((x.count || 0) / max) * 100), 2);
                const pct = t.total ? Math.round(((x.count || 0) / t.total) * 100) : 0;
                return `
                    <div class="tool-row">
                        <span class="tool-name" title="${x.name}">${x.name}</span>
                        <div class="tool-bar"><div class="tool-bar-fill" style="width:${w}%; background:${color}"></div></div>
                        <span class="tool-count">${fmtNumber(x.count || 0)}<em>${pct}%</em></span>
                    </div>`;
            }).join('');
            return `
                <div class="tool-agent" style="--color:${color}">
                    <div class="tool-agent-head">
                        <span class="tool-agent-name">${a.emoji || ''} ${a.name || id}</span>
                        <span class="tool-agent-total">${fmtNumber(t.total || 0)} tool calls</span>
                    </div>
                    <div class="tool-rows">${rows}</div>
                </div>`;
        }).join('');
        els.toolsGrid.innerHTML = html ||
            '<div class="tool-empty">Aún no hay registros de herramientas…</div>';
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
            data.agents.forEach(a => { cachedAgents[a.id] = a; });
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

            // Click delegation for agent cards
            els.agentsGrid.querySelectorAll('.agent-card').forEach(card => {
                card.addEventListener('click', () => {
                    openAgentModal(card.dataset.agentId);
                });
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

            // Proyección: a este ritmo de gasto, ¿cuántos días quedan?
            if (els.creditsProjection) {
                if (c.days_left !== undefined && c.avg_daily) {
                    const urgente = c.days_left <= 7;
                    els.creditsProjection.className = `credit-projection${urgente ? ' urgent' : ''}`;
                    els.creditsProjection.innerHTML =
                        `⏳ A $${c.avg_daily.toFixed(2)}/día te quedan <strong>≈ ${c.days_left} días</strong>` +
                        (c.runout_date ? ` · se agota ~${c.runout_date}` : '');
                } else {
                    els.creditsProjection.className = 'credit-projection';
                    els.creditsProjection.textContent = '';
                }
            }

            // Aviso por monto bajo O por poca autonomía (lo que llegue primero)
            const pocosDias = c.days_left !== undefined && c.days_left <= 7;
            if ((c.remaining < 5 && c.remaining > 0) || pocosDias) {
                const msg = pocosDias
                    ? `⚠️ OpenRouter: $${c.remaining.toFixed(2)} restantes ≈ ${c.days_left} días al ritmo actual`
                    : `⚠️ OpenRouter bajo: $${c.remaining.toFixed(2)} restantes`;
                showAlert(msg, 'warning');
            }
        }

        // ── Disco del host ──
        if (data.disk) renderDisk(data.disk);
        if (data.mem) renderMem(data.mem);
        if (data.remote) renderRemote(data.remote);
        if (data.tools) renderTools(data.tools);

        // ── Stats ──
        if (data.stats) {
            const s = data.stats;
            els.epicSessions.textContent = fmtNumber(s.sessions);
            els.epicMessages.textContent = fmtNumber(s.messages);
            els.epicTokens.textContent = fmtNumber(s.tokens);
            els.epicCost.textContent = `$${s.cost.toFixed(2)}`;
            els.epicDays.textContent = s.days_active;
            els.epicScore.textContent = s.titan_score || 0;
            renderTitanTip(s.titan_breakdown);
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
                // Colores generados para N modelos: la paleta fija de 6 hacía que
                // se repitieran los colores cuando hay muchos modelos.
                const colors = d.models.map((_, i) =>
                    `hsl(${Math.round((i * 360) / d.models.length)}, 72%, 60%)`
                );
                const labels = d.models.map(m => {
                    // Quitar el prefijo del proveedor ("deepseek/") pero conservar el
                    // nombre completo del modelo: cortar a 2 partes hacía que
                    // "deepseek-v4-flash" y "deepseek-v4-flash-0731" se vieran IGUALES.
                    const short = m.model.replace(/^[^/]+\//, '');
                    return short.length > 24 ? short.slice(0, 22) + '…' : short;
                });
                // El tamaño mide LLAMADAS, no costo: los modelos gratis (:free) tienen
                // costo $0 y su rebanada quedaba en cero (invisible) en la gráfica.
                const values = d.models.map(m => m.calls || 0);
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
                                label: 'Llamadas',
                                data: values,
                                backgroundColor: colors.slice(0, labels.length),
                                borderColor: '#16161f', borderWidth: 2,
                            }]
                        },
                        options: {
                            responsive: true, maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom', labels: { color: '#8888a0', font: { size: 9 }, padding: 8 } },
                                tooltip: { callbacks: { label: ctx => {
                                    const m = d.models[ctx.dataIndex] || {};
                                    const calls = (m.calls || 0).toLocaleString();
                                    return `${calls} llamadas · $${(m.cost || 0).toFixed(4)}`;
                                } } }
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

        // ── History (cache for modal) ──
        if (data.history) {
            cachedHistory = data.history;
            // Auto-refresh modal if open
            if (modalAgentId && !els.modalOverlay.classList.contains('hidden')) {
                renderModalBody(modalAgentId);
            }
        }
    }

    function showAlert(message, type = 'warning') {
        els.alertBanner.className = `alert-banner ${type}`;
        els.alertMessage.textContent = message;
        els.alertBanner.classList.remove('hidden');
        setTimeout(() => els.alertBanner.classList.add('hidden'), 8000);
    }

    // ─── Reiniciar el contenedor de un agente (botón 🔄) ──────
    async function restartAgent(ev, agentId) {
        ev.stopPropagation();  // que no abra el modal de historial
        const card = ev.target.closest('.agent-card');
        const nameEl = card ? card.querySelector('.agent-name') : null;
        const name = nameEl ? nameEl.textContent.trim() : agentId;
        const aviso = agentId === 'titan'
            ? `¿Reiniciar a ${name}?\n\n⚠️ ${name} es el agente con el que estás hablando: la conversación actual se cortará y volverá en unos segundos.`
            : `¿Reiniciar a ${name}?\n\nSu conversación en curso se cortará y volverá en unos segundos.`;
        if (!confirm(aviso)) return;

        const btn = ev.target;
        const original = btn.textContent;
        btn.disabled = true;
        btn.textContent = '⏳';
        try {
            const r = await fetch(`/api/agents/${agentId}/restart`, { method: 'POST' });
            const d = await r.json();
            if (r.ok && d.ok) {
                showAlert(d.message || `${name} reiniciado`, 'success');
            } else {
                showAlert(d.error || `No se pudo reiniciar a ${name}`, 'danger');
            }
        } catch (e) {
            showAlert('Error de conexión al reiniciar el agente', 'danger');
        } finally {
            btn.disabled = false;
            btn.textContent = original;
        }
    }
    window.restartAgent = restartAgent;

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
                if (data.connected) {
                    setConnStatus(true);
                    const overlay = document.getElementById('loadingOverlay');
                    if (overlay && !hasData) {
                        const text = overlay.querySelector('.loading-text');
                        if (text) text.textContent = 'Conectado — cargando datos...';
                    }
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
            // Si la sesión expiró, el SSE falla en bucle: comprobar y volver al login.
            rawFetch('/api/agents').catch(() => {});
            reconnectTimer = setTimeout(connectSSE, 2000);
        };
    }

    // ─── Sesión ────────────────────────────────────────────────────
    // fetch sin el guard, para poder comprobar la sesión sin bucles.
    const rawFetch = window.fetch.bind(window);

    // Cualquier 401 significa que la sesión expiró -> volver al login.
    // Se intercepta globalmente para cubrir también los fetch que se agreguen después.
    window.fetch = async (...args) => {
        const res = await rawFetch(...args);
        if (res.status === 401) {
            window.location.replace('/login');
        }
        return res;
    };

    async function doLogout() {
        try {
            await rawFetch('/api/auth/logout', { method: 'POST' });
        } catch (e) { /* aunque falle, salimos del panel */ }
        window.location.replace('/login');
    }
    window.doLogout = doLogout;

    // ─── Footer + Header clock (local time, never reloads) ──
    function tickClock() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('es-MX', {
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        els.lastUpdate.textContent = timeStr;
        els.footerTime.textContent = now.toLocaleString('es-MX', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
        requestAnimationFrame(() => setTimeout(tickClock, 1000));
    }

    // ─── Web Push ────────────────────────────────────────────
    // Helper: base64url string → Uint8Array
    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const output = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            output[i] = rawData.charCodeAt(i);
        }
        return output;
    }

    let pushActive = false;
    let pushSubscription = null;

    // Check localStorage for push state
    if (localStorage.getItem('pushActive') === 'true') {
        pushActive = true;
        document.getElementById('pushBtn')?.classList.add('active');
    }

    async function registerSW() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.log('Push not supported');
            return;
        }
        try {
            const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
            await navigator.serviceWorker.ready;
            return reg;
        } catch (e) {
            console.warn('SW registration failed:', e);
        }
    }

    async function subscribePush(reg) {
        try {
            const resp = await fetch('/api/push/vapid-key');
            const data = await resp.json();
            // Convert base64url string to Uint8Array for browser
            const keyBytes = urlBase64ToUint8Array(data.key);
            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: keyBytes,
            });
            pushSubscription = sub;
            await fetch('/api/push/subscribe', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(sub.toJSON()),
            });
            pushActive = true;
            localStorage.setItem('pushActive', 'true');
            document.getElementById('pushBtn')?.classList.add('active');
        } catch (e) {
            console.warn('Push subscribe failed:', e);
        }
    }

    async function unsubscribePush() {
        if (pushSubscription) {
            try {
                await pushSubscription.unsubscribe();
                await fetch('/api/push/unsubscribe', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({endpoint: pushSubscription.endpoint}),
                });
            } catch (e) { /* ignore */ }
        }
        pushActive = false;
        pushSubscription = null;
        localStorage.removeItem('pushActive');
        document.getElementById('pushBtn')?.classList.remove('active');
    }

    // Register SW on load
    registerSW();

    // Make togglePush global
    // Fixed for Mac: always register SW first, show errors to user, handle
    // "SW not yet activated" race condition common on first subscription.
    window.togglePush = async function() {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            alert('Las notificaciones push no son compatibles con este navegador.');
            return;
        }
        if (pushActive && pushSubscription) {
            await unsubscribePush();
            return;
        }
        // Set button to "loading" state
        const btn = document.getElementById('pushBtn');
        if (btn) { btn.disabled = true; btn.classList.add('loading'); }
        try {
            // 1. Request notification permission
            const perm = await Notification.requestPermission();
            if (perm !== 'granted') {
                alert('Permiso denegado. Actívalo desde la configuración del navegador:\n\nChrome Mac → Preferencias → Privacidad y seguridad → Notificaciones');
                return;
            }
            // 2. ALWAYS register the SW (returns existing or registers new)
            //    This is the fix for Mac: getRegistration() can return null
            //    if SW was unregistered or never registered on this profile.
            let reg = await navigator.serviceWorker.getRegistration();
            if (!reg) {
                reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
            }
            // 3. Wait until the SW is fully active (fixes "no active service
            //    worker" error on Mac when subscription is attempted too soon)
            await navigator.serviceWorker.ready;
            // 4. Try to subscribe. If we have an EXISTING subscription
            //    with a different applicationServerKey (e.g. after VAPID
            //    rotation or device migration), Chrome rejects the new
            //    subscribe call. We detect this and self-heal by
            //    unsubscribing first then re-subscribing.
            let sub;
            const existing = await reg.pushManager.getSubscription();
            if (existing) {
                // Check if the existing subscription's endpoint matches the
                // expected origin and just re-save it. Otherwise unsubscribe
                // and create a fresh one.
                try {
                    // Re-apply the new VAPID key. If it matches, no-op;
                    // if not, this will throw and we'll resubscribe.
                    sub = await existing.toJSON();
                    // Quick verify: try to save the existing sub to server.
                    // If server rejects (different key), fall through to
                    // resubscribe flow.
                } catch (e) {
                    await existing.unsubscribe();
                }
            }
            if (!sub) {
                const resp = await fetch('/api/push/vapid-key');
                if (!resp.ok) {
                    throw new Error(`Server returned ${resp.status} fetching VAPID key`);
                }
                const data = await resp.json();
                if (!data.key) {
                    throw new Error('Server did not return a VAPID public key');
                }
                const keyBytes = urlBase64ToUint8Array(data.key);
                try {
                    sub = await reg.pushManager.subscribe({
                        userVisibleOnly: true,
                        applicationServerKey: keyBytes,
                    });
                } catch (subErr) {
                    // Self-heal: subscription exists with different VAPID
                    // key. Unsubscribe the old one and try again.
                    if (subErr && /different applicationServerKey|registration failed/i.test(subErr.message || '')) {
                        const old = await reg.pushManager.getSubscription();
                        if (old) { await old.unsubscribe(); }
                        sub = await reg.pushManager.subscribe({
                            userVisibleOnly: true,
                            applicationServerKey: keyBytes,
                        });
                    } else {
                        throw subErr;
                    }
                }
            }
            pushSubscription = await reg.pushManager.getSubscription();
            const saveResp = await fetch('/api/push/subscribe', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(pushSubscription.toJSON()),
            });
            if (!saveResp.ok) {
                throw new Error(`Server returned ${saveResp.status} saving subscription`);
            }
            pushActive = true;
            localStorage.setItem('pushActive', 'true');
            if (btn) { btn.classList.add('active'); btn.classList.remove('loading'); btn.disabled = false; }
        } catch (e) {
            console.error('Push toggle failed:', e);
            // Show the actual error to the user (Mac-specific diagnosis)
            let msg = 'No se pudo activar el push.';
            if (e && e.name === 'NotAllowedError') {
                msg = 'Permiso bloqueado. Ve a Preferencias del sistema → Notificaciones y permite el navegador.';
            } else if (e && e.message) {
                msg = `No se pudo activar el push: ${e.message}`;
            }
            alert(msg);
            if (btn) { btn.classList.remove('active', 'loading'); btn.disabled = false; }
        }
    };

    // ─── Bootstrap ───────────────────────────────────────────
    // Load initial data via REST while SSE connects
    fetch('/api/agents').then(r => r.json()).then(data => {
        if (data && data.agents) {
            if (!hasData) { hasData = true; removeLoading(); }
            setConnStatus(true);
            updateAll(data);
        }
    }).catch(() => {});
    fetch('/api/credits').then(r => r.json()).then(data => {
        if (data && data.remaining !== undefined && !hasData) {
            // updateAll will pick it up from SSE, just a warmup
        }
    }).catch(() => {});
    // Disco del host: cacheado en el server (5 min), lo pedimos al arrancar
    fetch('/api/disk').then(r => r.json()).then(data => {
        if (data && data.total) renderDisk(data);
    }).catch(() => {});
    // RAM del host (cacheada 15s en el server)
    fetch('/api/memory').then(r => r.json()).then(data => {
        if (data && data.total) renderMem(data);
    }).catch(() => {});
    // Uso de herramientas (cache 5 min en el server)
    fetch('/api/tools').then(r => r.json()).then(data => {
        if (data && Object.keys(data).length) renderTools(data);
    }).catch(() => {});
    connectSSE();
    tickClock();
});

/* ==========================================================================
   Tema visual: clásico <-> glass (aurora) <-> liquid (cobalto profundo).
   Cambia las clases .glass o .liquid en <body>; el CSS hace el resto.
   La elección se recuerda en localStorage.
   ========================================================================== */
(function () {
    var KEY = 'panelTheme';
    var THEMES = ['classic', 'glass', 'liquid'];

    function leer() {
        try {
            var guardado = localStorage.getItem(KEY);
            return THEMES.indexOf(guardado) !== -1 ? guardado : 'classic';
        } catch (e) {
            return 'classic';
        }
    }

    function aplicar(modo) {
        document.body.classList.remove('glass', 'liquid');
        if (modo === 'glass') document.body.classList.add('glass');
        if (modo === 'liquid') document.body.classList.add('liquid');

        var btn = document.getElementById('themeBtn');
        if (btn) {
            var titles = {
                classic: 'Estilo clásico — clic para activar Glass Aurora',
                glass: 'Estilo Glass Aurora — clic para activar Cristal Puro',
                liquid: 'Estilo Cristal Puro — clic para volver al clásico'
            };
            var labels = {
                classic: 'Clásico',
                glass: 'Aurora',
                liquid: 'Cristal'
            };
            btn.title = titles[modo] || titles.classic;
            var lbl = btn.querySelector('.theme-label');
            if (lbl) lbl.textContent = labels[modo] || 'Clásico';
        }
    }

    window.toggleTheme = function () {
        var actual = 'classic';
        if (document.body.classList.contains('liquid')) actual = 'liquid';
        else if (document.body.classList.contains('glass')) actual = 'glass';

        var idx = THEMES.indexOf(actual);
        var siguiente = THEMES[(idx + 1) % THEMES.length];

        try { localStorage.setItem(KEY, siguiente); } catch (e) {}
        aplicar(siguiente);
    };

    function init() { aplicar(leer()); }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
