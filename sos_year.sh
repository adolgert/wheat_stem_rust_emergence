#!/bin/bash
year=$1
# This makes pix_for_R_1999.csv
#python aylor_corn.py --writer --year=${year}

Rscript -e "source(\"gam_try.R\"); process.year(${year},0.5)"

if test $? -ne 0; then exit; fi

python plot_obs.py --sos --year=${year}
