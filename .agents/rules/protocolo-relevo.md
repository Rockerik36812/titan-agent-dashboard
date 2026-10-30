# Relevo con Titán (Hermes)

Este repo lo trabajan **dos agentes en turnos**: tú (Antigravity) y Titán (Hermes, corre en el servidor de Erik). Nunca al mismo tiempo.

- **Al empezar:** `git pull`, lee `HANDOFF.md` y las últimas líneas de `.handoff/log.md`. Si `Dueño actual:` no dice `antigravity` o `libre`, **detente y avisa** a Erik.
- **Al terminar:** actualiza `HANDOFF.md` con **un solo SIGUIENTE PASO** accionable, agrega una línea a `.handoff/log.md`, commitea con prefijo `[antigravity]`, haz `push` y deja `Dueño actual: libre`.
- **Nunca cierres tu turno sin dejar el relevo escrito.** El otro agente no ve tu conversación ni tus archivos abiertos: si no está en el repo, no existe.
- **Nunca subas secretos** (tokens, contraseñas, IPs privadas). Documenta dónde vive el secreto, no su valor.

El protocolo completo está en `AGENTS.md`.
