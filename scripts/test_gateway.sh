#!/bin/sh
set -eu
docker run --rm --network none --tmpfs /tmp -e PYTHONPATH=/work/src -e HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis -v "$PWD:/work:ro" -w /work trading-gateway-check python -m pytest -q -p no:cacheprovider "$@"
