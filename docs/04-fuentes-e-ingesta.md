# 04. Fuentes e ingesta

Para cada fuente se indica cómo se obtiene, qué se sabe de su formato (verificado o por verificar), la clave para no duplicar y las reglas de importación. Cuando Claude Code compruebe algo marcado como **por verificar**, debe anotar aquí lo que encontró, con la fecha.

Pasos comunes a todos los importadores (skill `.claude/skills/importador-fuente`):
1. Validar la estructura antes de escribir nada. Si falla, el lote se rechaza entero con un mensaje claro.
2. Normalizar: fechas a UTC, importes a Decimal, textos sin espacios duplicados y URL canónica.
3. Hacer upsert por clave natural dentro de una transacción por bloque.
4. Registrar un `LoteImportacion` con sus contadores.
5. Enviar a la bandeja de revisión lo ambiguo, sin decidirlo a ciegas.

---

## 1. PLACSP: datos abiertos de sindicación (ATOM)

**Acceso.** Ficheros ATOM/XML y ZIP publicados por la Plataforma de Contratación del Sector Público y Hacienda (ADR-004). Conjuntos:
- Licitaciones de perfiles de contratante alojados en PLACSP, sin contratos menores. Feed: `https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom`, citado por Hacienda en datos.gob.es.
- Licitaciones publicadas mediante agregación, sin contratos menores. Feed: `https://contrataciondelestado.es/sindicacion/sindicacion_1044/PlataformasAgregadasSinMenores.atom`.
- ZIP por años (desde 2012) y por meses del año en curso. Los ficheros de un ZIP se leen empezando por el `.atom` principal; cada fichero enlaza con el siguiente.

**Verificado.**
- Cada fichero tiene un máximo de 500 entradas y se pagina con `atom:link` `rel="next"`.
- El conjunto se actualiza a diario.
- La especificación del formato es la versión 1.3 (05/08/2020). Incluye `at:deleted-entry` para entradas eliminadas y explica el uso de `feed/entry/updated`.
- Hubo una incidencia de ficheros incompletos, dada por resuelta el 28/07/2026.

**Verificado en la Fase 0 (05/11/2026)** con el ZIP real `licitacionesPerfilesContratanteCompleto3_202610.zip` (perfiles de contratante sin menores, octubre de 2026). Fixture: `tests/fixtures/placsp/perfiles_contratante_202610_extracto.atom`.

- [x] **Tamaños.**

  | Fichero | Tamaño | Cómo se midió |
  |---|---|---|
  | Perfiles, mensual 10/2026 | 193.793.721 bytes (194 MB) comprimido; 1.870 MB descomprimido en 124 ficheros `.atom` | Descarga completa |
  | Perfiles, anual 2025 | 2.172.595.976 bytes (2,17 GB) | Deducido del `ETag` (sin descargar) |
  | Agregación, mensual 10/2026 | 14.837.358 bytes (14,8 MB) | Deducido del `ETag` (sin descargar) |

  El servidor no envía `Content-Length` (respuesta `chunked`), ignora `Range` (no se puede reanudar una descarga) y corta las peticiones `HEAD`. El tamaño sale del `ETag` de Apache (`"<tamaño en hex>-<mtime>"`), un método validado con el mensual: `b8d0eb9` en hexadecimal son exactamente los 193.793.721 bytes descargados. Velocidad observada desde España: entre 165 y 244 KB/s, unos 20 minutos para el ZIP mensual.
