# 08. Seguridad y privacidad

## Autenticación y roles
- Sistema de usuarios de Django. Inicio de sesión con email (modelo de usuario propio con `email` como identificador, creado **en la primera migración**, porque cambiarlo después es costoso).
- Sin registro público. El administrador invita y el usuario fija su contraseña con un enlace de un solo uso.
- Validadores de contraseña de Django activos (longitud mínima 12).
- Bloqueo temporal tras intentos fallidos repetidos: django-axes, 5 fallos seguidos por usuario → 15 minutos (ADR-009, propuesta en la Fase 1).
- Roles con grupos de Django:
  - **Administrador**: todo.
  - **Analista**: importar, revisar, validar, editar evidencias y generar informes.
  - **Lector**: ver y descargar.
- Los permisos se comprueban en el servidor (decorador o mixin), no solo ocultando botones.
- El envío de correo de invitación y recuperación necesita un servicio SMTP (pregunta P-04). Mientras no exista, el administrador genera el enlace y lo comparte por otro canal. Implementado en la Fase 1: pantalla «Usuarios» → «Invitar» o «Enlace para nueva contraseña»; el enlace es de un solo uso (deja de valer al fijar la contraseña) y caduca a las 72 horas (`PASSWORD_RESET_TIMEOUT`).

## Aplicación
- `DEBUG=False`, `SECURE_*` activos (HSTS, cookies seguras, `SECURE_PROXY_SSL_HEADER` en Render), `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` por variable de entorno.
- Subidas: lista blanca de extensiones (`.csv`, `.xlsx`, `.pdf`, `.docx`) y comprobación del tipo real del archivo; tamaño máximo configurable (`SUBIDA_MAX_MB`, 50 por defecto, porque hay informes de 33 MB).
- Los archivos subidos nunca se ejecutan ni se sirven desde la misma ruta que los estáticos.
- Análisis de XML con `lxml` y protección frente a entidades externas (`resolve_entities=False`, `no_network=True`).
- Las peticiones salientes usan un `User-Agent` identificable de la aplicación, con tiempos de espera y reintentos con espera creciente. No se usan datos personales en las cabeceras.

## Secretos
- Solo en variables de entorno: `SECRET_KEY`, `DATABASE_URL`, `ANTHROPIC_API_KEY` y credenciales del almacén.
- `.env.example` sin valores reales. `pre-commit` con detección de secretos.

## Datos personales y confidencialidad
- Las menciones de Brandwatch incluyen autores y cuentas de redes sociales (`Author`, `Full Name`, `Avatar`…). **Solo se guardan los campos necesarios para el análisis.** Por defecto no se importan los datos de autores particulares; sí los de medios y cuentas corporativas (pregunta P-06 para el detalle).
- Las percepciones internas son información confidencial de la empresa: solo las ven usuarios autenticados y no salen en informes sin marcarlas como "Valoración interna".
- Los datos enviados a la API de Claude se limitan a lo necesario para cada tarea (`06`). José Luis confirmó (P-08) que no hace falta visto bueno de TI, legal ni protección de datos para enviar documentos internos a la API de Anthropic.

## Copias y recuperación
- Piloto: exportación manual semanal (`manage.py dumpdata` o `pg_dump`) a la carpeta corporativa. Las funciones de restauración de Neon en el plan Free están **por verificar**.
- Producción: copias automáticas diarias con retención de 30 días y prueba de restauración trimestral.

## Auditoría
- Se registran las acciones de RF-04 y la última conexión de cada usuario.
