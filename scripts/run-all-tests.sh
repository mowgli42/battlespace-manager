#!/usr/bin/env bash
# All battlespace-manager unit tests: both displays (API + vitest + build).
set -euo pipefail
BM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/env.sh
source "${BM_ROOT}/scripts/env.sh"

echo "== compat check =="
python3 "${BM_ROOT}/scripts/check-omy-compat.py"

echo "== entity-display API tests =="
cd "${BM_ROOT}/services/entity-display/api"
PYTHONPATH="${OMY_ROOT}/packages/uci_common/src:${BM_ROOT}/services/entity-display/api" \
  python3 -m unittest discover -s tests -p 'test_*.py' -v

echo "== entity-display web unit tests =="
cd "${BM_ROOT}/services/entity-display/web"
npm install --silent
npm run test

echo "== entity-display web build =="
npm run build

echo "== battlespace-display (API + web) =="
"${BM_ROOT}/scripts/run-display-tests.sh"

echo "== entity-display feature harness =="
python3 "${BM_ROOT}/scripts/verify-entity-display-features.py"

echo "== rf-display API tests =="
cd "${BM_ROOT}/services/rf-display/api"
PYTHONPATH="${OMY_ROOT}/packages/uci_common/src:${OMYSIM_ROOT}/packages/uci_common/src:${BM_ROOT}/services/rf-display/api" \
  python3 -m unittest discover -s tests -p 'test_*.py' -v

echo "== rf-display web unit tests =="
cd "${BM_ROOT}/services/rf-display/web"
npm install --silent
npm run test

echo "== rf-display web build =="
npm run build

echo "== rf-display feature harness =="
python3 "${BM_ROOT}/scripts/verify-rf-display-features.py"

echo "All battlespace-manager tests passed."
