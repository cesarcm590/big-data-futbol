#!/bin/zsh
# Envoltura para el temporizador (launchd). Corre la actualización semanal y deja todo en un log con fecha.
#
# Se usa un intérprete por RUTA ABSOLUTA en vez de `conda activate`: launchd arranca sin el perfil del usuario, así
# que no existe `conda` ni el PATH habitual. Apuntar al python del entorno es lo único que funciona sin depender
# de cómo esté configurada la shell.
PY=/Users/javiercarrillo/miniconda3/envs/futbol-bigdata/bin/python
RAIZ=/Users/javiercarrillo/Proyectos/Big_data_futbol
LOG=$RAIZ/registro/actualizacion_semanal.log

cd $RAIZ || exit 1
echo "\n================ $(date '+%Y-%m-%d %H:%M:%S') ================" >> $LOG
$PY $RAIZ/scripts/actualizar_semanal.py "$@" >> $LOG 2>&1
CODIGO=$?
echo "--- terminó con código $CODIGO ---" >> $LOG
exit $CODIGO
