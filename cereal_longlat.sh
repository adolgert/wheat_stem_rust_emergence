#!/bin/bash
CDLSDIR=2011_30m_cdls
CDLS="${CDLSDIR}/2011_30m_cdls.img"
TRANS="${CDLSDIR}/2011_cdls_cereal.img"
WARP="${CDLSDIR}/2011_cdls_cereal_longlat.tif"

python findp.py --pick --cdls ${CDLS} --outfile ${TRANS} --verbose

gdalwarp -t_srs "+proj=longlat +ellps=GRS80 +datum=NAD83 +no_defs" -s_srs "+proj=aea +lat_1=29.5 +lat_2=45.5 +lat_0=23 +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs" -r near -wm 2000 -of GTiff "${TRANS}" "${WARP}"
