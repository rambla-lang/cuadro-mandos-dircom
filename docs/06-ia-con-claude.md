# 06. IA con la API de Claude

Ver ADR-005 para la decisión y las fuentes verificadas.

## Principios

1. **La IA propone y la persona decide.** Toda salida que vaya a la base de datos se guarda como `PropuestaIA` hasta que alguien la valide.
2. **Solo con lo que se le da.** En extracción y redacción, el prompt incluye solo el documento o las evidencias, con la instrucción explícita de no usar conocimiento externo y de devolver `null` o "no consta" cuando el dato no esté.
3. **Salida estructurada.** Esquema JSON por tarea, validado con Pydantic al recibirlo. Si no valida, la llamada se marca como error y no se reintenta más de 2 veces.
4. **Trazable.** Cada llamada queda en `LlamadaIA` con la tarea, el modelo, la versión del prompt, los tokens, el coste estimado y el objeto relacionado.
5. **Con presupuesto.** Si el gasto estimado del mes supera `IA_LIMITE_MENSUAL_EUR`, las nuevas llamadas se bloquean con un mensaje al usuario.

## Configuración

```
ANTHROPIC_API_KEY=
IA_ACTIVADA=true
IA_MODELO_CLASIFICAR=        # modelo pequeño y barato (familia Haiku)
IA_MODELO_EXTRAER=           # modelo intermedio (familia Sonnet)
IA_MODELO_REDACTAR=          # modelo de mayor calidad (familia Sonnet u Opus)
IA_LIMITE_MENSUAL_EUR=
IA_PRECIOS_JSON=             # precios por millón de tokens por modelo, introducidos a mano desde la página oficial
```

