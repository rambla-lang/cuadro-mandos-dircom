# CLAUDE.md: cuadro-mandos-dircom

Cuadro de mandos web interno para la dirección de comunicación (DIRCOM). Sirve para analizar la competencia en la Comunitat Valenciana: quién presta agua, residuos y energía en cada municipio, contratos públicos, visibilidad en medios, presencia digital e informes ejecutivos. Usuarios: menos de 10, con email y contraseña. Idioma de la interfaz y del código de dominio: español.

Lee `docs/` antes de cambiar algo que afecte a datos, métricas o arquitectura. Si una instrucción de este archivo choca con un documento de `docs/`, avisa en vez de elegir por tu cuenta.

## Regla principal: no inventar

- Nunca escribas en la base de datos, en una pantalla ni en un informe una cifra, fecha, empresa adjudicataria, cita o fuente que no proceda de un registro con fuente trazable.
- Un dato sin fuente se guarda como `No localizado`, nunca como cero ni como "sin contrato".
- "0 resultados" en una búsqueda no significa "no existe". Muéstralo como "sin resultados en la fuente X a fecha Y".
- La salida de la IA es un borrador hasta que una persona la valida (`docs/06-ia-con-claude.md`). La IA nunca asigna por sí sola el nivel "Confirmado".
- Si no sabes algo de una API externa (campos, límites, formato), compruébalo en su documentación o con una petición real y deja el resultado en `docs/04-fuentes-e-ingesta.md`. No lo supongas.

## Stack (ver `docs/adr/`)

- Python 3.12 o superior, Django 6.x, plantillas de servidor + HTMX, Apache ECharts para gráficos y el mapa.
- PostgreSQL (Neon en el piloto). Los tests también usan PostgreSQL, en local (Postgres.app) y en CI; no se usa SQLite (decisión de la Fase 0, 05/11/2026).
- Tareas largas: modelo `TrabajoIngesta` + ejecutor en proceso, y el mismo servicio invocable por comando `manage.py`.
- IA: SDK oficial `anthropic` para Python. Modelos configurables por variable de entorno, nunca escritos en el código.
- Despliegue piloto: Render (servicio web gratuito) + Neon (Postgres gratuito).

## Comandos

```bash
cp .env.example .env                      # y rellena DATABASE_URL con tu Postgres local
uv sync                                   # instalar dependencias
uv run python manage.py migrate
uv run python manage.py cargar_municipios --provincias 03 12 46 --comunidad "Comunitat Valenciana"
uv run python manage.py cargar_competidores_iniciales
uv run python manage.py runserver
uv run pytest                             # todos los tests
uv run pytest -m "not externo"            # sin llamadas a servicios externos (por defecto en CI)
uv run ruff check . && uv run ruff format --check .
uv run python manage.py ingest_ted --desde 2026-01-01 --hasta 2026-10-31
uv run python manage.py ingest_placsp --fichero ruta.zip
uv run python manage.py import_brandwatch ruta.csv
```

Si cambias un comando, actualiza esta sección.

## Estructura

```
config/            settings (base, local, produccion), urls, wsgi
apps/
  nucleo/          usuarios, roles, auditoría, utilidades comunes
  territorio/      municipios, provincias, servicios municipales
  entidades/       empresas, grupos empresariales, alias de marca
  evidencias/      Evidencia, Fuente, NivelEvidencia (núcleo de trazabilidad)
  contratacion/    expedientes, adjudicaciones, importadores PLACSP/TED/BOE
  medios/          menciones, medios, importadores Brandwatch/clipping
  documentos/      PDF y Word subidos, texto extraído, valoraciones cualitativas
  digital/         métricas públicas de redes y webs
  ia/              cliente de Claude, prompts versionados, registro de llamadas
  informes/        plantillas y generación de informes y presentaciones
  cuadro/          vistas de cuadro de mandos (mapa, fichas, visibilidad)
static/  templates/  tests/  docs/  seed/
```

## Convenciones

- Nombres de modelos y campos de dominio en español, sin tildes en el identificador (`municipio`, `adjudicatario`, `nivel_evidencia`). El código técnico genérico, en inglés si es más claro.
- Lógica de negocio en `services.py` o `importers/` de cada app, no en vistas ni en modelos. Las vistas solo orquestan.
- Todo importador es idempotente: importar dos veces el mismo fichero no duplica registros (clave natural documentada en `docs/04`).
- Cada registro importado guarda `fuente`, `url_origen` (si existe), `fecha_consulta` y el identificador del lote de importación.
- Fechas en UTC en base de datos; la interfaz muestra Europe/Madrid.
- Importes en `Decimal`, nunca en float. Guarda si el importe es con o sin IVA cuando la fuente lo indique.
- Migraciones pequeñas y revisables. No edites una migración ya aplicada en producción.

## Forma de trabajar

- Para cualquier cambio no trivial, empieza en modo plan y espera aprobación.
- Escribe primero el test que falla (sobre todo en importadores y métricas), después el código.
- No des una tarea por terminada sin ejecutar `pytest` y `ruff`, y di qué ejecutaste.
- Los tests no llaman a servicios externos salvo los marcados `@pytest.mark.externo`. Usa los ficheros de `tests/fixtures/`.
- No subas secretos. `.env` está en `.gitignore`; usa `.env.example` como plantilla.
- No hagas peticiones masivas a PLACSP: usa sus ficheros de datos abiertos. El buscador web de PLACSP bloqueó un rastreo anterior.
- Cuando cambie el comportamiento de una métrica, actualiza `docs/05-modulos-analiticos.md` en el mismo cambio.

## Skills y subagentes del proyecto

- `.claude/skills/importador-fuente`: pasos obligatorios para crear o modificar un importador.
- `.claude/skills/regla-evidencia`: cómo asignar y mostrar niveles de evidencia.
- `.claude/agents/revisor-datos.md`: pásale cualquier cambio que toque importadores, métricas o informes antes de darlo por bueno.
