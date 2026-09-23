#!/bin/zsh
# Envoltura para el temporizador (launchd). Corre la actualización semanal y deja todo en un log con fecha.
#
# La raíz del proyecto se deduce de dónde está este script, así que el repositorio funciona clonado en cualquier
# carpeta. El intérprete sí hay que decirlo: launchd arranca SIN el perfil del usuario, así que no existe `conda`
# ni el PATH habitual. Se toma de FUTBOL_PYTHON (el .plist lo define) y si no, del entorno activo o del PATH.
RAIZ=${0:A:h:h}
PY=${FUTBOL_PYTHON:-${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}}
PY=${PY:-$(command -v python3)}
LOG=$RAIZ/registro/actualizacion_semanal.log

if [[ ! -x $PY ]]; then
  echo "No encuentro un intérprete de Python. Define FUTBOL_PYTHON con la ruta del entorno." >&2
  exit 1
fi

cd $RAIZ || exit 1
mkdir -p $RAIZ/registro
echo "\n================ $(date '+%Y-%m-%d %H:%M:%S') ================" >> $LOG
$PY $RAIZ/scripts/actualizar_semanal.py "$@" >> $LOG 2>&1
CODIGO=$?
echo "--- terminó con código $CODIGO ---" >> $LOG
exit $CODIGO
