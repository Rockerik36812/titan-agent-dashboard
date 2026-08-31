import asyncio
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
    "ts": 0,
}
_CACHE_READY = False
_PREV_ONLINE = {}


async def _update_cache():
    """Background task: refreshes all dashboard data in memory every 3s."""
    global _CACHE, _CACHE_READY, _PREV_ONLINE
    while True:
        try:
            # ── Agent stats ──
            agent_tasks = [get_agent_stats(aid, info) for aid, info in AGENTS.items()]
            agent_results = await asyncio.gather(*agent_tasks)
            total_ram = sum(a["mem_limit"] for a in agent_results if a["online"])
            used_ram = sum(a["mem_usage"] for a in agent_results if a["online"])

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
                "models": sorted(models_map.values(), key=lambda x: x["cost"], reverse=True),
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

            # ── Gateway ──
            gw_tasks = [get_gateway_health(info["container"]) for info in AGENTS.values()]
            gw_results = await asyncio.gather(*gw_tasks)
            gateways = {}
            for i, (aid, info) in enumerate(AGENTS.items()):
                g = gw_results[i]
                uptime = ""
                if g.get("start_time") and int(g["start_time"]) > 0:
                    secs = time.time() - int(g["start_time"])
                    hours, rem = divmod(int(secs), 3600)
                    mins = rem // 60
                    uptime = f"{hours}h {mins}m"
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

            # ── Auto Notify (push) ──
            for a in agent_results:
                aid = a["id"]
                was_online = _PREV_ONLINE.get(aid, True)
                if not a["online"] and was_online:
                    body = f"Agente fuera de línea"
                    asyncio.ensure_future(_send_push_notification(
                        title=f"⚠️ {a['emoji']} {a['name']} — fuera de línea",
                        body=body,
                        tag=f"offline-{aid}",
                        url="/",
                    ))
            _PREV_ONLINE = {a["id"]: a["online"] for a in agent_results}

            # ── Credits low ──
            if credits_data.get("remaining", 100) < 5 and credits_data.get("remaining", 0) > 0:
                asyncio.ensure_future(_send_push_notification(
                    title="💰 OpenRouter bajo",
                    body=f"${credits_data['remaining']:.2f} restantes de ${credits_data['total']:.2f}",
                    tag="credits-low",
                    url="/",
                ))

            # ── Update cache ──
            _CACHE = {
                "agents": agent_results,
                "totals": {"online": sum(1 for a in agent_results if a["online"]), "total": len(agent_results), "total_ram": total_ram, "used_ram": used_ram},
                "credits": credits_data, "stats": merged_stats, "analytics": analytics,
                "activity": feed[:10], "gateways": gateways, "history": history, "ts": time.time(),
            }
            _CACHE_READY = True
        except Exception:
            pass
        await asyncio.sleep(3)


@app.on_event("startup")
async def start_cache():
    asyncio.create_task(_update_cache())


async def exec_in_container(container_name: str, cmd: str) -> str:
    """Execute a command inside a Docker container and return stdout."""
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        result = container.exec_run(["sh", "-c", cmd], user="hermes")
        return result.output.decode() if result.output else ""
    except Exception as e:
        return f"ERROR: {e}"


async def exec_script(container_name: str, script: str) -> str:
    """Write a Python script via base64 + echo (safe quoting), then execute."""
    import base64
    b64 = base64.b64encode(script.encode()).decode()
    write_cmd = f"echo '{b64}' | base64 -d > /tmp/_dash_script.py"
    write_result = await exec_in_container(container_name, write_cmd)
    if write_result and "ERROR" in write_result:
        return write_result
    return await exec_in_container(container_name, "python3 /tmp/_dash_script.py")


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


# ─── NEW: Analytics ─────────────────────────────────────────────────

async def get_analytics(container_name: str) -> dict:
    """Get cost-over-time, model breakdown, and tool stats from one agent."""
    script = """import sqlite3, json
db = sqlite3.connect('/home/hermes/.hermes/state.db')

# Cost per day (last 30 days)
daily = db.execute(
    "SELECT date(started_at, 'unixepoch') as d, COALESCE(SUM(estimated_cost_usd), 0) "
    "FROM sessions WHERE started_at > strftime('%s', 'now', '-30 days') AND estimated_cost_usd > 0 "
    "GROUP BY d ORDER BY d"
).fetchall()

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
rows = db.execute(
    "SELECT id, title, last_activity_description, last_activity_at, estimated_cost_usd, "
    "message_count, started_at FROM sessions "
    "WHERE last_activity_description IS NOT NULL AND last_activity_description != '' "
    "ORDER BY last_activity_at DESC LIMIT {limit}"
).fetchall()
db.close()
print(json.dumps([{{
    'session_id': r[0],
    'title': r[1],
    'description': r[2],
    'timestamp': r[3],
    'cost_usd': round(r[4] or 0, 4),
    'message_count': r[5] or 0,
    'started_at': r[6],
}} for r in rows]))
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
    script = """import json
try:
    with open('/home/hermes/.hermes/gateway_state.json') as f:
        g = json.load(f)
    platforms = g.get('platforms', {})
    print(json.dumps({
        'gateway_state': g.get('gateway_state', 'unknown'),
        'start_time': g.get('start_time', 0),
        'active_agents': g.get('active_agents', 0),
        'platforms': {k: {'state': v.get('state', '?'), 'error': v.get('error_message')} for k, v in platforms.items()},
    }))
except FileNotFoundError:
    print(json.dumps({'gateway_state': 'no_state_file', 'start_time': 0, 'active_agents': 0, 'platforms': {}}))
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
        if g.get("start_time") and int(g["start_time"]) > 0:
            secs = time.time() - int(g["start_time"])
            hours, rem = divmod(int(secs), 3600)
            mins = rem // 60
            uptime = f"{hours}h {mins}m"

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

    payload = _json.dumps({"title": title, "body": body, "tag": tag, "url": url})

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
    """Save a push subscription from the browser."""
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

@app.on_event("startup")
async def startup():
    load_env()


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