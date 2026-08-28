import asyncio
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import docker
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
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
    """Load OpenRouter management key from env var or .env file."""
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


async def exec_in_container(container_name: str, cmd: str) -> str:
    """Execute a command inside a Docker container and return stdout."""
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        result = container.exec_run(cmd, user="hermes")
        return result.output.decode() if result.output else ""
    except Exception as e:
        return f"ERROR: {e}"


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
        code = (
            "import sqlite3, json\n"
            "db = sqlite3.connect('/home/hermes/.hermes/state.db')\n"
            f"rows = db.execute('SELECT id, title, started_at, ended_at, end_reason, message_count, tool_call_count, estimated_cost_usd, last_activity_description FROM sessions WHERE title IS NOT NULL AND title != ? ORDER BY started_at DESC LIMIT {limit}', ('',)).fetchall()\n"
            "db.close()\n"
            "print(json.dumps([{'id': r[0], 'title': r[1], 'started_at': r[2], 'ended_at': r[3], 'end_reason': r[4], 'message_count': r[5], 'tool_call_count': r[6], 'cost_usd': r[7], 'last_activity': r[8]} for r in rows]))\n"
        )
        result = await exec_in_container(container_name, f'python3 -c "{code}"')
        data = json.loads(result)
        return data
    except Exception as e:
        return []


@app.on_event("startup")
async def startup():
    load_env()


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "agents": len(AGENTS)}


@app.get("/api/agents")
async def api_agents():
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
    """Fetch OpenRouter credits from management API."""
    if not OPENROUTER_MGMT_KEY:
        return {"error": "No management key configured", "total": 0, "used": 0, "remaining": 0}

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/credits",
            headers={"Authorization": f"Bearer {OPENROUTER_MGMT_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            total = float(data.get("data", {}).get("total_credits", 0))
            usage = float(data.get("data", {}).get("total_usage", 0))
            return {
                "total": round(total, 2),
                "used": round(usage, 2),
                "remaining": round(total - usage, 2),
                "percent_used": round((usage / total) * 100, 1) if total > 0 else 0,
            }
    except Exception as e:
        return {"error": str(e), "total": 0, "used": 0, "remaining": 0}


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


@app.get("/api/agents/stream")
async def stream_agents(request: Request):
    """SSE stream for real-time agent updates."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            tasks = [get_agent_stats(aid, info) for aid, info in AGENTS.items()]
            results = await asyncio.gather(*tasks)
            total_ram = sum(a["mem_limit"] for a in results if a["online"])
            used_ram = sum(a["mem_usage"] for a in results if a["online"])
            data = {
                "agents": results,
                "totals": {
                    "online": sum(1 for a in results if a["online"]),
                    "total": len(results),
                    "total_ram": total_ram,
                    "used_ram": used_ram,
                }
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Serve static files
app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")