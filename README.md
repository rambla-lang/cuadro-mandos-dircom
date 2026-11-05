# Cuadro de mandos DIRCOM: documentación técnica para construir con Claude Code

Nombre provisional del proyecto: `cuadro-mandos-dircom` (puedes cambiarlo).

Este paquete contiene la documentación que Claude Code necesita para construir la aplicación. No contiene código. Se ha redactado el 05/11/2026 a partir de:

- Las respuestas de José Luis a las preguntas de alcance (resumidas en `docs/00-vision-y-alcance.md`).
- El trabajo real del análisis de competencia de Veolia en la Comunitat Valenciana: las exportaciones de Brandwatch, los recortes de prensa en PDF, los documentos Word, la tabla de municipios y el rastreo de PLACSP/TED.
- La documentación oficial consultada de PLACSP, TED, BOE, la API de Claude, Render y Neon (enlaces en cada documento).

**Si vas a desarrollar el proyecto, empieza por `ENTREGA.md`**: explica qué recibes, qué decides tú y qué se acuerda con José Luis.

## Cómo usarlo con Claude Code

1. Crea un repositorio vacío y copia en su raíz todo el contenido de esta carpeta, incluida la carpeta oculta `.claude/`.
2. Lee `ENTREGA.md` y `docs/11-preguntas-abiertas.md`: hay decisiones pendientes, unas de producto y otras técnicas, que bloquean algunas fases.
3. Abre Claude Code en la carpeta del repositorio. `CLAUDE.md` se carga solo en cada sesión.
4. Sigue `docs/10-plan-de-construccion.md` fase a fase. Cada fase incluye el prompt que puedes pegar en Claude Code y el criterio para darla por terminada.
5. Empieza cada fase en modo plan (Shift+Tab dos veces): Claude propone el plan, tú lo revisas y después lo ejecuta.

## Índice

| Archivo | Contenido |
|---|---|
| `ENTREGA.md` | Guía para el responsable de desarrollo: qué recibe, qué decide y cómo se trabaja con el propietario del producto |
| `CLAUDE.md` | Reglas permanentes del proyecto para Claude Code: stack, comandos, convenciones y reglas de no invención |
| `docs/00-vision-y-alcance.md` | Objetivo, usuarios, decisiones tomadas, alcance del MVP y lo que queda fuera |
| `docs/01-requisitos.md` | Requisitos funcionales (RF) y no funcionales (RNF) con identificador y criterio de aceptación |
| `docs/02-arquitectura.md` | Componentes, flujos de datos, despliegue piloto y límites conocidos |
| `docs/adr/` | Decisiones de arquitectura (ADR-001 a ADR-009) con alternativas y consecuencias |
| `docs/03-modelo-de-datos.md` | Entidades, campos, relaciones y niveles de evidencia |
| `docs/04-fuentes-e-ingesta.md` | Cada fuente: acceso, formato real observado, reglas de importación y lecciones aprendidas |
| `docs/05-modulos-analiticos.md` | Definición exacta de cada métrica y pantalla de análisis |
| `docs/06-ia-con-claude.md` | Usos de la API de Claude, esquemas de salida, salvaguardas y control de coste |
| `docs/07-ui-y-visualizacion.md` | Pantallas, componentes y reglas de visualización de datos |
| `docs/08-seguridad-y-privacidad.md` | Autenticación, roles, secretos, datos personales y copias |
| `docs/09-calidad-y-pruebas.md` | Estrategia de pruebas, datos de prueba y definición de terminado |
| `docs/10-plan-de-construccion.md` | Fases, tareas y prompts para Claude Code |
| `docs/11-preguntas-abiertas.md` | Lo que falta decidir o verificar |
| `.claude/skills/` | Dos skills del proyecto: añadir un importador y aplicar reglas de evidencia |
| `.claude/agents/revisor-datos.md` | Subagente que revisa cambios que tocan datos o métricas |
| `.env.example` | Variables de entorno necesarias, sin valores |
| `seed/` | Datos reales para arrancar: municipios con agua de Veolia, esa tabla con residuos y energía, cruce de servicios municipales de competidores, y cabecera real de un export de Brandwatch |

## Convención de este paquete

- **Verificado**: dato comprobado en una fuente oficial, con el enlace al lado.
- **Decisión**: elección tomada con José Luis o propuesta razonada en un ADR.
- **Por verificar**: dato o comportamiento que Claude Code debe comprobar antes de depender de él. Nunca se da por bueno sin comprobarlo.