- [x] **Contenido del mensual.** 61.638 entradas, 39.995 identificadores únicos (un expediente aparece varias veces en el mes) y 141 `at:deleted-entry`. Un fichero tiene como máximo 500 entradas. El `.atom` principal enlaza con el siguiente mediante `<link rel="next">` y todos van dentro del ZIP.
- [x] **Memoria.** Recorrido completo con `iterparse` y `clear()` leyendo cada miembro del ZIP sin extraerlo: pico de 39 MB de RSS y 24 s de CPU en un portátil. Cabe en 512 MB. El tiempo en una instancia de 0,1 CPU **no se ha medido**.
- [x] **Rutas XML** (prefijos del feed: `cbc`, `cac`, `cac-place-ext`, `cbc-place-ext` y `at`; `CFS` = `entry/cac-place-ext:ContractFolderStatus`):

  | Dato | Ruta | Observaciones |
  |---|---|---|
  | Id de la entrada | `entry/id` (`https://contrataciondelestado.es/sindicacion/licitacionesPerfilContratante/<n>`) | Único por expediente en PLACSP |
  | Versión | `entry/updated` (con zona horaria) | |
  | Enlace a la ficha | `entry/link/@href` | |
  | Nº de expediente | `CFS/cbc:ContractFolderID` | No es único entre órganos |
  | Estado | `CFS/cbc-place-ext:ContractFolderStatusCode` | Observados: `PUB`, `EV`, `ADJ`, `RES`, `PRE`; además `ANUL` en las entradas eliminadas (`at:comment type="ANULADA"`) |
  | Objeto | `CFS/cac:ProcurementProject/cbc:Name` (y `entry/title`) | |
  | Tipo de contrato | `CFS/cac:ProcurementProject/cbc:TypeCode` (+ `SubTypeCode`) | Códigos de la lista `ContractCode`; tabla de valores **no consultada aún** |
  | CPV | `CFS/cac:ProcurementProject/cac:RequiredCommodityClassification/cbc:ItemClassificationCode` (varios) | También por lote |
  | Importe de licitación | `CFS/cac:ProcurementProject/cac:BudgetAmount/cbc:TaxExclusiveAmount` (sin IVA), `cbc:TotalAmount` (con IVA) y `cbc:EstimatedOverallContractAmount` (valor estimado) | `@currencyID="EUR"` |
  | Lugar de ejecución | `CFS/cac:ProcurementProject/cac:RealizedLocation/cbc:CountrySubentityCode` (NUTS) y `cbc:CountrySubentity` (nombre) | Ver filtro territorial |
  | Lotes | `CFS/cac:ProcurementProjectLot` (`cbc:ID[@schemeName="ID_LOTE"]` y `cac:ProcurementProject` con nombre, importes, CPV y lugar) | |
  | Órgano: nombre | `CFS/cac-place-ext:LocatedContractingParty/cac:Party/cac:PartyName/cbc:Name` | |
  | Órgano: identificadores | `…/cac:Party/cac:PartyIdentification/cbc:ID` con `@schemeName` `ID_PLATAFORMA` (siempre), `NIF` (siempre) y `DIR3` (en el 73 % de una muestra de 776 entradas) | |
  | Órgano: dirección | `…/cac:Party/cac:PostalAddress/cbc:CityName`, `cbc:PostalZone` | |
  | Órgano: jerarquía | `…/cac-place-ext:ParentLocatedParty` anidados (p. ej. "Ayuntamientos" › provincia › comunidad › "ENTIDADES LOCALES" › "Sector Público"), a veces con `DIR3` | Profundidad variable |
  | Tipo de poder adjudicador | `…/cbc:ContractingPartyTypeCode` | |
  | Resultado | `CFS/cac:TenderResult/cbc:ResultCode`, `cbc:AwardDate`, `cbc:ReceivedTenderQuantity` y `cbc:Description` | Hay uno por lote (`cac:AwardedTenderedProject/cbc:ProcurementProjectLotID`) |
  | Adjudicatario | `CFS/cac:TenderResult/cac:WinningParty/cac:PartyName/cbc:Name` y `cac:PartyIdentification/cbc:ID` con `@schemeName` `NIF` u `OTROS` (empresas extranjeras) | |
  | Importe de adjudicación | `CFS/cac:TenderResult/cac:AwardedTenderedProject/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount` (sin IVA) y `cbc:PayableAmount` | |
  | Formalización | `CFS/cac:TenderResult/cac:Contract/cbc:ID` y `cbc:IssueDate` | Presente en una parte de los resultados |
  | Fechas de publicación | `CFS/cac-place-ext:ValidNoticeInfo/cbc-place-ext:NoticeTypeCode` (p. ej. `DOC_CD`) + `…/cac-place-ext:AdditionalPublicationStatus/cac-place-ext:AdditionalPublicationDocumentReference/cbc:IssueDate`, con `cbc-place-ext:PublicationMediaName` | Una por anuncio y medio |
  | Plazo de ofertas | `CFS/cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndDate` y `cbc:EndTime` | |
  | Duración | `CFS/cac:ProcurementProject/cac:PlannedPeriod/cbc:DurationMeasure[@unitCode]` o `StartDate`/`EndDate` | |
  | Enlace con TED | `CFS/cbc:UUID[@schemeName="TED"]` | En una parte de las entradas |
  | Modificaciones y prórrogas | `CFS/cac:ContractModification` | |
  | Fondos UE | `CFS/cac:TenderingTerms/cbc:FundingProgramCode` | |

- [x] **Última versión.** Confirmado: el mismo `entry/id` aparece varias veces con distinto `updated` y estado. En la fixture, `…/20815626` sale con `ADJ` (`updated` 2026-10-30) y con `RES` (`updated` 2026-10-31). La regla es quedarse con el `updated` mayor. Una entrada eliminada es `<at:deleted-entry ref="<entry/id>" when="…"><at:comment type="ANULADA"/></at:deleted-entry>`.
- [x] **Vinculación con el municipio sin usar el nombre.** El órgano trae `ID_PLATAFORMA` y `NIF` en todas las entradas, y `DIR3` en la mayoría. No hay código INE de municipio en el órgano. Propuesta para la Fase 3: vincular por `NIF`/`DIR3` del órgano con una tabla de órganos validados. El nombre solo sirve para proponer.
- [x] **Filtro territorial.** `ES52` sí aparece: `CountrySubentityCode` usa NUTS 3 (`ES521` Alicante, `ES522` Castellón y `ES523` Valencia), pero indica el **lugar de ejecución**, no el órgano, y a veces viene sin detallar (`ES`). En el mes: 7.146 entradas con NUTS `ES52*`, 6.819 con código postal del órgano 03/12/46 y 6.640 con ambos. La unión son 7.325 entradas, que corresponden a **4.905 expedientes únicos**. Propuesta: filtrar por la unión (NUTS de ejecución `ES52*` **o** código postal del órgano de la CV) y guardar cuál de los dos criterios se cumplió.
- Dominios: los ZIP se sirven desde `contrataciondelsectorpublico.gob.es` (enlaces de la página de Hacienda, consultada el 05/11/2026), mientras que los `id` y enlaces internos usan `contrataciondelestado.es`. El certificado TLS lo emite la FNMT (`AC RAIZ FNMT-RCM SERVIDORES SEGUROS`), que **no** está en el almacén de macOS ni en el `curl` del sistema, pero **sí** en el bundle de Mozilla (curl.se, `certifi`). Hay que usar `certifi` y no desactivar nunca la verificación.
- URL de los ZIP (página de Hacienda): `…/sindicacion_643/licitacionesPerfilesContratanteCompleto3_AAAAMM.zip` (mensual) y `…_AAAA.zip` (anual); agregación: `…/sindicacion_1044/PlataformasAgregadasSinMenores_AAAAMM.zip`.

