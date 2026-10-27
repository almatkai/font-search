#!/bin/sh
set -eu
. "$(dirname -- "$0")/qa-env.sh"
# Toolchains are preinstalled and read-only; this wrapper never runs rustup install/update.
export RUSTUP_HOME=/Users/almat/.rustup
export PLAYWRIGHT_BROWSERS_PATH="$QA_ROOT/playwright"
export UV_CACHE_DIR="$QA_ROOT/uv" PIP_CACHE_DIR="$QA_ROOT/pip"
export CARGO_TERM_COLOR=never
exec "$@"
