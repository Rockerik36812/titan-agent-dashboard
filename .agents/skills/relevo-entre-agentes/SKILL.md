---
name: relevo-entre-agentes
description: "Use when continúas un proyecto compartido con otro agente. Protocolo de relevo por HANDOFF.md."
---

# Relevo entre agentes

Cómo tomar y soltar un proyecto que se trabaja en turnos con otro agente (Titán ↔ Antigravity), sin que ninguno pierda el trabajo del otro.

## Cuándo usarla

- Cuando Erik dice "Antigravity se quedó en X, continúa tú" o "ya se me acabó el uso de Antigravity".
- Cuando vas a empezar a trabajar en un repo que tiene `HANDOFF.md` o `.handoff/log.md`.
- Cuando vas a pausar o cerrar un proyecto compartido.

## Cómo tomar el batón

1. `git pull` primero. Nunca trabajes sobre estado viejo.
2. Lee `HANDOFF.md` completo + las últimas 10 líneas de `.handoff/log.md`.
3. Verifica `Dueño actual:`. Si no está en `libre` ni en tu nombre, **para y avisa** — el otro agente no cerró.
4. Escribe tu nombre en `Dueño actual:` y commitea `[relevo] toma <nombre>`.
5. Ejecuta **solo** el "SIGUIENTE PASO" declarado. Si está mal, dilo antes de cambiarlo.
6. Lee `AGENTS.md` del repo: ahí están las reglas duras del proyecto.

## Cómo soltar el batón

1. `HANDOFF.md`: mueve lo terminado a **Hecho**; deja **un solo SIGUIENTE PASO** accionable (comando exacto si aplica); escribe bloqueos y decisiones pendientes; llena "Notas para el otro agente".
2. Una línea nueva en `.handoff/log.md` (append-only).
3. Commit con prefijo `[titán]` o `[antigravity]`, luego `push`.
4. `Dueño actual: libre`.

## Pitfalls que rompen el relevo

- **Cerrar sin actualizar `HANDOFF.md`**: el otro agente rehace trabajo o se queda parado. Es el error número uno.
- **Estado implícito**: "como te comenté antes" no sirve. El otro agente no ve tu conversación. Todo lo que importa va escrito en el repo.
- **Declarar hecho sin verificar**: si no corriste pruebas, escribe "sin verificar". Un relevo mentiroso cuesta más que uno vacío.
- **Secretos en el repo**: tokens, contraseñas e IPs privadas se quedan fuera. Se documenta *dónde* vive el secreto, no su valor.
- **Los dos trabajando a la vez**: si `Dueño actual` no está libre, no se toca. Los conflictos de merge queman más tiempo que esperar el turno.
- **Trabajar fuera del "Siguiente paso"**: si el plan está mal, se propone y se anota; no se cambia en silencio.
