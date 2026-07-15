#!/usr/bin/env bash
# Vendor private o-my / o-my-sim uci_common packages for Vercel builds.
#
# Token preference (do NOT rely on Vercel's auto GITHUB_TOKEN — it cannot read
# private sibling repos from a public project):
#   1. PRIVATE_REPO_TOKEN / OMY_READ_TOKEN  (recommended PAT)
#   2. GITHUB_TOKEN                        (local/CI only)
#
# On Vercel, missing/failed vendor is non-fatal when ALLOW_HARNESS_WITHOUT_VENDOR=1
# (default on Vercel) — battlespace harness fixtures do not need uci_common at runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="${ROOT}/.vercel-vendor"

# Prefer an explicit private-repo PAT over Vercel's injected GITHUB_TOKEN.
TOKEN="${PRIVATE_REPO_TOKEN:-${OMY_READ_TOKEN:-}}"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="${GITHUB_TOKEN:-}"
fi

ON_VERCEL=0
if [[ "${VERCEL:-}" == "1" || -n "${VERCEL_ENV:-}" ]]; then
  ON_VERCEL=1
fi
ALLOW_SOFT="${ALLOW_HARNESS_WITHOUT_VENDOR:-}"
if [[ -z "${ALLOW_SOFT}" && "${ON_VERCEL}" == "1" ]]; then
  ALLOW_SOFT=1
fi
ALLOW_SOFT="${ALLOW_SOFT:-0}"

copy_tree() {
  local src="$1"
  local dest="$2"
  mkdir -p "${dest}"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${src}/" "${dest}/"
  else
    cp -a "${src}/." "${dest}/"
  fi
}

soft_fail() {
  local msg="$1"
  if [[ "${ALLOW_SOFT}" == "1" || "${ALLOW_SOFT}" == "true" ]]; then
    echo "WARN: ${msg}" >&2
    echo "WARN: continuing without private vendor (harness mode still works)." >&2
    echo "WARN: set PRIVATE_REPO_TOKEN (Contents:Read on o-my + o-my-sim) to vendor deps." >&2
    rm -rf "${VENDOR}"
    mkdir -p "${VENDOR}"
    exit 0
  fi
  echo "ERROR: ${msg}" >&2
  exit 1
}

clone_sparse() {
  local repo="$1"
  local dest="$2"
  local tmp
  tmp="$(mktemp -d)"
  # Use a token that can read private repos. Mask token in logs.
  echo "Cloning mowgli42/${repo} (sparse packages/uci_common)…"
  if ! git clone --depth 1 --filter=blob:none --sparse \
    "https://x-access-token:${TOKEN}@github.com/mowgli42/${repo}.git" "${tmp}" 2>"${tmp}.err"; then
    echo "git clone failed for ${repo}:" >&2
    # Redact token if it somehow appears
    sed -E 's/x-access-token:[^@]+@/x-access-token:***@/g' "${tmp}.err" >&2 || true
    rm -rf "${tmp}" "${tmp}.err"
    return 1
  fi
  rm -f "${tmp}.err"
  git -C "${tmp}" sparse-checkout set packages/uci_common
  if [[ ! -d "${tmp}/packages/uci_common" ]]; then
    echo "sparse checkout missing packages/uci_common in ${repo}" >&2
    rm -rf "${tmp}"
    return 1
  fi
  copy_tree "${tmp}/packages/uci_common" "${dest}"
  rm -rf "${tmp}"
  return 0
}

OMY="${OMY_ROOT:-}"
OMYSIM="${OMYSIM_ROOT:-}"
if [[ -z "${OMY}" && -d "${ROOT}/../o-my/packages/uci_common" ]]; then
  OMY="$(cd "${ROOT}/../o-my" && pwd)"
fi
if [[ -z "${OMYSIM}" && -d "${ROOT}/../o-my-sim/packages/uci_common" ]]; then
  OMYSIM="$(cd "${ROOT}/../o-my-sim" && pwd)"
fi

rm -rf "${VENDOR}"
mkdir -p "${VENDOR}/o-my/uci_common" "${VENDOR}/o-my-sim/uci_common"

if [[ -n "${OMY}" && -d "${OMY}/packages/uci_common" ]]; then
  echo "Vendoring o-my from ${OMY}"
  copy_tree "${OMY}/packages/uci_common" "${VENDOR}/o-my/uci_common"
elif [[ -n "${TOKEN}" ]]; then
  if ! clone_sparse "o-my" "${VENDOR}/o-my/uci_common"; then
    soft_fail "could not clone private mowgli42/o-my (token missing scopes or repo access)"
  fi
else
  soft_fail "o-my not found and PRIVATE_REPO_TOKEN/OMY_READ_TOKEN unset"
fi

if [[ -n "${OMYSIM}" && -d "${OMYSIM}/packages/uci_common" ]]; then
  echo "Vendoring o-my-sim from ${OMYSIM}"
  copy_tree "${OMYSIM}/packages/uci_common" "${VENDOR}/o-my-sim/uci_common"
elif [[ -n "${TOKEN}" ]]; then
  if ! clone_sparse "o-my-sim" "${VENDOR}/o-my-sim/uci_common"; then
    soft_fail "could not clone private mowgli42/o-my-sim (token missing scopes or repo access)"
  fi
else
  soft_fail "o-my-sim not found and PRIVATE_REPO_TOKEN/OMY_READ_TOKEN unset"
fi

if [[ ! -d "${VENDOR}/o-my/uci_common/src/uci_common" ]]; then
  soft_fail "missing ${VENDOR}/o-my/uci_common/src/uci_common after vendor"
fi
if [[ ! -d "${VENDOR}/o-my-sim/uci_common/src/uci_common" ]]; then
  soft_fail "missing ${VENDOR}/o-my-sim/uci_common/src/uci_common after vendor"
fi

echo "Vercel vendor ready at .vercel-vendor/"