**Clave natural.** `entry/id` (confirmado en la Fase 0; `ContractFolderID` no sirve porque se repite entre órganos). Se guarda también el nombre del fichero y el `updated` de la entrada.

**Reglas.**
- Procesar en streaming con `lxml.etree.iterparse` y liberar cada elemento tras leerlo.
- Filtrar por territorio con los campos estructurados: NUTS de ejecución `ES52*` o código postal del órgano de la CV (verificado el 05/11/2026; ver arriba). No filtrar por nombre.
- Si una entrada es más antigua que la que ya hay guardada (`updated` anterior), no se sobrescribe.
- Tratar `deleted-entry`: el expediente se marca como eliminado en la fuente, no se borra.
- Clasificar el servicio por CPV (tabla editable `ReglaClasificacionCPV`) y después por palabras clave del objeto. Si no hay coincidencia, `sin_clasificar` y a la bandeja; la IA es opcional.
- Vincular con el municipio a través del órgano. Las reglas de nombre ("Ayuntamiento de X", "Ajuntament de X", "Pleno…", "Junta de Gobierno…", "Alcaldía…") solo proponen; la confirmación es automática solo con coincidencia exacta y única con `nombres_alternativos`.

**Implementado en la Fase 3 (06/11/2026).** `apps/contratacion/importers/placsp.py`, por comando (`manage.py ingest_placsp --fichero ZIP|ATOM` o `--mes AAAAMM`) o desde la web («Actualizar contratación», solo el mes en curso o el anterior, ADR-008). Cada `.atom` del ZIP es una parte del trabajo (ADR-007).
- **Filtro territorial:** NUTS de ejecución `ES52*` (también en los lotes) o código postal del órgano 03/12/46; se guarda cuál se cumplió en `criterio_territorial`.
- **Vinculación órgano-municipio** (`services.vincular_organo`): candidatos = el texto tras «Ayuntamiento de / Ajuntament de» al final del nombre y, si la jerarquía es «<municipio> › Ayuntamientos › …», el primer nivel; coincidencia exacta y única, restringida a la provincia del código postal; todos los candidatos deben dar el mismo municipio. Órgano municipal sin resolver → bandeja; no municipal → «no aplica» (editable en la administración, donde también se puede asignar una entidad supramunicipal).
- **Clasificación** (`ReglaClasificacion`, editable): primero el CPV con el prefijo más largo (en el orden de la fuente, proyecto y lotes); si ninguno casa, frases del objeto. Reglas iniciales en `seed/reglas_clasificacion.json` (`manage.py cargar_reglas_clasificacion`), con los códigos verificados el 06/11/2026 en la lista oficial CODICE `CPV2008-2.04.gc` de la DGPE (`https://contrataciondelestado.es/codice/cl/2.04/CPV2008-2.04.gc`, 9.454 códigos). El suministro eléctrico (`09310000`, `65300000`) queda como `energia/suministro_electrico` (CP-16).
- **Bandeja, con un cambio respecto a lo previsto:** un expediente sin clasificar **no** va a la bandeja (serían miles de contratos ajenos al análisis: obras, sanidad…); queda como «sin clasificar» y se puede consultar en el buscador. Van a la bandeja los objetos que apuntan a servicios distintos, los órganos municipales sin municipio claro y los adjudicatarios sin empresa del catálogo **solo en contratos de agua, residuos o energía**.
- **Adjudicatario:** por NIF si una empresa del catálogo lo tiene; si no, por alias o nombre, con y sin la forma jurídica final («URBASER, S.A.» → «urbaser»). Al resolverlo en la bandeja se puede guardar el alias y el NIF, y se resuelven solas las demás pendientes que casen. Sin adjudicatario publicado en un expediente `ADJ`/`RES`: adjudicación vacía con nivel `parcial` (CP-06).
- **Versiones:** se guarda la de `updated` mayor; una más antigua o igual no sobrescribe (CP-14). Al actualizar un expediente se rehacen sus lotes y adjudicaciones, conservando la empresa resuelta a mano.
- **Carga real de octubre de 2026 en local (06/11/2026):** 61.638 entradas leídas en 67 s; 4.944 expedientes de la CV (2.361 versiones posteriores aplicadas, 95 versiones antiguas descartadas, 11 anulaciones); 742 órganos: 406 vinculados automáticamente (317 municipios), 328 no municipales y 8 pendientes en la bandeja (EATIM, entidades locales menores y dos nombres que no coinciden con el INE: «Herbés» y «San Vicente Raspeig»). 314 expedientes clasificados en agua, residuos o energía; 217 adjudicatarios de esos contratos a la bandeja (ninguno coincide todavía con el catálogo, que no tiene NIF ni razones sociales).

 (se convierten en tests):
- Homónimos: "Agost" coincidía con "Llagostera" y "la Llagosta"; "Alicante" con la Diputación, el INSS y la Universidad. El órgano debe terminar en el nombre del municipio con límite de palabra y ser un órgano municipal.
- Nombres con artículo o en valenciano: "L'Eliana", "La Pobla de Vallbona", "El Campello", "Xixona/Jijona" y "Tavernes" (Tavernes de la Valldigna).
- "EL BOSQUE-CHIVA" no es un municipio: se buscó como Chiva. Este tipo de entradas se resuelve con un alias a mano.
- "Resuelta" o "Adjudicada" indica la fase del expediente, no la vigencia del servicio.
- El suministro eléctrico no es un servicio energético en este análisis.

