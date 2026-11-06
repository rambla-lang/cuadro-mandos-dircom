# 05. Módulos analíticos

Reglas comunes:
- Solo cuentan las evidencias en estado `validada`, salvo que el usuario active "incluir borradores". En ese caso la pantalla lo indica con una franja visible.
- Toda cifra lleva un enlace a la lista de evidencias que la componen (RF-61).
- Los filtros comunes son periodo, provincia, servicio, competidor y nivel mínimo de evidencia.
- Las empresas marcadas `es_propia` no aparecen en rankings ni comparativas.
- Las cifras mínimas se muestran como mínimos ("al menos 12") cuando la fuente no es exhaustiva (prensa, redes).

## 1. Mapa municipal (RF-50)

**Pregunta que responde:** ¿quién presta agua, residuos o energía en cada municipio y con qué seguridad?

**Datos:** `PrestacionServicio` con alguna evidencia validada. Con la casilla «Incluir borradores» se añaden las que solo tienen borradores, rayadas en el mapa y marcadas «[borrador]» en la tabla. Las evidencias rechazadas no cuentan. Con «todos los alcances», energía excluye el suministro eléctrico (comercializadora), que solo aparece si se elige ese alcance (docs/03).

**Vista mapa (ECharts):**
- Selector de servicio (agua, residuos o energía) y de alcance (por ejemplo, residuos con recogida o limpieza viaria).
- Dos modos de color:
  1. **Por operador**: **tres** empresas con color como máximo; el resto, «Otros operadores»; un municipio con dos o más operadores, «Varios operadores». Por defecto se colorean las tres con más municipios de ese servicio (solo evidencias validadas, en toda la comunidad), así que filtrar por provincia o incluir borradores no cambia los colores; se pueden elegir otras. *Cambio de la Fase 2 (06/11/2026):* el borrador decía hasta 8, pero en un mapa cualquier par de municipios puede ser vecino y la paleta categórica solo supera la validación «todos los pares» con sus tres primeros colores (docs/07, resultado de `scripts/validar_paleta.py`). El tooltip, el panel y la tabla nombran siempre el operador.
  2. **Por nivel de evidencia**: escala de 5 niveles, de `oficial` a `no_localizado`.
- Los municipios sin registro se pintan en gris neutro con el rótulo "No localizado", nunca en blanco ni como "sin servicio".
- Al pasar el ratón: municipio, operador, alcance, año de referencia y nivel. Al hacer clic se abre el panel del municipio.

**Panel del municipio:** tabla de servicio, alcance, operador, gestión, año, vigencia confirmada, nivel y evidencias; más los expedientes de contratación vinculados (los más recientes primero) y las menciones en medios con vínculo territorial.

**Tabla equivalente** (accesibilidad y exportación): una fila por municipio con una columna por servicio, igual que la tabla actual de Veolia.

**Indicadores en la cabecera:**
- Municipios con operador identificado, por servicio: número y porcentaje sobre los municipios del filtro.
- Distribución por nivel de evidencia.
- Top de operadores por número de municipios, por servicio. **Se cuenta municipios con alguna evidencia, no población ni alcance real**, y así se indica.

## 2. Ficha de competidor (RF-51)

Estructura acordada con José Luis, en tres bloques que coinciden con las diapositivas de la presentación:

**Bloque 1**
1. *Percepción interna y contraste*: los textos de `PercepcionInterna` se muestran en un recuadro diferenciado ("Valoración interna, no verificada"), con las evidencias que la confirman o la matizan.
2. *Municipios y servicios*: recuento por servicio y alcance, con lista desplegable y una advertencia fija: "Los recuentos reflejan municipios con alguna evidencia; el alcance puede ser distinto (abastecimiento o redes, recogida municipal, suministro energético o tratamiento consorcial)".
3. *Medios con más presencia*: los 5 medios con más piezas en el periodo, con su número de piezas.
4. *Eventos y premios*: lista de evidencias de esas categorías; en los premios se indica quién los concede si consta.

**Bloque 2**
5. *Grupos de interés*: universidades, fundaciones y asociaciones (evidencias de tipo `alianza` o `grupo_interes`).
6. *Innovación y financiación europea*.
7. *Informes de sostenibilidad y EINF*: hitos extraídos, con la página citada.

**Bloque 3**
8. *Redes sociales*: última observación por red (seguidores, si es visible) e indicador de histórico suficiente. Si no lo hay, se muestra el texto "Actividad no caracterizable con la evidencia pública disponible".
9. *Web corporativa*: la última auditoría.

