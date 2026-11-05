# ADR-003: Dónde se guardan los archivos subidos

**Estado:** Abierta (pregunta P-03)
**Fecha:** 05/11/2026

## Contexto
Los usuarios subirán PDF de prensa (en la muestra, entre 100 KB y 1,4 MB cada uno), Word de valoraciones e informes de sostenibilidad. Los informes de la muestra pesan hasta 33 MB y tienen hasta 468 páginas; la carpeta de ejemplo ocupa unos 101 MB. La base de datos gratuita tiene 0,5 GB y el servicio web gratuito no garantiza disco persistente (**por verificar**).

## Decisión propuesta
- En la base de datos solo se guardan metadatos, el texto extraído y una huella SHA-256 del archivo, que sirve para detectar duplicados.
- El archivo original va a un almacén de objetos compatible con S3, configurado con `django-storages`. En desarrollo se usa la carpeta local `media/`.
- Si en el piloto no se quiere crear una cuenta de almacenamiento, se puede trabajar en modo "sin originales": se guarda el texto extraído y se descarta el binario. En ese caso hay que volver a subir el archivo para releerlo.

## Opciones a decidir (P-03)
| Opción | A favor | En contra |
|---|---|---|
| Almacén S3 compatible con plan gratuito | Conserva los originales | Otra cuenta más; límites del plan **por verificar** antes de elegir |
| Modo sin originales | Cero cuentas nuevas | No se puede volver a abrir el original desde la app |
| Carpeta compartida corporativa (OneDrive o SharePoint) con enlace | Los originales siguen donde ya están | Hace falta guardar el enlace a mano; la app no puede leerlos |

## Consecuencias
El código usa siempre la API de almacenamiento de Django (`default_storage`), así que cambiar de opción es configuración, no código.
