# Protocolo de relevo entre agentes (Titán ↔ Antigravity ↔ OpenCode) · revisor: Muse

Este proyecto lo trabajan **tres agentes en turnos**: **Titán** (Hermes, vive en un servidor), **Antigravity** (IDE, vive en la máquina de Erik) y **OpenCode** (CLI, también en la máquina de Erik). Nunca trabajan al mismo tiempo. Se pasan un batón: el archivo `HANDOFF.md`.

**Dos pares y un trabajador:** Titán y Antigravity **deciden** — traen contexto y memoria propios. OpenCode **ejecuta**: no tiene memoria entre sesiones, así que su turno empieza leyendo `HANDOFF.md` y **termina con commit y push** — lo que no quedó en el repo, se perdió.

**Y un revisor que no es dueño:** **Muse** (Meta) lee el repo por su conector de GitHub, en **solo lectura**, y revisa commits y PRs. **No toma el batón** (ver *Revisor externo*).

## La regla que no se rompe

**Un solo agente es dueño a la vez. Al terminar tu turno, actualizas `HANDOFF.md`. Sin eso, el relevo se rompe y el otro agente pierde el trabajo.**

## Al EMPEZAR tu turno (cualquiera de los tres)

1. `git pull` — nunca trabajes sobre estado viejo.
2. Lee **`HANDOFF.md`** completo y las últimas 10 líneas de `.handoff/log.md`.
3. Si `Dueño actual:` **no eres tú** → detente y avisa a Erik. El otro no cerró su turno.
4. Ponte el batón: cambia `Dueño actual:` a tu nombre, actualiza la fecha, y commitea `[relevo] toma <nombre>`.
5. Trabaja **solo** en el "SIGUIENTE PASO". Si crees que está mal, dilo y propón otro — no lo cambies en silencio.

## Al TERMINAR tu turno

1. Actualiza `HANDOFF.md`: pasa lo terminado a **Hecho**, revisa **En curso**, y deja **un solo SIGUIENTE PASO** accionable (con el comando exacto si aplica).
2. Agrega una línea a `.handoff/log.md`: `fecha | agente | qué cambió | archivos | estado`.
3. `git add -A && git commit -m "[<agente>] <resumen>" && git push`.
4. Suelta el batón: `Dueño actual: libre`.

## Reglas duras

- **Nada de secretos en el repo.** Ni tokens, ni contraseñas, ni IPs privadas. Si hace falta un secreto, se documenta **dónde vive** (ej. "credencial `Ollama local` en n8n"), nunca su valor.
- **`Dueño actual:` acepta `titán`, `antigravity`, `opencode` o `libre`.** Cualquier otro valor (o un nombre que no sea el tuyo) significa que otro no cerró su turno.
- **El estado tiene que ser autocontenido.** El otro agente no ve tus sesiones, tu memoria ni tu historial de chat. Si no está en el repo, no existe.
- **Commits chicos y frecuentes**, cada uno con prefijo `[titán]`, `[antigravity]` o `[opencode]`.
- **No borres el trabajo del otro.** Si algo te parece mal, escríbelo en "Decisiones pendientes" y sigue.
- **Si no terminaste, dilo.** Un relevo mentiroso cuesta más que uno vacío. Escribe "a medias en X, falta Y".
- **Pruebas antes de declarar hecho.** Si no corriste nada, escribe "sin verificar".

## Revisor externo: Muse (Meta) — solo lectura

Este proyecto tiene un **revisor**, y no es un dueño: **Muse** (Meta), conectado por su conector de GitHub con permiso de **solo lectura**.

- **No toma el batón.** `Dueño actual:` sigue aceptando únicamente `titán`, `antigravity`, `opencode` o `libre`.
- **Qué hace:** lee el repo, revisa el commit o el PR que se le nombre, y dice qué cambia, qué podría romperse y qué hay que verificar antes de mergear. Puede **comentar**; **no** mergea, cierra, pushea ni borra nada sin la aprobación explícita de Erik.
- **Cómo entra su trabajo al repo:** quien tenga el batón transcribe la revisión a `.handoff/log.md` **firmada `muse (revisor)`** y anota qué agente la pasó. Si Muse comentó directo en el PR, ese comentario es el registro y la bitácora apunta a él.
- **Alcance:** solo repos del relevo. **Nunca** repos con datos de clientes (en este panel aplica igual: nada de IPs, teléfonos ni credenciales en lo que se le pase). La app corre en infraestructura de Meta y **entrena con las consultas por default**.
- **Una revisión no es una prueba.** El gate sigue siendo correr las pruebas; Muse es el segundo par de ojos, no el único.
- **Es reversible.** Si en 2-3 revisiones no aporta, se retira — el precedente está anotado: Copilot CLI entró al relevo y se fue con 0 commits.

## Quién es mejor para qué

- **Antigravity**: trabajo interactivo en el IDE, edición de código con los archivos abiertos, iteración rápida local, refactors grandes, trabajo con la vista puesta en el código.
- **Titán**: infraestructura, servidores, deploy, n8n, dashboards, bases de datos, Docker, y todo lo que requiera sus skills o acceso a las máquinas de Erik.
- **OpenCode**: ejecución acotada y repetible desde la terminal — features, refactors, pruebas, revisión de PRs (`opencode run '...'`). Sirve para trabajo en paralelo por worktrees y para tareas largas que no necesitan que Erik vea la pantalla.
- **⚠️ Antigravity y OpenCode viven en la misma máquina: no comparten carpeta.** Cada uno con **su clon o worktree** (ej. `~/proyectos/x` para Antigravity, `~/proyectos/x-opencode` para OpenCode), o trabajan en turnos. Compartir directorio = uno guarda encima del otro.
