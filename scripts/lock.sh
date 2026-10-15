#!/bin/sh
set -eu
python -m pip install pip-tools==7.5.3
for group in core test gateway; do
  pip-compile --allow-unsafe --generate-hashes --output-file requirements/$group.lock requirements/$group.in
done
