document.addEventListener('DOMContentLoaded', () => {
    const agentsGrid = document.getElementById('agentsGrid');
    const onlineCount = document.getElementById('onlineCount');
    const lastUpdateValue = document.getElementById('lastUpdateValue');
    const footerTime = document.getElementById('footerTime');
    const memValue = document.getElementById('memValue');

    // Agent card field mapping
    const agentFields = {
        gateway: 0,
        uptime: 1,
        cpu: 2,
        mem: 3,
        session: 4,
    };

    function updateAgentCard(agent) {
        const card = document.getElementById(`card-${agent.id}`);
        if (!card) return;

        card.classList.remove('loading');

        // Status badge
        const badge = card.querySelector('.status-badge');
        if (agent.online) {
            badge.className = 'status-badge status-online';
            badge.textContent = 'Online';
        } else {
            badge.className = 'status-badge status-offline';
            badge.textContent = 'Offline';
        }

        // Card border tint
        const borderColor = agent.online ? agent.color : '#ef4444';
        card.style.borderColor = agent.online ? (agent.color + '40') : 'rgba(239,68,68,0.3)';

        // Stats rows
        const rows = card.querySelectorAll('.stat-row .value');
        if (rows.length >= 5) {
            rows[0].textContent = agent.gateway && agent.gateway.includes('up') ? '✅ Activo' : (agent.gateway || '❌ Inactivo');
            rows[1].textContent = agent.uptime || '-';
            
            // CPU with mini bar
            const cpuVal = agent.cpu || 0;
            const cpuColor = cpuVal > 80 ? '#ef4444' : cpuVal > 50 ? '#eab308' : '#22c55e';
            rows[2].innerHTML = `${cpuVal.toFixed(1)}% <span class="cpu-bar-track"><span class="cpu-bar-fill" style="width:${Math.min(cpuVal,100)}%;background:${cpuColor}"></span></span>`;
            
            // RAM
            const memPct = agent.mem_pct || 0;
            rows[3].textContent = `${agent.mem_used || '-'}`;
            if (agent.mem_pct) {
                rows[3].innerHTML = `${agent.mem_used} / ${agent.mem_limit} <span class="mem-bar-track"><span class="mem-bar-fill" style="width:${memPct}%"></span></span>`;
            }
            
            // Last session
            const sessionStarted = agent.last_active && agent.last_active !== '-' ? agent.last_active : 'Sin actividad';
            rows[4].textContent = sessionStarted;
        }

        // Container ID in footer
        const footer = card.querySelector('.container-id');
        if (footer && agent.container_id) {
            footer.textContent = `📦 ${agent.container_id}`;
        }

        // Animate entry
        card.style.animation = 'none';
        card.offsetHeight; // reflow
        card.style.animation = 'cardFadeIn 0.4s ease';
    }

    function updateStatsBar(data) {
        let online = 0;
        let totalCpu = 0;
        let totalMem = 0;

        data.agents.forEach(a => {
            if (a.online) online++;
            totalCpu += a.cpu || 0;
            totalMem += a.mem_pct || 0;
        });

        onlineCount.textContent = `${online}/${data.agents.length}`;
        onlineCount.style.color = online > 0 ? '#22c55e' : '#ef4444';

        // System bars
        const avgCpu = totalCpu / data.agents.length;
        const avgMem = totalMem / data.agents.length;

        document.getElementById('cpuBar').style.width = `${Math.min(avgCpu, 100)}%`;
        document.getElementById('cpuTotalValue').textContent = `${avgCpu.toFixed(1)}%`;
        document.getElementById('ramBar').style.width = `${Math.min(avgMem, 100)}%`;
        document.getElementById('ramTotalValue').textContent = `${avgMem.toFixed(1)}%`;

        // Last update time
        const now = new Date();
        lastUpdateValue.textContent = now.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    // SSE connection for real-time updates
    let eventSource = null;

    function connectSSE() {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/api/agents/stream');

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                data.agents.forEach(updateAgentCard);
                updateStatsBar(data);
            } catch (e) {
                console.error('SSE parse error:', e);
            }
        };

        eventSource.onerror = () => {
            console.log('SSE connection error, reconnecting in 3s...');
            setTimeout(connectSSE, 3000);
        };
    }

    // Initial fetch (in case SSE fails)
    function fetchInitial() {
        fetch('/api/agents')
            .then(r => r.json())
            .then(data => {
                data.agents.forEach(updateAgentCard);
                updateStatsBar(data);
            })
            .catch(() => {
                // Fallback: show agents as loading
                document.querySelectorAll('.status-badge').forEach(b => {
                    b.className = 'status-badge status-offline';
                    b.textContent = 'Sin conexión';
                });
            });

        // Also fetch memory
        fetch('/api/memory')
            .then(r => r.json())
            .then(m => {
                memValue.textContent = `${m.total} GB`;
            })
            .catch(() => {});
    }

    // Inject animation styles
    const style = document.createElement('style');
    style.textContent = `
        @keyframes cardFadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);

    // Start
    fetchInitial();
    connectSSE();

    // Footer clock
    function updateClock() {
        const now = new Date();
        footerTime.textContent = now.toLocaleString('es-MX', {
            weekday: 'short',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'America/Mexico_City'
        });
    }
    updateClock();
    setInterval(updateClock, 1000);

    // Reconnect SSE on visibility change
    document.addEventListener('visibilitychange', () => {
        if (document.visible) {
            connectSSE();
            fetchInitial();
        }
    });
});