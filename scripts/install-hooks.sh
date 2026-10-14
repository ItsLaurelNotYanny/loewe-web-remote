#!/usr/bin/env bash
# Install project-gate hooks without replacing existing hook management.
set -euo pipefail
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }
case "${1:-}" in
    --help|-h) echo "Usage: install-hooks.sh [repository-path]"; exit 0 ;;
esac
[ "$#" -le 1 ] || fail "Usage: install-hooks.sh [repository-path]"
command -v git >/dev/null 2>&1 || fail "git is required"
ROOT=$(git -C "${1:-.}" rev-parse --show-toplevel 2>/dev/null) || fail "not a Git worktree"
cd -- "$ROOT"
[ -x ./check.sh ] || fail "create an executable root check.sh before installing hooks"
[ ! -f .pre-commit-config.yaml ] && [ ! -d .husky ] || fail "existing hook manager; integrate project-gate there"
CURRENT=$(git config --get core.hooksPath || true)
case "$CURRENT" in
    ''|.githooks|"$ROOT/.githooks") ;;
    *) fail "existing core.hooksPath=$CURRENT; preserve and integrate its hooks" ;;
esac
[ ! -L .githooks ] || fail ".githooks is a symlink; preserve and integrate its hooks"
[ ! -e .githooks ] || [ -d .githooks ] || fail ".githooks is not a directory"
if [ -z "$CURRENT" ]; then
    DEFAULT_HOOKS=$(git rev-parse --git-path hooks)
    for hook in "$DEFAULT_HOOKS"/*; do
        case "$hook" in *.sample) continue ;; esac
        [ ! -f "$hook" ] || [ ! -x "$hook" ] || fail "active existing hook: $hook; preserve and integrate it"
    done
fi
# Validate both versioned hooks before changing permissions or configuration.
for name in pre-commit pre-push; do
    [ ! -L ".githooks/$name" ] || fail "destination hook is a symlink: $name"
    [ -f ".githooks/$name" ] || fail "missing versioned hook: $name"
done
chmod +x .githooks/pre-commit .githooks/pre-push
git config --local core.hooksPath .githooks
printf 'OK: project-gate hooks installed (pre-commit=fast, pre-push=full)\n'
