#!/usr/bin/env bash
# Project-gate: configure stack checks before use. Checks must not modify source.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
FAST=0
case "${1:-}" in
    "") [ "$#" -eq 0 ] || { echo "ERROR: unexpected arguments" >&2; exit 2; } ;;
    --fast) [ "$#" -eq 1 ] || { echo "ERROR: unexpected arguments" >&2; exit 2; }; FAST=1 ;;
    *) echo "Usage: ./check.sh [--fast]" >&2; exit 2 ;;
esac
MODE=full
[ "$FAST" -eq 0 ] || MODE=fast
umask 077
LOG=$(mktemp "${TMPDIR:-/tmp}/project-gate.XXXXXX")
trap 'echo "ERROR: gate interrupted; log=$LOG" >&2; exit 2' INT TERM
need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: missing required tool: $1; log=$LOG" >&2
        exit 2
    fi
}
COUNT=0
run() {
    local label=$1 status
    shift
    printf '\n--- %s ---\n' "$label" >>"$LOG"
    if "$@" >>"$LOG" 2>&1; then
        COUNT=$((COUNT + 1))
    else
        status=$?
        printf 'FAIL: %s (exit=%s); log=%s\n' "$label" "$status" "$LOG" >&2
        tail -n 60 "$LOG" | { head -c 8000; cat >/dev/null; } >&2
        printf '\n' >&2
        case "$status" in 126|127) exit 2 ;; *) exit 1 ;; esac
    fi
}
# --- Rust + standard-library Python + embedded webpage ---
# Cargo.lock is tracked. Provision dependencies with cargo fetch outside the gate.
need git
need cargo
need rustfmt
need cargo-clippy
need python3
need node
# Keep gate artifacts separate from builds made by temporary review snapshots.
export CARGO_TARGET_DIR="$PWD/target/project-gate"
run "Gate shell syntax" bash -n check.sh scripts/install-hooks.sh .githooks/pre-commit .githooks/pre-push
run "Patch whitespace" git diff --check HEAD --
run "Rust format" cargo fmt --all -- --check
run "Rust build/type check" cargo check --workspace --all-targets --locked --offline
run "Rust lint" cargo clippy --workspace --all-targets --locked --offline -- -D warnings
run "Python syntax/indentation and frontend consistency/syntax" python3 -B scripts/project_checks.py fast
if [ "$FAST" -eq 0 ]; then
    run "Rust tests (nonempty discovery)" python3 -B scripts/project_checks.py rust-tests
    run "Python tests (nonempty discovery)" python3 -B scripts/project_checks.py python-tests
fi
# No Python formatter/type checker, ES5 parser, sanitizer or audit is configured.
# Node validates JavaScript syntax; ES5/browser behavior still needs review.
# --- custom checks (preserve during refresh) ---
[ "$COUNT" -gt 0 ] || { echo "ERROR: no checks ran; log=$LOG" >&2; exit 2; }
printf 'OK: project-gate (%s, checks=%s)\n' "$MODE" "$COUNT"
rm -f -- "$LOG"
