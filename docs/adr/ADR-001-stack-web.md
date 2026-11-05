# ADR-001: Stack de la aplicación web

**Estado:** Propuesta (decide el responsable de desarrollo; ver ENTREGA.md)
**Fecha:** 05/11/2026
**Decisores:** responsable de desarrollo (técnico); José Luis (propietario del producto) para el impacto en el usuario

## Contexto
Cuadro de mandos interno para menos de 10 usuarios con email y contraseña, roles, subida de archivos, importadores de datos, IA e informes Word y PowerPoint. Lo construirá Claude Code con supervisión de una persona que no es desarrolladora a tiempo completo. Prima la sencillez de mantenimiento sobre la sofisticación. El trabajo de datos (pandas, lectura de PDF y Word, generación de docx y pptx) es más maduro en Python.

## Decisión
Django 6.x con plantillas de servidor, HTMX para la interactividad parcial y Apache ECharts para los gráficos y el mapa. Un solo lenguaje (Python) en el servidor y nada de compilación de frontend.

## Opciones consideradas

### A. Django + HTMX + ECharts (elegida)
| Dimensión | Valoración |
|---|---|
| Complejidad | Baja: un proceso, un lenguaje, sin API intermedia |
| Coste | Cabe en la instancia gratuita |
| Escalabilidad | Sobrada para menos de 10 usuarios |
| Encaje con Claude Code | Alto: framework estable y muy documentado, con convenciones fuertes |

**A favor:** usuarios, contraseñas, permisos, administración, formularios, migraciones y protección CSRF vienen incluidos. El panel de administración de Django sirve de "back office" para catálogos desde el primer día.
**En contra:** interacciones muy ricas (arrastrar y soltar, edición en tabla compleja) son más laboriosas que en React.

### B. FastAPI + React (Next.js)
**A favor:** interfaz más rica y separación clara entre API y cliente.
**En contra:** dos proyectos y dos lenguajes; autenticación, administración y formularios hechos a mano; más superficie de errores para mantener con IA. No compensa con este número de usuarios.

### C. Streamlit
**A favor:** prototipos de análisis muy rápidos.
**En contra:** no trae usuarios con email y contraseña ni roles; el modelo de reejecución complica los flujos de revisión y validación; el diseño es poco controlable para la dirección.

## Análisis de compromisos
El valor del producto está en la trazabilidad y la validación (formularios, permisos, auditoría), no en interacciones ricas. Django cubre eso sin código propio. Si un día hace falta una pantalla muy interactiva, se puede incrustar un componente JavaScript aislado sin cambiar el stack.

## Consecuencias
- Más fácil: autenticación, roles, back office, migraciones y tests (pytest-django).
- Más difícil: pantallas de tipo hoja de cálculo editable (se resuelven con exportar, editar en Excel y reimportar).
- Revisar si en el futuro se piden más de unas decenas de usuarios concurrentes o una app móvil.

## Acciones
1. [ ] Fase 0: esqueleto Django con `uv`, `ruff`, `pytest-django`, settings por entorno y `.env.example`.
2. [ ] Fijar las versiones exactas en `pyproject.toml` en el momento de crearlo. Versiones publicadas en PyPI el 05/11/2026: Django 6.1.3, anthropic 2.5.0, django-htmx 1.29.0, psycopg 3.3.8, pandas 3.1.1.
