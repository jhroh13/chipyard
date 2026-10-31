#!/usr/bin/env bash
# Explicitly invoked publish helper. No force push, no credentials stored.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
if [[ -n "${TINY_NPU_PUBLISH_TOKEN:-}" ]]; then
  export GH_TOKEN="$TINY_NPU_PUBLISH_TOKEN"
fi
if [[ "$(gh api user --jq .login)" != jhroh13 ]]; then
  echo 'Expected authorized GitHub account jhroh13' >&2;exit 1
fi
if ! gh repo view jhroh13/TINY-NPU --json name >/dev/null 2>&1; then
  gh repo create jhroh13/TINY-NPU --private --description 'Chipyard-based TINY NPU RTL, HDD and LLM simulation roadmap'
fi
git push -u origin main
