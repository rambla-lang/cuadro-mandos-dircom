# Fixtures

Extractos pequeños de fuentes públicas reales, obtenidos en la Fase 0 (05/11/2026). No contienen material de `../muestras-dircom/`.

| Fichero | Origen | Recorte aplicado |
|---|---|---|
| `placsp/perfiles_contratante_202610_extracto.atom` | ZIP `licitacionesPerfilesContratanteCompleto3_202610.zip` (PLACSP, perfiles de contratante sin menores), ficheros `licitacionesPerfilesContratanteCompleto3.atom` y `..._20261001_201704.atom` | Cabecera original sin el enlace `rel="next"`; 5 entradas copiadas literalmente (1 fuera de la CV con adjudicatario extranjero, 1 de la CV `ES521` resuelta con adjudicatario, 1 de la CV `ES521` publicada sin adjudicatario, y la misma entrada `.../20815626` dos veces: `ADJ` con `updated` 2026-10-30 y `RES` con `updated` 2026-10-31) y 1 `at:deleted-entry` (`ANULADA`). Todos los adjudicatarios son empresas; los contactos son institucionales |
| `ted/search_es52_can_standard_202610.json` | `POST https://api.ted.europa.eu/v3/notices/search`, consulta `place-of-performance IN (ES52) AND notice-type IN (can-standard) AND publication-date>=20261001 AND publication-date<=20261031`, `limit` 3 | En `links` solo se conservan las variantes `MUL` y `SPA` |
| `ted/search_es52_2025_total.json` | Misma API, `place-of-performance IN (ES52)` en 2025, `limit` 1 | Sin recorte |
| `tabla_municipal/agua_sintetico.csv` | Sintético (Fase 2), con la forma de `seed/municipios_veolia_agua.csv` | Cinco filas inventadas para los tests: nombres que casan, «TAVERNES» y «EL BOSQUE-CHIVA» para la bandeja, «JIJONA/XIXONA» compuesto y un operador ficticio. Separador `;` para probar la detección |

Los tests de Excel de la Fase 2 construyen el libro en el propio test con `openpyxl` (datos sintéticos).
