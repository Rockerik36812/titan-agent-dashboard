import asyncio
import base64
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import docker
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Titan Agent Dashboard")

# Agent definitions
AGENTS = {
    "titan": {
        "name": "Titán",
        "emoji": "🚀",
        "container": "hermes-agent-gludih2hknhumvx9ufx0bdql",
        "color": "#00d4ff",
        "bg": "rgba(0, 212, 255, 0.1)",
    },
    "hermes": {
        "name": "Hermes",
        "emoji": "🤖",
        "container": "hermes-agent-v6y8md5qijrltg1rm34e90tj",
        "color": "#a855f7",
        "bg": "rgba(168, 85, 247, 0.1)",
    },
    "hermina": {
        "name": "Hermina",
        "emoji": "💜",
        "container": "hermes-agent-kqzoxrig0pspua7pymgdlaon",
        "color": "#ec4899",
        "bg": "rgba(236, 72, 153, 0.1)",
    },
}

OPENROUTER_MGMT_KEY = None


def load_env():
    global OPENROUTER_MGMT_KEY
    import os
    env_key = os.environ.get("OPENROUTER_MANAGEMENT_KEY")
    if env_key:
        OPENROUTER_MGMT_KEY = env_key
        return
    try:
        with open("/app/.env", "r") if Path("/app/.env").exists() else open("/home/hermes/.hermes/.env", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENROUTER_MANAGEMENT_KEY="):
                    OPENROUTER_MGMT_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        OPENROUTER_MGMT_KEY = None


# ─── Background Data Cache ──────────────────────────────────────────
_CACHE = {
    "agents": [],
    "totals": {"online": 0, "total": 0, "total_ram": 0, "used_ram": 0},
    "credits": {"total": 0, "used": 0, "remaining": 0, "percent_used": 0},
    "stats": {},
    "analytics": {},
    "activity": [],
    "gateways": {},
    "history": {},
    "tools": {},
    "ts": 0,
}
_CACHE_READY = False
# Initialize _PREV_ONLINE with all agents as online so first run detects transitions
_PREV_ONLINE = {aid: True for aid in AGENTS}
_PREV_LOW_CREDITS_SENT = set()  # tracks which thresholds we've notified

# ── Disco del host ──
# Se lee lanzando un contenedor efímero con / montado en modo lectura (el panel
# no ve el filesystem del host directamente). Es costoso -> cache de 5 min.
_DISK = {"total": 0, "used": 0, "free": 0, "percent": 0, "ts": 0}
_DISK_TTL = 120  # 2 min: leerlo lanza un contenedor efímero, no conviene más seguido
_PREV_DISK_ALERTS = set()  # umbrales de disco ya notificados


def _fmt_bytes(n) -> str:
    """Formatea bytes a algo legible (GB/MB)."""
    try:
        n = float(n)
    except Exception:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


async def get_host_disk(force: bool = False) -> dict:
    """Uso de disco del HOST. Cacheado (_DISK_TTL) porque lanza un contenedor efímero."""
    global _DISK
    now = time.time()
    if not force and _DISK.get("ts") and (now - _DISK["ts"]) < _DISK_TTL:
        return _DISK
    try:
        client = docker.from_env()

        def _run():
            return client.containers.run(
                "alpine", ["df", "-B1", "/host"],
                volumes={"/": {"bind": "/host", "mode": "ro"}},
                remove=True,
            )

        out = await asyncio.to_thread(_run)
        lines = [l for l in out.decode().strip().split("\n") if l.strip()]
        parts = lines[-1].split()
        total, used, free = int(parts[1]), int(parts[2]), int(parts[3])
        pct = round(used / total * 100, 1) if total else 0
        _DISK = {"total": total, "used": used, "free": free, "percent": pct, "ts": now}
    except Exception as e:
        print(f"DISK: error {e}", flush=True)
        _DISK["ts"] = now  # evitar reintentos en cada ciclo si falla
    return _DISK


# ── RAM del host ──
# /proc/meminfo dentro del contenedor YA refleja la memoria del host (Docker no
# la aísla, salvo que se use lxcfs) -> lectura directa, mucho más barata que el
# contenedor efímero del disco. Cache de 15s (casi en vivo).
_MEM = {"total": 0, "used": 0, "free": 0, "percent": 0, "ts": 0}
_MEM_TTL = 15  # refresco casi en vivo (leer /proc/meminfo es barato)


async def get_host_memory(force: bool = False) -> dict:
    """Uso de RAM del HOST leyendo /proc/meminfo."""
    global _MEM
    now = time.time()
    if not force and _MEM.get("ts") and (now - _MEM["ts"]) < _MEM_TTL:
        return _MEM
    try:
        vals = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    vals[key.strip()] = int(parts[0]) * 1024  # kB -> bytes
        total = vals.get("MemTotal", 0)
        # "used" como en `free`: total - disponible (MemAvailable incluye caché recuperable)
        avail = vals.get("MemAvailable") or vals.get("MemFree") or 0
        used = max(total - avail, 0)
        pct = round(used / total * 100, 1) if total else 0
        _MEM = {"total": total, "used": used, "free": avail, "percent": pct, "ts": now}
    except Exception as e:
        print(f"MEM: error {e}", flush=True)
        _MEM["ts"] = now  # evitar reintentos en cada ciclo si falla
    return _MEM


async def _update_cache():
    """Background task: refreshes all dashboard data in memory every 3s."""
    global _CACHE, _CACHE_READY, _PREV_ONLINE
    print("CACHE: _update_cache started", flush=True)
    while True:
        try:
            # ── Agent stats ──
            print("CACHE: cycle begin", flush=True)
            agent_tasks = [get_agent_stats(aid, info) for aid, info in AGENTS.items()]
            agent_results = await asyncio.gather(*agent_tasks)
            total_ram = sum(a["mem_limit"] for a in agent_results if a["online"])
            used_ram = sum(a["mem_usage"] for a in agent_results if a["online"])

            # ── Auto Notify (push) — must run FIRST, before anything can fail ──
            for a in agent_results:
                aid = a["id"]
                was_online = _PREV_ONLINE.get(aid, True)
                if not a["online"] and was_online:
                    print(f"NOTIFY: {aid} went offline (was_online={was_online})", flush=True)
                    asyncio.ensure_future(_send_push_notification(
                        title=f"⚠️ {a['emoji']} {a['name']} — fuera de línea",
                        body="Agente fuera de línea",
                        tag=f"offline-{aid}",
                        url="/",
                    ))
            _PREV_ONLINE = {a["id"]: a["online"] for a in agent_results}

            # ── Disco del host (+ alertas por umbral) ──
            global _PREV_DISK_ALERTS
            disk = await get_host_disk()
            mem = await get_host_memory()
            dpct = disk.get("percent", 0)
            for threshold in (90, 80):
                if dpct >= threshold and threshold not in _PREV_DISK_ALERTS:
                    _PREV_DISK_ALERTS.add(threshold)
                    print(f"NOTIFY: disco al {dpct}% (umbral {threshold})", flush=True)
                    asyncio.ensure_future(_send_push_notification(
                        title=f"💾 Disco al {dpct}%",
                        body=f"Quedan {_fmt_bytes(disk.get('free', 0))} libres de {_fmt_bytes(disk.get('total', 0))}",
                        tag=f"disk-{threshold}",
                        url="/",
                    ))
            # Reset cuando baja, para volver a avisar si sube otra vez
            if dpct < 75:
                _PREV_DISK_ALERTS.clear()

            # ── Credits ──
            credits_data = {"total": 0, "used": 0, "remaining": 0, "percent_used": 0}
            if OPENROUTER_MGMT_KEY:
                try:
                    req = urllib.request.Request(
                        "https://openrouter.ai/api/v1/credits",
                        headers={"Authorization": f"Bearer {OPENROUTER_MGMT_KEY}"},
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        cd = json.loads(resp.read())
                        total = float(cd.get("data", {}).get("total_credits", 0))
                        usage = float(cd.get("data", {}).get("total_usage", 0))
                        credits_data = {
                            "total": round(total, 2), "used": round(usage, 2),
                            "remaining": round(total - usage, 2),
                            "percent_used": round((usage / total) * 100, 1) if total > 0 else 0,
                        }
                except Exception:
                    pass

            # ── Epic stats ──
            stat_tasks = [get_epic_stats(info["container"]) for info in AGENTS.values()]
            stat_results = await asyncio.gather(*stat_tasks)
            merged_stats = {
                "sessions": sum(r.get("sessions", 0) for r in stat_results),
                "messages": sum(r.get("messages", 0) for r in stat_results),
                "tool_calls": sum(r.get("tool_calls", 0) for r in stat_results),
                "tokens": sum(r.get("tokens", 0) for r in stat_results),
                "cost": round(sum(r.get("cost", 0) for r in stat_results), 4),
                "days_active": max(r.get("days_active", 0) for r in stat_results),
                "sessions_24h": sum(r.get("sessions_24h", 0) for r in stat_results),
            }
            score = 0
            score += min(merged_stats["sessions"] * 2, 200)
            score += min(merged_stats["messages"] * 0.05, 150)
            score += min(merged_stats["tool_calls"] * 0.5, 100)
            score += min(merged_stats["days_active"] * 3, 150)
            score += merged_stats["sessions_24h"] * 5
            merged_stats["titan_score"] = min(int(score), 999)

            # ── Analytics ──
            an_tasks = [get_analytics(info["container"]) for info in AGENTS.values()]
            an_results = await asyncio.gather(*an_tasks)
            daily_map = {}
            for r in an_results:
                for d in r.get("daily_cost", []):
                    daily_map[d["day"]] = daily_map.get(d["day"], 0) + d["cost"]
            models_map = {}
            for r in an_results:
                for m in r.get("models", []):
                    nm = m["model"]
                    if nm not in models_map:
                        models_map[nm] = {"model": nm, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0}
                    models_map[nm]["calls"] += m["calls"]
                    models_map[nm]["input_tokens"] += m["input_tokens"]
                    models_map[nm]["output_tokens"] += m["output_tokens"]
                    models_map[nm]["cost"] += m["cost"]
            analytics = {
                "daily_cost": [{"day": k, "cost": round(v, 4)} for k, v in sorted(daily_map.items())],
                "models": sorted(models_map.values(), key=lambda x: x["calls"], reverse=True),
                "total_sessions": sum(r.get("total_sessions", 0) for r in an_results),
                "week_cost": round(sum(r.get("week_cost", 0) for r in an_results), 4),
            }

            # ── Activity ──
            act_tasks = [get_recent_activity(info["container"], 5) for info in AGENTS.values()]
            act_results = await asyncio.gather(*act_tasks)
            feed = []
            for i, (aid, info) in enumerate(AGENTS.items()):
                entries = act_results[i]
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    entry["agent_id"] = aid; entry["agent_name"] = info["name"]; entry["emoji"] = info["emoji"]; entry["color"] = info["color"]
                    feed.append(entry)
            feed.sort(key=lambda x: x.get("timestamp") or 0, reverse=True)

            # ── Uso de herramientas (cache 5 min: la query recorre toda la tabla) ──
            global _TOOLS
            if not _TOOLS["ts"] or (time.time() - _TOOLS["ts"]) > _TOOLS_TTL:
                tools_tasks = [get_tool_usage(info["container"]) for info in AGENTS.values()]
                tools_results = await asyncio.gather(*tools_tasks)
                _TOOLS = {
                    "by_agent": {aid: res for aid, res in zip(AGENTS.keys(), tools_results)},
                    "ts": time.time(),
                }
            tools_data = _TOOLS["by_agent"]

            # ── Gateway ──
            gw_tasks = [get_gateway_health(info["container"]) for info in AGENTS.values()]
            gw_results = await asyncio.gather(*gw_tasks)
            gateways = {}
            for i, (aid, info) in enumerate(AGENTS.items()):
                g = gw_results[i]
                uptime = ""
                # uptime_secs viene calculado en get_gateway_health (start_time NO es epoch)
                secs = int(g.get("uptime_secs") or 0)
                if secs > 0:
                    hours, rem = divmod(secs, 3600)
                    mins = rem // 60
                    uptime = f"{hours}h {mins}m" if hours else f"{mins}m"
                gateways[aid] = {"name": info["name"], "emoji": info["emoji"], "color": info["color"],
                    "state": g.get("gateway_state", "unknown"), "uptime": uptime,
                    "active_agents": g.get("active_agents", 0), "platforms": g.get("platforms", {}),
                }

            # ── History ──
            hist_tasks = [get_session_history(aid, info["container"], 5) for aid, info in AGENTS.items()]
            hist_results = await asyncio.gather(*hist_tasks)
            history = {}
            for i, (aid, info) in enumerate(AGENTS.items()):
                history[aid] = {"name": info["name"], "emoji": info["emoji"], "color": info["color"], "sessions": hist_results[i]}

            # ── Credits low progresivo ──
            global _PREV_LOW_CREDITS_SENT
            remaining = credits_data.get("remaining", 100)
            for threshold in [5, 4, 3, 2, 1]:
                if 0 < remaining < threshold and threshold not in _PREV_LOW_CREDITS_SENT:
                    _PREV_LOW_CREDITS_SENT.add(threshold)
                    asyncio.ensure_future(_send_push_notification(
                        title=f"💰 OpenRouter bajo — ${threshold}",
                        body=f"${remaining:.2f} restantes de ${credits_data['total']:.2f}",
                        tag=f"credits-low-{threshold}",
                        url="/",
                    ))
            # Reset si recarga (sube de $5 otra vez)
            if remaining > 5:
                _PREV_LOW_CREDITS_SENT.clear()

            # ── Update cache ──
            _CACHE = {
                "agents": agent_results,
                "totals": {"online": sum(1 for a in agent_results if a["online"]), "total": len(agent_results), "total_ram": total_ram, "used_ram": used_ram},
                "credits": credits_data, "stats": merged_stats, "analytics": analytics,
                "activity": feed[:10], "gateways": gateways, "history": history,
                "disk": {"total": disk.get("total", 0), "used": disk.get("used", 0),
                         "free": disk.get("free", 0), "percent": disk.get("percent", 0)},
                "mem": {"total": mem.get("total", 0), "used": mem.get("used", 0),
                        "free": mem.get("free", 0), "percent": mem.get("percent", 0)},
                "tools": tools_data,
                "ts": time.time(),
            }
            _CACHE_READY = True
        except Exception:
            pass
        await asyncio.sleep(3)


@app.on_event("startup")
async def on_startup():
    print("CACHE: startup event fires", flush=True)
    load_env()
    print("CACHE: load_env done", flush=True)
    try:
        asyncio.create_task(_update_cache())
        print("CACHE: task created successfully", flush=True)
    except Exception as e:
        print(f"CACHE: failed to create task: {e}", flush=True)


async def exec_in_container(container_name: str, cmd: str) -> str:
    """Execute a command inside a Docker container and return stdout."""
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        result = container.exec_run(["sh", "-c", cmd], user="hermes")
        return result.output.decode() if result.output else ""
    except Exception as e:
        return f"ERROR: {e}"


async def exec_python(container_name: str, script: str) -> str:
    """Execute Python code directly (no shell) — avoids all quoting issues."""
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        result = container.exec_run(["python3", "-c", script], user="hermes")
        return result.output.decode() if result.output else ""
    except Exception as e:
        return f"ERROR: {e}"


async def exec_script(container_name: str, script: str) -> str:
    """Execute a Python script in the container directly — avoids shell quoting issues."""
    return await exec_python(container_name, script)


async def get_model_info(container_name: str) -> dict:
    """Modelo configurado (principal + fallback) y el que está realmente en uso."""
    script = """import json, re, os
out = {'primary': None, 'fallback': None, 'in_use': None, 'fallback_active': False}
Q = chr(34); A = chr(39)
cfg_path = '/home/hermes/.hermes/config.yaml'
try:
    txt = open(cfg_path).read()
    # bloque model: -> default
    m = re.search(r'^model:\\s*\\n((?:[ \\t]+.*\\n?)*)', txt, re.M)
    if m:
        mm = re.search(r'default:\\s*(\\S+)', m.group(1))
        if mm:
            out['primary'] = mm.group(1).strip().strip(Q).strip(A) or None
    # bloque fallback_providers: -> primer model
    fm = re.search(r'^fallback_providers:\\s*\\n((?:[ \\t]+.*\\n?)*)', txt, re.M)
    if fm:
        fm2 = re.search(r'model:\\s*(\\S+)', fm.group(1))
        if fm2:
            out['fallback'] = fm2.group(1).strip().strip(Q).strip(A) or None
except Exception:
    pass
# modelo realmente en uso: ultimo 'model=' del agent.log (ultimos ~256KB)
try:
    log = '/home/hermes/.hermes/logs/agent.log'
    size = os.path.getsize(log)
    with open(log, 'rb') as f:
        if size > 262144:
            f.seek(size - 262144)
        txt = f.read().decode('utf-8', 'replace')
    found = re.findall(r'model=([\\w\\-\\./:]+)', txt)
    if found:
        out['in_use'] = found[-1]
except Exception:
    pass
out['fallback_active'] = bool(out['in_use'] and out['primary'] and out['in_use'] != out['primary'])
print(json.dumps(out))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except Exception:
        return {"primary": None, "fallback": None, "in_use": None, "fallback_active": False}


async def get_agent_stats(agent_id: str, info: dict) -> dict:
    """Get stats for a single agent."""
    container_name = info["container"]
    client = docker.from_env()

    try:
        container = client.containers.get(container_name)
        stats = container.stats(stream=False)

        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        num_cpus = stats["cpu_stats"]["online_cpus"]
        cpu_pct = (cpu_delta / system_delta) * num_cpus * 100 if system_delta > 0 else 0

        mem_usage = stats["memory_stats"]["usage"]
        mem_limit = stats["memory_stats"]["limit"]
        mem_pct = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0

        created = container.attrs["Created"]
        status = container.status
        uptime = ""
        if status == "running":
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - created_dt
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes = remainder // 60
            uptime = f"{hours}h {minutes}m"

        # Gateway status
        gateway = await exec_in_container(container_name,
            "cat /run/service/gateway-default/supervise/stat 2>/dev/null || "
            "s6-svstat /run/service/gateway-default 2>/dev/null || echo 'unknown'")
        gateway = gateway.strip()[:80]
        if not gateway or gateway == "unknown":
            if status == "running":
                gateway = "online"  # Agent is up but no gateway service = still good

        # Modelo configurado + modelo en uso (para ver si el fallback está activo)
        model_info = await get_model_info(container_name)

        return {
            "id": agent_id,
            "name": info["name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "online": status == "running",
            "cpu": round(cpu_pct, 1),
            "mem_usage": mem_usage,
            "mem_limit": mem_limit,
            "mem_pct": round(mem_pct, 1),
            "uptime": uptime,
            "gateway": gateway.strip()[:80],
            "container": container_name[:20],
            "model": model_info.get("in_use") or model_info.get("primary"),
            "model_primary": model_info.get("primary"),
            "model_fallback": model_info.get("fallback"),
            "fallback_active": bool(model_info.get("fallback_active")),
        }
    except Exception as e:
        return {
            "id": agent_id,
            "name": info["name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "online": False,
            "cpu": 0,
            "mem_usage": 0,
            "mem_limit": 0,
            "mem_pct": 0,
            "uptime": "offline",
            "gateway": "unknown",
            "container": container_name[:20],
            "model": None,
            "model_primary": None,
            "model_fallback": None,
            "fallback_active": False,
        }


async def get_session_history(agent_id: str, container_name: str, limit: int = 10) -> list:
    """Get session history from agent's state.db."""
    try:
        script = f"""import sqlite3, json
db = sqlite3.connect('/home/hermes/.hermes/state.db')
rows = db.execute(
    'SELECT id, title, started_at, ended_at, end_reason, message_count, tool_call_count, estimated_cost_usd, last_activity_description '
    'FROM sessions WHERE title IS NOT NULL AND title != ? ORDER BY started_at DESC LIMIT {limit}', ('',)
).fetchall()
db.close()
print(json.dumps([{{'id': r[0], 'title': r[1], 'started_at': r[2], 'ended_at': r[3], 'end_reason': r[4], 'message_count': r[5], 'tool_call_count': r[6], 'cost_usd': r[7], 'last_activity': r[8]}} for r in rows]))
"""
        result = await exec_script(container_name, script)
        data = json.loads(result)
        return data
    except Exception as e:
        return []


# ── Uso de herramientas por agente ──
# La query recorre toda la tabla `messages` (~34k filas en Titán, ~157 ms), así que
# NO va en el ciclo del SSE (3s): cache de 5 min.
_TOOLS = {"by_agent": {}, "ts": 0}
_TOOLS_TTL = 300


async def get_tool_usage(container_name: str, limit: int = 8) -> dict:
    """Desglose de herramientas usadas, desde messages.tool_name de state.db."""
    try:
        script = f"""import sqlite3, json
db = sqlite3.connect('/home/hermes/.hermes/state.db')
q = "SELECT tool_name, COUNT(*) FROM messages WHERE tool_name IS NOT NULL AND tool_name != '' GROUP BY tool_name ORDER BY COUNT(*) DESC LIMIT {limit}"
rows = db.execute(q).fetchall()
tot = db.execute("SELECT COUNT(*) FROM messages WHERE tool_name IS NOT NULL AND tool_name != ''").fetchone()[0]
db.close()
print(json.dumps({{'tools': [{{'name': r[0], 'count': r[1]}} for r in rows], 'total': tot}}))
"""
        result = await exec_script(container_name, script)
        return json.loads(result)
    except Exception as e:
        print(f"TOOLS: error {e}", flush=True)
        return {"tools": [], "total": 0}


# ─── NEW: Analytics ─────────────────────────────────────────────────

async def get_analytics(container_name: str) -> dict:
    """Get cost-over-time, model breakdown, and tool stats from one agent."""
    script = """import sqlite3, json
db = sqlite3.connect('/home/hermes/.hermes/state.db')

# Cost per day — últimos 30 días CON datos.
# OJO: antes filtraba por started_at > now-30d, y si el agente no tuvo sesiones
# recientes la gráfica salía vacía. Ahora tomamos los últimos días con costo real.
daily = db.execute(
    "SELECT date(started_at, 'unixepoch') as d, COALESCE(SUM(estimated_cost_usd), 0) "
    "FROM sessions WHERE estimated_cost_usd > 0 "
    "GROUP BY d ORDER BY d DESC LIMIT 30"
).fetchall()[::-1]

# Rellenar días intermedios sin actividad con 0 para una serie continua
if daily:
    from datetime import date, timedelta
    dmap = {r[0]: r[1] for r in daily}
    cur = date.fromisoformat(daily[0][0])
    last = date.fromisoformat(daily[-1][0])
    series = []
    while cur <= last:
        k = cur.isoformat()
        series.append((k, dmap.get(k, 0)))
        cur += timedelta(days=1)
    daily = series

# Model usage
models = db.execute(
    "SELECT model, SUM(api_call_count), SUM(input_tokens), SUM(output_tokens), "
    "COALESCE(SUM(estimated_cost_usd), 0) FROM session_model_usage "
    "GROUP BY model ORDER BY 5 DESC"
).fetchall()

# Totals
totals = db.execute(
    "SELECT COUNT(*), COALESCE(SUM(message_count),0), COALESCE(SUM(tool_call_count),0), "
    "COALESCE(SUM(input_tokens + output_tokens),0), COALESCE(SUM(estimated_cost_usd),0) "
    "FROM sessions"
).fetchone()

# Last 7 days cost
week = db.execute(
    "SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM sessions "
    "WHERE started_at > strftime('%s', 'now', '-7 days') AND estimated_cost_usd > 0"
).fetchone()[0]

db.close()
print(json.dumps({
    'daily_cost': [{'day': r[0], 'cost': round(r[1], 4)} for r in daily],
    'models': [{'model': r[0], 'calls': r[1] or 0, 'input_tokens': r[2] or 0, 'output_tokens': r[3] or 0, 'cost': round(r[4], 4)} for r in models],
    'total_sessions': totals[0] or 0,
    'total_messages': totals[1] or 0,
    'total_tool_calls': totals[2] or 0,
    'total_tokens': totals[3] or 0,
    'total_cost': round(totals[4] or 0, 4),
    'week_cost': round(week, 4),
}))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except Exception as e:
        return {"error": str(e), "daily_cost": [], "models": [], "total_sessions": 0, "total_messages": 0, "total_tool_calls": 0, "total_tokens": 0, "total_cost": 0, "week_cost": 0}

@app.get("/api/analytics")
async def api_analytics():
    """Aggregated analytics across all agents."""
    tasks = [get_analytics(info["container"]) for info in AGENTS.values()]
    results = await asyncio.gather(*tasks)

    # Merge daily cost
    daily_map = {}
    for r in results:
        for d in r.get("daily_cost", []):
            daily_map[d["day"]] = daily_map.get(d["day"], 0) + d["cost"]

    # Merge models
    models_map = {}
    for r in results:
        for m in r.get("models", []):
            nm = m["model"]
            if nm not in models_map:
                models_map[nm] = {"model": nm, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0}
            models_map[nm]["calls"] += m["calls"]
            models_map[nm]["input_tokens"] += m["input_tokens"]
            models_map[nm]["output_tokens"] += m["output_tokens"]
            models_map[nm]["cost"] += m["cost"]

    merged = {
        "daily_cost": [{"day": k, "cost": round(v, 4)} for k, v in sorted(daily_map.items())],
        "models": sorted(models_map.values(), key=lambda x: x["cost"], reverse=True),
        "total_sessions": sum(r.get("total_sessions", 0) for r in results),
        "total_messages": sum(r.get("total_messages", 0) for r in results),
        "total_tool_calls": sum(r.get("total_tool_calls", 0) for r in results),
        "total_tokens": sum(r.get("total_tokens", 0) for r in results),
        "total_cost": round(sum(r.get("total_cost", 0) for r in results), 4),
        "week_cost": round(sum(r.get("week_cost", 0) for r in results), 4),
    }
    return merged


# ─── NEW: Activity Feed ──────────────────────────────────────────────

async def get_recent_activity(container_name: str, limit: int = 5) -> list:
    """Get recent activity entries from an agent."""
    script = f"""import sqlite3, json, time
db = sqlite3.connect('/home/hermes/.hermes/state.db')
# OJO: antes se filtraba por last_activity_description no vacío, y ese campo
# casi nunca se llena (solo en eventos de compresión) -> el feed salía vacío.
# Ahora tomamos las sesiones recientes y derivamos una descripción útil.
rows = db.execute(
    "SELECT id, title, last_activity_description, last_activity_at, estimated_cost_usd, "
    "message_count, started_at, end_reason FROM sessions "
    "WHERE last_activity_at IS NOT NULL "
    "ORDER BY last_activity_at DESC LIMIT {limit}"
).fetchall()
db.close()
out = []
for r in rows:
    desc = (r[2] or '').strip() or (r[1] or '').strip()
    if not desc:
        er = (r[7] or '').strip()
        desc = ('Sesión ' + er) if er else 'Actividad reciente'
    out.append({{
        'session_id': r[0],
        'title': r[1],
        'description': desc,
        'timestamp': r[3],
        'cost_usd': round(r[4] or 0, 4),
        'message_count': r[5] or 0,
        'started_at': r[6],
    }})
print(json.dumps(out))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except Exception as e:
        return []

@app.get("/api/activity")
async def api_activity(limit: int = 5):
    """Recent activity feed from all agents, merged by time."""
    tasks = [get_recent_activity(info["container"], limit) for info in AGENTS.values()]
    results = await asyncio.gather(*tasks)

    feed = []
    for i, (aid, info) in enumerate(AGENTS.items()):
        for entry in results[i]:
            entry["agent_id"] = aid
            entry["agent_name"] = info["name"]
            entry["emoji"] = info["emoji"]
            entry["color"] = info["color"]
            feed.append(entry)

    feed.sort(key=lambda x: x.get("timestamp") or 0, reverse=True)
    return feed[:limit]


# ─── NEW: Gateway Health ─────────────────────────────────────────────

async def get_gateway_health(container_name: str) -> dict:
    """Get gateway health from an agent's gateway_state.json."""
    script = """import json, time, os
try:
    with open('/home/hermes/.hermes/gateway_state.json') as f:
        g = json.load(f)
    platforms = g.get('platforms', {})
    # ── Uptime real del proceso del gateway ──
    # OJO: g['start_time'] NO es un timestamp epoch (son ticks de /proc/PID/stat),
    # por eso no se puede hacer time.time() - start_time.
    uptime_secs = 0
    pid = g.get('pid')
    if pid:
        try:
            # método 1: /proc/uptime - (starttime_ticks / CLK_TCK)
            with open('/proc/%s/stat' % pid) as f:
                fields = f.read().split()
            starttime_ticks = int(fields[21])
            clk = os.sysconf('SC_CLK_TCK')
            with open('/proc/uptime') as f:
                system_uptime = float(f.read().split()[0])
            uptime_secs = max(0, int(system_uptime - (starttime_ticks / clk)))
        except Exception:
            try:
                import subprocess
                out = subprocess.check_output(['ps', '-o', 'etimes=', '-p', str(pid)], stderr=subprocess.DEVNULL)
                uptime_secs = max(0, int(out.decode().strip()))
            except Exception:
                uptime_secs = 0
    print(json.dumps({
        'gateway_state': g.get('gateway_state', 'unknown'),
        'start_time': g.get('start_time', 0),
        'uptime_secs': uptime_secs,
        'pid': pid,
        'active_agents': g.get('active_agents', 0),
        'platforms': {k: {'state': v.get('state', '?'), 'error': v.get('error_message')} for k, v in platforms.items()},
    }))
except FileNotFoundError:
    # No gateway state file yet — agent may still be starting or gateway not configured
    print(json.dumps({'gateway_state': 'running', 'start_time': int(time.time()), 'active_agents': 0, 'platforms': {}}))
except Exception as e:
    print(json.dumps({'gateway_state': f'error: {e}', 'start_time': 0, 'active_agents': 0, 'platforms': {}}))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except Exception as e:
        return {"gateway_state": f"error: {e}", "start_time": 0, "active_agents": 0, "platforms": {}}

@app.get("/api/gateway")
async def api_gateway():
    """Gateway health for all agents."""
    tasks = [get_gateway_health(info["container"]) for info in AGENTS.values()]
    results = await asyncio.gather(*tasks)

    output = {}
    for i, (aid, info) in enumerate(AGENTS.items()):
        g = results[i]
        uptime = ""
        # uptime_secs viene calculado en get_gateway_health (start_time NO es epoch)
        secs = int(g.get("uptime_secs") or 0)
        if secs > 0:
            hours, rem = divmod(secs, 3600)
            mins = rem // 60
            uptime = f"{hours}h {mins}m" if hours else f"{mins}m"

        output[aid] = {
            "name": info["name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "state": g.get("gateway_state", "unknown"),
            "uptime": uptime,
            "active_agents": g.get("active_agents", 0),
            "platforms": g.get("platforms", {}),
        }
    return output


# ─── NEW: Epic Stats ─────────────────────────────────────────────────

async def get_epic_stats(container_name: str) -> dict:
    """Get aggregate stats and first activity date from one agent."""
    script = """import sqlite3, json, time
db = sqlite3.connect('/home/hermes/.hermes/state.db')

# Session stats
s = db.execute("SELECT COUNT(*), COALESCE(SUM(message_count),0), COALESCE(SUM(tool_call_count),0), "
    "COALESCE(SUM(input_tokens + output_tokens),0), COALESCE(SUM(estimated_cost_usd),0), "
    "COALESCE(MIN(started_at),0), COALESCE(MAX(started_at),0) FROM sessions").fetchone()

# Last 24h activity
day = db.execute("SELECT COUNT(*) FROM sessions WHERE started_at > strftime('%s', 'now', '-1 day')").fetchone()[0]

db.close()

total_tokens = s[3] or 0
days_active = 0
first_ts = s[5] or 0
if first_ts > 0:
    days_active = max(1, int((time.time() - first_ts) / 86400))

print(json.dumps({
    'sessions': s[0] or 0,
    'messages': s[1] or 0,
    'tool_calls': s[2] or 0,
    'tokens': total_tokens,
    'cost': round(s[4] or 0, 4),
    'first_activity': first_ts,
    'last_activity': s[6] or 0,
    'days_active': days_active,
    'sessions_24h': day,
}))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except Exception as e:
        return {"sessions": 0, "messages": 0, "cost": 0, "days_active": 0, "first_activity": 0, "last_activity": 0, "sessions_24h": 0}

@app.get("/api/stats")
async def api_stats():
    """Epic aggregated stats across all agents."""
    tasks = [get_epic_stats(info["container"]) for info in AGENTS.values()]
    results = await asyncio.gather(*tasks)

    merged = {
        "sessions": sum(r.get("sessions", 0) for r in results),
        "messages": sum(r.get("messages", 0) for r in results),
        "tool_calls": sum(r.get("tool_calls", 0) for r in results),
        "tokens": sum(r.get("tokens", 0) for r in results),
        "cost": round(sum(r.get("cost", 0) for r in results), 4),
        "days_active": max(r.get("days_active", 0) for r in results),
        "sessions_24h": sum(r.get("sessions_24h", 0) for r in results),
        "first_activity": min(r.get("first_activity", 0) for r in results),
        "last_activity": max(r.get("last_activity", 0) for r in results),
    }

    # Titan Score: weighted formula
    score = 0
    score += min(merged["sessions"] * 2, 200)       # up to 200
    score += min(merged["messages"] * 0.05, 150)     # up to 150
    score += min(merged["tool_calls"] * 0.5, 100)     # up to 100
    score += min(merged["days_active"] * 3, 150)      # up to 150
    score += merged["sessions_24h"] * 5              # recent activity bonus
    merged["titan_score"] = min(int(score), 999)

    return merged


# ─── Web Push Notifications ──────────────────────────────────────────

import os, base64, json as _json
from pathlib import Path

VAPID_CLAIMS = {"sub": "mailto:titan@erikn8nservices.click"}
_SUBSCRIBERS_FILE = Path("/app/data/push_subscribers.json")

# Cached keys: private = base64url-encoded DER (pywebpush format), public = base64url uncompressed point
_vapid_private_b64 = None
_vapid_public_b64 = None


def _ensure_vapid():
    """Load or generate VAPID keys. Returns (private_b64, public_b64)."""
    global _vapid_private_b64, _vapid_public_b64
    if _vapid_private_b64 and _vapid_public_b64:
        return _vapid_private_b64, _vapid_public_b64

    key_file = Path("/app/data/push_vapid.json")
    if key_file.exists():
        try:
            saved = _json.loads(key_file.read_text())
            private = saved["private"]
            public = saved["public"]
            # Quick validation: try loading with py_vapid
            from py_vapid import Vapid
            Vapid.from_string(private_key=private)
            # Validate public key length (87 = standard EC uncompressed)
            if len(public) == 87:
                _vapid_private_b64 = private
                _vapid_public_b64 = public
                return _vapid_private_b64, _vapid_public_b64
        except Exception:
            pass

    # Generate using cryptography
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    import base64

    priv = ec.generate_private_key(ec.SECP256R1(), default_backend())
    pub = priv.public_key()

    # Private key: DER → base64url (pywebpush / Vapid.from_string expects this)
    priv_der = priv.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    _vapid_private_b64 = base64.urlsafe_b64encode(priv_der).rstrip(b"=").decode()

    # Public key: uncompressed point → base64url (browser pushManager expects this)
    pub_raw = pub.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    _vapid_public_b64 = base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode()

    try:
        key_file.write_text(_json.dumps({
            "private": _vapid_private_b64,
            "public": _vapid_public_b64,
        }))
    except Exception:
        pass

    return _vapid_private_b64, _vapid_public_b64


def _load_subscribers() -> list:
    if _SUBSCRIBERS_FILE.exists():
        try:
            return _json.loads(_SUBSCRIBERS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_subscribers(subs: list):
    try:
        _SUBSCRIBERS_FILE.write_text(_json.dumps(subs))
    except Exception:
        pass


async def _send_push_notification(title: str, body: str, tag: str = "agent-alert", url: str = "/"):
    """Send a push notification to all subscribers."""
    priv_b64, _ = _ensure_vapid()
    subs = _load_subscribers()
    if not subs:
        return

    payload = _json.dumps({"title": title, "body": body, "tag": tag, "url": url, "icon": "/static/favicon.svg"})

    try:
        from pywebpush import webpush, WebPushException

        for sub in subs:
            try:
                webpush(
                    subscription_info=sub,
                    data=payload,
                    vapid_private_key=priv_b64,
                    vapid_claims=VAPID_CLAIMS,
                    ttl=86400,
                )
            except WebPushException as ex:
                if ex.response and ex.response.status_code in (410, 404):
                    subs.remove(sub)
                    _save_subscribers(subs)
            except Exception:
                continue
    except ImportError:
        pass


@app.get("/api/push/vapid-key")
async def push_vapid_key():
    """Return the VAPID public key for push subscription."""
    _, pub_b64 = _ensure_vapid()
    return {"key": pub_b64}


@app.post("/api/push/subscribe")
async def push_subscribe(request: Request):
    """Save a push subscription from the browser — validate it first."""
    sub = await request.json()
    subs = _load_subscribers()
    # Avoid duplicates (same endpoint)
    endpoint = sub.get("endpoint", "")
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    subs.append(sub)
    _save_subscribers(subs)
    return {"status": "ok", "count": len(subs)}


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(request: Request):
    """Remove a push subscription."""
    body = await request.json()
    endpoint = body.get("endpoint", "")
    subs = _load_subscribers()
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    _save_subscribers(subs)
    return {"status": "ok", "count": len(subs)}


@app.post("/api/push/test")
async def push_test():
    """Send a test notification to all subscribers."""
    from pywebpush import webpush, WebPushException
    from fastapi import HTTPException
    priv_b64, _ = _ensure_vapid()
    subs = _load_subscribers()
    if not subs:
        raise HTTPException(400, "No subscribers. Click 🔔 first.")
    result = {"sent": 0, "errors": 0, "details": []}
    payload = _json.dumps({
        "title": "🔔 Panel de Agentes",
        "body": "Notificación de prueba — funciona!",
        "tag": "test", "url": "/"
    })
    for i, sub in enumerate(subs):
        try:
            resp = webpush(subscription_info=sub, data=payload,
                          vapid_private_key=priv_b64, vapid_claims=VAPID_CLAIMS, ttl=86400)
            result["sent"] += 1
            result["details"].append({"idx": i, "status": resp.status_code})
        except WebPushException as ex:
            status = ex.response.status_code if ex.response else 0
            result["errors"] += 1
            result["details"].append({"idx": i, "error": str(ex), "status": status})
            if status in (410, 404):
                subs.remove(sub)
                _save_subscribers(subs)
    return result

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "agents": len(AGENTS)}


@app.get("/api/agents")
async def api_agents():
    if _CACHE_READY:
        return _CACHE
    # Fallback: direct fetch if cache not ready
    tasks = [get_agent_stats(aid, info) for aid, info in AGENTS.items()]
    results = await asyncio.gather(*tasks)
    total_ram = sum(a["mem_limit"] for a in results if a["online"])
    used_ram = sum(a["mem_usage"] for a in results if a["online"])
    return {
        "agents": results,
        "totals": {
            "online": sum(1 for a in results if a["online"]),
            "total": len(results),
            "total_ram": total_ram,
            "used_ram": used_ram,
        }
    }


@app.get("/api/credits")
async def api_credits():
    if _CACHE_READY:
        return _CACHE["credits"]
    return {"total": 0, "used": 0, "remaining": 0, "percent_used": 0}


@app.get("/api/disk")
async def api_disk():
    """Uso de disco del host (cacheado 5 min)."""
    d = await get_host_disk()
    return {
        "total": d.get("total", 0), "used": d.get("used", 0), "free": d.get("free", 0),
        "percent": d.get("percent", 0),
        "total_h": _fmt_bytes(d.get("total", 0)), "used_h": _fmt_bytes(d.get("used", 0)),
        "free_h": _fmt_bytes(d.get("free", 0)),
    }


@app.get("/api/memory")
async def api_memory():
    """Uso de RAM del host (cacheado 15s)."""
    m = await get_host_memory()
    return {
        "total": m.get("total", 0), "used": m.get("used", 0), "free": m.get("free", 0),
        "percent": m.get("percent", 0),
        "total_h": _fmt_bytes(m.get("total", 0)), "used_h": _fmt_bytes(m.get("used", 0)),
        "free_h": _fmt_bytes(m.get("free", 0)),
    }


@app.get("/api/tools")
async def api_tools():
    """Uso de herramientas por agente (se llena con el cache, 5 min)."""
    return _CACHE.get("tools", {})


@app.get("/api/logs/{agent_id}")
async def api_logs(agent_id: str, lines: int = 200, which: str = "agent"):
    """Tail del log de un agente (agent.log por defecto, gateway.log con ?which=gateway)."""
    info = AGENTS.get(agent_id)
    if not info:
        return {"error": "agente desconocido"}
    try:
        n = max(10, min(int(lines), 2000))
    except Exception:
        n = 200
    fname = "gateway.log" if which == "gateway" else "agent.log"
    try:
        out = await exec_in_container(
            info["container"],
            f"tail -n {n} /home/hermes/.hermes/logs/{fname} 2>/dev/null || echo '(sin log disponible)'",
        )
        return {
            "agent_id": agent_id, "name": info["name"], "emoji": info["emoji"],
            "color": info["color"], "file": fname, "lines": out.split("\n"),
        }
    except Exception as e:
        return {"error": str(e), "agent_id": agent_id, "lines": []}


@app.get("/api/history")
async def api_history(limit: int = 8):
    """Get session history from all agents."""
    tasks = [get_session_history(aid, info["container"], limit) for aid, info in AGENTS.items()]
    results = await asyncio.gather(*tasks)

    output = {}
    for i, (aid, info) in enumerate(AGENTS.items()):
        output[aid] = {
            "name": info["name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "sessions": results[i],
        }
    return output


# ─── SSE Stream (all data, every 3s) ──────────────────────────────

@app.get("/api/stream")
async def stream_all(request: Request):
    """SSE stream that reads from in-memory cache — instant delivery."""
    async def event_generator():
        # Send immediate "connected" event
        yield "data: {\"connected\": true}\n\n"
        waited = 0
        # Wait for first cache fill (up to 20s)
        while not _CACHE_READY and waited < 20:
            await asyncio.sleep(0.5)
            waited += 0.5
        # Yield cached data immediately
        if _CACHE_READY:
            yield f"data: {json.dumps(_CACHE)}\n\n"
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(3)
            if _CACHE_READY:
                yield f"data: {json.dumps(_CACHE)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Serve static files
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.get("/")
async def serve_index():
    return FileResponse("/app/static/index.html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.get("/sw.js")
async def serve_sw():
    return FileResponse("/app/sw.js", media_type="application/javascript", headers={
        "Service-Worker-Allowed": "/",
        "Cache-Control": "no-cache",
    })


# Redirect old SW path so Brave doesn't register the stale one
@app.get("/static/sw.js")
async def old_sw_redirect():
    return FileResponse("/app/sw.js", media_type="application/javascript", headers={
        "Service-Worker-Allowed": "/",
        "Cache-Control": "no-cache",
    })


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("/app/static/favicon.svg")