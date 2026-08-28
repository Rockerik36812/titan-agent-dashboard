import asyncio
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import docker
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Agent Dashboard")

# Mount static files
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
        "network": "gludih2hknhumvx9ufx0bdql",
        "is_self": True,
    },
    {
        "id": "hermes",
        "name": "Hermes",
        "emoji": "🤖",
        "color": "#3b82f6",
        "container": "hermes-agent-v6y8md5qijrltg1rm34e90tj",
        "network": "v6y8md5qijrltg1rm34e90tj",
        "is_self": False,
    },
    {
        "id": "hermina",
        "name": "Hermina",
        "emoji": "💜",
        "color": "#a855f7",
        "container": "hermes-agent-kqzoxrig0pspua7pymgdlaon",
        "network": "kqzoxrig0pspua7pymgdlaon",
        "is_self": False,
    },
]


def format_uptime(seconds):
    """Format seconds into human-readable uptime."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "< 1s"


def get_container_stats(container_name):
    """Get Docker container stats via docker ps + docker stats."""
    try:
        # Basic info
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}",
             "--format", "{{.Status}}|{{.CreatedAt}}|{{.Image}}|{{.ID}}|{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        parts = result.stdout.strip().split("|")
        if len(parts) < 5 or not parts[0]:
            return {"online": False}

        status_str = parts[0]
        created_at = parts[1]
        image = parts[2][:40]
        container_id = parts[3]

        # Parse uptime from status
        uptime_seconds = 0
        if "up" in status_str.lower():
            # Try to get uptime via docker inspect
            inspect = subprocess.run(
                ["docker", "inspect", container_id, "--format", "{{.State.StartedAt}}"],
                capture_output=True, text=True, timeout=5
            )
            started_str = inspect.stdout.strip()
            if started_str:
                try:
                    started = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
                    uptime_seconds = (datetime.now(timezone.utc) - started).total_seconds()
                except Exception:
                    pass

        # Get live stats
        cpu = 0.0
        mem_used = 0
        mem_limit = 0
        mem_pct = 0.0

        stats_result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}", container_id],
            capture_output=True, text=True, timeout=5
        )
        stats_line = stats_result.stdout.strip()
        if stats_line and "|" in stats_line:
            parts = stats_line.split("|")
            cpu_str = parts[0].replace("%", "").strip()
            cpu = float(cpu_str) if cpu_str else 0.0
            mem_usage = parts[1] if len(parts) > 1 else ""
            mem_pct_str = parts[2].replace("%", "").strip() if len(parts) > 2 else "0"
            mem_pct = float(mem_pct_str) if mem_pct_str else 0.0

            # Parse mem usage string like "125.4MiB / 7.731GiB"
            if "/" in mem_usage:
                mem_parts = mem_usage.split("/")
                mem_used = mem_parts[0].strip()
                mem_limit = mem_parts[1].strip()

        return {
            "online": True,
            "container_id": container_id[:12],
            "image": image,
            "uptime": format_uptime(uptime_seconds),
            "uptime_seconds": int(uptime_seconds),
            "cpu": round(cpu, 1),
            "mem_used": mem_used,
            "mem_limit": mem_limit,
            "mem_pct": round(mem_pct, 1),
            "status": status_str[:50],
        }
    except subprocess.TimeoutExpired:
        return {"online": False, "error": "timeout"}
    except Exception as e:
        return {"online": False, "error": str(e)}


def get_gateway_status(container_name):
    """Get gateway status and session info via docker exec."""
    try:
        result = subprocess.run(
            ["docker", "exec", container_name,
             "/command/s6-svstat", "/run/service/gateway-default"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            return {"gateway": output, "online": True}
        return {"gateway": "unknown", "online": False}
    except Exception:
        return {"gateway": "unknown", "online": False}


def get_last_session(container_name):
    """Get last session activity via docker exec."""
    try:
        # Try to get the last session
        result = subprocess.run(
            ["docker", "exec", container_name,
             "python3", "-c", """
import json
from pathlib import Path

sessions_path = Path('/home/hermes/.hermes/sessions/sessions.json')
if sessions_path.exists():
    data = json.loads(sessions_path.read_text())
    sessions = data.get('sessions', {})
    if sessions:
        # Find most recent
        newest_id = max(sessions.keys(), key=lambda k: sessions[k].get('started_at', 0))
        s = sessions[newest_id]
        started = s.get('started_at', 0)
        ended = s.get('ended_at', 0)
        platform = s.get('platform', 'unknown')
        model = s.get('model', 'unknown')
        import datetime
        started_str = datetime.datetime.fromtimestamp(started).strftime('%H:%M %d/%m') if started else 'unknown'
        print(f'{{\\"session_id\\": \\"{newest_id[:16]}\\", \\"started\\": \\"{started_str}\\", \\"platform\\": \\"{platform}\\", \\"model\\": \\"{model}\\"}}')
    else:
        print('{}')
else:
    print('{}')
"""],
            capture_output=True, text=True, timeout=5
        )
        out = result.stdout.strip()
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
    """Get all agents' current state."""
    results = []
    for agent in AGENTS:
        results.append(get_agent_state(agent))
    return {"agents": results}


async def generate_agent_events():
    """SSE generator for real-time updates."""
    while True:
        results = []
        for agent in AGENTS:
            results.append(get_agent_state(agent))
        data = json.dumps({"agents": results})
        yield f"data: {data}\n\n"
        await asyncio.sleep(3)


@app.get("/api/agents/stream")
async def stream_agents():
    """SSE endpoint for real-time streaming."""
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
    """Health check."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat(), "agents": len(AGENTS)}


@app.get("/api/memory")
async def memory():
    """System memory info."""
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
    """Serve the dashboard."""
    html = Path("static/index.html").read_text()
    return HTMLResponse(html)