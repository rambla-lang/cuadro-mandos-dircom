# ADR-010: Sin contratación pública; «empresas gestoras» en lugar de «competidores»

**Estado:** Aceptada (10/11/2026, usuario DIRCOM)
**Fecha:** 10/11/2026
**Decisores:** usuario de la DIRCOM (decisión de alcance); responsable de desarrollo (ejecución)
**Sustituye a:** ADR-004 (ingesta de contratación pública) y ADR-008 (carga histórica de PLACSP).
**Relacionada con:** ADR-002 (volumen de Neon), ADR-007 (los trabajos en segundo plano siguen para los lotes de IA).

## Contexto
La primera carga real de contratación (octubre de 2026) dejó 5.307 expedientes de PLACSP y TED, de los que solo unos 40 eran de las empresas con ficha. Ninguno estaba asociado a una empresa, porque el catálogo no tenía razones sociales ni NIF. El usuario indicó que los expedientes no le sirven: lo que quiere gestionar es quién presta cada servicio en cada municipio. Pidió también dejar de usar el término «competidor» y tratar a Veolia como una empresa más.

## Decisión
1. Se elimina el módulo de contratación: la app `contratacion`, sus tablas, los importadores de PLACSP y TED, las reglas de clasificación por CPV, la tarea de IA T3 y los tipos de la bandeja de órganos, clasificación y adjudicatarios. Medios, documentos, redes, fichas, IA e informes se mantienen.
2. El núcleo del cuadro son tres tablas: `Municipio`, `Empresa` (empresa gestora) y `PrestacionServicio` (municipio, empresa, servicio, alcance y nivel). Cada prestación conserva sus evidencias: son la fuente del dato.
3. «Competidor» pasa a «empresa gestora» en pantallas, direcciones (`/empresas-gestoras/`), código y base de datos. `es_competidor_seguido` pasa a `con_ficha`, `AcotacionCompetidor` a `AcotacionEmpresa`, y desaparece `es_propia`.
4. Veolia e Hidraqua pasan a ser empresas gestoras con ficha dentro del grupo «Veolia», igual que FACSA dentro de Nealis. Entran en visibilidad, fichas e informes como las demás.

## Consecuencias
- La base local se copió antes del cambio (`copias/antes_retirar_contratacion_20261110.dump`). Los datos de PLACSP y TED son públicos y se pueden volver a obtener.
- Desaparece el riesgo de volumen de PLACSP en Neon (ADR-002) y la medición pendiente de ADR-008.
- Las verificaciones de PLACSP y TED de docs/04 §1-2 se conservan como referencia por si la contratación vuelve.
- Los informes guardados antes del cambio conservan sus métricas; la matriz comparativa pide regenerarlos para mostrar «Municipios con servicio».
