import os, json, time, asyncio, subprocess, sqlite3, itertools
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# ─── Config ───────────────────────────────────────────────────────────
# agent‑dashboard static build — deployed on Coolify
# uses Docker socket for introspection

MANAGEMENT_KEY = os.environ.get("OPENROUTER_MANAGEMENT_KEY", "")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DOCKER_SOCKET = "/var/run/docker.sock"

# ─── Agent Registry ───────────────────────────────────────────────────
AGENTS = {
    "titan": {"name": "Titán", "emoji": "🚀", "color": "#00d4ff", "container": "hermes-agent-gludih2hknhumvx9ufx0bdql"},
    "hermes": {"name": "Hermes", "emoji": "🤖", "color": "#a855f7", "container": "hermes-agent-v6y8md5qijrltg1rm34e90tj"},
    "hermina": {"name": "Hermina", "emoji": "💜", "color": "#ec4899", "container": "hermes-agent-kqzoxrig0pspua7pymgdlaon"},
}

# ─── Helpers ──────────────────────────────────────────────────────────


async def exec_script(container: str, script: str) -> str:
    """Run a Python script inside a container via docker exec."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", "-i", container, "python3", "-c", script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    if proc.returncode != 0:
        raise RuntimeError(f"exec_script failed: {stderr.decode()[:200]}")
    return stdout.decode().strip()


async def docker_inspect(container: str) -> dict:
    """Inspect a Docker container and return parsed JSON."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "inspect", container,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    if proc.returncode != 0:
        return {}
    return json.loads(stdout.decode())[0] if stdout else {}


