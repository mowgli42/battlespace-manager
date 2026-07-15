#!/usr/bin/env bash
# Vendor private o-my / o-my-sim uci_common packages for Vercel builds.
# Prefer sibling checkouts (local/CI); otherwise clone with GITHUB_TOKEN / PRIVATE_REPO_TOKEN.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="${ROOT}/.vercel-vendor"
TOKEN="${GITHUB_TOKEN:-${PRIVATE_REPO_TOKEN:-}}"

OMY="${OMY_ROOT:-}"
OMYSIM="${OMYSIM_ROOT:-}"
if [[ -z "${OMY}" && -d "${ROOT}/../o-my/packages/uci_common" ]]; then
  OMY="$(cd "${ROOT}/../o-my" && pwd)"
fi
if [[ -z "${OMYSIM}" && -d "${ROOT}/../o-my-sim/packages/uci_common" ]]; then
  OMYSIM="$(cd "${ROOT}/../o-my-sim" && pwd)"
fi

clone_sparse() {
  local repo="$1"
  local dest="$2"
  local tmp
  tmp="$(mktemp -d)"
  git clone --depth 1 --filter=blob:none --sparse \
    "https://x-access-token:${TOKEN}@github.com/mowgli42/${repo}.git" "${tmp}"
  git -C "${tmp}" sparse-checkout set packages/uci_common
  mkdir -p "${dest}"
  rsync -a "${tmp}/packages/uci_common/" "${dest}/"
  rm -rf "${tmp}"
}

rm -rf "${VENDOR}"
mkdir -p "${VENDOR}/o-my/uci_common" "${VENDOR}/o-my-sim/uci_common"

if [[ -n "${OMY}" && -d "${OMY}/packages/uci_common" ]]; then
  echo "Vendoring o-my from ${OMY}"
  rsync -a "${OMY}/packages/uci_common/" "${VENDOR}/o-my/uci_common/"
elif [[ -n "${TOKEN}" ]]; then
  echo "Cloning mowgli42/o-my (sparse packages/uci_common)"
  clone_sparse "o-my" "${VENDOR}/o-my/uci_common"
else
  echo "ERROR: o-my not found and GITHUB_TOKEN/PRIVATE_REPO_TOKEN unset" >&2
  echo "Clone o-my alongside this repo or set a PAT with Contents:Read on o-my + o-my-sim." >&2
  exit 1
fi

if [[ -n "${OMYSIM}" && -d "${OMYSIM}/packages/uci_common" ]]; then
  echo "Vendoring o-my-sim from ${OMYSIM}"
  rsync -a "${OMYSIM}/packages/uci_common/" "${VENDOR}/o-my-sim/uci_common/"
elif [[ -n "${TOKEN}" ]]; then
  echo "Cloning mowgli42/o-my-sim (sparse packages/uci_common)"
  clone_sparse "o-my-sim" "${VENDOR}/o-my-sim/uci_common"
else
  echo "ERROR: o-my-sim not found and GITHUB_TOKEN/PRIVATE_REPO_TOKEN unset" >&2
  exit 1
fi

if [[ ! -d "${VENDOR}/o-my/uci_common/src/uci_common" ]]; then
  echo "ERROR: missing ${VENDOR}/o-my/uci_common/src/uci_common" >&2
  exit 1
fi
if [[ ! -d "${VENDOR}/o-my-sim/uci_common/src/uci_common" ]]; then
  echo "ERROR: missing ${VENDOR}/o-my-sim/uci_common/src/uci_common" >&2
  exit 1
fi

echo "Vercel vendor ready at .vercel-vendor/"
