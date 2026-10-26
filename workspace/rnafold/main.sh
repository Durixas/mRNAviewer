#!/usr/bin/env bash
set -euo pipefail
mkdir -p output
"${MRNAVIEWER_RNAFOLD_BIN:-RNAfold}" -p -d2 --noLP --id-prefix=kdde -i"$1" > fold.log
perl relplot.pl kdde_0001_ss.ps kdde_0001_dp.ps > output/image.ps
"${MRNAVIEWER_BACKEND_PYTHON:-python3}" convert.py output/image.ps output/image.png
rm -f kdde_0001_ss.ps kdde_0001_dp.ps
"${MRNAVIEWER_BACKEND_PYTHON:-python3}" getval.py
