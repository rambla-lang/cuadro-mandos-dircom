# ADR-007: Trabajos largos (ingestas, lotes de IA, informes)

**Estado:** Propuesta
**Fecha:** 05/11/2026

## Contexto
La actualización es bajo demanda. Las ingestas y la generación de informes pueden tardar minutos. En el plan gratuito no hay trabajador (worker) dedicado gratuito y el servicio web se duerme sin tráfico.

## Decisión
- Modelo `TrabajoIngesta` (tipo, parámetros, estado, progreso, contadores, log y usuario) como cola en PostgreSQL.
- Ejecutor en proceso: al crear un trabajo, un hilo del servidor web toma trabajos pendientes con `select_for_update(skip_locked=True)` y los ejecuta por partes. Cada parte se confirma en la base de datos, de modo que si el proceso se reinicia el trabajo continúa desde la última parte.
- La página del trabajo consulta el progreso con HTMX cada 3 s, lo que además mantiene el servicio despierto mientras alguien mira.
- Los mismos servicios tienen comando `manage.py`, para ejecutarlos en local apuntando a la base de datos de Neon si un trabajo no cabe en la instancia gratuita.
- **Verificado el 05/11/2026** (https://docs.djangoproject.com/en/6.0/topics/tasks/): Django 6 incluye el marco `django.tasks`, pero "no proporciona un mecanismo de trabajador". Solo trae `ImmediateBackend` y `DummyBackend`, pensados para desarrollo y tests, no para producción. Un trabajador real (por ejemplo, el paquete `django-tasks`, 0.12.0 en PyPI) exige un proceso aparte, que la instancia gratuita de Render no ofrece. Se mantiene el ejecutor propio de esta ADR. Si en producción hay trabajador dedicado, valorar migrar a `django.tasks` con una ADR nueva.

Para PLACSP, ADR-008 concreta que la carga histórica se hace solo por comando local y que desde la web solo se actualiza el ZIP mensual, si se confirma que cabe.

## Alternativas
| Opción | Por qué no ahora |
|---|---|
| Celery + Redis | Otro servicio y otra cuenta; excesivo para pocos trabajos al mes |
| Trabajador de pago en Render | Contradice el coste 0 del piloto; será la opción natural en producción |
| GitHub Actions con `workflow_dispatch` | Viable, pero obliga a exponer secretos de base de datos en GitHub y a tener cuota de minutos (**por verificar**) |

## Consecuencias
- Un solo proceso gunicorn con un hilo ejecutor, para evitar dos ejecutores compitiendo; el bloqueo `skip_locked` protege igualmente.
- Revisar en producción: trabajador dedicado y programación periódica.

## Implementación (Fase 3, 06/11/2026)
`apps/nucleo/trabajos.py`: registro de tipos (`@registrar`), `procesar_parte` (cada parte en su transacción), `ejecutar_hasta_terminar` (comandos) y `lanzar_ejecutor` (hilo único por proceso). El hilo se arranca al crear un trabajo desde la web y cada vez que alguien abre la página de trabajos con trabajos activos, de modo que un reinicio del servidor se retoma en cuanto alguien mira. Un trabajo «en curso» sin latido en 3 minutos se considera abandonado y se retoma.
