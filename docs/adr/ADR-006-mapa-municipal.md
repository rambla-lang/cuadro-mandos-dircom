# ADR-006: Mapa municipal sin base de datos espacial

**Estado:** Propuesta
**Fecha:** 05/11/2026

## Contexto
El mapa colorea municipios según operador o nivel de evidencia. No hacen falta consultas espaciales (distancias, intersecciones): basta unir cada municipio por su código INE con un polígono.

## Decisión
- Los polígonos municipales se convierten una sola vez a GeoJSON simplificado y se sirven como archivo estático, uno por comunidad autónoma.
- La base de datos guarda solo `codigo_ine` por municipio, sin geometrías ni PostGIS.
- ECharts registra el GeoJSON (`echarts.registerMap`) y pinta la capa de datos que envía la vista en JSON.
- Fuente de los límites: Base de Datos de Divisiones Administrativas o líneas límite municipales del IGN/CNIG, descargables desde el Centro de Descargas del CNIG (https://centrodedescargas.cnig.es/), o el servicio WFS de unidades administrativas del IGN. Para la Comunitat Valenciana, el Institut Cartogràfic Valencià publica mejoras geométricas de las líneas límite (https://dadesobertes.gva.es/).
- **Por verificar:** licencia de uso y atribución exigida, el campo que contiene el código INE en el fichero descargado y la fecha de la versión. La atribución se mostrará al pie del mapa.

## Consecuencias
- El script de conversión (`scripts/geo/preparar_municipios.py`) queda en el repositorio con la fecha y la URL exactas de la versión descargada.
- La simplificación debe dejar un GeoJSON ligero, como objetivo menos de 2 MB por comunidad; se mide en la Fase 0.
- Si un municipio de la tabla no tiene polígono (por ejemplo, "EL BOSQUE-CHIVA", que no es un municipio), se lista aparte con una advertencia y no se fuerza en el mapa.

## Verificación (Fase 2, 06/11/2026)
Detalle en `docs/04` §11. Resumen de los «por verificar»:
- **Fuente elegida:** el servicio WFS de unidades administrativas del IGN (una de las opciones de arriba): no exige formulario de descarga y trae el código INE.
- **Licencia y atribución:** CC BY 4.0 ign.es; al pie del mapa, con la fórmula de obra derivada que piden las condiciones del IGN.
- **Campo del código INE:** últimos 5 dígitos de `nationalCode`. Los 542 casan con el INE.
- **Fecha de la versión:** no encontrada en el servicio (`beginLifespanVersion` vacío); se usa la fecha de descarga.
- **Tamaño:** 803 KB tras simplificar conservando la topología, por debajo del objetivo de 2 MB.
- El script es `scripts/geo/preparar_municipios.py`, con dependencias fijadas en su cabecera (PEP 723), que no entran en las dependencias de la aplicación.
- Para el mapa se usan Apache ECharts 6.1.0 y HTMX 2.0.11, servidos desde `static/vendor/` (docs/07).

El estado sigue siendo «Propuesta» hasta que el responsable de desarrollo lo apruebe.
