# 00. Visión y alcance

## Para qué sirve

Hoy el análisis de competencia se hace a mano en chats de IA, con hojas de cálculo y documentos sueltos. La plataforma debe permitir a la dirección de comunicación repetir y actualizar ese análisis desde un único sitio y sin perder la trazabilidad. Por ejemplo:

- Saber qué empresa presta agua, residuos o energía en cada municipio y con qué evidencia.
- Mantener una ficha por competidor con contratos, presencia en medios, eventos, premios, alianzas, innovación, sostenibilidad y ecosistema digital.
- Medir la visibilidad en medios por competidor, medio y periodo.
- Generar un informe ejecutivo o una presentación a partir de los datos validados.

## Usuarios y acceso (decisiones de José Luis, 05/11/2026)

| Tema | Decisión |
|---|---|
| Quién lo usa | Equipo de la DIRCOM, como web interna |
| Número de usuarios | Menos de 10 |
| Inicio de sesión | Email y contraseña gestionados en la propia aplicación |
| Ámbito territorial | Comunitat Valenciana ahora, diseñado para añadir territorios después |
| Alojamiento | Gratuito durante el piloto; se decidirá al pasar a producción |
| Restricciones de TI | Ninguna; el stack lo propone el equipo técnico (ver `adr/`) |
| IA externa | Sí, con API de Anthropic (clave propia) |

## Fuentes de la primera versión (decisiones de José Luis)

| Fuente | Cómo llega |
|---|---|
| Contratación pública: PLACSP, TED, BOE | Actualización manual bajo demanda (botón "Actualizar" o comando) |
| Prensa y menciones | Exportaciones CSV de Brandwatch, descargadas de forma puntual (sin API) |
| Recortes de prensa | PDF de clipping |
| Valoraciones cualitativas | Documentos Word (por ejemplo, percepciones internas sobre competidores) |
| Redes sociales y webs | Solo datos públicos básicos |
| Otros archivos | Excel y CSV que suba el usuario (como la tabla de municipios de Veolia) |

## Módulos imprescindibles del MVP

1. Mapa municipal: servicios de agua, residuos y energía por municipio, con operador, nivel de evidencia y fuente.
2. Ficha de competidor.
3. Visibilidad en medios.
4. Informes automáticos (informe ejecutivo y presentación).

## Cómo se trabajó hasta ahora (requisitos implícitos)

Del documento "Proceso seguido", del documento maestro y del trabajo con PLACSP salen estas reglas, que la plataforma debe respetar:

- La ficha de cada competidor tiene una estructura acordada. Bloque 1: percepción interna y contraste; municipios y servicios; medios con más presencia; eventos y premios. Bloque 2: grupos de interés; innovación y financiación europea; informes de sostenibilidad y EINF. Bloque 3: ecosistema digital, con redes sociales y web corporativa por separado.
- Las percepciones internas (Word) se integran en la ficha, separadas de los hechos verificables.
- Las menciones de una marca nacional no cuentan como valencianas solo por citar a la empresa: hace falta una referencia territorial o de actividad local.
- Se distingue que una cuenta en redes exista de que haya histórico suficiente para caracterizarla. Si no hay evidencia, se deja constancia del límite y no se infiere nada.
- Las reglas de recuento de prensa del documento maestro se convierten en reglas del sistema (ver `05-modulos-analiticos.md`).
- Veolia, Hidraqua y sus marcas locales son la referencia propia y no se incluyen en el benchmarking.
- Competidores con ficha en el análisis vigente: Nealis/FACSA, Aqualia, Hozono Global, Global Omnium, Cox, STV, Urbaser, PreZero, Valoriza, FCC, ENGIE, ACCIONA Energía y Naturgy. Hay acotaciones por empresa; por ejemplo, Aqualia se analiza separada de FCC y ACCIONA solo en energía. La lista y sus acotaciones serán datos editables, no código.

## Fuera del alcance del MVP

- Conexión directa a la API de Brandwatch (no hay acceso a la API).
- Recogida automática programada (se decidió actualizar bajo demanda).
- Rastreo automatizado de perfiles de redes sociales. Solo datos públicos básicos introducidos o importados; ver la pregunta abierta P-05.
- Análisis de los perfiles de Veolia como parte del benchmarking.
- Inicio de sesión corporativo (Microsoft o Google).
- Aplicación móvil nativa. La web debe poder leerse en móvil.

## Criterio de éxito del MVP

José Luis puede repetir en la plataforma, sin otra herramienta, el análisis que se hizo para Veolia en la Comunitat Valenciana. Para ello:

- Carga los exports de Brandwatch, los PDF de prensa y el Word de percepciones.
- Actualiza los contratos públicos de los municipios.
- Revisa y valida lo que propone la IA.
- Obtiene un informe y una presentación cuyas cifras se pueden rastrear, una a una, hasta su fuente.