async def docker_stats(container: str) -> dict:
    """Get container CPU and memory stats via docker stats (no‑stream)."""
    proc = await asyncio.create_subprocess_exec(
        "docker", "stats", "--no-stream", container,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    if proc.returncode != 0 or not stdout:
        return {"cpu": 0, "mem_pct": 0, "mem_usage": 0, "mem_limit": 0}
    lines = stdout.decode().strip().split("\n")
    # Skip header, get second line
    if len(lines) < 2:
        return {"cpu": 0, "mem_pct": 0, "mem_usage": 0, "mem_limit": 0}
    parts = [p for p in lines[1].split() if p]
    if len(parts) < 8:
        return {"cpu": 0, "mem_pct": 0, "mem_usage": 0, "mem_limit": 0}
    try:
        cpu = parts[2].replace("%", "")
        mem_pct = parts[6].replace("%", "")
        raw_mem_usage = parts[3]
        raw_mem_limit = parts[5]
        mem_usage = parse_mem(raw_mem_usage)
        mem_limit = parse_mem(raw_mem_limit)
        return {
            "cpu": float(cpu) if cpu else 0.0,
            "mem_pct": float(mem_pct) if mem_pct else 0.0,
            "mem_usage": mem_usage,
            "mem_limit": mem_limit,
        }
    except (ValueError, IndexError):
        return {"cpu": 0, "mem_pct": 0, "mem_usage": 0, "mem_limit": 0}


def parse_mem(raw: str) -> int:
    """Convert docker memory string (e.g. '12.5GiB' or '1.2GiB') to bytes."""
    raw = raw.strip()
    if raw.endswith("GiB"):
        return int(float(raw.replace("GiB", "")) * 1024 ** 3)
    if raw.endswith("MiB"):
        return int(float(raw.replace("MiB", "")) * 1024 ** 2)
    if raw.endswith("KiB"):
        return int(float(raw.replace("KiB", "")) * 1024)
    try:
        return int(raw)
    except ValueError:
        return 0


async def container_uptime_seconds(container: str) -> int:
    """Get the real container uptime in seconds from Docker."""
    try:
        info = await docker_inspect(container)
        if not info:
            return 0
        created_raw = info.get("State", {}).get("StartedAt", "")
        started = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - started
        return int(delta.total_seconds())
    except:
        return 0


# ─── FASTAPI ──────────────────────────────────────────────────────────

app = FastAPI(title="Panel de Agentes", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── API: Agents (live stats) ─────────────────────────────────────────

@app.get("/api/agents")
async def api_agents():
    """Live resource usage per agent."""
    tasks = []
    for info in AGENTS.values():
        tasks.append(docker_stats(info["container"]))
    stats = await asyncio.gather(*tasks)

    agents = []
    total_ram = 0
    used_ram = 0
    for i, (aid, info) in enumerate(AGENTS.items()):
        s = stats[i]
        uptime = ""
        try:
            secs = await container_uptime_seconds(info["container"])
            if secs:
                hours, rem = divmod(secs, 3600)
                mins = rem // 60
                uptime = f"{hours}h {mins}m"
        except:
            pass
        online = s["cpu"] > 0 or s["mem_pct"] > 0
        agents.append({
            "id": aid,
            "name": info["name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "online": online,
            "cpu": s["cpu"],
            "mem_usage": s["mem_usage"],
            "mem_limit": s["mem_limit"],
            "mem_pct": s["mem_pct"],
            "uptime": uptime,
            "gateway": "unknown",
            "container": info["container"],
        })
        total_ram += s["mem_limit"]
        used_ram += s["mem_usage"]

    return {
        "agents": agents,
        "totals": {
            "online": sum(1 for a in agents if a["online"]),
            "total": len(agents),
            "total_ram": total_ram,
            "used_ram": used_ram,
        },
    }


# ─── API: Credits / OpenRouter ───────────────────────────────────────

@app.get("/api/credits")
async def api_credits():
    """Fetch OpenRouter credits via management API."""
    if not MANAGEMENT_KEY or MANAGEMENT_KEY == "sk-or-...81b2":
        return {"error": "No management key configured", "total": 0, "used": 0, "remaining": 0}
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s",
            "-H", f"Authorization: Bearer {MANAGEMENT_KEY}",
            "https://openrouter.ai/api/v1/auth/key",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        data = json.loads(stdout.decode())
        if "data" in data and "limits" in data["data"]:
            total = data["data"]["limits"].get("monthly_dollar_limit", 50)
            used = data["data"]["usage"]
            remaining = round(total - used, 2)
            return {"total": total, "used": round(used, 2), "remaining": remaining}
        return {"error": "Unexpected response", "total": 0, "used": 0, "remaining": 0}
    except Exception as e:
        return {"error": str(e), "total": 0, "used": 0, "remaining": 0}


# ─── API: Gateway Health ─────────────────────────────────────────────

async def get_gateway_health(container_name: str) -> dict:
    """Get gateway health from an agent's gateway_state.json."""
    script = """import json, subprocess, os
try:
    with open('/home/hermes/.hermes/gateway_state.json') as f:
        g = json.load(f)
    pid = g.get('pid', 0)
    uptime_secs = 0
    if pid and pid > 0:
        try:
            r = subprocess.run(['ps', '-o', 'etimes=', '-p', str(pid)], capture_output=True, text=True, timeout=3)
            uptime_secs = int(r.stdout.strip())
        except:
            uptime_secs = 0
    platforms = g.get('platforms', {})
    print(json.dumps({
        'gateway_state': g.get('gateway_state', 'unknown'),
        'start_time': uptime_secs,
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
            secs = int(g["start_time"])
            hours, rem = divmod(secs, 3600)
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


# ─── API: Epic Stats ─────────────────────────────────────────────────

async def get_epic_stats(container_name: str) -> dict:
    """Get aggregate stats and first activity date from one agent."""
    script = """import sqlite3, json, time
db = sqlite3.connect('/home/hermes/.hermes/state.db')
total_sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
total_cost = db.execute("SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM sessions").fetchone()[0]
total_messages = db.execute("SELECT COALESCE(SUM(message_count), 0) FROM sessions").fetchone()[0]
first = db.execute("SELECT MIN(started_at) FROM sessions").fetchone()[0]
first_date = ""
if first:
    first_date = time.strftime('%Y-%m-%d', time.gmtime(first))
db.close()
print(json.dumps({'total_sessions': total_sessions, 'total_cost': round(total_cost, 2), 'total_messages': total_messages, 'first_date': first_date}))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except:
        return {"total_sessions": 0, "total_cost": 0, "total_messages": 0, "first_date": ""}


@app.get("/api/stats")
async def api_stats():
    """Aggregate stats for all agents."""
    tasks = [get_epic_stats(info["container"]) for info in AGENTS.values()]
    results = await asyncio.gather(*tasks)

    total = {"sessions": 0, "cost": 0, "messages": 0, "first_date": ""}
    first_dates = []
    output = {}
    for i, (aid, info) in enumerate(AGENTS.items()):
        s = results[i]
        output[aid] = s
        total["sessions"] += s["total_sessions"]
        total["cost"] += s["total_cost"]
        total["messages"] += s["total_messages"]
        if s["first_date"]:
            first_dates.append(s["first_date"])
    total["first_date"] = min(first_dates) if first_dates else ""
    return {"agents": output, "total": total}


# ─── API: Analytics (cost per day, models, tools) ────────────────────

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
    "COALESCE(SUM(estimated_cost_usd), 0) FROM sessions "
    "WHERE model IS NOT NULL AND model != '' AND api_call_count > 0 "
    "GROUP BY model ORDER BY COUNT(*) DESC"
).fetchall()

db.close()
print(json.dumps({
    'daily': [{'date': r[0], 'cost': r[1]} for r in daily],
    'models': [{'name': r[0], 'calls': r[1], 'input_tokens': r[2], 'output_tokens': r[3], 'cost': r[4]} for r in models],
}))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except:
        return {"daily": [], "models": []}


@app.get("/api/analytics")
async def api_analytics():
    """Combined analytics from all agents."""
    tasks = [get_analytics(info["container"]) for info in AGENTS.values()]
    results = await asyncio.gather(*tasks)

    combined_daily = {}
    combined_models = {}
    for r in results:
        for d in r.get("daily", []):
            date = d["date"]
            combined_daily[date] = combined_daily.get(date, 0) + d["cost"]
        for m in r.get("models", []):
            name = m["name"]
            if name not in combined_models:
                combined_models[name] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0}
            combined_models[name]["calls"] += m["calls"]
            combined_models[name]["input_tokens"] += m["input_tokens"]
            combined_models[name]["output_tokens"] += m["output_tokens"]
            combined_models[name]["cost"] += m["cost"]

    daily_list = [{"date": d, "cost": round(c, 4)} for d, c in sorted(combined_daily.items())]
    models_list = [{"name": n, **m} for n, m in sorted(combined_models.items(), key=lambda x: x[1]["calls"], reverse=True)]

    # Titan Score
    total_cost = sum(d["cost"] for d in daily_list)
    total_calls = sum(m["calls"] for m in models_list)
    days_active = len(daily_list)
    titan_score = round((days_active * 10) + (total_calls * 0.5) + max(0, 100 - total_cost * 2), 0)

    return {"daily": daily_list, "models": models_list, "titan_score": titan_score}


# ─── API: Activity Feed ──────────────────────────────────────────────

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
print(json.dumps([
    {{'session_id': r[0], 'title': r[1], 'description': r[2], 'timestamp': r[3], 'cost': r[4], 'messages': r[5], 'started_at': r[6]}}
    for r in rows if r[3]]))
"""
    try:
        result = await exec_script(container_name, script)
        return json.loads(result)
    except:
        return []


@app.get("/api/history")
async def api_history():
    """Recent activity for all agents."""
    tasks = [get_recent_activity(info["container"]) for info in AGENTS.values()]
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
    return feed[:10]


# ─── API: History with limit parameter ───────────────────────────────

@app.get("/api/history/{limit}")
async def api_history_with_limit(limit: int = 10):
    """Recent activity for all agents with configurable limit."""
    limit = min(max(limit, 1), 50)
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


# ─── API: SSE Stream ─────────────────────────────────────────────────

@app.get("/api/stream")
async def api_stream():
    """Unified SSE endpoint that pushes all data (agents, credits, stats, analytics, activity, gateways, history) every N seconds."""

    INTERVAL = 3.0

    async def event_stream():
        while True:
            try:
                agents_task = asyncio.create_task(api_agents())
                credits_task = asyncio.create_task(api_credits())
                stats_task = asyncio.create_task(api_stats())
                analytics_task = asyncio.create_task(api_analytics())
                activity_task = asyncio.create_task(api_history())
                gateway_task = asyncio.create_task(api_gateway())

                done, _ = await asyncio.wait(
                    [agents_task, credits_task, stats_task, analytics_task, activity_task, gateway_task],
                    timeout=4.0,
                )

                data = {}
                for task in done:
                    result = task.result()
                    # identify task by its coroutine name
                    coro_name = task.get_coro().__name__ if hasattr(task, 'get_coro') else ''
                    if hasattr(task, '_coro'):
                        coro = task._coro
                        coro_name = coro.__name__ if hasattr(coro, '__name__') else ''

                    if 'api_agents' in coro_name:
                        data["agents"] = result.get("agents", [])
                        data["totals"] = result.get("totals", {})
                    elif 'api_credits' in coro_name:
                        data["credits"] = result
                    elif 'api_stats' in coro_name:
                        data["stats"] = result
                    elif 'api_analytics' in coro_name:
                        data["analytics"] = result
                    elif 'api_history' in coro_name:
                        data["activity"] = result
                    elif 'api_gateway' in coro_name:
                        data["gateway"] = result

                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(INTERVAL)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── Serve HTML ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "agents": len(AGENTS)}


@app.get("/")
async def index():
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return HTMLResponse(f.read())


# ─── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8999, reload=False)