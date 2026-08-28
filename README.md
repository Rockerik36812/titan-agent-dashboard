# 🚀 Titan Agent Dashboard

Dashboard en tiempo real para monitorear tus 3 agentes de Hermes (Titán, Hermes, Hermina).

## Features
- 🟢 Estado online/offline de cada agente
- 📊 CPU y RAM en vivo
- ⏱️ Uptime por agente
- 🔄 Gateway status
- 🕐 Última actividad
- 🌙 Dark mode
- ⚡ Actualización vía SSE (Server-Sent Events)

## APIs
- `GET /` — Dashboard web
- `GET /api/agents` — Estado actual de todos los agentes
- `GET /api/agents/stream` — SSE en tiempo real
- `GET /api/memory` — Memoria del sistema
- `GET /health` — Health check

## Requisitos
- Docker socket montado en el contenedor
- Red Docker compartida con los agentes o acceso via `docker exec`