## 2. TED: Search API v3

**Acceso.** `POST https://api.ted.europa.eu/v3/notices/search` con consulta experta (la misma sintaxis que la búsqueda experta de la web de TED). No requiere clave.

**Verificado (documentación).** En modo paginación: máximo 15.000 avisos recuperables y 250 por página; el modo scroll no tiene límite de avisos. Fuente original: https://docs.ted.europa.eu/api/endpoints/ted-europa-eu.html, que el 05/11/2026 **devuelve 404**. Página vigente: https://docs.ted.europa.eu/api/latest/search.html, que solo describe la API y remite al Swagger (https://api.ted.europa.eu/swagger-ui/index.html, que carga una especificación de ejemplo y no la de TED). No se ha localizado una especificación OpenAPI pública de TED.

**Verificado con 3 peticiones reales (05/11/2026)**, con al menos 1 s entre ellas. Fixtures en `tests/fixtures/ted/`.
- [x] **Consulta.** Funciona `place-of-performance IN (ES52) AND publication-date>=AAAAMMDD AND publication-date<=AAAAMMDD`. `place-of-performance` es jerárquico: `ES52` devuelve avisos con `ES521` y `ES523`. Para filtrar por tipo, `notice-type IN (can-standard)`. Cuerpo: `{"query", "fields", "limit", "page", "paginationMode": "PAGE_NUMBER"}`. Respuesta: `notices`, `totalNoticeCount`, `iterationNextToken` y `timedOut`.
- [x] **Campos aceptados y su forma en la respuesta:** `publication-number` (texto, `674270-2026`), `notice-type` (`cn-standard`, `can-standard`, `can-social`…), `publication-date` (`2026-10-01+02:00`), `buyer-name` (objeto por idioma: `{"spa": [...]}`), `buyer-identifier` (lista), `buyer-city` (`{"mul": [...]}`), `buyer-country` (`["ESP"]`), `classification-cpv` (lista **con repeticiones**), `place-of-performance` (lista con repeticiones y `ESP`), `contract-nature` (lista), `procedure-type`, `winner-name` (por idioma), `winner-identifier` (lista) y `total-value` (número, sin moneda ni indicación de IVA). Cada aviso trae también `links` a XML, PDF y HTML. No se ha probado qué devuelve la API con un campo inexistente.
- [x] **Cautelas observadas:**
  - `place-of-performance IN (ES52)` también devuelve contratos **de ámbito nacional** que enumeran todas las NUTS de España (por ejemplo, un aviso de Renfe con comprador en Madrid). Hay que combinarlo con la ubicación del comprador (`buyer-city` o `buyer-identifier`) o mandar estos casos a revisión.
  - `winner-identifier` puede venir **enmascarado** (`"****2507*"`). No se debe usar como NIF.
  - El significado exacto de `total-value` (estimado o adjudicado, con o sin IVA) **no está documentado** en lo consultado. Se guarda como "valor TED" sin interpretarlo.
- [x] **Volumen.** C. Valenciana (`ES52`): 639 avisos en octubre de 2026 y 6.861 en 2025, con el ruido de los avisos nacionales incluido.
- [ ] **Política de uso o límite de peticiones:** **no encontrado** en la documentación consultada. Seguimos con un máximo de 1 petición por segundo.

**Verificado el 06/11/2026** (1 petición, fixture `tests/fixtures/ted/search_es52_can_titulo_20261001.json`): `notice-title` existe y llega por idioma (`spa`: «España – <descripción del CPV> – <título>»); `buyer-identifier` trae el `ID_PLATAFORMA` de PLACSP y el NIF del comprador (en el aviso valenciano de la muestra, `20896620133422` y `Q4601065H`), lo que permite cruzar TED con los órganos de PLACSP.

**Implementado en la Fase 3** (`apps/contratacion/importers/ted.py`, `manage.py ingest_ted --desde --hasta` o desde la web): páginas de 100 avisos, una petición por segundo como máximo. Solo se guardan los avisos con **comprador valenciano**: su identificador coincide con un órgano de PLACSP de la CV, o su ciudad es un municipio de la CV con coincidencia exacta. `total-value` se guarda en `datos_fuente.valor_ted` sin interpretar; `winner-name` como adjudicatario literal; `winner-identifier` no se usa. Octubre de 2026: 639 avisos con `ES52`, 363 guardados y 276 descartados, todos con comprador fuera de la CV (Madrid 180, Majadahonda 49, Barcelona 13, Sevilla 7…). El modo por páginas solo devuelve 15.000 avisos: la web limita la actualización de TED a un año.

**Clave natural.** Número de publicación del aviso (por ejemplo, `397637-2021`, como en la tabla actual).

**Reglas.** TED solo cubre contratos por encima de los umbrales europeos, y la interfaz debe decirlo cuando se muestre "sin resultados en TED".

## Estimación de volumen de un año de la Comunitat Valenciana (Fase 0, 05/11/2026)

Estimación, no medición de la base de datos: el tamaño real se medirá con `pg_total_relation_size` tras la primera carga de la Fase 3. Límite de referencia: 0,5 GB en Neon Free (dato de ADR-002, no reverificado hoy) y umbral de alarma de 300 MB (ADR-002).

