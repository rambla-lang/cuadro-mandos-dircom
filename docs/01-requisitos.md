# 01. Requisitos

Cada requisito tiene un identificador para referenciarlo desde tareas, tests y commits. MVP = obligatorio en la primera versión.

## Requisitos funcionales

### Acceso y administración
| ID | Requisito | Criterio de aceptación | Prioridad |
|---|---|---|---|
| RF-01 | Inicio de sesión con email y contraseña | Un usuario sin sesión que entra en cualquier URL es redirigido al login; no hay registro público | MVP |
| RF-02 | Roles: administrador, analista, lector | El lector no ve botones de importar, validar ni editar, y el servidor rechaza esas acciones (403) | MVP |
| RF-03 | Alta de usuarios por invitación del administrador | Solo el administrador crea usuarios; el usuario fija su contraseña la primera vez | MVP |
| RF-04 | Registro de auditoría | Cada importación, validación, edición de evidencia y generación de informe queda registrada con usuario y fecha | MVP |

### Catálogos editables
| ID | Requisito | Criterio | Prioridad |
|---|---|---|---|
| RF-10 | Gestión de empresas, grupos y alias de marca | Se puede indicar que "Nealis" y "FACSA" pertenecen al mismo grupo y que "Fomento Benicasim, S.A." es un alias de Fobesa | MVP |
| RF-11 | Acotaciones por empresa gestora | Se puede limitar una empresa a servicios concretos (por ejemplo, ACCIONA solo energía); las métricas respetan la acotación | MVP |
| RF-12 | Marca propia | Se marcan las empresas propias (Veolia, Hidraqua…), que quedan excluidas del benchmarking | MVP |
| RF-13 | Municipios por territorio | Se cargan los municipios con su código INE; añadir otra comunidad no exige cambiar el código | MVP |

### Contratación pública

**Retirado el 10/11/2026 (ADR-010).** Los requisitos RF-20 a RF-25 quedan fuera: la DIRCOM no usa los expedientes de contratación; el cuadro gestiona quién presta cada servicio en cada municipio (municipio, empresa gestora y servicio).
| ID | Requisito | Criterio | Prioridad |
|---|---|---|---|
| RF-20 | Importar datos abiertos de PLACSP | Desde un ZIP o ATOM de datos abiertos se cargan los expedientes de órganos de la Comunitat Valenciana, sin duplicados al repetir | MVP |
| RF-21 | Importar anuncios de TED por API | Por rango de fechas y país o región; idempotente por número de publicación | MVP |
| RF-22 | Importar anuncios del BOE (sección V.A) | Por rango de fechas; solo licitaciones y adjudicaciones de órganos de la Comunitat Valenciana | Posterior al MVP |
| RF-23 | Clasificar expedientes por servicio | Cada expediente queda como agua, residuos, energía, otro o sin clasificar, mediante reglas por código CPV y palabras clave más una propuesta de IA revisable | MVP |
| RF-24 | Vincular expediente y municipio | Por órgano de contratación; los casos ambiguos (homónimos, mancomunidades, consorcios) quedan pendientes de revisión, nunca asignados a ciegas | MVP |
| RF-25 | Actualizar bajo demanda | Botón "Actualizar contratación" con rango de fechas; muestra progreso y resultado (nuevos, actualizados, errores) | MVP |

### Medios y menciones
| ID | Requisito | Criterio | Prioridad |
|---|---|---|---|
| RF-30 | Importar CSV de Brandwatch | Acepta el formato real (8 líneas de metadatos, cabecera en la línea 9, 129 columnas); deduplica entre exportaciones solapadas | MVP |
| RF-31 | Atribuir menciones a empresas gestoras | El export no trae la empresa mencionada; se detecta por alias en título y extracto, con propuesta de IA para los dudosos y validación humana | MVP |
| RF-32 | Pertinencia territorial | Cada mención se marca como "con vínculo valenciano" solo si hay una referencia territorial o de actividad local; el motivo queda guardado | MVP |
| RF-33 | Subir recortes PDF | Subida múltiple; extrae medio, fecha y página del nombre de archivo cuando sigue el patrón conocido; si no, los pide o los propone la IA | MVP |
| RF-34 | Recortes escaneados | Los PDF sin capa de texto se procesan con lectura visual de la IA y se marcan como "texto obtenido por IA" | MVP |
| RF-35 | Registro de piezas y regla de recuento | Se aplican las reglas de recuento del documento maestro (ver `05`) | MVP |