Identificadores de modelo vigentes: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`. **Verificado el 06/11/2026** en la referencia oficial de la API de Anthropic usada por Claude Code (tabla de modelos actualizada el 06/10/2026), junto con sus precios por millón de tokens en dólares: Haiku 5.5, 0,10 / 0,50 (hasta 100.000 tokens de entrada); Sonnet 5.5, 2 / 10; Opus 5.5, 4 / 20. El administrador los pasa a euros en `IA_PRECIOS_JSON`. Nunca se escriben en el código.

## Tareas

| Tarea | Entrada | Salida (esquema) | Modelo | Modo |
|---|---|---|---|---|
| T1. Atribuir mención | Título + extracto + lista de empresas gestoras con alias y acotaciones | `{empresas:[{empresa_id, fragmento, confianza}], vinculo_territorial: si/no/dudoso, motivo, municipios:[codigo_ine]}` | Clasificar | Lotes si son más de 50 |
| T2. Leer recorte PDF | PDF (texto + imagen) | `{medio, fecha_publicacion, pagina, titular, resumen_breve, empresas:[…], municipios:[…], es_publicidad_identificada: bool}` con citas | Extraer | Directo |
| ~~T3. Clasificar expediente dudoso~~ | Retirada el 10/11/2026 con la contratación (ADR-010) | — | — | — |
| T4. Dividir Word de percepciones | Texto completo + lista de empresas | `{fragmentos:[{empresa_id, texto}]}`. El texto se copia literal, sin reescribir | Extraer | Directo |
| T5. Hitos de un informe de sostenibilidad | Rango de páginas del PDF | `{hitos:[{tipo, descripcion, cifra_declarada, pagina}]}` con citas | Extraer | Directo por partes |
| T6. Redactar sección de informe | Métricas calculadas + evidencias validadas (id, fecha, fuente, extracto) + estructura | `{parrafos:[{texto, evidencias:[id]}]}` | Redactar | Directo |

## Instrucciones comunes del sistema (plantilla)

Guardar en `apps/ia/prompts/comun_v1.md`. Su sentido:

- Trabajas para la dirección de comunicación. Analizas la competencia en la Comunitat Valenciana.
- Usa solo la información del mensaje. Si un dato no está, devuelve `null` o "no consta". No completes con conocimiento general.
- No conviertas indicios en hechos. Si el texto dice "se prevé" o "según el sindicato", consérvalo.
- No calcules cifras nuevas: usa solo las que se te dan.
- Distingue "la fuente no lo dice" de "no existe".
- Responde en español.

## Salvaguardas específicas

- **T1:** un alias ambiguo ("Cox" es empresa y municipio) solo se atribuye si hay contexto de actividad (agua, energía, etc.); si no, la confianza es baja y va a revisión.
- **T2:** si el PDF es publicidad identificable, se marca y no cuenta como pieza periodística sin validación (regla 5 de `05`).
- **T6:** después de la llamada, el validador comprueba los números y los identificadores (`05` §4). Ningún párrafo sin evidencias pasa a la versión final.
- Los textos de prensa que se envían a la API son extractos, nunca artículos enteros, salvo los PDF que el propio usuario sube.

## Coste

- Precios: no se escriben en el código. El administrador los introduce desde la página oficial de precios. El coste mostrado es una estimación con tokens × precio.
- PDF: la documentación indica entre 1.500 y 3.000 tokens de texto por página. Además, cada página se procesa también como imagen (coste adicional **por verificar**).
- Usar lotes (Message Batches) para T1 cuando no hay prisa, y caché de prompt para el bloque fijo de empresas gestoras y alias (**por verificar** las condiciones mínimas de la caché).

## Pruebas de la IA

- Los tests unitarios no llaman a la API: usan respuestas grabadas (fixtures JSON) y un cliente falso.
- Juego de evaluación (`tests/eval/`): unas 50 menciones reales ya atribuidas a mano, unos 10 recortes y 1 Word. Se ejecuta a mano (`pytest -m externo`) al cambiar un prompt o un modelo, y se compara precisión y cobertura con la versión anterior. El resultado se anota en `apps/ia/prompts/CHANGELOG.md`.

## Implementación (Fase 5, 06/11/2026)

- `apps/ia/cliente.py` es el único punto de llamada (SDK `anthropic` 2.1.0). Petición con salida estructurada (`output_config.format` de tipo `json_schema`) y nivel de esfuerzo por tarea (`low` en T1 y T3, `medium` en T2 y T4). El sistema común y el catálogo de empresas van marcados para la caché de prompt.
- **Disponibilidad:** la IA no se usa si falta la clave, el modelo o el precio del modelo en `IA_PRECIOS_JSON` (sin precio no se puede controlar el gasto), si `IA_ACTIVADA=false` o si el gasto estimado del mes alcanza `IA_LIMITE_MENSUAL_EUR` (por defecto 0: todo bloqueado hasta configurarlo). La llamada bloqueada se registra y no se envía (CP-15).
- **Coste estimado:** tokens × precio; la escritura en caché a 1,25× y la lectura a 0,1× del precio de entrada (referencia oficial del SDK).
- **Rechazos:** con modelos Sonnet u Opus se envía `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`), que reintenta en otro modelo si el elegido rechaza la petición por seguridad. Se desactiva con `IA_FALLBACKS=false`. Si aun así hay rechazo, la llamada queda como «rechazada».
- **Validación:** la respuesta se valida con Pydantic (`apps/ia/esquemas.py`); si no valida, se reintenta como mucho 2 veces y queda en error.
- **Propuestas:** cada resultado crea una `PropuestaIA` y un elemento «Propuesta de la IA» en la bandeja. Al aceptarla, la persona elige qué empresas acepta; las atribuciones quedan con método `ia` y validadas por esa persona.
- **Lotes:** desde Panel IA, como mucho 50 objetos por lote, como trabajo por partes (ADR-007). **No se usa todavía la Message Batches API** (50 % más barata, asíncrona): queda como mejora cuando haya volumen.
- **T2 sin citas:** las citas de la API son incompatibles con la salida estructurada (devuelven un error 400), así que T2 pide la transcripción literal en el JSON y no usa citas. Límites de PDF verificados en la misma referencia: 32 MB por petición y 600 páginas (100 en modelos de 200.000 tokens de contexto).
- **T5 y T6:** T5 (informes de sostenibilidad) es posterior al MVP; T6 se implementa con los informes (Fase 7).
- **Juego de evaluación:** `manage.py preparar_eval_menciones` exporta 50 menciones al azar (semilla fija) a `media/eval/menciones_t1.csv`, fuera del repositorio porque contiene extractos de prensa. Se anota a mano (P-12) y se mide con `pytest -m externo tests/eval`.
