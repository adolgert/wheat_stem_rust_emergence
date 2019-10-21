#!/bin/bash
CDLS=$1
COUNTY=$2
NDVI=$3
script_start=$4
NEAR_END=$5

# This does a diff between times in seconds.
tdiff () {
    printf '%s' $(( $(date -u -d"$1" +%s) - $(date -u -d"$2" +%s) ))
}

TMPDIR=/media/data0/counties

while [[ $(tdiff "$(date -u '+%F %T.%N %Z')" "$script_start") -lt "${NEAR_END}" ]]
do
  geoid=`python county_client.py`

  echo Starting county ${geoid}.
  echo ./triple --cdls "${CDLS}" --ndvi "${NDVI}" --counties "${COUNTY}"
  echo    --feature "${geoid}" --point > "${TMPDIR}/${geoid}.txt"

  time ./triple --cdls "${CDLS}" --ndvi "${NDVI}" --counties "${COUNTY}" \
      --feature "${geoid}" --point > "${TMPDIR}/${geoid}.txt"

  if [ $? -ne 0 ]
  then
      echo "XXX Failed." >> "${TMPDIR}/${geoid}.txt"
      echo Failed on $geoid `date`
      exit
  fi
done

