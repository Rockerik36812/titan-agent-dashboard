import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import docker
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Agent Dashboard")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Docker client
try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None

AGENTS = [
    {
        "id": "titan",
        "name": "Titán",
        "emoji": "🚀",
        "color": "#f97316",
        "container": "hermes-agent-gludih2hknhumvx9ufx0bdql",
        "is_self": True,
    },
    {
        "id": "hermes",
        "name": "Hermes",
        "emoji": "🤖",
        "color": "#3b82f6",
        "container": "hermes-agent-v6y8md5qijrltg1rm34e90tj",
        "is_self": False,
    },
    {
        "id": "hermina",
        "name": "Hermina",
        "emoji": "💜",
        "color": "#a855f7",
        "container": "hermes-agent-kqzoxrig0pspua7pymgdlaon",
        "is_self": False,
    },
]


def format_uptime(seconds):
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if secs: parts.append(f"{secs}s")
    return " ".join(parts) if parts else "< 1s"


def get_container_stats(container_name):
    """Get container stats using Docker SDK."""
    try:
        if not docker_client:
            return {"online": False, "error": "no docker"}

        try:
            container = docker_client.containers.get(container_name)
        except docker.errors.NotFound:
            return {"online": False, "error": "not found"}

        if container.status != "running":
            return {"online": False, "error": f"status: {container.status}"}

        # Container info
        attrs = container.attrs
        started_at = attrs["State"].get("StartedAt", "")
        if started_at:
            try:
                started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime_seconds = (datetime.now(timezone.utc) - started).total_seconds()
            except Exception:
                uptime_seconds = 0
        else:
            uptime_seconds = 0

        image = attrs["Config"].get("Image", "?")[:40]
        container_id = container.short_id

        # Live stats
        cpu = 0.0
        mem_used_str = "-"
        mem_limit_str = "-"
        mem_pct = 0.0

        try:
            stats = container.stats(stream=False)
            # CPU calculation
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            num_cpus = stats["cpu_stats"].get("online_cpus", 1)
            if system_delta > 0 and cpu_delta > 0:
                cpu = (cpu_delta / system_delta) * num_cpus * 100.0

            # Memory
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            if mem_limit > 0:
                mem_pct = (mem_usage / mem_limit) * 100.0

            # Format memory
            def fmt_bytes(b):
                b = int(b)
                if b >= 1073741824:
                    return f"{b/1073741824:.1f}GiB"
                elif b >= 1048576:
                    return f"{b/1048576:.1f}MiB"
                elif b >= 1024:
                    return f"{b/1024:.1f}KiB"
                return f"{b}B"

            mem_used_str = fmt_bytes(mem_usage)
            mem_limit_str = fmt_bytes(mem_limit)
        except Exception as e:
            pass

        return {
            "online": True,
            "container_id": container_id,
            "image": image,
            "uptime": format_uptime(uptime_seconds),
            "uptime_seconds": int(uptime_seconds),
            "cpu": round(cpu, 1),
            "mem_used": mem_used_str,
            "mem_limit": mem_limit_str,
            "mem_pct": round(mem_pct, 1),
            "status": container.status,
        }
    except Exception as e:
        return {"online": False, "error": str(e)}


def get_gateway_status(container_name):
    """Get gateway status via Docker exec."""
    try:
        if not docker_client:
            return {"gateway": "unknown", "online": False}
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            return {"gateway": "offline", "online": False}
        result = container.exec_run(["/command/s6-svstat", "/run/service/gateway-default"])
        if result.exit_code == 0:
            output = result.output.decode().strip()
            return {"gateway": output, "online": True}
        return {"gateway": "unknown", "online": False}
    except Exception:
        return {"gateway": "unknown", "online": False}


def get_last_session(container_name):
    """Get last session info via Docker exec."""
    try:
        if not docker_client:
            return {}
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            return {}

        script = """
import json, datetime
from pathlib import Path
p = Path('/home/hermes/.hermes/sessions/sessions.json')
if p.exists():
    data = json.loads(p.read_text())
    sessions = data.get('sessions', {})
    if sessions:
        newest_id = max(sessions.keys(), key=lambda k: sessions[k].get('started_at', 0))
        s = sessions[newest_id]
        started = s.get('started_at', 0)
        platform = s.get('platform', 'unknown')
        model = s.get('model', 'unknown')
        ended = s.get('ended_at', 0)
        started_str = datetime.datetime.fromtimestamp(started).strftime('%H:%M %d/%m') if started else 'unknown'
        status = 'En curso' if not ended else 'Completado'
        print(json.dumps({'session_id': newest_id[:16], 'started': started_str, 'platform': platform, 'model': model, 'status': status}))
"""
        result = container.exec_run(["python3", "-c", script])
        if result.exit_code == 0:
            out = result.output.decode().strip()
            if out:
                return json.loads(out)
        return {}
    except Exception:
        return {}


def get_agent_state(agent):
    """Get full state for a single agent."""
    container = agent["container"]
    stats = get_container_stats(container)

    if not stats.get("online"):
        return {
            "id": agent["id"],
            "name": agent["name"],
            "emoji": agent["emoji"],
            "color": agent["color"],
            "online": False,
            "uptime": "-",
            "cpu": 0,
            "mem_used": "-",
            "mem_limit": "-",
            "mem_pct": 0,
            "gateway": "offline",
            "last_session": {},
            "last_active": "-",
        }

    gateway = get_gateway_status(container)
    session = get_last_session(container)

    return {
        "id": agent["id"],
        "name": agent["name"],
        "emoji": agent["emoji"],
        "color": agent["color"],
        "online": True,
        "uptime": stats.get("uptime", "-"),
        "uptime_seconds": stats.get("uptime_seconds", 0),
        "cpu": stats.get("cpu", 0),
        "mem_used": stats.get("mem_used", "-"),
        "mem_limit": stats.get("mem_limit", "-"),
        "mem_pct": stats.get("mem_pct", 0),
        "gateway": gateway.get("gateway", "unknown"),
        "container_id": stats.get("container_id", ""),
        "image": stats.get("image", ""),
        "last_session": session,
        "last_active": session.get("started", "-"),
    }


@app.get("/api/agents")
async def get_agents():
    results = []
    for agent in AGENTS:
        results.append(get_agent_state(agent))
    return {"agents": results}


async def generate_agent_events():
    while True:
        results = []
        for agent in AGENTS:
            results.append(get_agent_state(agent))
        data = json.dumps({"agents": results})
        yield f"data: {data}\n\n"
        await asyncio.sleep(3)


@app.get("/api/agents/stream")
async def stream_agents():
    return StreamingResponse(
        generate_agent_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "agents": len(AGENTS)}


@app.get("/api/memory")
async def memory():
    import psutil
    mem = psutil.virtual_memory()
    return {
        "total": round(mem.total / (1024**3), 1),
        "used": round(mem.used / (1024**3), 1),
        "free": round(mem.available / (1024**3), 1),
        "percent": mem.percent,
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    html = Path("static/index.html").read_text()
    return HTMLResponse(html)