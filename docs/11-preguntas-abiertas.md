# 11. Preguntas abiertas y verificaciones pendientes

El reparto de quién decide está explicado en `ENTREGA.md`. José Luis es el propietario del producto; el responsable de desarrollo decide lo técnico.

## Decisiones de producto (Decide: José Luis)

| ID | Pregunta | Bloquea | Opciones o propuesta |
|---|---|---|---|
| P-05 | Redes y webs: ¿basta con introducir a mano los datos públicos básicos o se quiere captura automática de las webs corporativas? | Fase 6 | Hay que revisar los términos de uso de cada red antes de automatizar nada |
| P-06 | ¿Qué datos de autores de Brandwatch se pueden guardar? (Particulares en redes frente a medios y cuentas corporativas) | Fase 4 | Propuesta: no guardar autores particulares |
| P-07 | ¿Incluir contratos menores de PLACSP? | Fase 3 | Más volumen y ruido; muchos servicios municipales pequeños solo aparecen así |
| P-09 | ¿El lector del CEO necesita algo distinto (vista resumida, solo informes)? | Fase 7 | Rol lector actual o vista ejecutiva |
| P-10 | ¿Qué periodo por defecto usan los análisis? (El documento maestro usó 12 meses: del 14/10/2025 al 14/10/2026) | Fase 4 | 12 meses móviles |
| P-12 | ¿Cuándo se anota el juego de evaluación de la IA (50 menciones)? Lo anota José Luis | Fase 5 | — |
| P-13 | Nombre definitivo de la aplicación y colores de marca, si hay guía de estilo | Fase 1 (no bloquea) | — |

## Respondidas por José Luis (05/11/2026)

| ID | Pregunta | Respuesta |
|---|---|---|
| P-08 | ¿Hace falta visto bueno de TI, legal o protección de datos para enviar documentos internos (percepciones) a la API de Anthropic? | **No.** Se pueden enviar, limitando lo enviado a lo necesario para cada tarea (`06`) |
| P-11 | ¿Existe como archivo la tabla de 251 municipios que menciona el documento "Proceso seguido"? | **No está disponible.** Esa tabla se generó en otra herramienta y no se ha localizado. Semillas disponibles: `seed/municipios_veolia_agua.csv` (76 municipios con agua de Veolia), `seed/Municipios_Veolia_agua_residuos_energia.xlsx` (esos 76 con residuos y energía) y `seed/cruce_servicios_municipales_CV.xlsx` (98 registros empresa-servicio-municipio, 87 municipios, 8 empresas, elaborado el 01/11/2026 con búsqueda web: 17 confirmados, 11 parciales y 70 sin verificar la figura jurídica) |
| P-14 | ¿Quién paga la clave de la API de Anthropic que usará la aplicación? | **El responsable de desarrollo.** La cuenta y la clave son suyas |

## Decisiones técnicas (Decide: responsable de desarrollo)

| ID | Pregunta | Bloquea | Propuesta en la documentación |
|---|---|---|---|
| P-01 | Stack | Fase 0 | ADR-001: Django + HTMX + ECharts |
| P-02 | Alojamiento y base de datos del piloto (requisito de José Luis: gratuito durante el piloto) | Fase 8 | ADR-002: Render Free + Neon Free |
| P-03 | Almacenamiento de los archivos originales (PDF y Word) | Fase 4 | ADR-003: tres opciones |
| P-15 | Dónde se ejecuta la carga histórica de PLACSP | Fase 3 | ADR-008 (aceptada): solo por comando local; desde la web, solo el mes en curso si cabe en Render Free |
| P-04 | Correo (SMTP) para invitaciones y recuperación de contraseñas | Fase 1 (no bloquea: hay alternativa manual) | Correo corporativo, servicio transaccional o enlace manual |

Si una decisión técnica afecta a lo que ve o hace el usuario (por ejemplo, arranques en frío lentos o no poder reabrir los PDF originales), se comenta con José Luis antes de cerrarla.

## Verificaciones técnicas que hará Claude Code (ya marcadas en los documentos)

- PLACSP: tamaño de los ZIP, rutas XML, campo de territorio y última versión del expediente (`04` §1).
- TED: campos de consulta y respuesta, y política de uso (`04` §2).
- BOE: endpoint vigente de la API de sumario del BOE (`04` §3).
- Brandwatch: zona horaria de la columna `Date` (`04` §4). Se puede preguntar al soporte de Brandwatch o deducir comparando con fechas de publicación conocidas.
- Límites de PDF de la API de Claude, lista de modelos con salidas estructuradas, precios y caché de prompt (ADR-005, `06`).
- Render: límites vigentes de la instancia Free y disco persistente (ADR-002 y ADR-003).
- Neon: regiones disponibles y restauración en el plan Free (ADR-002, `08`).
- IGN/CNIG o ICV: licencia, campo del código INE y versión del GeoJSON municipal (ADR-006).
- Django 6: si existe un marco de tareas en segundo plano utilizable (ADR-007).
