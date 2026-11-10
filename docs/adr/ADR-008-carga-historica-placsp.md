# ADR-008: Carga histórica de PLACSP solo por comando local

**Estado:** Sustituida por ADR-010 (10/11/2026). Antes: aceptada (05/11/2026, responsable de desarrollo)
**Fecha:** 05/11/2026
**Decisores:** responsable de desarrollo; José Luis queda informado porque afecta a quién puede lanzar la carga inicial
**Relacionada con:** ADR-002 (Render Free y Neon Free), ADR-004 (datos abiertos de PLACSP) y ADR-007 (trabajos largos). No sustituye a ninguna: concreta dónde se ejecuta cada tipo de ingesta de PLACSP.

## Contexto
ADR-007 prevé que las ingestas se lancen desde la web (`TrabajoIngesta` + hilo en proceso), con un comando `manage.py` como alternativa si el plan gratuito se queda corto. La Fase 0 midió los ficheros reales (`docs/04` §1, 05/11/2026):

| Fichero | Tamaño | Otras mediciones |
|---|---|---|
| ZIP mensual de perfiles (10/2026) | 194 MB comprimido; 1.870 MB descomprimido en 124 `.atom` | 61.638 entradas, de ellas 4.905 expedientes únicos de la C. Valenciana. Recorrido en streaming: pico de 39 MB de memoria y 24 s de CPU en un portátil |
| ZIP anual de perfiles (2025) | 2,17 GB comprimido | Del orden de 10 veces el mensual (no descargado) |
| ZIP mensual de agregación (10/2026) | 14,8 MB | No descargado |

Además, en las pruebas:
- **El servidor de PLACSP no admite reanudar descargas.** Ignora `Range` y no envía `Content-Length`, así que un corte obliga a empezar de cero.
- **La descarga es lenta:** se observaron entre 165 y 244 KB/s desde España (unos 20 min para el mensual). A esa velocidad, el anual tardaría unas 2,5 h.
- **Un ZIP solo se puede leer completo:** su índice está al final, de modo que hay que guardarlo en un fichero temporal antes de procesarlo.

En Render Free, el servicio se duerme a los 15 min sin tráfico entrante, tiene 0,1 CPU y 512 MB de memoria, y el espacio de disco temporal disponible está **por verificar**. Un trabajo de horas que no se puede reanudar a mitad de la descarga no encaja ahí.

## Decisión
1. **Carga histórica** (ZIP anuales y cualquier carga de más de un mes): **solo** con `manage.py ingest_placsp --fichero <zip>`, ejecutado en local por el responsable técnico con `DATABASE_URL` apuntando a Neon. La interfaz web no ofrece esta opción.
2. **Actualización bajo demanda desde la web:** solo el ZIP mensual del mes en curso o del anterior (unos 200 MB), con las dos condiciones de abajo:
   - el ZIP se descarga a un fichero temporal y cada `.atom` interno es una "parte" de `TrabajoIngesta` que confirma su progreso (ADR-007). Si el proceso se reinicia después de la descarga, se continúa por el siguiente `.atom`; si se corta durante la descarga, se vuelve a descargar;
   - **condicionado** a medir en la Fase 3, sobre la instancia real de Render, el espacio temporal disponible y el tiempo total (descarga más proceso). Si no cabe o pasa de unos 30 minutos, la actualización de PLACSP también pasa a ser solo por comando y el botón "Actualizar contratación" ofrece solo TED. Ese cambio se anota aquí, sin ADR nueva.
3. **TED** se mantiene en la web: son respuestas JSON pequeñas y paginadas, sin ficheros grandes.
4. **Un único servicio de importación**, invocado igual desde el comando y desde el trabajo web, con la misma idempotencia por `entry/id` y `updated` (docs/04 §1). El comando acepta un ZIP ya descargado (`--fichero`), para no repetir descargas.

## Opciones consideradas
| Opción | Valoración |
|---|---|
| Todo desde la web, también el histórico | Descartada: 2,17 GB a la velocidad observada son horas de descarga sin poder reanudar, en un servicio que se duerme y sin disco temporal garantizado |
| **Histórico por comando local y mes actual desde la web, si se confirma que cabe (elegida)** | Coste 0; el caso de uso diario (actualizar el último mes) sigue en la web; la carga pesada se hace una vez |
| GitHub Actions con `workflow_dispatch` | Viable más adelante: más disco y tiempo que Render Free. Exige guardar la `DATABASE_URL` de Neon como secreto de GitHub y depende de la cuota de minutos (**por verificar**). Se puede reconsiderar sin cambiar el servicio de importación |
| Trabajador de pago en Render | Contradice el coste 0 del piloto; es la opción natural en producción (ADR-002, ADR-007) |
| Leer el feed ATOM en línea en lugar de los ZIP | Descartada para cargas de un mes o más: el XML viaja sin comprimir (1,87 GB por mes frente a 194 MB del ZIP). Podría servir para actualizaciones de pocos días; se valorará en la Fase 3 si hace falta |

## Consecuencias
- La carga inicial la hace el responsable técnico, no el analista. Se documentará en `docs/12-operacion.md` (Fase 8): qué años cargar, el comando exacto y cómo comprobar el resultado.
- La carga local consume horas de cómputo de Neon (100 CU-horas al mes en el plan Free, dato de ADR-002). Una carga anual debería caber, pero se medirá en la primera ejecución y se anotará aquí.
- La interfaz debe explicar por qué no hay opción de "cargar años anteriores" y quién la hace.
- Los contratos menores (P-07) no están incluidos. Si se aprueban, habrá que medir su volumen y revisar esta ADR.

## Acciones
1. [x] Fase 3: implementado `ingest_placsp --fichero` (y `--mes`) con partes por `.atom`. El mes de octubre de 2026 tarda 67 s en un portátil a partir del ZIP ya descargado (06/11/2026).
2. [ ] Fase 3: medir en Render Free el espacio temporal, el tiempo de descarga y el tiempo de proceso del ZIP mensual; anotar el resultado aquí y decidir el punto 2.
3. [ ] Primera carga anual en local: anotar la duración, las CU-horas de Neon consumidas y el tamaño de la base de datos (`pg_total_relation_size`) en `docs/04`.
4. [ ] Fase 8: describir el procedimiento en `docs/12-operacion.md`.
