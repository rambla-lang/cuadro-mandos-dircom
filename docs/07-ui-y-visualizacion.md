# 07. Interfaz y visualización

## Mapa de pantallas

| Pantalla | Rol mínimo | Contenido |
|---|---|---|
| Inicio | Lector | Indicadores clave (municipios con operador identificado por servicio, piezas del periodo, pendientes de revisión) y accesos directos |
| Mapa municipal | Lector | Mapa + tabla + panel de municipio (`05` §1) |
| Competidores | Lector | Listado con indicadores y acceso a cada ficha |
| Ficha de competidor | Lector | Bloques 1-3 y pestaña de contratación (`05` §2) |
| Medios | Lector | Visibilidad (`05` §3) |
| Contratación | Lector | Buscador de expedientes con filtros; detalle con enlace a la fuente |
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
- Los estados vacíos explican la causa: "Sin resultados en TED a 05/11/2026; TED solo publica contratos por encima de los umbrales europeos".
- Aviso de arranque en frío: si la primera respuesta tarda, una página ligera indica "La aplicación se está activando…".
- Responsive: las tablas pasan a tarjetas en móvil; el mapa se puede usar con el dedo.

## Reglas de visualización de datos

Método de la skill de visualización usada al redactar este documento, resumido y adaptado:

1. **Primero la forma; el color al final.**
   - Comparar magnitudes entre competidores: barras horizontales ordenadas.
   - Evolución mensual: líneas, o barras si hay pocos meses.
   - Una cifra principal: tarjeta con el número, no un gráfico.
   - Composición por nivel de evidencia: barra apilada al 100 % con 5 segmentos como máximo.
   - Territorio: mapa de coropletas solo cuando la pregunta es "dónde"; si es "cuántos", barras.
2. **Color según su función.**
   - Identidad (operador o competidor): paleta categórica en orden fijo. **El color sigue a la empresa, no a su posición en el ranking**: cada empresa tiene un color asignado y guardado, y un filtro no lo cambia. Como máximo 8 categorías; el resto es "Otros".
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
