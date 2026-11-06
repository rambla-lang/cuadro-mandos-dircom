# 03. Modelo de datos

El centro del modelo es la **Evidencia**: un hecho concreto, fechado y con fuente. Las métricas y los textos se calculan a partir de evidencias validadas.

## Diagrama (simplificado)

```mermaid
erDiagram
  PROVINCIA ||--o{ MUNICIPIO : contiene
  MUNICIPIO }o--o{ ENTIDAD_SUPRAMUNICIPAL : "es miembro de"
  GRUPO_EMPRESARIAL ||--o{ EMPRESA : agrupa
  EMPRESA ||--o{ ALIAS_EMPRESA : "se nombra como"
  EMPRESA ||--o{ ACOTACION_COMPETIDOR : "se limita a"
  ORGANO_CONTRATACION }o--o| MUNICIPIO : "vinculado a"
  ORGANO_CONTRATACION ||--o{ EXPEDIENTE : publica
  EXPEDIENTE ||--o{ LOTE : tiene
  LOTE ||--o{ ADJUDICACION : resuelve
  ADJUDICACION }o--o| EMPRESA : "adjudicatario resuelto"
  PRESTACION_SERVICIO }o--|| MUNICIPIO : en
  PRESTACION_SERVICIO }o--o| EMPRESA : operador
  PRESTACION_SERVICIO }o--o{ EVIDENCIA : "se apoya en"
  EVIDENCIA }o--o{ EMPRESA : menciona
  EVIDENCIA }o--o{ MUNICIPIO : "se refiere a"
  EVIDENCIA }o--|| FUENTE : procede
  MENCION }o--|| MEDIO : "publicada en"
  MENCION }o--o| PIEZA : "cuenta como"
  PIEZA }o--o| HITO : "trata de"
  MENCION ||--o{ MENCION_EMPRESA : atribuye
  DOCUMENTO ||--o{ FRAGMENTO : divide
  FRAGMENTO }o--o| EMPRESA : "trata de"
  PERFIL_DIGITAL ||--o{ OBSERVACION_DIGITAL : registra
  LOTE_IMPORTACION ||--o{ EVIDENCIA : crea
  PROPUESTA_IA }o--|| LLAMADA_IA : "generada por"
  INFORME_GENERADO }o--o{ EVIDENCIA : usa
```

## Enumeraciones (valores fijos en código)

### NivelEvidencia
Son los niveles del análisis vigente. Su significado no cambia sin actualizar este documento.

| Valor | Etiqueta | Cuándo se usa |
|---|---|---|
| `oficial` | Confirmado (fuente oficial) | Anuncio de adjudicación o formalización en PLACSP, TED o BOE; acta municipal; boletín oficial |
| `prensa` | Confirmado (prensa) | Pieza periodística que afirma el hecho; no hay fuente oficial localizada |
| `empresa` | Confirmado por la empresa | Web, nota de prensa, memoria o informe de la propia empresa |
| `parcial` | Parcial | Hay indicios, pero falta una parte: alcance, vigencia, adjudicatario no leído, título truncado o contrato antiguo sin confirmar la vigencia |
| `no_localizado` | No localizado | No se encontró fuente fiable. No equivale a "no existe" |

Reglas:
- Un nivel `oficial` exige una URL de origen oficial guardada.
- La IA nunca deja una evidencia en `oficial`, `prensa` ni `empresa`: propone, y una persona valida.
- La percepción interna **no** es un nivel de evidencia. Es otro tipo de registro (`PercepcionInterna`) y se muestra siempre separada.

### Servicio y alcance
| Servicio | Alcances (`alcance`) |
|---|---|
| `agua` | abastecimiento, saneamiento, depuración, ciclo integral, otro |
| `residuos` | recogida de RSU, limpieza viaria, ecoparque o punto limpio, tratamiento (a menudo consorcial), transporte o transferencia, otro |
| `energia` | mantenimiento de alumbrado público, gestión energética (ESE), instalaciones térmicas o climatización, mantenimiento eléctrico, renovación o eficiencia (obra), suministro eléctrico (comercializadora), otro |

El suministro eléctrico (comercializadora) se guarda como dato complementario y por defecto **no** cuenta como "servicio energético", según el criterio del análisis vigente.

