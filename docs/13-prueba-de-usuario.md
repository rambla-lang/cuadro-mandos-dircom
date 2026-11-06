# 13. Prueba de usuario (versión local, 06/11/2026)

Versión completa de las fases 1 a 8, en tu ordenador, con datos reales ya cargados. El despliegue en Render y Neon está preparado (docs/12) y solo falta crear las cuentas.

## Arrancar

```bash
cd cuadro-mandos-dircom
uv run python manage.py runserver
```

Abre http://localhost:8000 y entra con el administrador de desarrollo (su contraseña está en tu `.env`, `DEV_ADMIN_PASSWORD`). Para probar los otros roles, Usuarios → Invitar crea un analista o un lector con un enlace de un solo uso.

## Datos que ya hay en tu base local

| Bloque | Contenido |
|---|---|
| Municipios | 542 de la Comunitat Valenciana (INE) con su polígono (IGN) |
| Tablas municipales | Las tres de `seed/`: agua de Veolia (validada), residuos y energía (validada) y el cruce multiempresa (borradores) |
| Contratación | PLACSP de octubre de 2026 (4.944 expedientes valencianos) y TED de octubre (363 avisos de compradores valencianos) |
| Medios | Los tres exports de Brandwatch (2.500 menciones únicas) y la lista de publicaciones del Word |
| Documentos | Percepciones internas (5 empresas) y las 98 evidencias del anexo del documento maestro, en borrador |
| Bandeja | Unos 985 elementos pendientes de todos los tipos |

## Qué probar (criterios de aceptación de docs/10)

- [ ] **Usuarios y roles (Fase 1).** Invita un analista y un lector; entra con cada uno. El lector no ve Importar, Revisión ni IA, y si fuerza la URL recibe 403.
- [ ] **Mapa (Fase 2).** Agua, residuos y energía; color por nivel y por operador; casilla de borradores. Pulsa un municipio para abrir su panel (servicios, evidencias y contratación). Exporta la tabla a CSV y Excel. «EL BOSQUE-CHIVA» y «TAVERNES» están en la bandeja: resuélvelos (Tavernes de la Valldigna; Chiva o rechazar).
- [ ] **Contratación (Fase 3).** Contratación → filtra por servicio y municipio, abre un expediente y su enlace a PLACSP o TED. Actualizar contratación con TED de unos días (tarda segundos) y mira el progreso en Trabajos. Repite: no duplica.
- [ ] **Medios (Fase 4).** Medios: comprueba el total de piezas y el reparto por competidor (por ejemplo, con una tabla dinámica de los CSV). Cada cifra enlaza con sus piezas. Sube algún recorte PDF.
- [ ] **IA (Fase 5).** Sin clave aparece «No disponible» con el motivo. Para activarla: en `.env`, `ANTHROPIC_API_KEY`, los tres `IA_MODELO_*`, `IA_PRECIOS_JSON` (en euros) e `IA_LIMITE_MENSUAL_EUR` mayor que 0; reinicia y lanza un lote pequeño desde el panel de IA. Las propuestas van a la bandeja.
- [ ] **Fichas (Fase 6).** Competidores → FACSA: valoración interna aparte, municipios, medios, evidencias, redes y contratación. Valida algunas evidencias del anexo (Evidencias → filtro «Borrador») y comprueba que aparecen en la ficha. Añade una observación de redes con «no visible».
- [ ] **Informes (Fase 7).** Hay un borrador generado (Informes). Elige 10 cifras al azar: cada una lleva `[Mn]` o `[E-xxxxxx]`, y el anexo y la tabla de métricas te llevan a sus evidencias. Edita una sección con una cifra inventada: el validador la marca y no deja publicar. Publica y descarga el Word y el PowerPoint.

## Lo que verás vacío o incompleto, y por qué

- **Pocas prestaciones de competidores en el mapa.** El cruce multiempresa entró en borrador (docs/04 §9): hasta que se validen sus evidencias o se resuelva la bandeja, solo cuenta lo validado. La casilla «Incluir borradores» lo muestra.
- **Adjudicaciones sin empresa.** El catálogo no tiene NIF ni razones sociales: los adjudicatarios de agua, residuos y energía están en la bandeja para resolverlos una vez (se guarda el alias o el NIF y los siguientes se resuelven solos).
- **Eventos, premios, grupos de interés, innovación.** Dependen de evidencias con esa categoría; las del anexo entraron como «mención en medios», «digital» u «otra» y hay que reclasificarlas al validarlas.
- **Redes y web.** No hay datos hasta que se introduzcan (no hay rastreo automático, P-05).
- **Informes de sostenibilidad (T5) y BOE.** Posteriores al MVP.

## Decisiones pendientes que afectan a la prueba

P-03 (originales), P-05 (redes), P-06 (autores de Brandwatch, de momento no se guardan), P-07 (contratos menores), P-10 (periodo por defecto: 12 meses), P-12 (anotar el juego de evaluación de la IA, plantilla en `media/eval/menciones_t1.csv`), P-17 (nivel de la tabla de agua de Veolia y «TERESA»), P-18 (colores del mapa por operador). Lista completa en docs/11.
