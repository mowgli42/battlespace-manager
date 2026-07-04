#!/usr/bin/env bash
set -euo pipefail
BM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env.sh
source "${BM_ROOT}/scripts/env.sh"

echo "== battlespace-display API tests =="
cd "${BM_ROOT}/services/battlespace-display/api"
PYTHONPATH="${OMY_ROOT}/packages/uci_common/src:${OMYSIM_ROOT}/packages/uci_common/src:${BM_ROOT}/services/battlespace-display/api" \
  python3 -m unittest discover -s tests -p 'test_*.py' -v

echo "== battlespace-display web unit tests =="
cd "${BM_ROOT}/services/battlespace-display/web"
npm install --silent
npm run test

echo "== battlespace-display web build =="
npm run build

echo "== battlespace-display feature harness =="
python3 "${BM_ROOT}/scripts/verify-battlespace-display-features.py"

echo "All display tests passed."