### Otros
- `EstadoValidacion`: `borrador`, `validada`, `rechazada`.
- `Origen`: `importador`, `ia`, `manual`.
- `TipoFuente`: `contratacion_oficial`, `boletin_oficial`, `acta_municipal`, `prensa_digital`, `prensa_impresa`, `red_social`, `web_corporativa`, `informe_empresa`, `documento_interno`, `otra`.
- `CategoriaEvidencia`: `servicio_municipal`, `contrato`, `mencion_medios`, `evento`, `premio`, `alianza`, `innovacion_financiacion`, `sostenibilidad`, `grupo_interes`, `digital`, `otra`.
- `VinculoTerritorial`: `si`, `no`, `dudoso`.

## Entidades

Campos mínimos. Todos los modelos tienen además `creado`, `modificado` y, si procede, `creado_por`.

### territorio
- **Provincia**: `codigo_ine` (2 dígitos, único), `nombre`, `comunidad`.
- **Municipio**: `codigo_ine` (5 dígitos, único), `nombre_oficial`, `nombres_alternativos` (lista, incluye castellano y valenciano y formas con o sin artículo), `provincia`. Además, `nombres_normalizados` (derivado al guardar, sin tildes ni mayúsculas, con índice GIN) para resolver nombres, y `lote_importacion`. Carga y reglas de nombres en `04` §10.
- **EntidadSupramunicipal**: `nombre`, `tipo` (consorcio, mancomunidad, diputación, otro) y municipios miembros. Hace falta porque el tratamiento de residuos suele ser consorcial.

### entidades
- **GrupoEmpresarial**: `nombre`.
- **Empresa**: `nombre`, `grupo`, `nif` (opcional, único si existe), `es_propia` (excluida del benchmarking), `es_competidor_seguido`, `notas`.
- **AliasEmpresa**: `empresa`, `texto`, `tipo` (marca, razón social, abreviatura, marca local), `requiere_contexto` (para alias ambiguos, como "Cox", que también es un municipio).
- **AcotacionCompetidor**: `empresa`, `servicios_incluidos`, `ambito_geografico`, `nota` (por ejemplo, "STV: solo jardines y zonas verdes de Elche"), `fuente` (documento o decisión de la que sale). `servicios_incluidos` vacío significa que la acotación no limita por servicio; la nota explica el límite (caso de STV, cuyo servicio no está en el catálogo).

### evidencias
- **Fuente**: `tipo`, `nombre`, `dominio` o `url_base`.
- **Evidencia**: `codigo` (legible, `E-000123`, único), `clave_importacion` (clave natural del importador, única si existe; Fase 2), `categoria`, `titulo`, `extracto` (máximo unas 300 palabras; no se guardan artículos completos de prensa), `url_origen`, `fecha_publicacion`, `fecha_evento` (opcional; nunca sustituye a la de publicación), `fecha_consulta`, `fuente`, `empresas`, `municipios`, `servicio`, `alcance`, `nivel`, `estado_validacion`, `origen`, `lote_importacion`, `tratamiento_limites` (texto de cautelas, como en el anexo del documento maestro), `datos_extra` (JSON, por ejemplo con quién concede un premio), `validado_por`, `validado_en`.
- **PrestacionServicio** (vista curada que alimenta el mapa): `municipio`, `servicio`, `alcance` (vacío = la fuente no lo concreta), `empresa` (o nulo si es gestión directa, no localizado o pendiente de resolver), `operador_texto` (literal de la fuente, sin reinterpretar; se muestra mientras la empresa está sin resolver), `gestion` (indirecta, directa municipal, empresa pública, consorcial, no localizada), `anio_referencia`, `vigencia_confirmada` (sí, no, desconocida), `nivel`, `evidencias`. Unicidad: (`municipio`, `servicio`, `alcance`, `empresa`) cuando hay empresa; (`municipio`, `servicio`, `alcance`, `operador_texto` normalizado) cuando no la hay, para que dos operadores sin catalogar distintos no se fundan. El nivel y el año se recalculan a partir de sus evidencias no rechazadas: manda el mejor nivel entre las validadas y, si no hay ninguna validada, entre los borradores (la prestación es entonces un borrador). Cambio de la Fase 2.

