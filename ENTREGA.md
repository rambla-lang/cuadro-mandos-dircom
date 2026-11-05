# Entrega del proyecto al responsable de desarrollo

Este documento es para la persona que va a liderar y desarrollar la aplicación en su propia infraestructura (su cuenta de GitHub, su plan de Claude Code y sus cuentas de alojamiento). José Luis actúa como **propietario del producto**: define qué se necesita, aporta los datos de muestra y acepta cada fase. No mantiene infraestructura.

## Qué recibes

1. **Este paquete** (`cuadro-mandos-dircom-docs.zip`). Descomprímelo en la raíz de un repositorio nuevo. Incluye:
   - `CLAUDE.md` y la carpeta `.claude/`, que Claude Code carga automáticamente;
   - `docs/`: requisitos, arquitectura, ADR, modelo de datos, fuentes, métricas, IA, interfaz, seguridad, pruebas y plan por fases;
   - `seed/`: las tablas municipales (76 municipios de Veolia y un cruce de 98 registros de competidores) y la cabecera real de una exportación de Brandwatch.
2. **Material de muestra confidencial**, por un canal aparte y **no para el repositorio**:
   - 3 exportaciones CSV de Brandwatch (2026);
   - 30 recortes de prensa en PDF y 6 informes de sostenibilidad o EINF;
   - los Word de percepciones internas, el documento maestro y el documento de proceso.
   Sirven para la Fase 0 y para preparar fixtures sintéticas. Ver `docs/04` y `docs/09`.

## Qué decides tú, como responsable técnico

Las decisiones técnicas de `docs/adr/` son **propuestas**: puedes cambiarlas. Si cambias una, deja un ADR nuevo que explique por qué, para que la documentación siga siendo fiable para Claude Code. En concreto, son tuyas:
- el stack (ADR-001), el alojamiento y la base de datos (ADR-002), el almacenamiento de archivos (ADR-003) y la ejecución de trabajos largos (ADR-007);
- las cuentas de servicios: GitHub, alojamiento, base de datos y API de Anthropic. La clave de la API de Anthropic es tuya y la pagas tú (P-14);
- la organización del trabajo: ramas, integración continua y cómo usar Claude Code.

## Qué no debe cambiar sin hablar con José Luis

- Las reglas de evidencia y de no invención (`CLAUDE.md`, `docs/03`, `.claude/skills/regla-evidencia`).
- Las reglas de recuento de prensa y la definición de las métricas (`docs/05`).
- La estructura de la ficha de competidor y de los informes (`docs/05` §2 y §4).
- El alcance del MVP (`docs/00`).

## Cómo se trabajará juntos

- **Al cerrar cada fase:** demo corta y prueba de aceptación de José Luis (criterios en `docs/10`).
- **Preguntas de producto:** las que están marcadas "Decide: José Luis" en `docs/11`. Hasta tener respuesta, Claude Code sigue con lo que no esté bloqueado.
- **Datos reales:** José Luis valida las atribuciones y propuestas de la IA en la bandeja de revisión y anota el juego de evaluación de la IA (`docs/06`).
- **Acceso de José Luis:** como mínimo, un usuario con rol administrador o analista en la aplicación desplegada, para hacer las aceptaciones. No necesita acceso al código ni a las cuentas técnicas.

## Primer paso recomendado

Abre Claude Code en el repositorio, entra en modo plan y pega el prompt de la **Fase 0** de `docs/10-plan-de-construccion.md`. Esa fase resuelve las verificaciones técnicas marcadas como "por verificar" antes de escribir importadores.
