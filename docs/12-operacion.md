# 12. Operación del piloto

Guía para el responsable técnico. Plataforma: Render (servicio web gratuito) y Neon (PostgreSQL gratuito), según ADR-002. Verificado el 06/11/2026 en la documentación de Render: el servicio gratuito se duerme a los 15 minutos sin tráfico y tarda alrededor de un minuto en despertar, mientras Render muestra su propia página de carga; el disco es efímero (se pierde al reiniciar, redesplegar o dormirse) y no admite disco persistente; no hay comando previo al despliegue ni consola en el plan gratuito.

## Despliegue inicial

1. **Neon:** crea el proyecto y la base de datos. Copia la cadena de conexión (con `sslmode=require`).
2. **GitHub:** sube el repositorio a un repositorio **privado** (contiene `seed/` con datos de negocio). La integración continua (`.github/workflows/ci.yml`) se ejecuta en cada push.
3. **Render:** «New → Blueprint» con el repositorio. Render lee `render.yaml` y pide los valores marcados `sync: false`:
   - `DATABASE_URL`: la cadena de Neon.
   - `ALLOWED_HOSTS`: el dominio `….onrender.com` que asigne Render.
   - `CSRF_TRUSTED_ORIGINS`: `https://….onrender.com`.
   - `ANTHROPIC_API_KEY` e `IA_PRECIOS_JSON`: vacíos si no se usa la IA todavía. `IA_LIMITE_MENSUAL_EUR` está a 0: la IA queda bloqueada hasta subirlo.
   `SECRET_KEY` la genera Render. Cada arranque ejecuta las migraciones y `preparar_piloto` (municipios, competidores y reglas; idempotente).
4. **Primer administrador:** como no hay consola, se crea desde tu ordenador contra Neon:
   ```bash
   DATABASE_URL='postgres://…neon…' uv run python manage.py createsuperuser
   ```
   Después, en la aplicación, Usuarios → Invitar para el resto (enlace de un solo uso, 72 horas).
5. **Comprueba** `https://…onrender.com/salud/` (debe responder `{"estado": "ok"}`), entra con el administrador y revisa el mapa.

## Carga de datos

- **Tablas municipales:** desde la web (Importar → Tabla municipal) o por comando contra Neon con las plantillas de `seed/plantillas_importacion/`.
- **Contratación:** la carga histórica de PLACSP **solo por comando local** contra Neon (ADR-008):
  ```bash
  DATABASE_URL='postgres://…neon…' uv run python manage.py ingest_placsp --fichero licitacionesPerfilesContratanteCompleto3_2025.zip
  ```
  Desde la web: «Actualizar contratación» para TED y el ZIP del mes en curso o el anterior. **Pendiente (ADR-008, acción 2):** medir en la instancia real si el ZIP mensual (unos 200 MB) cabe en el disco temporal y en tiempo; si no, la actualización de PLACSP pasa a ser solo por comando.
- **Medios:** Importar → Brandwatch (varios CSV a la vez) y Recortes.
- **Documentos:** Importar → Documentos Word.
- **Validación en bloque:** solo cuando una persona con permiso de validar da por buenos todos los borradores. Valida las evidencias en borrador a su nombre (con auditoría) y fija como «parcial» el nivel de las que lo tenían pendiente; nunca toca las propuestas de la IA. Probar antes con `--simular`:
  ```bash
  uv run python manage.py validar_borradores --usuario EMAIL --comentario "Motivo y fecha" --simular
  ```
  Usado el 10/11/2026 en local: el usuario dio por buenos los datos de base (185 validadas; 25 con nivel «parcial»).

## Archivos originales (ADR-003, abierta)

En Render Free los PDF y Word subidos se guardan en un disco que se borra al reiniciar o dormirse. Consecuencias mientras ADR-003 no se decida:
- Lanza la lectura por IA (T2) de los recortes sin texto **justo después de subirlos**; si el servicio se ha reiniciado, súbelos de nuevo (no se duplican: la clave es su huella SHA-256).
- Los informes Word y PowerPoint no dependen del disco: se regeneran al descargarlos desde lo guardado en la base de datos.

## Copia de seguridad semanal

```bash
DATABASE_URL='postgres://…neon…' scripts/copia_seguridad.sh
```

Deja `copias/cuadro_AAAAMMDD-HHMM.dump` (la carpeta está en `.gitignore`). Guárdala fuera del portátil. **Prueba de restauración** (una vez al mes) en un Postgres local vacío:

```bash
createdb cuadro_restaurado && pg_restore --no-owner --dbname=cuadro_restaurado copias/cuadro_AAAAMMDD-HHMM.dump
DATABASE_URL=postgres://localhost/cuadro_restaurado uv run python manage.py check
```

La restauración desde el propio Neon (historial y ramas del plan gratuito) está **por verificar** (docs/11).

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| Página de carga de Render durante un minuto | Normal tras 15 minutos sin uso |
| Error 500 | Registros del servicio en el panel de Render (salen por consola) |
| `/salud/` falla | Comprueba `DATABASE_URL` y el estado de Neon |
| Un trabajo de actualización queda «en curso» | Abre Trabajos: el ejecutor lo retoma si lleva más de 3 minutos sin latido |
| La IA no aparece disponible | El panel de IA dice el motivo: clave, modelo, precio o límite mensual |
| Usuario bloqueado | Espera 15 minutos o, como administrador, borra su bloqueo en Administración → Axes |

## Lista de comprobación del despliegue

- [ ] Repositorio privado en GitHub y CI en verde.
- [ ] Blueprint de Render creado con `render.yaml` y variables rellenas.
- [ ] `/salud/` responde y el login funciona con HTTPS.
- [ ] Primer administrador creado e invitaciones enviadas.
- [ ] Datos cargados (tablas municipales, contratación, medios).
- [ ] Copia de seguridad hecha **y restaurada** en local.
- [ ] Medición de ADR-008 (ZIP mensual de PLACSP en Render) anotada.
