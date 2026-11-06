# ADR-005: Uso de la API de Claude

**Estado:** Aceptada (José Luis confirmó el uso de la API de Anthropic)
**Fecha:** 05/11/2026

## Contexto
Varias tareas necesitan lenguaje natural: atribuir menciones a competidores, leer PDF escaneados, extraer hitos de informes de sostenibilidad, clasificar expedientes dudosos y redactar los textos de los informes. El riesgo principal es que la IA invente datos.

## Decisión
- SDK oficial `anthropic` para Python, envuelto en un único módulo `apps/ia/cliente.py`. Ninguna otra parte del código llama a la API directamente.
- Salidas estructuradas con esquema JSON para todo lo que acabe en la base de datos.
- Lectura de PDF con el soporte nativo de PDF de la API, con texto e imagen de cada página. Así se resuelven los recortes escaneados sin un OCR aparte.
- Citas (citations) cuando la tarea extrae datos de un documento, para guardar la página o fragmento de origen.
- Lotes (Message Batches API) para clasificaciones masivas que no corren prisa.
- Modelo por tarea, configurable por variable de entorno (`IA_MODELO_CLASIFICAR`, `IA_MODELO_EXTRAER`, `IA_MODELO_REDACTAR`).
- Todo resultado de IA queda como borrador y requiere validación humana (ver `06`).

## Datos verificados
- Todos los modelos activos admiten PDF; cada página se procesa como texto y como imagen: https://platform.claude.com/docs/build-with-claude/pdf-support
- Un PDF se puede enviar por URL, en base64 o mediante `file_id` de la Files API (misma página).
- Coste orientativo de un PDF: entre 1.500 y 3.000 tokens de texto por página, a tarifa estándar (misma página).
- La Files API recomienda convertir a PDF los .docx con imágenes (https://platform.claude.com/docs/en/docs/build-with-claude/files).
- Las salidas estructuradas están disponibles de forma general en la API: https://platform.claude.com/docs/es/build-with-claude/structured-outputs
- **Verificado el 06/11/2026** (referencia oficial de la API usada por Claude Code): PDF de hasta 32 MB y 600 páginas por petición (100 en modelos de 200.000 tokens); identificadores y precios de los modelos vigentes en docs/06; las citas no se pueden combinar con la salida estructurada. Queda **por verificar** la lista exacta de modelos con salida estructurada (se comprobará con la primera llamada real).

## Opciones consideradas
| Opción | Valoración |
|---|---|
| Claude con salidas estructuradas y citas (elegida) | Encaja con la regla de trazabilidad |
| OCR local (Tesseract) y reglas | Gratis, pero peor en maquetación de prensa y no atribuye empresas |
| Sin IA | Posible solo para importar y contar; la atribución y la redacción serían manuales |

## Consecuencias
- Hace falta la variable `ANTHROPIC_API_KEY` y un límite de gasto mensual en la aplicación (RNF-09).
- Los informes de sostenibilidad grandes (hasta 468 páginas en la muestra) se dividen por rangos de páginas antes de enviarlos.
- Los prompts se versionan en el repositorio (`apps/ia/prompts/`) y cada llamada registra la versión usada.