**Contratación (pestaña adicional):** expedientes con adjudicación a la empresa (o a su grupo) en el territorio, con importes. Las sumas de importes se muestran solo si todos los importes son comparables (con o sin IVA, todos conocidos); si no, se muestra el recuento y la advertencia.

## 3. Visibilidad en medios (RF-52)

**Unidad de recuento: la pieza.** Reglas del documento maestro, implementadas tal cual:
1. Una URL periodística canónica cuenta como una pieza. Dos medios sobre el mismo acto son dos piezas y un hito.
2. No se duplican traducciones, fotografías sueltas, parámetros de seguimiento ni republicaciones del mismo post.
3. Los comunicados propios, posts y documentos oficiales se separan de la prensa.
4. Las piezas compartidas entre empresas se registran una sola vez, pero cuentan para cada empresa: la suma de piezas por marca puede superar el total de piezas.
5. Una sección empresarial o una noticia favorable no se califica como pagada sin evidencia de contratación.
6. La fecha de un acto no sustituye a la fecha de publicación.
7. Los meses con piezas prueban dispersión temporal; los meses sin piezas no prueban silencio.
8. Una denuncia sindical o un recurso contractual se atribuye a la fuente y no se convierte en un hecho probado más amplio.

**Métricas (todas sobre piezas con vínculo territorial `si`, salvo que se indique otra cosa):**

| Métrica | Definición exacta |
|---|---|
| Piezas por competidor | Nº de piezas distintas con `MencionEmpresa` validada para la empresa en el periodo |
| Cuota de piezas | Piezas del competidor / total de piezas distintas del periodo (las compartidas cuentan en el numerador de cada empresa, por eso la suma puede pasar del 100 %, lo que se indica en pantalla) |
| Concentración por medio | % de piezas del total que aportan los N medios principales (el documento maestro usó 3: "concentran 32 de las 57 piezas, un 56 %") |
| Medios por competidor | Nº de medios distintos con al menos una pieza |
| Evolución mensual | Piezas por mes. Los meses sin piezas se pintan, pero no se interpretan como silencio (regla 7) |
| Mezcla de tono | Distribución del sentimiento *según Brandwatch* (`sentimiento_fuente`). Se rotula así y no se presenta como análisis propio |
| Piezas por tipo de fuente | Prensa digital, prensa impresa, redes y comunicados propios, por separado (regla 3) |

**No se calcula:** audiencia o alcance regional estimado, ni "valor publicitario". El documento maestro dejó claro que no son estimables con rigor; aunque Brandwatch exporta `Estimated Reach` y `Ad Value`, no se muestran como resultados.

## 4. Informes automáticos (RF-53, RF-54)

**Informe ejecutivo (docx)**. Estructura del documento maestro:
1. Portada (periodo, ámbito, fecha de revisión, base documental: número de evidencias por tipo).
2. Resumen ejecutivo.
3. Alcance, fuentes y método, con las reglas de interpretación.
4. Análisis por competidor.
5. Matriz comparativa.
6. Lectura transversal.
7. Oportunidades.
8. Límites y siguiente nivel de precisión.
9. Anexo de evidencias (tabla `ID | Marca | Fecha | Fuente | Tema y enlace | Tratamiento / límites`).

**Presentación (pptx)**: portada, mensaje principal, tres diapositivas por competidor (bloques 1, 2 y 3), recomendaciones, y un anexo de método y evidencias. Se siguen las reglas de la skill de informe ejecutivo del usuario: un mensaje por diapositiva en el título, cada cifra con fuente y fecha, y lo no verificado marcado como tal.

**Proceso de generación:**
1. Selección de periodo, competidores y plantilla.
2. Cálculo de métricas (en código, no con la IA).
3. La IA redacta las secciones de texto recibiendo **solo** las métricas calculadas y las evidencias validadas (identificador, fecha, fuente y extracto), con la instrucción de citar `[E-xxxx]` en cada afirmación.
4. Validador posterior: comprueba que cada número del texto aparece en las métricas o en las evidencias aportadas y que cada `[E-xxxx]` existe. Si falla, el texto se marca para revisión y no se publica.
5. Se genera el archivo y queda registrado `InformeGenerado` con las evidencias usadas.
6. La persona revisa el texto en la aplicación antes de descargar la versión final.

## 5. Bandeja de revisión (RF-60)

Una sola cola con filtros por tipo: atribución de mención, vínculo territorial dudoso, vínculo de órgano y municipio, clasificación de servicio, posible duplicado, propuesta de IA en documento y resolución del adjudicatario. Cada elemento muestra el dato original, la propuesta y el motivo, con las acciones aceptar, corregir y rechazar. Las acciones se pueden aplicar en bloque a elementos del mismo tipo.
