# HANDOFF — Panel de Agentes

**Dueño actual:** libre  ·  válidos: `titán`, `antigravity`, `opencode`, `libre` (Muse **nunca** va aquí)
**Última actualización:** 2026-11-19 18:26 (CST)
**Estado:** 🟢 en marcha (Rayo ⚡ animado restaurado a gusto de Erik; 4 temas preservados)

> 2026-11-19 — Titán: el protocolo ahora también nombra a **Muse** (Meta) como **revisor de solo lectura** por su conector de GitHub: **no es dueño**, no toma el batón, y sus revisiones entran a la bitácora firmadas `muse (revisor)`. De paso se corrigió la regla de Antigravity, que seguía diciendo "dos agentes" (le faltaba OpenCode). **Nada del panel (UI) se tocó.**
>
> 2026-11-12 — Titán: el protocolo ahora contempla **3 agentes** (Titán, Antigravity, OpenCode). `Dueño actual: opencode` es válido; Antigravity y OpenCode no comparten carpeta (un clon/worktree por agente). Nada del panel se tocó: solo el reglamento del relevo.

## Objetivo

Que Erik pueda ver el estado de sus 3 Hermes (**Titán, Hermina y Hermes**) desde el celular o la PC, sin entrar por SSH: online/offline, CPU, RAM, uptime, última actividad, créditos y 2º servidor. Está **sano** cuando el panel refleja la realidad en vivo y cualquier cosa que necesite saber de sus agentes se ve ahí.

## SIGUIENTE PASO

> Probar en el celular o PC con recarga forzada para ver el rayo ⚡ original con su animación pulse restaurado junto con el nuevo layout responsivo.

## Hecho

**Verificado por Antigravity el 2026-11-17 (Aprobado por Erik):**

- [x] **Rayo `⚡` original restaurado en el logo**: Restituido el emoji de rayo original con animación `pulse 2s` que se integra naturalmente con todos los temas visuales.
- [x] **Calibración Responsive Mobile First (Celulares y Tablets)**:
  - **Header móvil calibrado**: Cuadrícula simétrica para métricas clave y barra de acción compacta para los botones de Push, Tema, Salir y estado de conexión sin desbordes.
  - **Layout adaptativo móvil**: `.dashboard-kpi-row` y `.dashboard-split-grid` colapsan a 1 sola columna fluida con ritmo visual compacto (`gap: 1rem`).
  - **OpenRouter móvil optimizado**: 3 columnas en una sola fila para Total/Usado/Restante con la barra debajo, ahorrando espacio en pantalla.
  - **Epic Stats 3x2**: Números y etiquetas ajustados para que no desborden ni rompan en pantallas pequeñas (< 480px).
  - **Bumping de caché**: `style.css?v=37` y `app.js?v=33`.

- [x] **Rediseño Macro de Observabilidad (Layout Unslop)**:
  - **Agentes en la cima absoluta (`Hero Command Row`)**: Titán, Hermina y Hermes ahora se ven de inmediato al abrir el panel, sin requerir scroll vertical.
  - **Línea de acento distintiva**: Barra superior iluminada con el color único de cada agente activo (`--color`).
  - **Fila dual de métricas y hardware (`.dashboard-kpi-row`)**: Métricas Globales y Recursos de Sistema (Host + VPS) en dos columnas en desktop/tablet.
  - **Grid dividido de operaciones (`.dashboard-split-grid`)**: Analíticas + Gateways a la izquierda; Actividad en vivo + Herramientas a la derecha.
  - **Viewport ampliado a 1360px**: Aprovecha el ancho de pantalla de PC/Mac y colapsa a 1 columna automáticamente en celular.
  - **Bumping de caché**: `style.css?v=36` y `app.js?v=32`.

**Verificado por Antigravity el 2026-11-16 (Aprobado por Erik):**

- [x] **Pase de refinamiento Unslop (UI/UX profesional)**:
  - **Iconografía vectorial SVG**: Reemplazados los emojis en títulos de sección, botón de Web Push (`pushBtn`), salida (`logoutBtn`), botón de reinicio de agente y logo por vectores SVG limpios monocromáticos (Lucide style) que adaptan su color dinámicamente según el tema.
  - **Copywriting y tono técnico**: "Estadísticas Épicas" migrado a "Métricas Globales"; status `✅ up / ❌ down` sustituido por badges discretos `up` (verde esmeralda) y `down` (rojo sutil).
  - **Terminal de logs para agentes**: El modal de visualización de logs de agente/gateway (`#modal-logs`) ahora tiene estética de consola de observabilidad (`#090a0f`, fuente monoespaciada `ui-monospace`, sombra interna y contraste optimizado).
  - **Preservación total de los 4 temas**: Se mantuvo al 100% la funcionalidad del switch cíclico de temas (`Clásico`, `Aurora`, `Ultra Glass`, `Día de Muertos 🏵️`) y su almacenamiento en `localStorage`.
  - **Bumping de caché**: `style.css?v=35` y `app.js?v=31` en `index.html`.
  - **Respaldos de seguridad**: Rama `backup-pre-unslop`, tag `backup-pre-unslop` y carpeta física `static_backup_pre_unslop/`.

**Verificado por Antigravity el 2026-11-01 (Aprobado por Erik):**

- [x] **4º Tema Visual: Día de Muertos 💀🏵️ (Auténtica Tradición Mexicana)**:
  - **La Catrina Ilustrada en el Logo**: Icono con sombrero de ala ancha, plumas turquesa, flores de cempasúchil, ojos con pétalos y sonrisa calada con animación de veladora (`catrinaFlicker`).
  - **Guirnalda de Papel Picado en Header**: Cenefa festoneada colgante a lo largo de todo el header con los 5 colores típicos de ofrenda (Rosa Mexicano `#e4007c`, Naranja Cempasúchil `#f29f05`, Amarillo Sol `#ffd100`, Azul Turquesa `#00bcd4`, Morado `#6a2c91`) con calaveritas, huesos y flores caladas.
  - **Camino de Cempasúchil, Calaveritas y Pan de Muerto**: Fondo animado continuo con lluvia suave de pétalos de cempasúchil dorados y bugambilia, flores completas de 20 pétalos, calaveritas de azúcar mexicanas y pan de muerto tradicional con canillas/huesos.
  - **Tarjetas Altar Glass con Esquinas de Papel Picado**: Esquinas decoradas con papel picado calado en rosa mexicano con cempasúchil dorado y calaverita sonriente.
  - **Atmósfera Cálida de Ofrenda**: Resplandores de luz de veladoras en lugar de niebla tenebrosa.
- [x] **Switch de 4 posiciones calibrado**: Track con los 5 colores de papel picado, knob en oro cempasúchil y persistencia en `localStorage`.
- [x] **Bumping de caché**: `style.css?v=34` y `app.js?v=30` en `index.html`.

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

## Pruebas y revisión

- **Pruebas corridas:** las que cada agente anota en **Hecho** (si no corriste nada, escribe "sin verificar").
- **Revisión de Muse:** ninguna en este proyecto todavía (la del repo de relevo, issue #1, quedó atendida el 2026-11-20).
- **Repos que Muse puede ver:** `titan-agent-dashboard` (público).

Una revisión **no** sustituye a las pruebas: van en campos separados a propósito.

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