| Bloque | Base medida | Supuesto | Estimación anual |
|---|---|---|---|
| PLACSP perfiles (sin menores) | 4.905 expedientes únicos de la CV en 10/2026; 503 bytes útiles de media por entrada (p95: 848) | Cota superior: 12 × 4.905 = 58.860 expedientes (en la práctica serán menos, porque un mismo expediente reaparece en varios meses). Factor ×3 por filas de lote y adjudicación, cabeceras de fila e índices: unos 1,5 KB por expediente (2,6 KB con el p95) | **88 MB** (150 MB en el peor caso) |
| PLACSP agregación | ZIP mensual de 14,8 MB frente a 194 MB de perfiles | Proporcional al tamaño (no se ha medido la parte valenciana) | ~7–12 MB |
| TED | 6.861 avisos `ES52` en 2025 | 1,5 KB por aviso | ~10 MB |
| Brandwatch | 2.742 filas en las tres exportaciones de 2026 (RNF-03) | Hasta 10.000 menciones al año, a 5 KB por fila con título, extracto, JSON de columnas útiles e índices | ≤ 50 MB |
| Texto extraído de documentos | 30 recortes y 6 informes de la muestra | Solo texto, sin binarios (ADR-003) | ~10 MB |
| **Total** | | | **~120 MB realista y ~230 MB en el peor caso** |

**Conclusión:** un año cabe en Neon Free y queda por debajo del umbral de 300 MB, siempre que no se guarde el XML completo y que **no** se incluyan contratos menores (P-07, sin medir; añadirían mucho volumen). Para dos años habría que volver a medir.

**Consecuencia para la ingesta (ADR-008, aceptada):** el ZIP mensual (194 MB, unos 20 min de descarga a la velocidad observada, 39 MB de memoria) es viable bajo demanda. El anual (2,17 GB) no es razonable en Render Free: la carga histórica inicial debería hacerse con `manage.py ingest_placsp` en local contra Neon.

## 3. BOE: sección V.A (después del MVP)

**Acceso.** Datos abiertos del BOE. Hay una API de sumario por fecha, documentada para el BORME en `/datosabiertos/api/borme/sumario/{fecha}`. La sección 5A del sumario del BOE corresponde a "Licitaciones públicas y adjudicaciones". El sumario en XML también se obtiene en `https://boe.es/diario_boe/xml.php?id=BOE-S-AAAAMMDD` según la documentación v1.0.
**Por verificar:** el endpoint actual equivalente para el BOE, el formato JSON o XML y los campos del anuncio. La reutilización implica aceptar la licencia del BOE: incluir la atribución.
**Clave natural.** Identificador del anuncio, por ejemplo `BOE-B-2016-49469`.

## 4. Brandwatch: exportación CSV de menciones

**Formato real observado** (tres ficheros de muestra, 05/11/2026):
- Líneas 1 a 7: metadatos entre comillas (`"Mention Data Export"`, `"Mentions","1 to N of N"`, `"Project Id"`, `"Query Id"`, `"Start Date"`, `"End Date"`, `"Xthread Entry Type"`).
- Línea 8: vacía. Línea 9: cabecera de 129 columnas; la primera no tiene nombre (índice de fila).
- `Start Date` y `End Date` vienen en formato texto (`Wed Dec 31 23:00:00 UTC 2025`). La columna `Date` viene como `2026-10-30 08:30:00.000`, sin zona horaria. **Por verificar** si `Date` está en UTC o en la hora del proyecto de Brandwatch. Hasta confirmarlo, se interpreta como UTC y se avisa en la interfaz.
- Columnas útiles: `Query Id`, `Query Name`, `Date`, `Title`, `Snippet`, `Url`, `Domain`, `Sentiment`, `Emotion`, `Page Type`, `Language`, `Country`, `Region`, `City`, `Author`, `Resource Id`, `Thread Id`, `Thread URL`, `Publication Name`, `Estimated Reach`, `Potential Audience`, `Impressions`, `Engagement Score`, `Likes`, `Comments`, `Shares`, `Tags`, `Category Details`.
- Valores observados: `Page Type` es news, twitter o blog; `Sentiment` es neutral, negative o positive; `Language` es es o ca; `Country` siempre Spain; `Region` está vacía en la mayoría de filas.
- Todas las filas tienen el mismo `Query Name` ("MONITORIZACION COMPETENCIA") y `Tags` está vacío. **El export no dice a qué competidor se refiere cada mención**: hay que deducirlo (RF-31).
- Las exportaciones se solapan en fechas (por ejemplo, "mentions (9)" va del 31/05 al 30/10/2026 y "mentions (8)" del 30/09 al 30/10/2026). Por eso hay que deduplicar.
- Cabecera real de referencia: `seed/brandwatch_cabecera_ejemplo.csv`.

**Clave natural.** `Resource Id`; si falta, la URL canónica.

**Reglas.**
- Lector tolerante: detectar la línea de cabecera buscando `"Query Id"` y no fijar un número de línea, y validar que existen las columnas útiles.
- URL canónica: minúsculas en el dominio, sin parámetros de seguimiento (`utm_*`, `fbclid`, etc.) y sin barra final.
- `sentimiento_fuente` se guarda tal cual, como dato de Brandwatch, y no se presenta como análisis propio.
- `Estimated Reach` y similares se guardan en `datos_fuente`, pero no se usan como audiencia real (regla del documento maestro: el alcance regional numérico no es estimable con rigor).
- Atribución a competidores: primero por alias (con límites de palabra y alias que requieren contexto), después propuesta de IA para lo dudoso, y al final validación.
- Pertinencia territorial: `si` si hay un municipio, comarca o provincia valenciana o actividad local en el título o el extracto; `no` si es claramente de otro territorio; `dudoso` en otro caso. El motivo se guarda siempre.

