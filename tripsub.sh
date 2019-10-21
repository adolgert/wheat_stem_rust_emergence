#!/bin/bash
#PBS -l walltime=00:20:00,nodes=1
#PBS -A sc167_0001
#PBS -j oe
#PBS -N batchtest
#PBS -q v4-64g
#PBS -S /bin/bash

# Turn on echo of shell commands
#set -x

min=60
NEAR_END=$((5*min))

CDLSDIR=2011_cdls
COUNTYDIR=tl_2010_us_county10
NDVIDIR=gimms

script_start=$(date -u  '+%F %T.%N %Z')
echo $script_start

source ~/dev/py27/bin/activate

cd ~/dev/land_use

for datadir in "${CDLSDIR}" "${COUNTYDIR}" "${NDVIDIR}"
do
  cp -R "${datadir}" "${TMPDIR}"
done

echo 'copy done' `date`



CDLSNAME=2011_30m_cdls.img
COUNTYNAME=tl_2010_us_county10.shp
NDVINAME=sample.tif

CDLS="${TMPDIR}/${CDLSDIR}/${CDLSNAME}"
COUNTY="${TMPDIR}/${COUNTYDIR}/${COUNTYNAME}"
NDVI="${TMPDIR}/${NDVIDIR}/${NDVINAME}"

for t in {1..8}
do
    ./fly.sh "${CDLS}" "${COUNTY}" "${NDVI}" "${script_start}" "${NEAR_END}"&
done
