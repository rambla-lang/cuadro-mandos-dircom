# 07. Interfaz y visualización

## Mapa de pantallas

| Pantalla | Rol mínimo | Contenido |
|---|---|---|
| Inicio | Lector | Indicadores clave (municipios con operador identificado por servicio, piezas del periodo, pendientes de revisión) y accesos directos |
| Mapa municipal | Lector | Mapa + tabla + panel de municipio (`05` §1) |
| Empresas gestoras | Lector | Listado con indicadores y acceso a cada ficha |
| Ficha de empresa gestora | Lector | Bloques 1-3 (`05` §2) |
| Medios | Lector | Visibilidad (`05` §3) |
| Evidencias | Lector | Buscador global de evidencias; ficha de evidencia con su historial |
| Importar | Analista | Asistentes por fuente, historial de lotes y trabajos |
| Revisión | Analista | Bandeja (`05` §5) |
| Informes | Analista (generar) / Lector (descargar) | Generador e historial |
| Administración | Administrador | Usuarios, catálogos (empresas, alias, acotaciones, reglas CPV), uso de IA y límites |

## Patrones de interfaz

- Diseño sobrio, de uso interno. Barra lateral con las secciones y filtros comunes en una fila sobre los gráficos.
- Cada cifra es un enlace a sus evidencias.
- Los niveles de evidencia se muestran siempre con etiqueta de texto y color, nunca solo con color.
- Los textos de la IA no validados llevan la etiqueta "Borrador IA".
- Las percepciones internas van en un recuadro diferenciado con la etiqueta "Valoración interna".
- Los estados vacíos explican la causa: "Sin resultados en Brandwatch para el periodo elegido a 05/11/2026".
- Aviso de arranque en frío: si la primera respuesta tarda, una página ligera indica "La aplicación se está activando…".
- Responsive: las tablas pasan a tarjetas en móvil; el mapa se puede usar con el dedo.

## Reglas de visualización de datos

Método de la skill de visualización usada al redactar este documento, resumido y adaptado:

1. **Primero la forma; el color al final.**
   - Comparar magnitudes entre empresas gestoras: barras horizontales ordenadas.
   - Evolución mensual: líneas, o barras si hay pocos meses.
   - Una cifra principal: tarjeta con el número, no un gráfico.
   - Composición por nivel de evidencia: barra apilada al 100 % con 5 segmentos como máximo.
   - Territorio: mapa de coropletas solo cuando la pregunta es "dónde"; si es "cuántos", barras.
2. **Color según su función.**
   - Identidad (operador o empresa gestora): paleta categórica en orden fijo. **El color sigue a la empresa, no a su posición en el ranking**: cada empresa tiene un color asignado y guardado, y un filtro no lo cambia. Como máximo 8 categorías; el resto es "Otros".
   - Magnitud: un solo tono, de claro a oscuro.
   - Niveles de evidencia: escala ordenada propia, que no se reutiliza para otra cosa.
   - Los colores de estado (correcto, aviso, error) se reservan para el estado de las importaciones y no se usan en series de datos.
3. **Validar la paleta con un script**, en claro y en oscuro: separación para daltonismo y contraste. No vale "a ojo". Guardar el script en `scripts/validar_paleta.js` o un equivalente en Python, y su resultado en `docs/`.
4. **Nunca dos ejes Y** en un mismo gráfico. Dos medidas de distinta escala van en dos gráficos.
5. **Marcas finas, rejilla discreta y etiquetas selectivas.** Leyenda siempre que haya 2 series o más; sin número en cada punto.
6. **Interacción por defecto:** tooltip al pasar el ratón en barras, puntos y municipios; tabla equivalente debajo o en una pestaña.
7. **Texto con colores de texto**, nunca con el color de la serie.
8. **Revisar visualmente** cada gráfico renderizado (captura en el test E2E) antes de darlo por terminado: solapes, etiquetas cortadas, desbordes.

## Accesibilidad

- Contraste AA en el texto y foco visible.
- Cada gráfico tiene `aria-label` con la conclusión y una tabla de datos accesible.
- No se transmite información solo con color (niveles con etiqueta; en el mapa, con trama opcional).

## Librerías del frontend

- HTMX y Apache ECharts servidos como estáticos versionados (sin CDN en producción, para no depender de terceros).
- CSS: una hoja propia con variables (tokens) o un micro-framework sin compilación. Que Claude Code proponga en la Fase 1 y quede como ADR si se añade algo.

## Validación de la paleta (Fase 2, 06/11/2026)

Script: `scripts/validar_paleta.py` (copia del validador de la skill de visualización; se ejecuta con `python3 scripts/validar_paleta.py "<hex,...>" --mode light [--pairs all] [--ordinal]`). Superficie clara `#fcfcfb`.

| Paleta | Uso | Resultado |
|---|---|---|
| Categórica de 8: `#2a78d6, #eb6834, #1baf7a, #eda100, #e87ba4, #008300, #6250d6, #e34948` | Barras y líneas (pares adyacentes) | Pasa. Peor par adyacente para daltonismo ΔE 9,1; visión normal 19,6. Aviso de contraste (aguamarina, amarillo y rosa por debajo de 3:1): obliga a etiquetas visibles o tabla |
| La misma, todos los pares | Mapas | **No pasa** (verde y naranja ΔE 3,2 con protanopía; rojo y naranja 7,1 con visión normal). Los tres primeros (`#2a78d6, #eb6834, #1baf7a`) sí pasan todos los pares, según la referencia de la paleta. Por eso el mapa por operador usa solo tres colores (docs/05 §1) |
| Ordinal de niveles: `#104281, #256abf, #5598e7, #86b6ef` (oficial → parcial), más «No localizado» en gris `#d9d8d2` | Mapa por nivel y barra de distribución | Pasa con `--ordinal`: un solo tono, luminosidad monótona, saltos de 0,06 o más, extremo claro a 2,06:1 |

Neutros del mapa por operador: «Otros operadores» `#9a9993`, «Varios operadores» `#52514e`, «No localizado» `#d9d8d2`. Siempre van con etiqueta en la leyenda y en el tooltip.

**Diferencia con la regla 2 («cada empresa tiene un color asignado y guardado»):** en el mapa no hay un color guardado por empresa, porque con tres colores no alcanza para las 15 del catálogo. Las tres con color salen de un recuento fijo por servicio, que no cambia con los filtros de provincia ni con los borradores, o las elige el usuario. Si se quiere un color fijo por empresa, habrá que limitar qué empresas pueden tenerlo. Queda para revisar (docs/11, P-18).

**Pendiente:** modo oscuro. La interfaz todavía solo tiene tema claro; cuando se añada, hay que validar los pasos oscuros sobre `#1a1a19`.
