#!/usr/bin/env bash
# Bootstrap a Codespace using the setup script from this checkout.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if [[ "$(uname -m)" != x86_64 ]]; then
    echo "This Codespaces configuration requires x86_64 Linux." >&2
    exit 1
fi

# Prevent concurrent bootstrap runs.
exec 9>"$repo_dir/.devcontainer/.setup.lock"
flock 9
head_sha="$(git rev-parse HEAD)"
stamp="$repo_dir/.devcontainer/.setup-complete"
if [[ -f "$stamp" ]]; then
    if [[ "$(cat "$stamp")" == "$head_sha" && -f env.sh && -f .conda-env/conda-meta/history ]]; then
        echo "Chipyard setup already completed for $head_sha."
        exit 0
    fi
    echo "The checkout or environment changed. Create a fresh Codespace for this revision." >&2
    exit 1
fi

source /opt/conda/etc/profile.d/conda.sh
conda activate base
# Upstream setup scripts are not written for nounset.
set +u
if [[ ! -f .conda-env/conda-meta/history ]]; then
    if [[ -d .conda-env || -d .conda-lock-env ]]; then
        echo "Conda setup was interrupted. Create a fresh Codespace to retry cleanly." >&2
        exit 1
    fi
    # Install the environment first, so later failures can resume without recreating it.
    ./build-setup.sh riscv-tools --use-lean-conda -s 2 -s 3 -s 5 -s 10 -s 11
fi
if [[ ! -f env.sh ]]; then
    echo "Missing env.sh. Create a fresh Codespace to recreate the environment." >&2
    exit 1
fi
source "$repo_dir/env.sh"
./build-setup.sh riscv-tools --use-lean-conda -s 1 -s 11
source "$repo_dir/env.sh"
for tool in riscv64-unknown-elf-gcc spike verilator java sbt firtool; do
    command -v "$tool" >/dev/null || {
        echo "Setup verification failed: $tool is missing." >&2
        exit 1
    }
done
riscv64-unknown-elf-gcc --version
verilator --version
firtool --version

# Make new interactive terminals enter this workspace's Chipyard environment.
if ! grep -q '^# Chipyard Codespaces environment$' "$HOME/.bashrc"; then
    {
        printf '\n# Chipyard Codespaces environment\n'
        printf 'if [ -f %q ]; then source %q; fi\n' "$repo_dir/env.sh" "$repo_dir/env.sh"
    } >> "$HOME/.bashrc"
fi
printf '%s\n' "$head_sha" > "$stamp"
echo "Chipyard RTL development environment is ready."