## 5. Recortes de prensa en PDF

**Formato real observado** (30 PDF de muestra):
- Casi todos de 1 página, entre 100 KB y 1,4 MB.
- 7 de los 30 no tienen capa de texto útil (los de Las Provincias, La Razón y ABC): necesitan lectura visual.
- Nombre de archivo con patrón frecuente `MEDIO-EDICION-DD_MM_AAAA-PAGINA.pdf` (por ejemplo, `LEVANTE-GENERAL-01_10_2026-7.pdf` o `El Mundo-Castellon-17_10_2026-27.pdf`), pero no siempre (`Las Provincias3.pdf`, `ABC.pdf`).
- En la muestra, el usuario agrupa los recortes en carpetas por empresa (`Prensa/Aqualia/…`). La aplicación ofrece elegir la empresa al subirlos, como propuesta inicial que se puede corregir.

**Clave natural.** SHA-256 del archivo.

**Reglas.**
- Expresión del patrón de nombre en `apps/medios/clipping.py`, con tests de los nombres reales de arriba.
- Si no hay texto extraíble (menos de unos 200 caracteres en la página), se usa la IA con el PDF (`06`) y se marca `texto_obtenido_por_ia`.
- Un recorte es una `Pieza` de prensa impresa. Si el mismo artículo existe en digital, la vinculación se propone, no se fusiona automáticamente.

## 6. Documentos Word

**Muestras observadas:**
- *Análisis subjetivo: percepciones competencia*: texto sin estilos de título; cada empresa empieza con una línea en mayúsculas ("NEALIS /FACSA") seguida de párrafos.
- *Publicaciones en prensa*: lista de URL agrupadas por empresa ("FACSA (NEALIS):"). Se importa como lista de URL candidatas a `Mencion` manual.
- *Documento maestro*: informe con títulos (Heading 1 y 2) por competidor y tablas de anexo de evidencias con columnas `ID | Marca | Fecha / control temporal | Fuente | Tema y enlace | Tratamiento / límites` (98 evidencias: P001-P057 prensa, S001-S027 social, D001-D014 propias u oficiales). **Es la mejor semilla de evidencias**: se importa una vez como `Evidencia` en estado `borrador`.

**Reglas.**
- Extraer con `python-docx`. Separar por empresa usando el estilo de título o, si no lo hay, las líneas que coinciden con un alias de empresa en mayúsculas.
- Las percepciones internas van a `PercepcionInterna`, nunca a `Evidencia`.

## 7. Informes de sostenibilidad y EINF (después del MVP)

**Muestras:** 6 PDF de entre 0,8 y 33 MB y de 23 a 468 páginas. Al menos uno no tiene capa de texto en su primera página (Global Omnium).
**Reglas:** dividir por rangos de páginas según el límite de la API (**por verificar**) y extraer hitos (premios, alianzas, proyectos europeos, cifras declaradas) con cita de página. Las cifras declaradas por la empresa se guardan con nivel `empresa`.

## 8. Redes sociales y web (datos públicos básicos)

**Decisión de José Luis:** solo datos públicos básicos.
**Implementación MVP:** formulario y plantilla CSV (`perfil_url, red, fecha_observacion, seguidores, publicaciones_observadas, periodo_observado, historico_suficiente, notas`). No hay rastreo automático de redes (pregunta P-05: términos de uso de cada red).
**Web corporativa:** formulario de auditoría (tono, contenidos y usabilidad) con la fecha de observación. Una descarga automática de páginas propias de competidores podría añadirse respetando `robots.txt`; se decidirá en P-05.

## 9. Excel y CSV del usuario (tablas municipales)

**Muestra:** `seed/municipios_veolia_agua.csv`, con columnas `MUNICIPIO, SERVICIO DE AGUAS, SERVICIO DE RESIDUOS, SERVICIOS ENERGÉTICOS` y 76 municipios en mayúsculas. Incluye entradas que no son municipios ("EL BOSQUE-CHIVA") y nombres abreviados ("TAVERNES").
**Muestra enriquecida:** `seed/Municipios_Veolia_agua_residuos_energia.xlsx`, con hojas "Municipios Veolia", "Resumen" y "Método y límites", y columnas de empresa, detalle, fuente, año y nivel por servicio, más hallazgos de PLACSP.
**Muestra multiempresa:** `seed/cruce_servicios_municipales_CV.xlsx`, elaborado el 01/11/2026 solo con búsqueda web. Hojas "Léeme", "Municipios" (columnas `Empresa, Servicio, Municipio, Provincia, Figura, Detalle / duración, Verificación, Fuente`; 98 filas, 87 municipios, 8 empresas), "Cruce por empresa" y "Sin evidencia". Su columna `Verificación` toma los valores `Confirmado`, `Parcial` y `Sin verificar figura`; se mapean a niveles en el asistente: `Confirmado` → revisar la fuente para decidir entre `oficial`, `prensa` o `empresa`; `Parcial` → `parcial`; `Sin verificar figura` → `parcial`. Todo se importa como borrador. El propio fichero advierte que es parcial y no exhaustivo.
**Reglas:** asistente de importación con correspondencia de columnas guardable. Cada nombre de municipio se resuelve contra `Municipio.nombres_alternativos`; lo que no casa va a la bandeja.

**Implementado en la Fase 2 (06/11/2026).** Asistente web en `Importar → Tabla municipal` (archivo, hoja, columnas, valores, vista previa y confirmación) y comando `manage.py importar_tabla_municipal --fichero F --plantilla P --usuario EMAIL [--fecha-consulta AAAA-MM-DD] [--simular]`, que llaman al mismo servicio (`apps/evidencias/importers/tabla_municipal.py`). Las plantillas de las tres semillas están en `seed/plantillas_importacion/`.

