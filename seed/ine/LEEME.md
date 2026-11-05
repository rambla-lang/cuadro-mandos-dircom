# Relación de municipios del INE

- `26codmun.xlsx`: «Relación de municipios y códigos a 1 de enero de 2026», descargado el 05/11/2026 de https://www.ine.es/daco/daco42/codmun/26codmun.xlsx (SHA-256 `b4bea7c3cc1b295a73f7fa3ca68b2ef25c3a59833bd91ea5315ae25dcc1ca741`).
- Fuente: Sitio web del INE: www.ine.es. Reutilización según el aviso legal del INE (cita de la fuente obligatoria).
- Se carga con `uv run python manage.py cargar_municipios --provincias 03 12 46 --comunidad "Comunitat Valenciana"`. Formato y reglas en `docs/04-fuentes-e-ingesta.md` §10.
