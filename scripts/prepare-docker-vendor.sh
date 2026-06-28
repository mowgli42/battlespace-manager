#!/usr/bin/env bash
# Stage sibling uci_common packages for Docker builds.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="${ROOT}/.docker-vendor"
OMY="${OMY_ROOT:-$(cd "$ROOT/../o-my" && pwd)}"
OMYSIM="${OMYSIM_ROOT:-$(cd "$ROOT/../o-my-sim" && pwd)}"

rm -rf "${VENDOR}"
mkdir -p "${VENDOR}/o-my" "${VENDOR}/o-my-sim"
rsync -a "${OMY}/packages/uci_common/" "${VENDOR}/o-my/uci_common/"
rsync -a "${OMYSIM}/packages/uci_common/" "${VENDOR}/o-my-sim/uci_common/"
cp "${ROOT}/fixtures/commlink-directory-v1.1.xml" "${VENDOR}/"
echo "Docker vendor context ready at .docker-vendor/"
