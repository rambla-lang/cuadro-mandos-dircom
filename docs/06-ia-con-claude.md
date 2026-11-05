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

Identificadores de modelo vigentes a 05/11/2026 según la información de producto de Anthropic: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`. **Por verificar** en https://platform.claude.com/docs antes de configurarlos. Nunca se escriben en el código.

## Tareas

| Tarea | Entrada | Salida (esquema) | Modelo | Modo |
|---|---|---|---|---|
| T1. Atribuir mención | Título + extracto + lista de competidores con alias y acotaciones | `{empresas:[{empresa_id, fragmento, confianza}], vinculo_territorial: si/no/dudoso, motivo, municipios:[codigo_ine]}` | Clasificar | Lotes si son más de 50 |
| T2. Leer recorte PDF | PDF (texto + imagen) | `{medio, fecha_publicacion, pagina, titular, resumen_breve, empresas:[…], municipios:[…], es_publicidad_identificada: bool}` con citas | Extraer | Directo |
| T3. Clasificar expediente dudoso | Objeto + CPV + órgano | `{servicio, alcance, motivo}` | Clasificar | Lotes |
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
- Usar lotes (Message Batches) para T1 y T3 cuando no hay prisa, y caché de prompt para el bloque fijo de competidores y alias (**por verificar** las condiciones mínimas de la caché).

## Pruebas de la IA

- Los tests unitarios no llaman a la API: usan respuestas grabadas (fixtures JSON) y un cliente falso.
- Juego de evaluación (`tests/eval/`): unas 50 menciones reales ya atribuidas a mano, unos 10 recortes y 1 Word. Se ejecuta a mano (`pytest -m externo`) al cambiar un prompt o un modelo, y se compara precisión y cobertura con la versión anterior. El resultado se anota en `apps/ia/prompts/CHANGELOG.md`.
