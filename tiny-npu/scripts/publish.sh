#!/usr/bin/env bash
# Push this development branch to the existing Chipyard repository. No force push.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
if [[ "$(git branch --show-current)" != tiny-npu ]]; then
  echo 'Expected development branch tiny-npu' >&2; exit 1
fi
case "$(git remote get-url origin)" in
  https://github.com/jhroh13/chipyard.git|https://github.com/jhroh13/chipyard) ;;
  *) echo 'Expected origin jhroh13/chipyard' >&2; exit 1 ;;
esac
git push -u origin tiny-npu