### Documentos cualitativos y digital
| ID | Requisito | Criterio | Prioridad |
|---|---|---|---|
| RF-40 | Subir Word de valoraciones | Se extrae el texto y se divide por empresa; cada fragmento queda como "percepción interna", separada de los hechos | MVP |
| RF-41 | Subir informes de sostenibilidad o EINF | Se guarda la referencia y se extraen hitos con IA, con cita de página; los hitos quedan como borrador hasta validarlos | Posterior al MVP |
| RF-42 | Métricas públicas de redes y web | Formulario o CSV con cuenta, red, fecha de observación, seguidores y publicaciones observadas; si un dato no es visible se guarda como "no visible", no como cero | MVP |

### Análisis e informes
| ID | Requisito | Criterio | Prioridad |
|---|---|---|---|
| RF-50 | Mapa municipal | Ver `05-modulos-analiticos.md` §1 | MVP |
| RF-51 | Ficha de empresa gestora | Ver §2 | MVP |
| RF-52 | Visibilidad en medios | Ver §3 | MVP |
| RF-53 | Informe ejecutivo | Genera un documento Word con la estructura definida; cada cifra lleva su referencia de evidencia | MVP |
| RF-54 | Presentación | Genera un PowerPoint con la estructura de tres diapositivas por empresa | MVP |
| RF-55 | Exportar datos | Cada tabla del cuadro se exporta a Excel o CSV con fuentes y niveles | MVP |
| RF-56 | Comparar periodos | La visibilidad en medios admite comparar dos periodos de igual duración | Posterior al MVP |

### Validación humana
| ID | Requisito | Criterio | Prioridad |
|---|---|---|---|
| RF-60 | Bandeja de revisión | Lista de todo lo pendiente: propuestas de IA, vínculos ambiguos y duplicados dudosos; se acepta, corrige o rechaza | MVP |
| RF-61 | Trazabilidad de una cifra | Desde cualquier número del cuadro se llega a la lista de evidencias que lo componen | MVP |

## Requisitos no funcionales

| ID | Requisito | Medida |
|---|---|---|
| RNF-01 | Coste de alojamiento del piloto | 0 €/mes, sin contar la API de Claude |
| RNF-02 | Arranque en frío | En el plan gratuito de Render el servicio se duerme tras 15 min sin tráfico; se acepta y la interfaz avisa con un mensaje de "despertando" (ver ADR-002) |
| RNF-03 | Volumen esperado | Del orden de miles de menciones al año (las tres exportaciones de 2026 suman 2.742 filas antes de deduplicar) (los expedientes de contratación se retiraron el 10/11/2026, ADR-010). Revisar tras la Fase 0 |
| RNF-04 | Memoria | Los importadores procesan los ficheros en streaming, sin cargarlos enteros en memoria. La instancia gratuita de Render tiene 512 MB |
| RNF-05 | Almacenamiento | La base de datos gratuita de Neon tiene 0,5 GB por proyecto; los PDF originales no se guardan en la base de datos (ADR-003) |
| RNF-06 | Seguridad | HTTPS, contraseñas con hash de Django, CSRF activo y secretos solo en variables de entorno (ver `08`) |
| RNF-07 | Accesibilidad | Contraste AA, navegación por teclado, gráficos con tabla alternativa |
| RNF-08 | Idioma | Interfaz en español; contenido de entrada en español y valenciano (en las tres exportaciones de Brandwatch, entre el 3 % y el 6 % de las menciones tiene idioma "ca") |
| RNF-09 | Coste de IA controlado | Límite mensual de gasto configurable; cada llamada registra tokens y modelo; se bloquea al superar el límite |
| RNF-10 | Mantenibilidad | Cobertura de tests de al menos el 80 % en `importers/` y en el cálculo de métricas |
| RNF-11 | Portabilidad | Todo configurable por variables de entorno; cambiar de Render y Neon a otro proveedor no exige tocar código |
