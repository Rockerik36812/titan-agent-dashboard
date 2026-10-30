# HANDOFF — Panel de Agentes

**Dueño actual:** libre
**Última actualización:** 2026-10-30 02:36 (CST)
**Estado:** 🟢 en marcha

## Objetivo

Que Erik pueda ver el estado de sus 3 Hermes (**Titán, Hermina y Hermes**) desde el celular o la PC, sin entrar por SSH: online/offline, CPU, RAM, uptime, última actividad, créditos y 2º servidor. Está **sano** cuando el panel refleja la realidad en vivo y cualquier cosa que necesite saber de sus agentes se ve ahí.

## SIGUIENTE PASO

> Barrer el repo y poner el README al día: borrar el CSS muerto y documentar lo que el panel ya hace y no está escrito.

```bash
# 1. eliminar el respaldo muerto (42 KB, no referenciado en ninguna parte)
git rm static/style.css.v1-glass

# 2. verificar que nada lo usaba (debe salir vacío)
grep -rn 'v1-glass' --include='*.py' --include='*.js' --include='*.html' . || echo "OK: no referenciado"

# 3. commit
git commit -m "[antigravity] limpia css muerto y actualiza el README"
```

Al terminar, el README debe mencionar las 6 cosas que hoy **no** están documentadas: proyección de créditos, monitoreo del 2º servidor, notificaciones Web Push, tema glass (switch en el header), login y reinicio del contenedor de un agente.

## Hecho

**Verificado por Titán el 2026-10-30:**

- [x] Panel vivo: `https://dash.erikservicios.click/health` → HTTP 200; `/` → 302 (redirige al login)
- [x] **Tema glass v2 desplegado y confirmado**: el `style.css` servido tiene el mismo md5 que el local (`6f929bd2…`) → producción = repo
- [x] 105 commits desde el 28-ago-2026
- [x] Último commit real: `ac28b0f` "glass v2 - aurora animada, grano, refraccion fuerte y glows" (26-oct)

**Funcionalidad ya implementada (según código y commits):**

- [x] Estado online/offline + CPU + RAM + uptime por agente (SSE en vivo)
- [x] Proyección de créditos y monitoreo del 2º servidor (`9fd4f52`)
- [x] Titan Score con tooltip explicativo (`aaac211`)
- [x] Badge del servidor de clientes con % de disco (`0426da5`)
- [x] Botón para reiniciar el contenedor de un agente desde el panel (`d1581f8`)
- [x] Web Push (service worker `sw.js`) + login con sesión
- [x] Tema glass con switch en el header (`ed65290`, `ac28b0f`)

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
