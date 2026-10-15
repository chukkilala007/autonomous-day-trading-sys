#!/bin/sh
set -eu
# Reuse the locked image while testing current source. Build it first with:
# docker build --target runtime -t trading-dev .
docker run --rm --network none --tmpfs /tmp -e PYTHONPATH=/work/src -e HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis -v "$PWD:/work:ro" -w /work trading-dev python -m pytest -q -p no:cacheprovider "$@"
