# ADR-009: Bloqueo temporal de acceso tras intentos fallidos

**Estado:** Aceptada (06/11/2026, responsable de desarrollo)
**Fecha:** 05/11/2026
**Decisores:** responsable de desarrollo
**Relacionada con:** docs/08 («Bloqueo temporal tras intentos fallidos repetidos. Librería o implementación a decidir en la Fase 1; documentarlo en un ADR»), ADR-002 (Render Free).

## Contexto
La aplicación es interna, con menos de 10 usuarios y acceso por email y contraseña, sin registro público. docs/08 pide un bloqueo temporal tras intentos fallidos repetidos. En el piloto, la aplicación corre detrás del proxy de Render; qué cabeceras pone ese proxy con la IP real del cliente está **por verificar** (Fase 8).

## Decisión
- Usar **django-axes 9.0.0** (versión verificada en PyPI el 05/11/2026; declara compatibilidad con Django 5.2, 6.0 y 6.1), con su backend de base de datos, sin caché ni servicios externos.
- Bloquear **por usuario** (`AXES_LOCKOUT_PARAMETERS = ["username"]`), con el email normalizado (en minúsculas y sin espacios), igual que el login.
- **5 fallos seguidos** → bloqueo de **15 minutos** (`AXES_FAILURE_LIMIT = 5`, `AXES_COOLOFF_TIME = 15 min`). Un acceso correcto reinicia el contador (`AXES_RESET_ON_SUCCESS`).
- Durante el bloqueo, el login responde 429 con una página que explica cuánto esperar y que el administrador puede generar un enlace para fijar una contraseña nueva.
- Se silencia el aviso `axes.W006` (recomienda incluir la IP) porque la decisión de no usar la IP es deliberada.

## Opciones consideradas
| Opción | Valoración |
|---|---|
| **django-axes, por usuario (elegida)** | Librería mantenida y extendida; registra intentos en la base de datos y se administra desde el panel de Django. Bloquear por usuario funciona igual detrás de cualquier proxy |
| django-axes, por usuario e IP | Evita que un tercero bloquee a un usuario sabiendo su email. Detrás del proxy de Render, sin verificar las cabeceras, todos los clientes podrían compartir la misma IP o la IP se podría falsificar. Se reconsiderará en la Fase 8 |
| Implementación propia (contador en la base de datos) | Poco código, pero hay que mantenerla y probar casos que la librería ya cubre |
| django-ratelimit | Limita peticiones por vista; no ofrece bloqueo por cuenta ni registro de intentos |

## Consecuencias
- Un tercero que conozca el email de un usuario puede bloquearlo 15 minutos con 5 intentos. Con menos de 10 usuarios internos se acepta; el administrador puede desbloquearlo borrando sus intentos en el panel (sección «Axes»).
- Los tests que inician sesión deben usar `force_login` o un POST real al login: `client.login()` falla con axes porque no pasa la petición al backend.
- django-axes añade sus tablas y registra cada acceso. El volumen con menos de 10 usuarios es despreciable frente a los 0,5 GB de Neon Free.

## Acciones
1. [x] Fase 1: configurar django-axes y tests de bloqueo (`tests/nucleo/test_bloqueo.py`).
2. [ ] Fase 8: verificar las cabeceras de IP del proxy de Render y decidir si se añade la IP al bloqueo.
