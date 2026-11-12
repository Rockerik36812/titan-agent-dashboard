# Relevo con Titán (Hermes)

Este repo lo trabajan **cuatro agentes en turnos**: tú (Antigravity) y Titán (Hermes, corre en el servidor de Erik) — los dos que deciden — y OpenCode y Copilot (CLI, en tu misma máquina), que ejecutan. Nunca al mismo tiempo.

- **Al empezar:** `git pull`, lee `HANDOFF.md` y las últimas líneas de `.handoff/log.md`. Si `Dueño actual:` no dice `libre` ni tu nombre (`antigravity`), **detente y avisa** a Erik.
- **Al terminar:** actualiza `HANDOFF.md` con **un solo SIGUIENTE PASO** accionable, agrega una línea a `.handoff/log.md`, commitea con prefijo `[antigravity]`, haz `push` y deja `Dueño actual: libre`. **No compartas carpeta con OpenCode ni con Copilot**: cada uno su clon/worktree.
- **Nunca cierres tu turno sin dejar el relevo escrito.** El otro agente no ve tu conversación ni tus archivos abiertos: si no está en el repo, no existe.
- **Nunca subas secretos** (tokens, contraseñas, IPs privadas). Documenta dónde vive el secreto, no su valor.

El protocolo completo está en `AGENTS.md`.
