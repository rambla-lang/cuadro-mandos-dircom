# 09. Calidad y pruebas

## Pirámide de pruebas

| Nivel | Qué | Herramienta | Cuándo se ejecuta |
|---|---|---|---|
| Unitarias | Normalizadores, analizadores (Brandwatch, ATOM, nombre de recorte), reglas de clasificación, cálculo de métricas, validador de informes | pytest | Siempre (`pytest -m "not externo"`) |
| Integración | Importadores completos sobre Postgres de test con fixtures reales; vistas con permisos; generación de docx y pptx | pytest-django | Siempre |
| Contrato externo | Una llamada real a Claude (las de PLACSP y TED se retiraron con la contratación, ADR-010) | pytest `-m externo` | A mano y antes de desplegar |
| E2E | Recorridos clave en el navegador, con captura de pantalla | Playwright | Antes de cerrar cada fase |
| Evaluación de IA | Precisión de T1 y T2 sobre el juego anotado | pytest `-m externo` + informe | Al cambiar un prompt o un modelo |

Objetivo de cobertura: ≥ 80 % en `importers/`, `services/` de métricas y `apps/ia/validacion`. No se persigue cobertura en plantillas ni en el panel de administración.

## Datos de prueba (`tests/fixtures/`)

- `brandwatch/`: la cabecera real de `seed/` y unas 30 filas sintéticas que reproducen casos reales (fila duplicada entre dos exports, URL con `utm_`, idioma ca, mención de "Cox" municipio frente a Cox empresa, `Region` vacía).
- `clipping/`: nombres de archivo reales (lista en `04` §5) y 2 PDF pequeños, uno con texto y otro sin él, generados para el test. No se usan recortes de prensa reales en el repositorio, por derechos de autor.
- `word/`: un docx sintético con la estructura del documento de percepciones (líneas de empresa en mayúsculas seguidas de párrafos).
- `municipios/`: `seed/municipios_veolia_agua.csv`.

## Casos de prueba obligatorios (proceden de problemas reales)

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-01 | Importar dos veces el mismo CSV de Brandwatch | Cero menciones nuevas en la segunda importación |
| CP-02 | Dos exports solapados ("mentions (8)" dentro del periodo de "mentions (9)") | Las menciones comunes no se duplican (por `Resource Id`) |
| CP-03 | Órgano "Ayuntamiento de Llagostera" al buscar Agost | No se vincula con Agost |
| CP-04 | Órgano "Junta de Gobierno del Ayuntamiento de Monforte del Cid" | Se vincula con Monforte del Cid |
| CP-05 | "L'Eliana", "l'Eliana" y "Eliana" | Resuelven el mismo municipio si figuran en `nombres_alternativos` |
| CP-06 (retirado, ADR-010) | Expediente sin adjudicatario | `Adjudicacion` sin empresa y nivel `parcial`, nunca con un nombre inventado |
| CP-07 | Municipio sin ningún registro | Aparece como "No localizado" en el mapa y la tabla, no como 0 |
| CP-08 | Pieza compartida por dos empresas | Cuenta 1 en el total y 1 para cada empresa |
| CP-09 | Texto de la IA con una cifra que no está en las métricas | El validador marca la sección para revisión |
| CP-10 | Texto de la IA que cita `[E-999999]` inexistente | El validador lo rechaza |
| CP-11 | Usuario lector que hace POST a importar | 403 |
| CP-12 | Seguidores "no visible" | Se guarda NULL y la interfaz muestra "no visible" |
| CP-13 | PDF sin capa de texto | Se marca para lectura por IA; con IA desactivada queda pendiente con aviso |
| CP-14 | ATOM con entrada más antigua que la guardada | No sobrescribe |
| CP-15 | Superar el límite mensual de IA | La llamada se bloquea con un mensaje y no se envía a la API |
| CP-16 | Suministro eléctrico de Iberdrola | Se clasifica como `energia/suministro_electrico` y no cuenta como servicio energético en la ficha |

## Definición de terminado (para cada tarea de Claude Code)

- [ ] Tests nuevos o actualizados que fallaban antes del cambio y pasan después.
- [ ] `pytest -m "not externo"` y `ruff` sin errores (indicar la salida).
- [ ] Migraciones generadas y revisadas.
- [ ] Documentación de `docs/` actualizada si cambia el comportamiento.
- [ ] Revisión del subagente `revisor-datos` si se tocan importadores, métricas o informes.
- [ ] En cambios visibles: captura de pantalla revisada.

## Integración continua

GitHub Actions: `ruff`, `pytest -m "not externo"` con un servicio Postgres, y comprobación de migraciones pendientes (`makemigrations --check`). El despliegue en Render se hace desde la rama principal solo si la integración continua pasa.
