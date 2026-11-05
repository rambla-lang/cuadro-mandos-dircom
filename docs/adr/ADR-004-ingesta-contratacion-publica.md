# ADR-004: Cómo se obtienen los datos de contratación pública

**Estado:** Aceptada (por la experiencia del rastreo de noviembre de 2026)
**Fecha:** 05/11/2026

## Contexto
En noviembre de 2026 se rastreó el buscador web de PLACSP (contrataciondelestado.es) municipio a municipio. Se encontró esto:
- El cortafuegos de PLACSP respondió "The requested URL was rejected" tras un volumen alto de peticiones y bloqueó el rastreo durante horas.
- Las búsquedas por nombre fallan en municipios con artículo ("L'Eliana", "El Campello") y mezclan homónimos ("Agost" con "Llagostera", o "Alicante" con la Diputación y la Universidad).
- En municipios con muchos expedientes solo se pudieron leer las páginas más recientes, y los títulos llegaban truncados.
- Para conocer el adjudicatario había que abrir la ficha de cada expediente.

PLACSP y Hacienda publican datos abiertos oficiales en formato ATOM/XML con la información de licitaciones y adjudicaciones.

## Decisión
1. **PLACSP: usar los datos abiertos de sindicación, nunca rastrear el buscador web.** Se procesan los ZIP mensuales del año en curso o anuales de años anteriores, con dos conjuntos:
   - licitaciones de perfiles de contratante alojados en PLACSP (sin contratos menores);
   - licitaciones publicadas mediante agregación (plataformas autonómicas, sin menores).
   Los contratos menores son un conjunto aparte; incluirlos es la pregunta P-07.
2. **TED: Search API v3** (`POST https://api.ted.europa.eu/v3/notices/search`), sin clave, con consulta experta. Solo cubre contratos por encima de los umbrales europeos.
3. **BOE: API de datos abiertos del sumario**, sección V.A (licitaciones públicas y adjudicaciones), después del MVP.
4. Filtrar por territorio con los datos estructurados de ubicación o del órgano de contratación, no por nombre (el campo exacto está **por verificar** en la especificación de sindicación de PLACSP).

## Opciones consideradas
| Opción | Resultado |
|---|---|
| Rastrear el buscador web de PLACSP | Descartada: bloqueos, resultados incompletos y homónimos (comprobado) |
| Datos abiertos ATOM de PLACSP | Elegida: oficial, completa por diseño y reutilizable |
| OpenPLACSP (herramienta oficial que convierte el ATOM a Excel) | Útil para validar a mano lo que importa la aplicación, no como importador |
| Servicios comerciales de licitaciones | Coste; no hace falta en el piloto |

## Datos verificados
- Los datos abiertos de PLACSP se publican en Atom/XML (RFC 4287): manual de OpenPLACSP v2.1, https://contrataciondelestado.es/datosabiertos/DGPE_PLACSP_OpenPLACSP_v.2.1.pdf
- Cada fichero ATOM contiene como máximo 500 entradas y enlaza con el siguiente (`atom:link rel="next"`); el conjunto se actualiza a diario: https://www.hacienda.gob.es/en-GB/GobiernoAbierto/Datos%20Abiertos/Paginas/LicitacionesAgregacion.aspx
- Hay ZIP por año desde el 1 de enero de 2012 y por meses del año en curso: https://www.hacienda.gob.es/en-GB/GobiernoAbierto/Datos%20Abiertos/Paginas/LicitacionesContratante.aspx
- Especificación del formato de sindicación, versión 1.3: https://www.hacienda.gob.es/Documentacion/Publico/D.G.%20PATRIMONIO/Plataforma_Contratacion/especificacion-sindicacion-1-3.pdf
- Incidencia conocida: en 2026 hubo una generación incompleta de ficheros de PLACSP que dejó fuera algunas licitaciones; Hacienda la dio por resuelta el 28/07/2026. Ficha en datos.gob.es: https://datos.gob.es/es/catalogo/e05250001-licitaciones-publicadas-en-los-perfiles-del-contratante-ubicados-en-la-plataforma-de-contratacion-del-sector-publico-excluyendo-los-contratos-menores
- TED Search API: sin clave; en modo paginación, máximo 15.000 avisos recuperables y 250 por página; el modo scroll no tiene límite de avisos: https://docs.ted.europa.eu/api/endpoints/ted-europa-eu.html (esta URL devuelve 404 desde el 05/11/2026; página vigente: https://docs.ted.europa.eu/api/latest/search.html. Resultados de la Fase 0 en `docs/04` §1-2)

## Consecuencias
- La clasificación por servicio y la vinculación con el municipio se hacen sobre campos estructurados (CPV y órgano), mucho más fiables que el título.
- El adjudicatario viene en los datos de resolución del ATOM (estructura exacta **por verificar** en la especificación), sin abrir fichas una a una.
- Hay que guardar de qué fichero y entrada procede cada expediente, porque un expediente cambia de estado a lo largo del tiempo y aparece varias veces. Prevalece la entrada con `updated` más reciente; ver `04`.
- El tamaño de los ZIP está **por verificar** en la Fase 0 antes de decidir si la ingesta cabe en la instancia gratuita.
