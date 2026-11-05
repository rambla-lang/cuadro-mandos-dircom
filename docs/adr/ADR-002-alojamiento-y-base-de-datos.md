# ADR-002: Alojamiento y base de datos del piloto

**Estado:** Propuesta
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
