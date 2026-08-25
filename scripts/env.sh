#!/usr/bin/env bash
# Source from run scripts: . "$(dirname "$0")/env.sh"
BM_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OMY_ROOT="${OMY_ROOT:-$(cd "${BM_ROOT}/../o-my" && pwd)}"
OMYSIM_ROOT="${OMYSIM_ROOT:-$(cd "${BM_ROOT}/../o-my-sim" && pwd)}"

if [[ ! -d "${OMY_ROOT}/packages/uci_common" ]]; then
  echo "o-my not found at ${OMY_ROOT} — clone alongside battlespace-manager" >&2
  exit 1
fi
if [[ ! -d "${OMYSIM_ROOT}/packages/uci_common" ]]; then
  echo "o-my-sim not found at ${OMYSIM_ROOT} — clone alongside battlespace-manager" >&2
  exit 1
fi

# o-my first (C2 modules), o-my-sim second (gulfwar_sim via pkgutil.extend_path).
# Do NOT put entity/battlespace/rf `app` packages here — they all expose app.main
# and uvicorn would import the wrong one (mowgli42/battlespace-manager#37).
export PYTHONPATH="${OMY_ROOT}/packages/uci_common/src:${OMYSIM_ROOT}/packages/uci_common/src:${PYTHONPATH:-}"
export COMMLINK_DIRECTORY_XML="${COMMLINK_DIRECTORY_XML:-${BM_ROOT}/fixtures/commlink-directory-v1.1.xml}"
