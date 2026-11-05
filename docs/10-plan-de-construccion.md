# 10. Plan de construcción con Claude Code

Cada fase termina con algo que funciona y se puede enseñar. Las fases son orientativas en orden. No se dan plazos: dependen del tiempo que dediques a revisar.

## Cómo trabajar cada fase

1. Abre Claude Code en la raíz del repositorio y entra en modo plan (Shift+Tab dos veces).
2. Pega el prompt de la fase.
3. Revisa el plan que propone. Comprueba que cita los documentos de `docs/` y que no se salta tests.
4. Aprueba y deja que ejecute. Si una tarea es grande, pide que la divida en commits pequeños.
5. Al terminar, pide: "Ejecuta la definición de terminado de `docs/09` y pasa los cambios por el subagente revisor-datos".
6. Haz tú la prueba de aceptación de la fase.
7. Usa `/clear` entre fases para empezar con el contexto limpio. CLAUDE.md y `docs/` llevan la memoria del proyecto.

---

## Fase 0. Cimientos y verificación de fuentes

**Objetivo:** esqueleto desplegable y resolver los "por verificar" que condicionan el diseño.

**Prompt:**
> Lee CLAUDE.md, docs/00 a 04 y los ADR. Crea el esqueleto Django según ADR-001: uv, ruff, pytest-django, settings por entorno, .env.example, usuario propio con email, apps vacías con la estructura de CLAUDE.md y GitHub Actions según docs/09. Después, sin escribir importadores todavía, haz las verificaciones marcadas "Por verificar en la Fase 0" en docs/04 §1 y §2: descarga un ZIP mensual real de PLACSP, mide su tamaño, localiza las rutas XML de los campos listados y haz 2 o 3 peticiones a la Search API de TED para ver los campos. Anota en docs/04 lo que encuentres, con la fecha, y guarda extractos pequeños como fixtures. No inventes rutas ni campos: si algo no aparece, anótalo como no encontrado.

**Aceptación:**
- `pytest` y `ruff` pasan; la aplicación arranca en local con el login.
- `docs/04` §1 y §2 tienen las casillas de "por verificar" resueltas o explicadas.
- Hay una medición del tamaño de los datos de un año de la Comunitat Valenciana y una nota sobre si cabe en Neon Free.

## Fase 1. Catálogos, territorio y evidencias

**Prompt:**
> Implementa las apps territorio, entidades y evidencias según docs/03, con su administración de Django y roles según docs/08. Carga los municipios y provincias de la Comunitat Valenciana desde una fuente oficial con código INE (propón la fuente, verifica su URL y licencia, y anótalo en docs/04). Crea el comando `cargar_competidores_iniciales` con la lista de docs/00 y sus acotaciones como datos editables. Implementa el modelo de usuario con invitación. Tests: CP-05, CP-11.

**Aceptación:** puedo entrar como administrador, crear un analista y un lector, ver los municipios valencianos y editar empresas, alias y acotaciones.

## Fase 2. Importación de la tabla municipal y mapa

**Prompt:**
> Implementa el asistente de importación de Excel/CSV municipal (docs/04 §9) y `PrestacionServicio`. Importa seed/municipios_veolia_agua.csv, seed/Municipios_Veolia_agua_residuos_energia.xlsx y seed/cruce_servicios_municipales_CV.xlsx (este último como borradores): los nombres que no casen van a la bandeja de revisión. Prepara el GeoJSON municipal según ADR-006 (verifica fuente, licencia y campo del código INE) y la pantalla de mapa de docs/05 §1 con su tabla equivalente. Tests: CP-07.

**Aceptación:** veo el mapa de la Comunitat Valenciana con los municipios de Veolia y su información de residuos y energía, con niveles; "EL BOSQUE-CHIVA" y "TAVERNES" quedan resueltos o en la bandeja, y puedo exportar la tabla.

## Fase 3. Contratación pública (PLACSP y TED)

