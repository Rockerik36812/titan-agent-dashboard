# Protocolo de relevo entre agentes (Titán ↔ Antigravity)

Este proyecto lo trabajan **dos agentes en turnos**: **Titán** (Hermes, vive en un servidor) y **Antigravity** (IDE, vive en la máquina de Erik). Nunca trabajan al mismo tiempo. Se pasan un batón: el archivo `HANDOFF.md`.

## La regla que no se rompe

**Un solo agente es dueño a la vez. Al terminar tu turno, actualizas `HANDOFF.md`. Sin eso, el relevo se rompe y el otro agente pierde el trabajo.**

## Al EMPEZAR tu turno (cualquiera de los dos)

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
- **El estado tiene que ser autocontenido.** El otro agente no ve tus sesiones, tu memoria ni tu historial de chat. Si no está en el repo, no existe.
- **Commits chicos y frecuentes**, cada uno con prefijo `[titán]` o `[antigravity]`.
- **No borres el trabajo del otro.** Si algo te parece mal, escríbelo en "Decisiones pendientes" y sigue.
- **Si no terminaste, dilo.** Un relevo mentiroso cuesta más que uno vacío. Escribe "a medias en X, falta Y".
- **Pruebas antes de declarar hecho.** Si no corriste nada, escribe "sin verificar".

## Quién es mejor para qué

- **Antigravity**: trabajo interactivo en el IDE, edición de código con los archivos abiertos, iteración rápida local, refactors grandes, trabajo con la vista puesta en el código.
- **Titán**: infraestructura, servidores, deploy, n8n, dashboards, bases de datos, Docker, y todo lo que requiera sus skills o acceso a las máquinas de Erik.
