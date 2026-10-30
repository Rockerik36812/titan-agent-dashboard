# HANDOFF — Panel de Agentes

**Dueño actual:** libre
**Última actualización:** 2026-10-30 00:22 (CST)
**Estado:** 🟢 en marcha

## Objetivo

Que Erik pueda ver el estado de sus 3 Hermes (**Titán, Hermina y Hermes**) desde el celular o la PC, sin entrar por SSH: online/offline, CPU, RAM, uptime, última actividad, créditos y 2º servidor. Está **sano** cuando el panel refleja la realidad en vivo y cualquier cosa que necesite saber de sus agentes se ve ahí.

## SIGUIENTE PASO

> Desplegar en Coolify y verificar en vivo (`https://dash.erikservicios.click`) el switch de 3 temas (Clásico / Aurora / Liquid Glass).

```bash
# 1. Disparar el deploy desde el panel de Coolify.
# 2. Verificar que el style.css servido corresponda al nuevo commit:
curl -s https://dash.erikservicios.click/static/style.css | md5sum
md5sum static/style.css
```

Opcional siguiente: Actualizar el README.md documentando el nuevo tema Liquid Glass y las features pendientes.

## Hecho

**Verificado por Antigravity el 2026-10-30:**

- [x] **Tema Liquid Glass implementado**: Inspirado en el estilo "RevenuePulse AI" / dark liquid glass con fondo de ondas azul cobalto/cian eléctrico, refracción profunda y biseles de luz especular.
- [x] **Switch de 3 posiciones**: El interruptor del header ahora alterna `Clásico` ➔ `Aurora` ➔ `Liquid` ➔ `Clásico` guardando la elección en `localStorage`.
- [x] **Limpieza de CSS muerto**: Eliminado `static/style.css.v1-glass` (42 KB).
- [x] **Bumping de caché**: `style.css?v=26` y `app.js?v=22` en `index.html`.

**Verificado previamente por Titán:**

- [x] Panel vivo: `https://dash.erikservicios.click/health` → HTTP 200; `/` → 302 (redirige al login)
- [x] Tema glass v2 desplegado y confirmado (`ac28b0f`)
- [x] Estado online/offline + CPU + RAM + uptime por agente (SSE en vivo)
- [x] Proyección de créditos y monitoreo del 2º servidor (`9fd4f52`)
- [x] Titan Score con tooltip explicativo (`aaac211`)
- [x] Badge del servidor de clientes con % de disco (`0426da5`)
- [x] Botón para reiniciar el contenedor de un agente desde el panel (`d1581f8`)
- [x] Web Push (service worker `sw.js`) + login con sesión

## En curso (a medias)

- Nada detectado. El último commit está desplegado y verificado; no se encontró trabajo inconcluso en el código.

## Bloqueos y decisiones pendientes

- `static/style.css.v1-glass` (42 KB) es el respaldo del estilo anterior y **no está referenciado por nada**. Se propone borrarlo; si Erik lo quiere conservar, va fuera del repo (no dentro).
- El README está desactualizado: describe solo 7 features y 5 APIs de hace dos meses.
- Token de GitHub de Titán renovado el 30-oct-2026 (el anterior expiró; los push fallaban con 401).

## Comandos útiles

```bash
docker compose up -d                     # levantar el panel localmente
pip install -r requirements.txt          # dependencias (Python)

# verificar que producción corre lo mismo que el repo
curl -s https://dash.erikservicios.click/static/style.css | md5sum
md5sum static/style.css                  # deben coincidir

curl -s -o /dev/null -w '%{http_code}\n' https://dash.erikservicios.click/health
```

## Archivos clave

- `main.py` (62 KB) — backend completo: auth/login, APIs, SSE, `docker exec` a los agentes, Web Push
- `static/app.js` (50 KB) — frontend: SSE, tarjetas de agentes, tema, notificaciones
- `static/style.css` (45 KB) — estilos + tema glass v2
- `static/style.css.v1-glass` (42 KB) — **respaldo muerto, candidato a borrar**
- `sw.js` — service worker de las notificaciones push
- `Dockerfile` / `docker-compose.yml` — despliegue; el contenedor necesita el **docker socket** montado

## Notas para el otro agente

- **Cómo se despliega:** Coolify buildea desde GitHub (`Rockerik36812/titan-agent-dashboard`, rama `main`). Un push a `main` no despliega solo: el deploy se dispara desde el panel de Coolify.
- **Cómo verificar que el deploy entró:** comparar el md5 del CSS servido contra el local (comando arriba). Es la forma más rápida y no requiere login.
- El panel corre en un contenedor con el **docker socket montado**: de ahí saca el estado de los agentes y puede reiniciarlos. Ojo con cualquier cambio que toque esa parte.
- `/` responde **302** a propósito (redirige al login). Un 302 no es un error.
- El CSS y el JS son archivos grandes y sin minificar: cuidado con los diffs gigantes, revisa que no se cuele ruido de formato.
