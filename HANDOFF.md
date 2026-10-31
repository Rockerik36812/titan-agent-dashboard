# HANDOFF — Panel de Agentes

**Dueño actual:** libre
**Última actualización:** 2026-10-31 01:05 (CST)
**Estado:** 🟢 en marcha (Aprobado por Erik)

## Objetivo

Que Erik pueda ver el estado de sus 3 Hermes (**Titán, Hermina y Hermes**) desde el celular o la PC, sin entrar por SSH: online/offline, CPU, RAM, uptime, última actividad, créditos y 2º servidor. Está **sano** cuando el panel refleja la realidad en vivo y cualquier cosa que necesite saber de sus agentes se ve ahí.

## SIGUIENTE PASO

> Probar el panel en el **celular** con el tema Ultra Glass (scroll y batería). Si se siente pesado o caliente: bajar el `blur(45px)` del fondo animado y limpiar los ~15 `!important` del bloque nuevo (es mejora de mantenimiento, no cambio de diseño).

## Hecho

**Verificado por Antigravity el 2026-10-30 (Aprobado por Erik):**

- [x] **Tema Ultra Glass calibrado y aprobado**: Fondo oscuro profundo con auroras nocturnas suaves y tarjetas de cristal ahumado translúcidas con bisel de luz especular.
- [x] **Switch de 3 posiciones (`Clásico` ➔ `Aurora` ➔ `Ultra Glass`)**: Completamente funcional, ciclando con persistencia en `localStorage`.
- [x] **Limpieza de CSS muerto**: Eliminado `static/style.css.v1-glass` (42 KB).
- [x] **Bumping de caché**: `style.css?v=31` y `app.js?v=27` en `index.html`.

**Hecho por Titán el 2026-10-31:**

- [x] **README.md al día**: reescrito con las features reales (agentes, épicas, OpenRouter, sistema + 2º VPS, gateways, herramientas, actividad, analíticas, Web Push, los 3 temas y el auth), **la tabla de los 28 endpoints**, requisitos, despliegue y cómo verificar el deploy por md5.
- [x] **Tamaños reales** en "Archivos clave" (`style.css` 52 KB, `app.js` 49 KB, `main.py` 61 KB).
- [x] **Bitácora**: nota de zona horaria en el encabezado — de aquí en adelante todo en hora de México.
- [x] Detectado y documentado: `docker-compose.yml` está desalineado con el despliegue real.

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

- Nada detectado. El nuevo tema Ultra Glass y el switch de 3 estados quedaron probados, desplegados y aprobados.

## Bloqueos y decisiones pendientes

- Nada del README: quedó al día el 2026-10-31 (28 endpoints documentados).
- `docker-compose.yml` desalineado con el despliegue real (`ghcr.io`/puerto `8000` vs Coolify/`8999`): decidir si se alinea o se borra para no confundir.
- Token de GitHub renovado y configurado en el entorno local.

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

- `main.py` (61 KB) — backend completo: auth/login, APIs, SSE, `docker exec` a los agentes, Web Push
- `static/app.js` (49 KB) — frontend: SSE, tarjetas de agentes, tema, notificaciones
- `static/style.css` (52 KB) — estilos + 3 temas visuales (Clásico, Aurora y Ultra Glass)
- `README.md` (6 KB) — features reales, los 28 endpoints, despliegue y verificación por md5
- `sw.js` — service worker de las notificaciones push
- `Dockerfile` / `docker-compose.yml` — despliegue; el contenedor necesita el **docker socket** montado

## Notas para el otro agente

- **Cómo se despliega:** Coolify buildea desde GitHub (`Rockerik36812/titan-agent-dashboard`, rama `main`). Un push a `main` no despliega solo: el deploy se dispara desde el panel de Coolify.
- **Cómo verificar que el deploy entró:** comparar el md5 del CSS servido contra el local (comando arriba). Es la forma más rápida y no requiere login.
- El panel corre en un contenedor con el **docker socket montado**: de ahí saca el estado de los agentes y puede reiniciarlos. Ojo con cualquier cambio que toque esa parte.
- `/` responde **302** a propósito (redirige al login). Un 302 no es un error.
- El CSS y el JS son archivos grandes y sin minificar: cuidado con los diffs gigantes, revisa que no se cuele ruido de formato.
