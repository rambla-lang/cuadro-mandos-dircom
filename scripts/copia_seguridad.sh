#!/usr/bin/env bash
# Copia de seguridad de la base de datos (docs/12). Uso:
#   DATABASE_URL='postgres://…neon…' scripts/copia_seguridad.sh
# Deja un fichero copias/cuadro_AAAAMMDD-HHMM.dump (formato personalizado de pg_dump).
set -euo pipefail
: "${DATABASE_URL:?Define DATABASE_URL con la conexión de Neon}"
mkdir -p copias
destino="copias/cuadro_$(date +%Y%m%d-%H%M).dump"
pg_dump --format=custom --no-owner --no-privileges --dbname="$DATABASE_URL" --file="$destino"
echo "Copia en $destino ($(du -h "$destino" | cut -f1))"