### contratacion
- **OrganoContratacion**: `id_plataforma` (`ID_PLATAFORMA` de PLACSP, único; vacío si el órgano solo viene de TED), `nif`, `dir3`, `ciudad`, `codigo_postal`, `jerarquia` (los `ParentLocatedParty`), `tipo_poder`, `nombre`, `municipio` (nulo si no está vinculado), `entidad_supramunicipal`, `estado_vinculacion` (`automatica`, `validada`, `pendiente`, `no_aplica`).
- **Expediente**: `fuente` (placsp, ted, boe), `id_externo` (clave natural por fuente; ver `04`), `numero_expediente`, `organo`, `objeto`, `tipo_contrato`, `cpv` (lista), `estado`, `importe_licitacion`, `iva_incluido` (sí, no o desconocido), `fecha_publicacion`, `fecha_actualizacion_fuente`, `url_origen`, `servicio_clasificado`, `alcance_clasificado`, `metodo_clasificacion` (cpv, palabras clave, ia, manual, sin clasificar), `regla_clasificacion`, `entrada_atom_id` y `fichero_origen` para trazar de dónde salió; además `eliminado_en_fuente`, `importe_licitacion_con_iva`, `valor_estimado`, `nuts`, `criterio_territorial` y `datos_fuente` (por ejemplo, el valor de TED sin interpretar). Unicidad: (`fuente`, `id_externo`).
- **Lote**: `expediente`, `numero`, `objeto`, `importe`.
- **Adjudicacion**: `lote` (o el expediente si no hay lotes), `adjudicatario_texto` (literal de la fuente), `adjudicatario_nif` (si viene), `empresa` (resuelta por alias o NIF; nula si no se resuelve), `importe_adjudicacion` (sin IVA), `importe_pagable`, `fecha_adjudicacion`, `fecha_formalizacion`, `duracion_texto`, `codigo_resultado` y `nivel` (`oficial` si la fuente publica el adjudicatario; `parcial` si no, CP-06).
- **ReglaClasificacion** (Fase 3; sustituye a la `ReglaClasificacionCPV` prevista): `tipo` (prefijo CPV o frase del objeto), `patron`, `servicio`, `alcance`, `activa`, `nota`.

### medios
- **Medio**: `nombre`, `dominio` (único; vacío en prensa impresa sin dominio), `ambito` (local, comarcal, regional, nacional, sectorial, agencia; además red social y «sin clasificar» al importar), `grupo_editorial` (opcional).
- **Mencion**: `origen` (brandwatch, clipping, manual), `resource_id` (Brandwatch, único si existe), `url`, `url_canonica`, `fecha_publicacion`, `titulo`, `extracto`, `medio`, `tipo_pagina` (news, twitter, blog…), `idioma`, `sentimiento_fuente` (lo que dice Brandwatch, sin reinterpretar), `region_fuente`, `datos_fuente` (JSON con columnas útiles no modeladas), `vinculo_territorial`, `motivo_vinculo`, `pieza`, `documento` (si sale de un recorte) y `lote_importacion`.
- **MencionEmpresa**: `mencion`, `empresa`, `metodo` (alias, ia, manual), `estado_validacion`, `fragmento_detectado`, `validado_por`, `validado_en`. Única por (`mencion`, `empresa`).
- **Pieza**: la unidad de recuento de prensa (una URL periodística canónica o un recorte). Tiene `codigo` (`P000123`), `tipo` (prensa digital, prensa impresa, redes sociales, comunicado propio), `medio`, `url_canonica` (única si existe), `titulo`, `fecha_publicacion`, `es_comunicado_propio` y `hito`.
- **Hito**: acto o noticia de fondo que agrupa varias piezas ("dos medios sobre el mismo acto son dos piezas y un hito").

