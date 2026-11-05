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