**Prompt:**
> Implementa TrabajoIngesta (ADR-007) y los importadores de PLACSP (datos abiertos) y TED según ADR-004 y docs/04 §1-2, con clasificación por CPV (tabla editable) y vinculación órgano-municipio con bandeja de revisión. Botón "Actualizar contratación" con progreso por HTMX y comandos manage.py equivalentes. Tests: CP-03, CP-04, CP-06, CP-14, CP-16 y la idempotencia.

**Aceptación:** con un rango de fechas, la aplicación carga los expedientes valencianos, los clasifica y los muestra en el panel de cada municipio. Una segunda ejecución no duplica nada.

## Fase 4. Medios: Brandwatch y recortes

**Prompt:**
> Implementa el importador de Brandwatch (docs/04 §4) con deduplicación, medios, menciones, piezas e hitos (docs/03), y la atribución por alias con bandeja de revisión. Implementa la subida de recortes PDF (docs/04 §5) sin IA todavía: extracción de texto y metadatos del nombre de archivo. Pantalla de visibilidad en medios (docs/05 §3) con las reglas de recuento. Tests: CP-01, CP-02, CP-08.

**Aceptación:** subo los tres exports reales y el total de menciones únicas es coherente (lo compruebo con una tabla dinámica en Excel); veo las piezas por competidor y medio con enlace a cada pieza.

## Fase 5. IA

**Prompt:**
> Implementa apps/ia según ADR-005 y docs/06: cliente único, salidas estructuradas validadas con Pydantic, registro LlamadaIA, PropuestaIA, límite mensual y las tareas T1 a T4. Usa respuestas grabadas en los tests. Crea el juego de evaluación de docs/06 con 50 menciones que yo anotaré: prepara la plantilla para que la rellene. Tests: CP-13, CP-15.

**Aceptación:** los recortes escaneados se leen y las menciones dudosas reciben una propuesta. Nada se publica sin validarlo y el panel de uso muestra tokens y coste estimado.

## Fase 6. Fichas, documentos cualitativos y digital

**Prompt:**
> Implementa la importación de Word (docs/04 §6), incluida la importación única del anexo de evidencias del documento maestro como borradores, PercepcionInterna, ObservacionDigital y AuditoriaWeb (docs/04 §8) y la ficha de competidor completa (docs/05 §2). Tests: CP-12.

**Aceptación:** la ficha de FACSA muestra los tres bloques con datos reales validados y la percepción interna separada.

## Fase 7. Informes

**Prompt:**
> Implementa la generación de informe docx y presentación pptx según docs/05 §4, con la tarea T6 de docs/06 y el validador de cifras y citas. Tests: CP-09, CP-10.

**Aceptación:** genero un informe del último año. Elijo 10 cifras al azar y todas me llevan a sus evidencias.

## Fase 8. Despliegue del piloto

**Prompt:**
> Prepara el despliegue según ADR-002: render.yaml o la configuración equivalente vigente (verifícala en la documentación de Render), whitenoise, migraciones en el despliegue, variables de entorno, página de "activando" y la guía docs/12-operacion.md (alta de usuarios, copia semanal, actualización de datos, qué hacer si algo falla). Ejecuta la checklist de despliegue.

**Aceptación:** el equipo entra por una URL con HTTPS. Tengo hecha y probada una copia de seguridad.

---

## Consejos de trabajo con Claude Code

- Una fase por sesión. Si la sesión se alarga, usa `/compact` antes de que lo haga solo.
- Si Claude Code propone algo que contradice un ADR, pídele que redacte un ADR nuevo antes de cambiarlo.
- Cuando corrijas algo dos veces, pídele que añada la regla a CLAUDE.md.
- Usa subagentes para revisar (`revisor-datos`) o investigar, no para escribir en paralelo en los mismos archivos.
- Haz commits pequeños con mensajes que citen los requisitos (`RF-30: importador Brandwatch`).
