# 🚀 Titan Agent Dashboard

Panel en tiempo real para ver el estado de mis 3 agentes de Hermes (**Titán**, **Hermina** y **Hermes**) desde el celular o la PC, sin entrar por SSH.

- **Producción:** https://dash.erikservicios.click (login obligatorio)
- **Health check público:** `GET /health` → `{"status":"ok","timestamp":"…","agents":3}`
- Corre en un contenedor con el **docker socket montado**: de ahí saca el estado de los agentes y puede reiniciarlos.

---

## ✨ Features

### 🤖 Agentes
- Estado online/offline, CPU, RAM, uptime y última actividad de cada agente, en vivo.
- **Reiniciar el contenedor** de un agente desde su tarjeta (con confirmación; al reiniciar vuelve su gateway).
- Modal de detalle por agente, con uso de herramientas y **tail de sus logs** (`agent.log`, o `gateway.log` con `?which=gateway`).

### 🏆 Estadísticas Épicas
- Mensajes, sesiones, tokens, costo acumulado y días activos.
- **Titan Score** con tooltip que explica cómo se calcula.

### 💰 OpenRouter
- Crédito total, usado y restante, con barra de porcentaje.
- **Proyección de días** de crédito al ritmo de gasto actual.
- Gráfica de costo diario.

### 💾 Sistema y 2º servidor
- Disco y RAM del host, con alerta cuando se acercan al límite.
- Badge con el **% de disco del servidor de clientes** (2º VPS, leído por Tailscale SSH; cacheado 5 min).

### 🔴 Gateways · 🔧 Herramientas · 💬 Actividad · 📊 Analíticas
- Salud de los gateways de cada agente.
- Uso de herramientas por agente.
- Feed de actividad reciente (mezclado por hora) y analíticas agregadas.

### 🔔 Web Push
- Notificaciones al celular/navegador (service worker `sw.js` + VAPID), suscripción por dispositivo y botón de prueba.

### 🎨 Tema visual (3 estados)
Un solo botón en el header cicla los temas; la elección se recuerda en `localStorage`.

| Tema | Cómo se ve |
| --- | --- |
| **Clásico** | Fondo plano y tarjetas sólidas |
| **Aurora** | Aurora animada de fondo, tarjetas de vidrio con refracción |
| **Ultra Glass** | Base casi negra, auroras nocturnas suaves y tarjetas de cristal ahumado con bisel de luz especular |

Los tres respetan `prefers-reduced-motion` (sin animaciones si el sistema lo pide).

### 🔐 Acceso
- Login propio (un solo usuario dueño) con cookie de sesión firmada: **12 h**, o **7 días** con "recordarme".
- **Todo requiere sesión** salvo: `/login`, `/api/auth/*`, `/health`, `/static/*`, `/sw.js` y `/favicon.ico`.
- Sin sesión: `401` en JSON para las APIs y redirect `302` al login para el resto (un `/` en 302 es correcto, no es error).
- Contraseña con salt + hash, mínimo 8 caracteres.

---

## 🔌 API

Todas las rutas `/api/*` piden sesión (responden `401` en JSON sin ella).

| Método | Ruta | Qué devuelve |
| --- | --- | --- |
| GET | `/api/agents` | Estado actual de los 3 agentes |
| POST | `/api/agents/{agent_id}/restart` | Reinicia el contenedor del agente |
| GET | `/api/stream` | **SSE** en vivo (lee del cache en memoria: entrega instantánea) |
| GET | `/api/stats` | Estadísticas épicas agregadas |
| GET | `/api/analytics` | Analíticas por agente |
| GET | `/api/activity` | Actividad reciente, mezclada por hora |
| GET | `/api/gateway` | Salud de los gateways |
| GET | `/api/credits` | Crédito disponible y proyección |
| GET | `/api/disk` | Disco del host (cache 5 min) |
| GET | `/api/memory` | RAM del host (cache 15 s) |
| GET | `/api/remote` | Disco y RAM del 2º VPS (cache 5 min) |
| GET | `/api/tools` | Uso de herramientas por agente |
| GET | `/api/logs/{agent_id}` | Tail del log (`?which=gateway` para el otro) |
| GET | `/api/history` | Historial de sesiones de los agentes |
| GET | `/api/auth/status` | ¿Ya hay contraseña configurada? |
| POST | `/api/auth/setup` | Crea la contraseña (solo la primera vez) |
| POST | `/api/auth/login` | Entrar |
| POST | `/api/auth/logout` | Salir |
| GET | `/api/push/vapid-key` | Llave pública VAPID |
| POST | `/api/push/subscribe` | Guarda la suscripción de este dispositivo |
| POST | `/api/push/unsubscribe` | Quita la suscripción |
| POST | `/api/push/test` | Manda una notificación de prueba |
| GET | `/health` | Health check público |
| GET | `/` · `/login` · `/sw.js` · `/favicon.ico` | Panel, login y estáticos |

---

## 🧱 Requisitos

- Docker con el **socket montado** en el contenedor del panel.
- **Red Docker compartida** con los agentes (los lee por `docker exec`).
- Acceso **SSH por Tailscale** al 2º VPS (solo para el badge de disco de clientes).
- Python 3.13 y las dependencias de `requirements.txt` (FastAPI, uvicorn, docker, psutil, pywebpush, py-vapid, cryptography).

## 🚀 Despliegue

Coolify construye la imagen **desde este repo** (rama `main`). Un push **no despliega solo**: el deploy se dispara desde el panel de Coolify.
La app escucha en `0.0.0.0:8999` (uvicorn) y el contenedor necesita el docker socket montado.

```bash
docker compose up -d                     # levantar el panel localmente
pip install -r requirements.txt          # dependencias
```

> ⚠️ `docker-compose.yml` quedó desactualizado (apunta a una imagen de `ghcr.io` y al puerto `8000`): el despliegue real es Coolify desde el repo y la app escucha en `8999`. Pendiente alinearlo.

## ✅ Cómo saber si el deploy entró

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://dash.erikservicios.click/health   # 200
curl -s https://dash.erikservicios.click/static/style.css | md5sum
md5sum static/style.css                  # deben coincidir
```

## 🗂️ Estructura

- `main.py` — backend completo: auth, APIs, SSE, `docker exec` a los agentes y Web Push.
- `static/index.html` — el panel · `static/login.html` — el login · `static/style.css` — los 3 temas · `static/app.js` — SSE, tarjetas, tema y notificaciones.
- `sw.js` — service worker de las notificaciones push.
- `Dockerfile` / `docker-compose.yml` — despliegue.
- `HANDOFF.md` — estado del proyecto y siguiente paso · `.handoff/log.md` — bitácora de relevos · `AGENTS.md` — protocolo para cuando otro agente trabaja aquí.