- **Qué crea.** Por cada celda de operador: una `Evidencia` (categoría servicio municipal, origen importador, con su lote) y la `PrestacionServicio` que la agrupa. La fecha de consulta es la de elaboración de la tabla cuando se conoce (03/11/2026 en el Excel enriquecido, según su hoja «Método y límites»; 01/11/2026 en el cruce) y, si no, la de importación.
- **Clave natural:** fuente, hoja, municipio tal como viene, servicio, alcance y operador tal como viene (`Evidencia.clave_importacion`, única en la base de datos). Reimportar no duplica nada; los pendientes de la bandeja tampoco se duplican.
- **Municipio.** Coincidencia exacta y única (docs/04 §10); si no, se prueba cada parte separada por «/» y solo vale si todas dan el mismo municipio («JIJONA/XIXONA», «Alcoy / Alcoi»). La columna de provincia solo restringe la búsqueda cuando nombra una sola provincia. Lo demás va a la bandeja con sugerencias que solo orientan. Una fila rechazada en la bandeja no se vuelve a proponer.
- **Operador.** Se resuelve contra los alias y nombres del catálogo sin coincidencias parciales: texto completo; si es una UTE o una lista con «/» o «+», cada parte, y solo si todas dan la misma empresa («Nealis / FACSA» → FACSA); si es «X (Y)», X y después Y («AGUAS DE ALICANTE (VEOLIA)» → Veolia). Un alias marcado `requiere_contexto` (ACCIONA, Cox) no resuelve solo. «No localizado» → gestión no localizada; «Gestión directa…» → directa municipal; «… empresa municipal / pública» → empresa pública. Lo demás queda con el literal en `operador_texto` y va a la bandeja (se puede asignar a una o varias empresas, guardar el texto como alias o dejarlo como operador no catalogado).
- **Nivel.** Correspondencia de valores en el asistente, con una propuesta según la etiqueta con la que empieza el valor («Confirmado (fuente oficial) (contrato de 2019)» → `oficial`). «Decidir en la bandeja» y un `oficial` sin URL dejan la evidencia en **borrador con nivel provisional `parcial`** y la mandan a la bandeja; nunca se rebaja ni se sube un nivel sin que lo decida una persona.
- **URL.** La primera URL literal de la columna de fuente. Si no hay URL pero sí un número de anuncio «TED nnnnnn-aaaa», se forma `https://ted.europa.eu/es/notice/-/detail/nnnnnn-aaaa`, la forma de `links.html.SPA` comprobada en la Search API (§2). Queda anotado en `datos_extra.url_derivada_de`. BOE, actas y prensa sin URL no se completan.
- **«No localizado» sin detalle ni fuente:** no se guarda (no hay nada que trazar); el mapa ya lo muestra como «No localizado». Con detalle o fuente (por ejemplo, «adjudicación publicada sin nombre del adjudicatario») se guarda como evidencia `no_localizado`.
- **Archivo subido:** se guarda en `media/importaciones/pendientes/` solo mientras dura el asistente y se borra al terminar o cancelar; del original queda el SHA-256 en el lote.

**Resultado de las semillas en local (06/11/2026):**

| Fichero (plantilla) | Estado | Evidencias | Prestaciones | A la bandeja |
|---|---|---|---|---|
| `municipios_veolia_agua.csv` (agua, nivel `empresa`) | validada | 69 | 69 | 7 municipios: TAVERNES, EL BOSQUE-CHIVA, BENIPARREL, BENITATXELL, FORMENTERA DE SEGURA, POLOP DE LA MARINA, TEULADA-MORAIRA |
| `Municipios_Veolia_agua_residuos_energia.xlsx` (residuos, energía y suministro; sin la columna de agua, que la propia hoja dice que es la del CSV) | validada | 73 (80 celdas «No localizado» sin datos no se guardan) | 73 | 7 municipios, 60 operadores fuera del catálogo, 10 niveles por decidir (suministro eléctrico sin nivel y oficiales sin URL) |
| `cruce_servicios_municipales_CV.xlsx` | borrador | 87 | 85 | 11 municipios (agregados como «Otros 22 municipios», consorcios, «Alcudia (¿Alcudia de Veo?)»…), 15 niveles «Confirmado» por decidir, 3 operadores |

Una segunda importación de cada fichero no crea nada. «TERESA» casa exactamente con Teresa (Castellón, 12110); hay también Teresa de Cofrentes (Valencia). La regla de coincidencia exacta lo resuelve así; conviene confirmarlo en la tabla de Veolia.

## 10. Municipios y provincias: relación de municipios del INE (Fase 1, verificado el 05/11/2026)

**Fuente:** INE, «Relación de municipios y sus códigos por provincias», referida a 1 de enero de 2026 y publicada el 04/02/2026. Página: https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177031&menu=ultiDatos&idp=1254734710990
**Fichero usado:** `https://www.ine.es/daco/daco42/codmun/26codmun.xlsx` (318.222 bytes; SHA-256 `b4bea7c3cc1b295a73f7fa3ca68b2ef25c3a59833bd91ea5315ae25dcc1ca741`). Copia versionada en `seed/ine/26codmun.xlsx`. La misma página ofrece `diccionario26.xlsx` (todas las provincias en una hoja, con `CODAUTO`) y `26codislas.xlsx`; no se usan.
**Licencia (aviso legal del INE, apartado «Reutilización de la información contenida en este sitio web»):** se permite la reutilización, también comercial, si se cita la fuente («Fuente: Sitio web del INE: www.ine.es», o «Elaboración propia con datos extraídos del sitio web del INE» si se trata la información), no se altera el sentido, se indica la fecha de actualización y no se sugiere que el INE patrocina el uso. La lista de municipios muestra esa atribución al pie.

