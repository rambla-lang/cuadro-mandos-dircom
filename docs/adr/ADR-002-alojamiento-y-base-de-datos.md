# ADR-002: Alojamiento y base de datos del piloto

**Estado:** Propuesta
**Nota (10/11/2026):** con la retirada de la contratación (ADR-010) desaparece el volumen de PLACSP, que era el principal consumo previsto de Neon.
**Fecha:** 05/11/2026
**Decisores:** responsable de desarrollo; José Luis por el requisito de coste 0 en el piloto

## Contexto
José Luis pide alojamiento gratuito durante el piloto y decidir el de producción más adelante. La aplicación necesita un servicio web Python y PostgreSQL. Los usuarios son pocos y el uso, intermitente.

## Decisión
- Web: Render, instancia Free, desplegada desde el repositorio de GitHub.
- Base de datos: Neon, plan Free (PostgreSQL), en un proyecto dedicado.
- Todo se configura con `DATABASE_URL` y demás variables de entorno, para poder migrar sin tocar código.

## Opciones consideradas

### A. Render Free + Neon Free (elegida)
| Dimensión | Valoración |
|---|---|
| Coste | 0 € |
| Limitaciones | Web: 512 MB, 0,1 CPU, se duerme tras 15 min sin tráfico y tarda en torno a 1 min en despertar. Neon: 0,5 GB y 100 CU-horas por proyecto al mes, suspensión tras 5 min |
| Permanencia | El plan Free de Neon es permanente según su documentación |

### B. Render Free con su Postgres gratuito
Descartada: varias fuentes de terceros indican que la base de datos gratuita de Render caduca a los 30 días (una habla de 90). Las cifras no coinciden, así que se verificará, pero en ambos casos no sirve para guardar datos de forma permanente.

### C. Ejecutar en local (en un ordenador del equipo)
Útil para desarrollo, pero no cumple "equipo DIRCOM, web interna".

## Análisis de compromisos
Lo gratuito obliga a aceptar arranques en frío y límites de memoria y almacenamiento. Para un piloto con pocos usuarios es aceptable si:
- la interfaz avisa cuando el servicio está despertando;
- los importadores trabajan en streaming (RNF-04);
- no se guardan archivos binarios en la base de datos (ADR-003).

## Consecuencias
- Hay que medir en la Fase 0 cuánto ocupa un año de datos de la Comunitat Valenciana. Si supera unos 300 MB, hay que replantear qué se guarda.
- Antes de pasar a producción: instancia sin suspensión, copias de seguridad automáticas y dominio propio.

## Fuentes
- Neon, límites del plan Free: https://neon.com/faqs/free-plan-limits-and-quotas
- Render, resúmenes de precios de 2026 (fuentes de terceros; verificar en la página oficial https://render.com/pricing antes de desplegar).

## Acciones
1. [ ] Verificar en render.com los límites vigentes de la instancia Free y si permite disco persistente.
2. [ ] Crear el proyecto en Neon en la región europea disponible (**por verificar** qué regiones ofrece).
3. [ ] Medir el tamaño de la base de datos tras la carga inicial (Fase 0).

## Verificación y preparación (Fase 8, 06/11/2026)
En https://render.com/docs/free y https://render.com/docs/blueprint-spec: el servicio web gratuito se duerme a los 15 minutos sin tráfico entrante y tarda alrededor de un minuto en despertar (Render muestra su propia página de carga, que cubre el aviso de arranque en frío de docs/07); 750 horas de instancia gratuitas al mes por espacio de trabajo; disco efímero y sin disco persistente; `preDeployCommand` solo en planes de pago. Python con `.python-version` o `PYTHON_VERSION`; uv se usa si hay `uv.lock`. Preparado: `render.yaml`, WhiteNoise, gunicorn (1 proceso, 4 hilos, para que el ejecutor de ADR-007 sea único), `/salud/` y `preparar_piloto` en el arranque. Procedimiento en docs/12. **Por verificar:** RAM y CPU de la instancia gratuita (la página consultada no las da) y la restauración en Neon Free.