### documentos
- **Documento**: `tipo` (recorte, valoracion_interna, informe_sostenibilidad, otro), `nombre_archivo`, `sha256` (único), `ruta_almacen` (vacía en modo sin originales), `paginas`, `texto_extraido`, `texto_obtenido_por_ia`, `lectura` (texto, pendiente de IA, IA, error), `metadatos` (medio, fecha y página deducidos del nombre del archivo), `empresa_propuesta`, `subido_por`. Tipos añadidos en la Fase 6: lista de publicaciones y documento maestro.
- **Fragmento**: `documento`, `empresa`, `pagina_inicio`, `pagina_fin`, `texto`.
- **PercepcionInterna**: `empresa`, `texto`, `documento_origen`, `contraste` (texto que la relaciona con evidencias), `evidencias_relacionadas`.

### digital
- **PerfilDigital**: `empresa`, `red` (instagram, linkedin, x, facebook, youtube, tiktok, web), `url` (única), `cuenta_verificada` (sí, no o desconocido).
- **ObservacionDigital**: `perfil`, `fecha_observacion`, `seguidores` (entero o nulo si no es visible), `publicaciones_observadas`, `periodo_observado`, `historico_suficiente` (bool), `notas`. Nunca se guarda 0 cuando el dato no es visible. Única por (`perfil`, `fecha_observacion`).
- **AuditoriaWeb**: `empresa`, `url`, `fecha`, `tono`, `contenidos_destacados`, `usabilidad` (texto libre con cita de lo observado).

### ia, sistema e informes
- **LlamadaIA**: `tarea`, `modelo`, `version_prompt`, `tokens_entrada`, `tokens_salida`, `coste_estimado`, `estado`, `error`, `usuario`, `objeto_relacionado` (genérico).
- **PropuestaIA**: `llamada`, `tipo_objetivo`, `id_objetivo`, `propuesta` (JSON validado con su esquema), `estado_revision`, `revisado_por`, `comentario`.
- **LoteImportacion**: `tipo`, `parametros`, `archivo_sha256`, `usuario`, `inicio`, `fin`, `leidos`, `nuevos`, `actualizados`, `descartados`, `errores`, `log`. Vive en la app `nucleo` porque la usan todos los importadores.
- **TrabajoIngesta** (app `nucleo`): `tipo`, `parametros`, `estado` (pendiente, en curso, terminado, error, cancelado), `progreso` (estado entre partes), `partes_total`, `partes_hechas`, `contadores`, `log`, `usuario`, `lote_importacion`, `inicio`, `fin`, `latido`. Ver ADR-007.
- **RegistroAuditoria**: `usuario`, `accion`, `objeto`, `antes`, `despues`, `fecha`.
- **ElementoRevision** (bandeja, RF-60; app `nucleo`): `tipo` (municipio no resuelto, operador no resuelto, nivel por decidir; se añadirán los de las fases 3 a 5), `estado` (pendiente, aceptado, corregido, rechazado), `clave` (única, para no duplicar al reimportar), `texto` (el dato original), `motivo`, `propuesta`, `datos` (lo necesario para completar la operación, como la fila pendiente), `objeto` (genérico), `lote_importacion`, `resuelto_por`, `resuelto_en`, `resolucion`, `comentario`.
- **PlantillaImportacion** (app `evidencias`): `nombre` (único), `tipo`, `descripcion`, `configuracion` (correspondencia de columnas y valores del asistente, docs/04 §9).
- **InformeGenerado**: `tipo` (docx, pptx), `parametros`, `archivo`, `evidencias_usadas`, `llamadas_ia`, `generado_por`.

## Reglas de integridad
- Las relaciones `Evidencia`–`Empresa` y `Evidencia`–`Municipio` usan tablas intermedias explícitas con `PROTECT`, para que la restricción de borrado se aplique también a través de la relación muchos a muchos.
- Restricciones de base de datos en `Evidencia`: el nivel `oficial` exige `url_origen`; con `origen = ia`, los niveles `oficial`, `prensa` y `empresa` exigen `validado_por`; el estado `validada` exige `validado_por` y `validado_en`; el alcance debe pertenecer al servicio. `PrestacionServicio` tiene dos restricciones de unicidad parciales (con empresa y sin empresa, ver arriba) y su alcance, si no está vacío, debe pertenecer al servicio.
- Borrar una empresa con evidencias está prohibido (`PROTECT`); se desactiva.
- Una evidencia validada solo se modifica dejando registro de auditoría.
- Las claves naturales de importación tienen restricción `UNIQUE` en la base de datos, no solo en código.