**Formato observado:** una hoja por provincia, cuyo nombre es el código de provincia (`01` a `52`). Fila 1: título («Relación de municipios y códigos a 1 de enero de 2026»); fila 2: nombre de la provincia («Valencia/València»); fila 3: cabecera `CPRO, CMUN, DC, NOMBRE`; después, un municipio por fila. El código INE de 5 dígitos es `CPRO` + `CMUN`; `DC` es el dígito de control y no se guarda.
**Comunitat Valenciana:** 542 municipios: 141 en Alicante (03), 135 en Castellón (12) y 266 en Valencia (46).
**Nombres:** 35 nombres bilingües con barra (`Elx/Elche`, `Alacant/Alicante`) y 57 con el artículo pospuesto (`Eliana, l'`, `Montesinos, Los`, `Orxa, l'/Lorcha`). No existe ningún municipio llamado «Tavernes»: hay `Tavernes Blanques` (46237) y `Tavernes de la Valldigna` (46238).

**Reglas de importación** (`manage.py cargar_municipios --provincias 03 12 46 --comunidad "Comunitat Valenciana"`):
- Clave natural: `codigo_ine`. Idempotente: una segunda carga no crea ni cambia nada.
- `nombre_oficial` es el nombre del INE tal cual. `nombres_alternativos` recibe cada parte de un nombre bilingüe, la forma con el artículo delante (`l'Eliana`) y la forma sin artículo (`Eliana`). La forma sin artículo no se añade si coincide con la de otro municipio (en la carga de 2026 no hubo ninguna coincidencia).
- Los nombres alternativos añadidos a mano (por ejemplo, `El Bosque-Chiva` para Chiva) se conservan en cargas posteriores. Un municipio que deje de figurar en el fichero se conserva y se anota en el registro del lote.
- La comparación de nombres ignora tildes, mayúsculas, el tipo de apóstrofo, los guiones y la ele geminada (`l·l`). Solo hay coincidencias exactas y únicas: «Agost» no casa con «Llagostera», y «TAVERNES» queda sin resolver (va a la bandeja de revisión).
- Otra comunidad autónoma se carga con el mismo comando y otros códigos de provincia (RF-13).

## 11. Límites municipales para el mapa: WFS de unidades administrativas del IGN (Fase 2, verificado el 06/11/2026)

**Fuente:** servicio WFS INSPIRE «Unidades administrativas de España» del IGN, `https://www.ign.es/wfs-inspire/unidades-administrativas` (WFS 2.0.0), tipo de objeto `au:AdministrativeUnit`. Es una de las fuentes que propone ADR-006.
**Licencia:** `AccessConstraints` del servicio: «CC BY 4.0 ign.es»; `Fees`: «No se aplican condiciones». Las condiciones de la licencia del IGN (`https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf`, documento del CNIG de 13/11/2017) dicen que, para servicios sin datos acoplados, se usa la fórmula del `AccessConstraints`; que una obra derivada antepone «Obra derivada de»; y que la mención debe verse junto al mapa, a pie de mapa. Al pie del mapa: «Límites municipales: obra derivada del servicio WFS «Unidades administrativas» del IGN, CC BY 4.0 ign.es (descarga del 06/11/2026)». El identificador de producto de la tabla de `scne.es/productos.php` no se ha podido consultar (la página no respondió): **no encontrado**.
**Código INE:** campo `nationalCode`, de 11 dígitos: `34` (España) + código de comunidad (`10`) + código de provincia + código INE de municipio de 5 dígitos. Ejemplo: `34100303076` → Guardamar del Segura, `03076`. El nivel se lee en `nationalLevelName` («Municipio», «Provincia»…). Nombre en `name.GeographicalName.spelling.SpellingOfName.text`.
**Versión:** `beginLifespanVersion` viene vacío (`nil`) en las respuestas: **fecha de versión no encontrada** en el servicio. Se anota la fecha de descarga.
**Descarga:** una petición por provincia con filtro `PropertyIsLike` sobre `au:nationalCode` (`341003*`, `341012*`, `341046*`), `outputFormat=application/geo+json`, `srsName` EPSG:4326 y `count=1000`. Tamaños: 11.141.052, 7.759.207 y 11.289.038 bytes (SHA-256 `71b659b4…5e7c35`, `a2421d82…468349`, `bd7e7c17…8b68`). Los ficheros descargados no se versionan.
**Comprobación:** 542 municipios, y los 542 códigos coinciden uno a uno con los del INE (§10). 58 nombres difieren solo en la posición del artículo («el Castell de Guadalest» frente a «Castell de Guadalest, el»); el mapa usa el código, no el nombre.
**Conversión:** `uv run scripts/geo/preparar_municipios.py au_03.geojson au_12.geojson au_46.geojson --salida static/geo/municipios_cv.json --fecha-descarga 2026-11-06`. Simplificación que conserva la topología (bordes compartidos simplificados una vez, sin huecos), tolerancia 0,0003° (unos 30 m) y 4 decimales. Resultado: `static/geo/municipios_cv.json`, 803.130 bytes, por debajo del objetivo de 2 MB de ADR-006.
