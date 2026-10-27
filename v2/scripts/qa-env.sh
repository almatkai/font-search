#!/bin/sh
# Source before any QA dependency or executable invocation. All mutable state is local.
QA_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/.qa
export HOME="$QA_ROOT/home" TMPDIR="$QA_ROOT/tmp" TMP="$QA_ROOT/tmp" TEMP="$QA_ROOT/tmp"
export XDG_CACHE_HOME="$QA_ROOT/xdg-cache" XDG_CONFIG_HOME="$QA_ROOT/xdg-config" XDG_DATA_HOME="$QA_ROOT/xdg-data"
export CARGO_HOME="$QA_ROOT/cargo" CARGO_TARGET_DIR="$QA_ROOT/../target"
export npm_config_cache="$QA_ROOT/npm" PYTHONDONTWRITEBYTECODE=1
export CARGO_NET_GIT_FETCH_WITH_CLI=true GIT_CONFIG_NOSYSTEM=1
mkdir -p "$HOME" "$TMPDIR" "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$CARGO_HOME" "$npm_config_cache"
